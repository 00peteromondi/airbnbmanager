from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from users.models import CustomUser
from .models import Host, Listing

class HostRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email',)

    @transaction.atomic
    def save(self, commit=True):
        # Save the CustomUser first
        user = super().save(commit=False)
        user.is_host = True
        user.save()
        
        # Then create the associated Host profile
        host = Host.objects.create(user=user)
        return user
# A form for creating a new listing
from django import forms
from .models import Listing

class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        # We specify the fields to be included in the form
        fields = [
            'name',
            'city',
            'price',
            'description',
            'property_type',
            'beds',
            'baths',
            'sqft',
            'status',
        ]
        # We can add custom CSS classes for Tailwind styling
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'city': forms.TextInput(attrs={'class': 'form-input'}),
            'price': forms.NumberInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea'}),
            'property_type': forms.Select(attrs={'class': 'form-select'}),
            'beds': forms.NumberInput(attrs={'class': 'form-input'}),
            'baths': forms.NumberInput(attrs={'class': 'form-input'}),
            'sqft': forms.NumberInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
