# invoices/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Invoice

@login_required
def invoice_list(request):
    """لیست فاکتورها برای کاربر معمولی"""
    if request.user.user_type == 'customer':
        invoices = request.user.customer_profile.invoices.all()
    else:
        invoices = Invoice.objects.all()
    
    return render(request, 'invoices/invoice_list.html', {'invoices': invoices})

@login_required
def invoice_detail(request, invoice_id):
    """جزئیات یک فاکتور"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # بررسی دسترسی
    if request.user.user_type == 'customer' and invoice.customer.user != request.user:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("شما دسترسی به این فاکتور ندارید")
    
    return render(request, 'invoices/invoice_detail.html', {'invoice': invoice})