from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from users.models import CustomUser
from .models import Host
from properties.models import Property, PropertyImage

class HostRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True, max_length=30)
    last_name = forms.CharField(required=True, max_length=30)
    phone_number = forms.CharField(max_length=20, required=True)
    company_name = forms.CharField(max_length=200, required=False)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.role = 'host'  # Set role to host
        
        if commit:
            user.save()
        return user
# A form for creating a new Property
from django import forms
from properties.models import Property

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
            'state', 'country', 'price', 'max_guests', 
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
        # Set initial amenities if editing
        if self.instance and self.instance.pk:
            self.initial['amenities'] = self.instance.amenities
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.amenities = self.cleaned_data['amenities']
        if commit:
            instance.save()
        return instance
    
class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ['image', 'caption', 'is_primary']