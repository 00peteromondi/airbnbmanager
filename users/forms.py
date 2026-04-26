from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, UserProfile
from hosts.models import Host

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'phone_number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'input-shell'

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'phone_number', 'profile_picture')

from django import forms
from .models import CustomUser

class RoleSelectionForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['role']
        widgets = {
            'role': forms.HiddenInput(),  # We'll handle this via JavaScript
        }
    
    def clean_role(self):
        role = self.cleaned_data.get('role')
        if not role:
            raise forms.ValidationError("Please select a role to continue.")
        return role


class ProfileDetailsForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'username', 'email', 'phone_number',
            'date_of_birth', 'bio', 'profile_picture', 'address_line_1',
            'address_line_2', 'city', 'state', 'country', 'zip_code',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = 'input-shell'
            if isinstance(field.widget, forms.Textarea):
                css += ' min-h-28'
            field.widget.attrs['class'] = css


class GovernmentIdForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            'government_id_type',
            'government_id_number',
            'government_id_document',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'input-shell'

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.government_id_document:
            user.government_id_status = 'pending'
        if commit:
            user.save()
        return user


class ProfilePreferencesForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'website', 'facebook', 'twitter', 'instagram', 'linkedin',
            'email_notifications', 'sms_notifications', 'promotional_emails',
            'profile_public', 'show_email', 'show_phone',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4'
            else:
                field.widget.attrs['class'] = 'input-shell'


class HostFinancialDetailsForm(forms.ModelForm):
    class Meta:
        model = Host
        fields = [
            'company_name',
            'tax_id',
            'payout_method',
            'payout_reference_name',
            'mpesa_phone_number',
            'bank_name',
            'account_number',
            'routing_number',
            'business_license',
            'same_day_bookings',
            'instant_book',
            'auto_approval',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4'
            else:
                field.widget.attrs['class'] = 'input-shell'
