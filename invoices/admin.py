# invoices/admin.py
from django.contrib import admin
from .models import Invoice, InvoiceItem, InvoiceStatus


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    max_num = 20
    fields = ['product_code', 'quantity', 'price', 'points_earned']
    readonly_fields = ['product_code', 'quantity', 'price', 'points_earned']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_id',
        'accounting_invoice_id',
        'customer',
        'total',
        'status',
        'payment_status',
        'date'
    ]
    list_filter = ['status', 'payment_status']
    search_fields = [
        'invoice_id',
        'accounting_invoice_id',
        'customer__user__first_name',
        'customer__user__last_name'
    ]
    readonly_fields = [
        'invoice_id',
        'accounting_invoice_id',
        'sent_to_accounting_at'
    ]
    
    fields = [
        'invoice_id',
        'accounting_invoice_id',
        'customer',
        'status',
        'payment_status',
        'subtotal',
        'discount',
        'total',
        'sent_to_accounting',
        'sent_to_accounting_at',
        'notes',
        'date',
        'confirmed_date',
        'confirmed_by'
    ]
    
    inlines = [InvoiceItemInline]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = [
        'invoice',
        'product_code',        # جایگزین product
        'quantity',
        'price',
        'points_earned'
    ]
    list_filter = ['invoice__status']
    search_fields = [
        'product_code',
        'invoice__invoice_id',
        'invoice__customer__user__first_name',
        'invoice__customer__user__last_name'
    ]
    readonly_fields = ['product_code', 'quantity', 'price', 'points_earned']


@admin.register(InvoiceStatus)
class InvoiceStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_final']
    search_fields = ['name', 'code']