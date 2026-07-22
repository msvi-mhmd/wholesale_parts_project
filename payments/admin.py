# payments/admin.py
from django.contrib import admin
from .models import PaymentType, BankAccount, InvoicePayment, Payment


@admin.register(PaymentType)
class PaymentTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'code']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['id', 'bank_name', 'account_number', 'account_holder', 'is_active']
    list_filter = ['is_active', 'bank_name']
    search_fields = ['bank_name', 'account_number', 'account_holder']


@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'invoice', 'customer', 'amount', 'method', 'status', 'created_at']
    list_filter = ['method', 'status', 'created_at']
    search_fields = ['invoice__invoice_id', 'customer__user__first_name', 'customer__user__last_name', 'confirmation_code']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('invoice', 'customer', 'method', 'amount')
        }),
        ('اطلاعات پرداخت', {
            'fields': ('bank_account', 'confirmation_code', 'payment_date', 'payment_time', 'receipt_image')
        }),
        ('وضعیت', {
            'fields': ('status', 'confirmed_at', 'confirmed_by')
        }),
        ('سیستم حسابداری', {
            'fields': ('accounting_number', 'sent_to_accounting', 'sent_to_accounting_at')
        }),
        ('سایر', {
            'fields': ('notes',)
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'customer', 'amount', 'payment_type', 'status', 'is_confirmed', 'date']
    list_filter = ['status', 'is_confirmed', 'payment_type', 'date']
    search_fields = ['payment_id', 'customer__user__first_name', 'customer__user__last_name', 'customer__user__national_id', 'confirmation_code']
    readonly_fields = ['payment_id', 'date']
    list_editable = ['is_confirmed', 'status']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('payment_id', 'customer', 'amount', 'payment_type')
        }),
        ('وضعیت', {
            'fields': ('status', 'is_confirmed', 'confirmed_by', 'confirmed_date')
        }),
        ('اطلاعات تکمیلی', {
            'fields': ('confirmation_code', 'receipt_image', 'payment_date', 'payment_time')
        }),
        ('یادداشت', {
            'fields': ('notes',)
        }),
    )