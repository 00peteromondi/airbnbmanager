from django import forms
from .models import Property, PropertyImage, Review

class PropertyForm(forms.ModelForm):
    amenities = forms.MultipleChoiceField(
        choices=Property.AMENITY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = Property
        fields = [
            'name', 'description', 'property_type', 'address', 'city', 
            'state', 'country', 'latitude', 'longitude', 'price_per_night',
            'max_guests', 'bedrooms', 'beds', 'bathrooms', 'sqft',
            'amenities', 'check_in_time', 'check_out_time', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'address': forms.TextInput(),
            'check_in_time': forms.TimeInput(attrs={'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['amenities'] = self.instance.amenities
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                continue
            css = 'input-shell'
            if isinstance(field.widget, forms.Textarea):
                css += ' min-h-32'
            field.widget.attrs['class'] = css
        self.fields['address'].widget.attrs.update({
            'class': 'input-shell pl-11',
            'data-location-input': 'true',
            'data-location-address': 'true',
            'autocomplete': 'off',
            'placeholder': 'Start typing for address suggestions',
        })
        self.fields['city'].widget.attrs['data-location-city'] = 'true'
        self.fields['state'].widget.attrs['data-location-state'] = 'true'
        self.fields['country'].widget.attrs['data-location-country'] = 'true'

    def clean(self):
        cleaned_data = super().clean()
        address = (cleaned_data.get('address') or '').strip()
        city = (cleaned_data.get('city') or '').strip()
        state = (cleaned_data.get('state') or '').strip()
        country = (cleaned_data.get('country') or '').strip()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        if address and (latitude in (None, '') or longitude in (None, '')):
            self.add_error('address', 'Choose a suggested location or click the map so this listing is pinned to a real place.')

        if latitude not in (None, ''):
            if not city:
                self.add_error('city', 'Town or city should come from the selected map location.')
            if not state:
                self.add_error('state', 'Region should come from the selected map location.')
            if not country:
                self.add_error('country', 'Country should come from the selected map location.')

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.amenities = self.cleaned_data.get('amenities', [])
        # Save price_per_night from the form into the instance (keeps price in sync in model.save)
        if 'price_per_night' in self.cleaned_data:
            instance.price_per_night = self.cleaned_data.get('price_per_night')
        if commit:
            instance.save()
        return instance

class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ['image', 'caption', 'is_primary']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].required = not bool(self.instance and self.instance.pk)
        for name, field in self.fields.items():
            if name == 'is_primary':
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' input-shell').strip()

    def clean(self):
        cleaned_data = super().clean()
        image = cleaned_data.get('image')
        caption = (cleaned_data.get('caption') or '').strip()
        is_primary = cleaned_data.get('is_primary')

        if not image and not self.instance.pk and (caption or is_primary):
            self.add_error('image', 'Choose an image file for this gallery slot or clear the extra details.')

        return cleaned_data

PropertyImageFormSet = forms.inlineformset_factory(
    Property,
    PropertyImage,
    form=PropertyImageForm,
    extra=5,  # Number of empty image forms
    can_delete=True,
    max_num=10  # Maximum number of images
)


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(),
            'comment': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].widget.attrs['class'] = 'input-shell'
        self.fields['comment'].widget.attrs['class'] = 'input-shell min-h-28'
