from django.contrib import admin
from .models import Host, HostSubscription, HostSubscriptionCharge

admin.site.register(Host)
admin.site.register(HostSubscription)
admin.site.register(HostSubscriptionCharge)
