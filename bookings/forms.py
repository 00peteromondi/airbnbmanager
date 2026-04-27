from django import forms
from .models import Booking, HostWithdrawal

class BookingForm(forms.ModelForm):
    mpesa_phone_number = forms.CharField(max_length=20, required=False)
    charge_now = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = Booking
        fields = ['check_in_date', 'check_out_date', 'num_guests', 'special_requests']
        widgets = {
            'check_in_date': forms.DateInput(attrs={'type': 'date'}),
            'check_out_date': forms.DateInput(attrs={'type': 'date'}),
            'special_requests': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4'
            else:
                css = 'input-shell'
                if isinstance(field.widget, forms.Textarea):
                    css += ' min-h-28'
                field.widget.attrs['class'] = css
            if name == 'mpesa_phone_number':
                field.widget.attrs.update({
                    'placeholder': '719463611',
                    'autocomplete': 'tel-national',
                    'data-phone-input': 'true',
                })


class WithdrawalRequestForm(forms.ModelForm):
    class Meta:
        model = HostWithdrawal
        fields = ['amount', 'mpesa_phone_number', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = 'input-shell'
            if isinstance(field.widget, forms.Textarea):
                css += ' min-h-24'
            field.widget.attrs['class'] = css
            if name == 'mpesa_phone_number':
                field.widget.attrs.update({
                    'placeholder': '719463611',
                    'autocomplete': 'tel-national',
                    'data-phone-input': 'true',
                })
