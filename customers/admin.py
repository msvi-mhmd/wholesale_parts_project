# customers/admin.py
from django.contrib import admin
from .models import Customer, CustomerLevel, CustomerPointHistory


@admin.register(CustomerLevel)
class CustomerLevelAdmin(admin.ModelAdmin):
    list_display = ['name', 'min_credit', 'discount_percent', 'priority']
    list_filter = ['priority']
    search_fields = ['name']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'customer_code', 'credit', 'max_credit', 'created_at','nikan_customer_code']
    search_fields = ['user__first_name', 'user__last_name', 'user__phone', 'customer_code']
    list_filter = ['customer_level', 'created_at']


@admin.register(CustomerPointHistory)
class CustomerPointHistoryAdmin(admin.ModelAdmin):
    list_display = ['customer', 'points', 'reason', 'created_at']
    search_fields = ['customer__user__first_name', 'customer__user__last_name']
    list_filter = ['created_at']