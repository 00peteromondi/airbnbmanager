from django import forms
from .models import Property, PropertyImage

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
            'state', 'country', 'price_per_night', 'max_guests', 
            'bedrooms', 'bathrooms', 'amenities', 'check_in_time', 
            'check_out_time', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'check_in_time': forms.TimeInput(attrs={'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['amenities'] = self.instance.amenities
    
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

PropertyImageFormSet = forms.inlineformset_factory(
    Property,
    PropertyImage,
    form=PropertyImageForm,
    extra=5,  # Number of empty image forms
    can_delete=True,
    max_num=10  # Maximum number of images
)