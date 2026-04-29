from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AssistantChat, Conversation, CustomUser, Message, Notification
from .forms import CustomUserCreationForm, CustomUserChangeForm

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ['email', 'username', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ( 'phone_number', 'profile_picture')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ( 'phone_number', 'profile_picture')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Notification)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(AssistantChat)
