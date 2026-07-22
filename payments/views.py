# payments/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Payment

@login_required
def payment_list(request):
    """لیست پرداخت‌ها برای کاربر معمولی"""
    if request.user.user_type == 'customer':
        payments = request.user.customer_profile.payments.all()
    else:
        payments = Payment.objects.all()
    
    return render(request, 'payments/payment_list.html', {'payments': payments})

@login_required
def payment_detail(request, payment_id):
    """جزئیات یک پرداخت"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # بررسی دسترسی
    if request.user.user_type == 'customer' and payment.customer.user != request.user:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("شما دسترسی به این پرداخت ندارید")
    
    return render(request, 'payments/payment_detail.html', {'payment': payment})