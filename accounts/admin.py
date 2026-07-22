# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, RegistrationRequest

class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'phone', 'national_id', 'user_type', 'is_active']
    list_filter = ['user_type', 'is_active', 'is_staff']
    search_fields = ['username', 'first_name', 'last_name', 'phone', 'national_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('اطلاعات ورود', {
            'fields': ('username', 'password')
        }),
        ('اطلاعات شخصی', {
            'fields': ('first_name', 'last_name', 'phone', 'national_id', 'email', 'city', 'street', 'address')
        }),
        ('نوع کاربر', {
            'fields': ('user_type', 'invitation_code', 'invited_by')
        }),
        ('دسترسی‌ها', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('تاریخ', {
            'fields': ('created_at', 'updated_at', 'last_login', 'date_joined')
        }),
    )
    add_fieldsets = (
        ('اطلاعات ورود', {
            'fields': ('username', 'password1', 'password2')
        }),
        ('اطلاعات شخصی', {
            'fields': ('first_name', 'last_name', 'phone', 'national_id', 'email')
        }),
        ('نوع کاربر', {
            'fields': ('user_type',)
        }),
    )

@admin.register(RegistrationRequest)
class RegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'phone', 'national_id', 'status', 'is_viewed', 'created_at']
    list_filter = ['status', 'is_viewed', 'created_at']
    search_fields = ['first_name', 'last_name', 'phone', 'national_id']
    readonly_fields = ['created_at']  # فقط created_at رو به عنوان خواندنی قرار بده
    
    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('first_name', 'last_name', 'national_id', 'phone', 'email', 'city', 'street', 'address')
        }),
        ('اطلاعات ثبت‌نام', {
            'fields': ('invitation_code',)
        }),
        ('وضعیت', {
            'fields': ('status', 'is_viewed', 'notes')
        }),
        ('تاریخ', {
            'fields': ('created_at',)
        }),
    )

# ثبت مدل User با تنظیمات سفارشی
admin.site.register(User, CustomUserAdmin)