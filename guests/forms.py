from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

# Get the custom user model defined in settings.py
CustomUser = get_user_model()

class GuestSignUpForm(UserCreationForm):
    class Meta:
        model = CustomUser
        # You can specify which fields to include in the form
        fields = ('username', 'email')

    # A custom save method can be used to add logic after user creation,
    # like creating a related Guest profile.
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # This is where you can create a related Guest model instance
            from .models import Guest
            Guest.objects.create(user=user, full_name=user.username)
        return user
