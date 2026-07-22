from django.contrib import admin
from .models import SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'setting_type', 'is_active', 'created_at']
    list_filter = ['setting_type', 'is_active']
    search_fields = ['key', 'value']
    readonly_fields = ['created_at', 'updated_at']