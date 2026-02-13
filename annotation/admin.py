from django.contrib import admin
from django.apps import apps

# Register all models automatically, avoiding AlreadyRegistered error
for model in apps.get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
