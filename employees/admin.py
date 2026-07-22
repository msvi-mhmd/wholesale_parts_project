# employees/admin.py
from django.contrib import admin
from .models import Employee, EmployeePermission

@admin.register(EmployeePermission)
class EmployeePermissionAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'module']
    list_filter = ['module']
    search_fields = ['code', 'name']
    ordering = ['module', 'name']

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'position', 'phone', 'is_active']
    list_filter = ['is_active', 'position']
    search_fields = ['first_name', 'last_name', 'national_id', 'phone', 'position']
    readonly_fields = ['hired_date']
    
    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('first_name', 'last_name', 'national_id', 'phone', 'email', 'address')
        }),
        ('اطلاعات شغلی', {
            'fields': ('position', 'is_active')
        }),
        ('دسترسی‌ها', {
            'fields': (
                'access_customers', 'access_products', 'access_invoices', 
                'access_payments', 'access_employees', 'access_reports',
                'access_sync', 'access_brands_categories', 'access_blog', 'access_comments'
            )
        }),
        ('تاریخ', {
            'fields': ('hired_date',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')