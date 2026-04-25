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
        })
        self.fields['city'].widget.attrs['data-location-city'] = 'true'
        self.fields['state'].widget.attrs['data-location-state'] = 'true'
        self.fields['country'].widget.attrs['data-location-country'] = 'true'
    
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = 'input-shell'

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
