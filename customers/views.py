# customers/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from decimal import Decimal
import json
from django.utils import timezone
import jdatetime
from datetime import datetime

from .models import Customer, CustomerLevel, CustomerPointHistory
from products.models import Product
from invoices.models import Invoice, InvoiceStatus, InvoiceItem
from payments.models import Payment, PaymentType, InvoicePayment, BankAccount
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from accounting.api_client import AccountingAPIClient


@login_required
def customer_panel(request):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    try:
        customer = request.user.customer_profile
    except:
        messages.error(request, 'پروفایل مشتری یافت نشد')
        return redirect('home')
    
    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())
    
    recent_invoices = customer.invoices.order_by('-date')[:5]
    recent_payments = customer.payments.order_by('-date')[:5]
    available_points = customer.available_points
    
    from invoices.models import Invoice
    from payments.models import Payment
    from django.db.models import Sum
    from decimal import Decimal
    
    total_invoices = Invoice.objects.filter(
        customer=customer,
        status__code='CONFIRMED'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    total_payments = Payment.objects.filter(
        customer=customer,
        is_confirmed=True,
        status='confirmed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # ===== بدهی =====
    total_debt = (total_invoices + customer.debt_before_1404_02) - total_payments
    debt = max(Decimal('0'), total_debt)
    
    # ===== بستانکاری =====
    total_receivable = total_payments - (total_invoices + customer.debt_before_1404_02)
    receivable = max(Decimal('0'), total_receivable)
    
    available_credit_left = max(Decimal('0'), customer.max_credit - debt)
    
    from payments.models import PaymentType
    payment_types = PaymentType.objects.all()
    
    context = {
        'customer': customer,
        'available_credit': customer.credit,
        'debt': debt,
        'receivable': receivable,
        'max_credit': customer.max_credit,
        'available_credit_left': available_credit_left,
        'total_invoices': total_invoices,
        'total_payments': total_payments,
        'cart_count': cart_count,
        'recent_invoices': recent_invoices,
        'recent_payments': recent_payments,
        'available_points': available_points,
        'payment_types': payment_types,
    }
    
    return render(request, 'customers/panel.html', context)



# customers/views.py - اصلاح customer_statement

@login_required
def customer_statement(request):
    """صورتحساب مشتری - نمایش همه تراکنش‌ها"""
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    customer = request.user.customer_profile
    
    from invoices.models import Invoice
    from payments.models import Payment
    from django.db.models import Sum
    from decimal import Decimal
    from django.core.paginator import Paginator
    from datetime import datetime
    from payments.models import PaymentType 
    
    payment_types = PaymentType.objects.all()
    
    # ===== آمار =====
    confirmed_payments_count = customer.payments.filter(is_confirmed=True, status='confirmed').exclude(payment_category='invoice').count()
    pending_payments_count = customer.payments.filter(is_confirmed=False).count()
    confirmed_invoices_count = customer.invoices.filter(status__code='CONFIRMED').count()
    pending_invoices_count = customer.invoices.filter(status__code='PENDING').count()
    
    # ===== محاسبه مالی =====
    total_invoices = Invoice.objects.filter(
        customer=customer,
        status__code='CONFIRMED'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    total_payments = Payment.objects.filter(
        customer=customer,
        is_confirmed=True,
        status='confirmed'
    ).exclude(
        payment_category='invoice'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    raw_debt = total_invoices - total_payments
    debt = max(Decimal('0'), raw_debt)
    receivable = max(Decimal('0'), -raw_debt)
    available_credit_left = max(Decimal('0'), customer.max_credit - debt)
    
    # ===== دریافت فیلترها =====
    filter_type = request.GET.get('type', '')
    search = request.GET.get('search', '')
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    
    # ===== دریافت تراکنش‌ها =====
    transactions = []
    
    # ۱. فاکتورها
    invoices = customer.invoices.all().order_by('-date')
    
    # ۲. پرداخت‌ها (بدون پرداخت فاکتور)
    payments = customer.payments.filter(
        is_confirmed=True,
        status='confirmed'
    ).exclude(
        payment_category='invoice'
    ).order_by('-date')
    
    # فیلتر بر اساس نوع
    if filter_type == 'invoice':
        payments = Payment.objects.none()
    elif filter_type == 'payment':
        invoices = Invoice.objects.none()
    
    # جستجو
    if search:
        invoices = invoices.filter(invoice_id__icontains=search)
        payments = payments.filter(payment_id__icontains=search)
    
    # فیلتر تاریخ
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            invoices = invoices.filter(date__date__gte=date_from)
            payments = payments.filter(date__date__gte=date_from)
        except:
            pass
    
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            invoices = invoices.filter(date__date__lte=date_to)
            payments = payments.filter(date__date__lte=date_to)
        except:
            pass
    
    # ترکیب تراکنش‌ها
    for invoice in invoices:
        transactions.append({
            'type': 'invoice',
            'id': invoice.invoice_id,
            'date': invoice.date,
            'amount': invoice.total,
            'status': invoice.status.code,
            'status_display': invoice.status.name,
            'object': invoice
        })
    
    for payment in payments:
        transactions.append({
            'type': 'payment',
            'id': payment.payment_id,
            'date': payment.date,
            'amount': payment.amount,
            'status': payment.status,
            'status_display': 'تایید شده' if payment.is_confirmed else 'در انتظار تایید',
            'object': payment
        })
    
    # مرتب‌سازی بر اساس تاریخ (جدیدترین اول)
    transactions.sort(key=lambda x: x['date'], reverse=True)
    
    # ===== جمع‌آوری کل مبالغ =====
    total_invoices_sum = sum(t['amount'] for t in transactions if t['type'] == 'invoice')
    total_payments_sum = sum(t['amount'] for t in transactions if t['type'] == 'payment')
    
    # ===== صفحه‌بندی =====
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customer': customer,
        'transactions': page_obj,
        'confirmed_payments_count': confirmed_payments_count,
        'pending_payments_count': pending_payments_count,
        'confirmed_invoices_count': confirmed_invoices_count,
        'pending_invoices_count': pending_invoices_count,
        'debt': debt,
        'receivable': receivable,
        'available_credit_left': available_credit_left,
        'total_invoices': total_invoices_sum,
        'total_payments': total_payments_sum,
        'filter_type': filter_type,
        'search': search,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'payment_types': payment_types,
    }
    return render(request, 'customers/statement.html', context)



@login_required
def payment_detail_api(request, payment_id):
    """دریافت جزئیات پرداخت (API)"""
    if request.user.user_type != 'customer':
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    payment = get_object_or_404(Payment, id=payment_id, customer=request.user.customer_profile)
    
    return JsonResponse({
        'success': True,
        'payment_id': payment.payment_id,
        'amount': f"{payment.amount:,.0f}",
        'date': payment.date.strftime('%Y/%m/%d'),
        'payment_type': payment.payment_type.name if payment.payment_type else '-',
        'confirmation_code': payment.confirmation_code or '-',
        'status': payment.status,
        'status_text': 'تایید شده' if payment.is_confirmed else 'در انتظار تایید',
        'notes': payment.notes or '',
        'receipt_image': payment.receipt_image.url if payment.receipt_image else None,
    })


@login_required
def cart_view(request):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    cart = request.session.get('cart', {})
    cart_items = []
    total = Decimal('0')
    total_points = 0
    
    for product_id, quantity in cart.items():
        product = Product.objects.filter(id=product_id, is_active=True).first()
        if product:
            price = product.final_price
            item_total = price * quantity
            total += item_total
            total_points += product.point_of_buy * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'total': item_total,
                'points': product.point_of_buy * quantity
            })
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'total_points': total_points,
    }
    return render(request, 'customers/cart.html', context)


@login_required
def add_to_cart(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    data = json.loads(request.body)
    product_id = str(data.get('product_id'))
    quantity = int(data.get('quantity', 1))
    
    product = Product.objects.filter(id=product_id, is_active=True).first()
    if not product:
        return JsonResponse({'success': False, 'error': 'محصول یافت نشد'})
    
    if not product.is_in_stock:
        return JsonResponse({'success': False, 'error': 'محصول ناموجود است'})
    
    cart = request.session.get('cart', {})
    current_qty = cart.get(product_id, 0)
    
    if current_qty + quantity > product.left_in_stock:
        return JsonResponse({'success': False, 'error': 'موجودی کافی نیست'})
    
    cart[product_id] = current_qty + quantity
    request.session['cart'] = cart
    request.session.modified = True
    
    cart_count = sum(cart.values())
    
    return JsonResponse({
        'success': True,
        'cart_count': cart_count,
        'message': 'محصول به سبد خرید اضافه شد'
    })


@login_required
def remove_from_cart(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    data = json.loads(request.body)
    product_id = str(data.get('product_id'))
    
    cart = request.session.get('cart', {})
    if product_id in cart:
        del cart[product_id]
        request.session['cart'] = cart
        request.session.modified = True
    
    cart_count = sum(cart.values())
    
    return JsonResponse({
        'success': True,
        'cart_count': cart_count
    })


@login_required
def cart_count_api(request):
    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())
    return JsonResponse({'count': cart_count})


@login_required
def update_cart_quantity(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    data = json.loads(request.body)
    product_id = str(data.get('product_id'))
    quantity = int(data.get('quantity', 0))
    
    product = Product.objects.filter(id=product_id).first()
    if not product:
        return JsonResponse({'success': False, 'error': 'محصول یافت نشد'})
    
    if quantity > product.left_in_stock:
        return JsonResponse({'success': False, 'error': 'موجودی کافی نیست'})
    
    cart = request.session.get('cart', {})
    if quantity <= 0:
        if product_id in cart:
            del cart[product_id]
    else:
        cart[product_id] = quantity
    
    request.session['cart'] = cart
    request.session.modified = True
    
    total = Decimal('0')
    for pid, qty in cart.items():
        p = Product.objects.filter(id=pid).first()
        if p:
            total += p.final_price * qty
    
    cart_count = sum(cart.values())
    
    return JsonResponse({
        'success': True,
        'cart_count': cart_count,
        'total': str(total)
    })


@login_required
def checkout(request):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    customer = request.user.customer_profile
    cart = request.session.get('cart', {})
    
    if not cart:
        messages.error(request, 'سبد خرید شما خالی است')
        return redirect('customers:cart')
    
    cart_items = []
    total = Decimal('0')
    total_points = 0
    
    for product_id, quantity in cart.items():
        product = Product.objects.filter(id=product_id, is_active=True).first()
        if product and product.is_in_stock:
            price = product.final_price
            item_total = price * quantity
            total += item_total
            total_points += product.point_of_buy * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'total': item_total,
                'points': product.point_of_buy * quantity
            })
    
    discount_percent = customer.customer_level.discount_percent if customer.customer_level else 0
    discount_amount = (total * discount_percent) / 100
    final_total = total - discount_amount
    
    available_points = customer.available_points
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'discount_percent': discount_percent,
        'discount_amount': discount_amount,
        'final_total': final_total,
        'total_points': total_points,
        'can_purchase': True,
        'available_points': available_points,
        'customer_credit': customer.credit,
        'max_credit': customer.max_credit,
    }
    return render(request, 'customers/checkout.html', context)



@login_required
def confirm_order(request):
    if request.method != 'POST':
        return redirect('customers:cart')
    
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    customer = request.user.customer_profile
    cart = request.session.get('cart', {})
    
    if not cart:
        messages.error(request, 'سبد خرید خالی است')
        return redirect('customers:cart')
    
    total = Decimal('0')
    items_data = []
    insufficient_stock = []
    
    for product_id, quantity in cart.items():
        product = Product.objects.filter(id=product_id, is_active=True).first()
        if not product:
            continue
            
        if not product.is_in_stock or product.left_in_stock < quantity:
            insufficient_stock.append(product.name)
            continue
            
        price = product.final_price
        item_total = price * quantity
        total += item_total
        items_data.append({
            'product_id': product.id,
            'name': product.name,
            'quantity': quantity,
            'price': str(price),
            'total': str(item_total),
            'points': product.point_of_buy * quantity
        })
    
    if insufficient_stock:
        messages.error(request, f'موجودی برخی محصولات کافی نیست: {", ".join(insufficient_stock)}')
        return redirect('customers:cart')
    
    if not items_data:
        messages.error(request, 'سبد خرید خالی است')
        return redirect('customers:cart')
    
    discount_percent = customer.customer_level.discount_percent if customer.customer_level else 0
    discount_amount = (total * discount_percent) / 100
    final_total = total - discount_amount
    
    # ===== ثبت تخفیف امتیاز (بدون کسر) =====
    points_to_use = int(request.POST.get('points_to_use', 0))
    points_discount = 0
    points_used_temp = 0
    
    if points_to_use > 0:
        max_points = min(points_to_use, customer.available_points)
        points_discount = min(max_points, int(final_total))
        points_used_temp = points_discount  # تعداد امتیازی که قراره کسر بشه
        final_total = max(0, final_total - points_discount)
    
    pending_status, _ = InvoiceStatus.objects.get_or_create(
        code='PENDING',
        defaults={'name': 'در انتظار تایید', 'is_final': False}
    )
    
    invoice = Invoice.objects.create(
        customer=customer,
        items={'products': items_data},
        subtotal=total,
        discount=discount_amount + Decimal(str(points_discount)),
        total=final_total,
        status=pending_status,
        payment_status='pending',
        notes=request.POST.get('notes', '')
    )
    
    for item in items_data:
        product = Product.objects.get(id=item['product_id'])
        InvoiceItem.objects.create(
            invoice=invoice,
            product_code=product.product_code,
            quantity=item['quantity'],
            price=item['price'],
            points_earned=0
        )
    
    # ===== ذخیره موقت امتیاز استفاده شده در session =====
    if points_used_temp > 0:
        request.session['pending_points_usage'] = {
            'invoice_id': invoice.id,
            'points_used': points_used_temp
        }
    
    request.session['cart'] = {}
    request.session.modified = True
    
    messages.success(
        request, 
        f'✅ سفارش شما با شماره {invoice.invoice_id} ثبت شد و در انتظار تایید است.'
    )
    return redirect('customers:invoice_detail', invoice_id=invoice.invoice_id)



@login_required
def invoice_history(request):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    customer = request.user.customer_profile
    invoices = customer.invoices.all().order_by('-date')
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        invoices = invoices.filter(status__code=status_filter)
    
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_purchases = customer.total_purchases
    total_points_earned = customer.total_points
    
    from payments.models import PaymentType
    payment_types = PaymentType.objects.all()
    
    context = {
        'invoices': page_obj,
        'total_purchases': total_purchases,
        'total_points_earned': total_points_earned,
        'payment_types': payment_types,
    }
    return render(request, 'customers/invoice_history.html', context)


@login_required
def invoice_detail(request, invoice_id):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    customer = request.user.customer_profile
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id, customer=customer)
    
    context = {
        'invoice': invoice,
    }
    return render(request, 'customers/invoice_detail.html', context)


@login_required
def payment_history(request):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    customer = request.user.customer_profile
    payments = customer.payments.all().order_by('-date')
    
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_payments = customer.total_payments
    
    context = {
        'payments': page_obj,
        'total_payments': total_payments,
    }
    return render(request, 'customers/payment_history.html', context)


@login_required
def add_payment(request):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    customer = request.user.customer_profile
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            payment_type_id = request.POST.get('payment_type')
            confirmation_code = request.POST.get('confirmation_code', '')
            notes = request.POST.get('notes', '')
            receipt_image = request.FILES.get('receipt_image')
            
            if amount <= 0:
                messages.error(request, 'مبلغ پرداخت باید بیشتر از صفر باشد')
                return redirect('customers:payment_history')
            
            if not payment_type_id:
                messages.error(request, 'لطفاً نوع پرداخت را انتخاب کنید')
                return redirect('customers:payment_history')
            
            payment_type = get_object_or_404(PaymentType, id=payment_type_id)
            
            payment = Payment.objects.create(
                customer=customer,
                amount=amount,
                payment_type=payment_type,
                confirmation_code=confirmation_code,
                notes=notes,
                receipt_image=receipt_image,
                is_confirmed=False,
                status='pending'
            )
            
            messages.success(request, f'پرداخت شما با شماره {payment.payment_id} ثبت شد و در انتظار تایید است.')
            return redirect('customers:payment_history')
            
        except Exception as e:
            messages.error(request, f'خطا در ثبت پرداخت: {str(e)}')
            return redirect('customers:payment_history')
    
    payment_types = PaymentType.objects.all()
    context = {
        'payment_types': payment_types,
    }
    return render(request, 'customers/add_payment.html', context)


@login_required
def pay_debt(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if request.user.user_type != 'customer':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    data = json.loads(request.body)
    amount = Decimal(data.get('amount', 0))
    
    customer = request.user.customer_profile
    
    if amount <= 0:
        return JsonResponse({'success': False, 'error': 'مبلغ باید بیشتر از صفر باشد'})
    
    if amount > customer.debt:
        return JsonResponse({'success': False, 'error': 'مبلغ بیشتر از بدهی شماست'})
    
    if amount > customer.credit:
        return JsonResponse({'success': False, 'error': 'اعتبار کافی برای پرداخت بدهی ندارید'})
    
    customer.credit -= amount
    customer.save()
    
    payment_type, _ = PaymentType.objects.get_or_create(
        code='CREDIT',
        defaults={'name': 'پرداخت از اعتبار'}
    )
    Payment.objects.create(
        customer=customer,
        amount=amount,
        payment_type=payment_type,
        is_confirmed=True,
        confirmed_by=request.user,
        confirmed_date=timezone.now(),
        notes=f'پرداخت بدهی از اعتبار - مبلغ: {amount:,.0f} ریال'
    )
    
    return JsonResponse({
        'success': True,
        'new_credit': str(customer.credit),
        'new_debt': str(customer.debt),
        'message': 'پرداخت با موفقیت انجام شد'
    })


@login_required
def redeem_points(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if request.user.user_type != 'customer':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    data = json.loads(request.body)
    points = int(data.get('points', 0))
    reward_type = data.get('reward_type')
    
    customer = request.user.customer_profile
    
    if points <= 0:
        return JsonResponse({'success': False, 'error': 'مبلغ امتیاز باید بیشتر از صفر باشد'})
    
    if points > customer.available_points:
        return JsonResponse({'success': False, 'error': 'امتیاز کافی ندارید'})
    
    rewards = {
        'discount_5': {'points': 100000, 'value': 5, 'type': 'discount'},
        'discount_10': {'points': 200000, 'value': 10, 'type': 'discount'},
        'gift_100k': {'points': 50000, 'value': 100000, 'type': 'credit'},
        'gift_500k': {'points': 200000, 'value': 500000, 'type': 'credit'},
    }
    
    if reward_type not in rewards:
        return JsonResponse({'success': False, 'error': 'جایزه نامعتبر است'})
    
    reward = rewards[reward_type]
    
    if points < reward['points']:
        return JsonResponse({'success': False, 'error': 'امتیاز کافی برای این جایزه ندارید'})
    
    if customer.use_points(points):
        CustomerPointHistory.objects.create(
            customer=customer,
            points=-points,
            reason=f'استفاده از امتیاز برای دریافت {reward_type}'
        )
        
        if reward['type'] == 'credit':
            customer.credit += reward['value']
            customer.save()
            message = f'{reward["value"]:,.0f} تومان به اعتبار شما اضافه شد'
        else:
            request.session['discount_coupon'] = {
                'percent': reward['value'],
                'points_used': points
            }
            message = f'تخفیف {reward["value"]}% برای خرید بعدی شما فعال شد'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'available_points': customer.available_points,
            'credit': str(customer.credit)
        })
    
    return JsonResponse({'success': False, 'error': 'خطا در استفاده از امتیاز'})


@login_required
def change_password(request):
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'رمز عبور شما با موفقیت تغییر کرد')
            return redirect('customers:customer_panel')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'customers/change_password.html', {'form': form})


def club(request):
    levels = CustomerLevel.objects.all().order_by('priority')
    
    level_details = []
    for level in levels:
        level_details.append({
            'name': level.name,
            'min_credit': level.min_credit,
            'discount_percent': level.discount_percent,
            'priority': level.priority,
            'benefits': get_benefits_for_level(level.name),
            'requirements': get_requirements_for_level(level.name),
        })
    
    context = {
        'levels': level_details,
    }
    return render(request, 'customers/club.html', context)


def get_benefits_for_level(level_name):
    benefits = {
        'برنزی': [
            'امتیاز مضاعف در خرید‌ها',
            'پشتیبانی تلفنی در ساعات اداری',
        ],
        'نقره‌ای': [
            '5% تخفیف روی تمام محصولات',
            '2x امتیاز مضاعف در خرید‌ها',
            'پشتیبانی ۲۴ ساعته',
            'ارسال رایگان برای خرید بالای ۵ میلیون',
        ],
        'طلایی': [
            '10% تخفیف روی تمام محصولات',
            '3x امتیاز مضاعف در خرید‌ها',
            'پشتیبانی VIP',
            'ارسال رایگان برای خرید بالای ۳ میلیون',
            'هدیه ویژه در مناسبت‌ها',
        ],
        'پلاتینیوم': [
            '15% تخفیف روی تمام محصولات',
            '5x امتیاز مضاعف در خرید‌ها',
            'پشتیبانی اختصاصی ۲۴ ساعته',
            'ارسال رایگان برای تمام خریدها',
            'هدیه تولد اختصاصی',
            'دعوت به رویدادهای ویژه',
            'مشاوره خرید رایگان',
        ],
    }
    return benefits.get(level_name, ['تخفیف پایه', 'امتیاز خرید'])


def get_requirements_for_level(level_name):
    requirements = {
        'برنزی': [
            'ثبت‌نام در سایت',
            'تکمیل اطلاعات کاربری',
        ],
        'نقره‌ای': [
            'حداقل ۱۰,۰۰۰,۰۰۰ تومان خرید',
            'حداقل ۵ فاکتور خرید',
        ],
        'طلایی': [
            'حداقل ۵۰,۰۰۰,۰۰۰ تومان خرید',
            'حداقل ۱۵ فاکتور خرید',
            'عضویت حداقل ۶ ماه',
        ],
        'پلاتینیوم': [
            'حداقل ۱۰۰,۰۰۰,۰۰۰ تومان خرید',
            'حداقل ۳۰ فاکتور خرید',
            'عضویت حداقل ۱ سال',
            'دعوت حداقل ۵ دوست به سایت',
        ],
    }
    return requirements.get(level_name, ['ثبت‌نام در سایت'])


def invoice_print(request, invoice_id):
    from invoices.models import Invoice
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id)
    
    if request.user.user_type == 'customer' and invoice.customer.user != request.user:
        return redirect('customers:invoice_history')
    
    html_string = render_to_string('customers/invoice_print.html', {'invoice': invoice})
    return HttpResponse(html_string)


@login_required
def online_payment(request):
    """ثبت درخواست پرداخت آنلاین - نیاز به تایید ادمین"""
    
    if request.user.user_type != 'customer':
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    if not settings.ZARINPAL.get('ENABLED', False):
        return JsonResponse({
            'success': False, 
            'error': 'درگاه پرداخت موقتاً غیرفعال است'
        }, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    amount = request.POST.get('amount')
    payment_type_id = request.POST.get('payment_type')
    
    if not amount or int(amount) < 1000:
        return JsonResponse({'success': False, 'error': 'مبلغ باید حداقل ۱۰۰۰ ریال باشد'})
    
    try:
        from payments.models import PaymentType
        
        payment_type = get_object_or_404(PaymentType, id=payment_type_id)
        customer = request.user.customer_profile
        
        # ===== ثبت درخواست پرداخت =====
        payment = Payment.objects.create(
            customer=customer,
            amount=int(amount),
            payment_type=payment_type,
            is_confirmed=False,
            status='pending',
            payment_category='wallet',
            method='online',
            notes=f'درخواست پرداخت آنلاین - مبلغ: {int(amount):,} ریال'
        )
        
        # ===== ذخیره در سشن برای مرحله بعد =====
        request.session['online_payment'] = {
            'payment_id': payment.id,
            'amount': int(amount),
            'payment_type_id': payment_type_id,
            'customer_id': customer.id,
        }
        
        # ===== ارسال به درگاه زرین‌پال =====
        import requests
        from django.conf import settings
        
        merchant_id = settings.ZARINPAL.get('MERCHANT_ID', '')
        callback_url = settings.ZARINPAL.get('CALLBACK_URL', 'http://127.0.0.1:8000/customers/verify-payment/')
        sandbox = settings.ZARINPAL.get('SANDBOX', True)
        
        amount_toman = int(amount) / 10
        
        data = {
            'merchant_id': merchant_id,
            'amount': int(amount_toman),
            'currency': 'IRT',
            'callback_url': callback_url,
            'description': f'شارژ کیف پول - {request.user.get_full_name()}',
            'metadata': {
                'mobile': request.user.phone,
                'email': request.user.email or ''
            }
        }
        
        if sandbox:
            url = 'https://sandbox.zarinpal.com/pg/v4/payment/request.json'
        else:
            url = 'https://api.zarinpal.com/pg/v4/payment/request.json'
        
        response = requests.post(url, json=data, timeout=30)
        result = response.json()
        
        if result.get('data', {}).get('code') == 100:
            authority = result['data']['authority']
            request.session['online_payment_authority'] = authority
            
            # ===== ذخیره authority در پرداخت =====
            payment.confirmation_code = authority
            payment.save()
            
            if sandbox:
                payment_url = f'https://sandbox.zarinpal.com/pg/StartPay/{authority}'
            else:
                payment_url = f'https://www.zarinpal.com/pg/StartPay/{authority}'
            
            return JsonResponse({
                'success': True,
                'payment_url': payment_url,
                'authority': authority
            })
        else:
            error_message = result.get('errors', {}).get('message', 'خطا در اتصال به درگاه پرداخت')
            return JsonResponse({'success': False, 'error': error_message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required
def verify_payment(request):
    """تایید پرداخت از درگاه زرین‌پال - ثبت درخواست برای تایید ادمین"""
    if not settings.ZARINPAL.get('ENABLED', False):
        messages.error(request, 'درگاه پرداخت موقتاً غیرفعال است')
        return redirect('customers:customer_panel')

    authority = request.GET.get('Authority')
    status = request.GET.get('Status')
    
    if not authority:
        messages.error(request, 'اطلاعات پرداخت یافت نشد')
        return redirect('customers:customer_panel')
    
    payment_info = request.session.get('online_payment', {})
    if not payment_info:
        messages.error(request, 'اطلاعات پرداخت یافت نشد')
        return redirect('customers:customer_panel')
    
    if status != 'OK':
        messages.error(request, 'پرداخت ناموفق بود')
        request.session.pop('online_payment', None)
        request.session.pop('online_payment_authority', None)
        return redirect('customers:customer_panel')
    
    try:
        import requests
        from django.conf import settings
        
        merchant_id = settings.ZARINPAL.get('MERCHANT_ID', '')
        sandbox = settings.ZARINPAL.get('SANDBOX', True)
        
        amount_toman = int(payment_info['amount']) / 10
        
        data = {
            'merchant_id': merchant_id,
            'authority': authority,
            'amount': int(amount_toman)
        }
        
        if sandbox:
            url = 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json'
        else:
            url = 'https://api.zarinpal.com/pg/v4/payment/verify.json'
        
        response = requests.post(url, json=data, timeout=30)
        result = response.json()
        
        if result.get('data', {}).get('code') == 100:
            # ===== پیدا کردن پرداخت =====
            payment = Payment.objects.filter(
                id=payment_info['payment_id'],
                customer_id=payment_info['customer_id'],
                status='pending'
            ).first()
            
            if payment:
                # ===== فقط تایید از درگاه (بدون افزایش اعتبار) =====
                payment.confirmation_code = authority
                payment.is_confirmed = False  # هنوز تایید نشده
                payment.status = 'pending'    # منتظر تایید ادمین
                payment.save()
                
                messages.success(
                    request, 
                    f'✅ پرداخت شما با موفقیت انجام شد و در انتظار تایید ادمین است.\n'
                    f'مبلغ: {payment_info["amount"]:,} ریال'
                )
            else:
                messages.error(request, 'پرداخت یافت نشد')
        else:
            messages.error(request, f'پرداخت ناموفق بود. کد خطا: {result.get("data", {}).get("code")}')
            
    except Exception as e:
        messages.error(request, f'خطا در تایید پرداخت: {str(e)}')
    
    request.session.pop('online_payment', None)
    request.session.pop('online_payment_authority', None)
    
    return redirect('customers:payment_history')



@login_required
def pay_invoice(request, invoice_id):
    """پرداخت فاکتور توسط مشتری"""
    if request.user.user_type != 'customer':
        return redirect('accounts:dashboard_redirect')
    
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id, customer=request.user.customer_profile)
    
    if invoice.status.code != 'CONFIRMED':
        messages.error(request, 'این فاکتور قابل پرداخت نیست')
        return redirect('customers:invoice_detail', invoice_id=invoice.invoice_id)
    
    if invoice.is_paid:
        messages.error(request, 'این فاکتور قبلاً پرداخت شده است')
        return redirect('customers:invoice_detail', invoice_id=invoice.invoice_id)
    
    customer = request.user.customer_profile
    
    from payments.models import BankAccount
    bank_accounts = BankAccount.objects.filter(is_active=True)
    
    context = {
        'invoice': invoice,
        'bank_accounts': bank_accounts,
        'customer_credit': customer.credit,
    }
    return render(request, 'customers/pay_invoice.html', context)


@login_required
def process_invoice_payment(request, invoice_id):
    """پردازش پرداخت فاکتور"""
    if request.user.user_type != 'customer':
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id, customer=request.user.customer_profile)
    customer = request.user.customer_profile
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    method = request.POST.get('method')
    amount = Decimal(request.POST.get('amount', invoice.total))
    
    if amount <= 0 or amount > invoice.total:
        return JsonResponse({'success': False, 'error': 'مبلغ نامعتبر'})
    
    # ===== پرداخت از اعتبار =====
    if method == 'credit':
        if customer.credit < amount:
            return JsonResponse({'success': False, 'error': 'اعتبار کافی نیست'})
        
        customer.credit -= amount
        customer.save()
        
        invoice.payment_status = 'paid'
        invoice.save()
        
        from payments.models import InvoicePayment
        InvoicePayment.objects.create(
            invoice=invoice,
            customer=customer,
            method='credit',
            amount=amount,
            status='paid',
            sent_to_accounting=True,
            sent_to_accounting_at=timezone.now()
        )
        
        payment_type, _ = PaymentType.objects.get_or_create(
            code='CREDIT',
            defaults={'name': 'پرداخت از اعتبار'}
        )
        Payment.objects.create(
            customer=customer,
            amount=amount,
            payment_type=payment_type,
            is_confirmed=True,
            status='confirmed',
            confirmed_by=request.user,
            confirmed_date=timezone.now(),
            notes=f'پرداخت فاکتور {invoice.invoice_id} از اعتبار',
            payment_category='invoice'
        )
        
        return JsonResponse({'success': True, 'message': 'پرداخت با موفقیت انجام شد'})
    
    # ===== پرداخت آنلاین =====
    elif method == 'online':
        request.session['online_payment'] = {
            'invoice_id': invoice.invoice_id,
            'amount': float(amount),
            'customer_id': customer.id,
            'payment_type': 'invoice',
        }
        
        import uuid
        authority = str(uuid.uuid4()).replace('-', '')[:8]
        
        callback_url = request.build_absolute_uri(
            f"/customers/verify-invoice-online-payment/?Authority={authority}&Status=OK"
        )
        
        from payments.models import InvoicePayment
        InvoicePayment.objects.create(
            invoice=invoice,
            customer=customer,
            method='online',
            amount=amount,
            status='pending',
            confirmation_code=authority
        )
        
        return JsonResponse({
            'success': True,
            'redirect_url': callback_url,
            'authority': authority
        })
    
    # ===== کارت به کارت یا حواله بانکی =====
    elif method in ['card_to_card', 'bank_transfer']:
        bank_account_id = request.POST.get('bank_account')
        confirmation_code = request.POST.get('confirmation_code')
        payment_date = request.POST.get('payment_date')
        payment_time = request.POST.get('payment_time')
        receipt_image = request.FILES.get('receipt_image')
        notes = request.POST.get('notes', '')
        
        if not bank_account_id or not confirmation_code or not payment_date or not payment_time:
            return JsonResponse({'success': False, 'error': 'لطفاً تمام اطلاعات را وارد کنید'})
        
        from payments.models import BankAccount, InvoicePayment
        bank_account = get_object_or_404(BankAccount, id=bank_account_id)
        
        payment = InvoicePayment.objects.create(
            invoice=invoice,
            customer=customer,
            method=method,
            amount=amount,
            bank_account=bank_account,
            confirmation_code=confirmation_code,
            payment_date=payment_date,
            payment_time=payment_time,
            receipt_image=receipt_image,
            notes=notes,
            status='awaiting_approval'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'پرداخت شما ثبت شد و در انتظار تایید است',
            'payment_id': payment.id
        })
    
    # ===== ثبت چک =====
    elif method == 'cheque':
        return JsonResponse({
            'success': False,
            'error': 'برای ثبت چک لطفاً با پشتیبانی تماس بگیرید',
            'show_contact': True
        })
    
    return JsonResponse({'success': False, 'error': 'روش پرداخت نامعتبر'})


@login_required
def verify_invoice_online_payment(request):
    """تایید پرداخت آنلاین فاکتور"""
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')
    
    if not authority:
        messages.error(request, 'اطلاعات پرداخت یافت نشد')
        return redirect('customers:customer_panel')
    
    from payments.models import InvoicePayment
    payment = InvoicePayment.objects.filter(confirmation_code=authority, status='pending').first()
    if not payment:
        messages.error(request, 'پرداخت یافت نشد')
        return redirect('customers:customer_panel')
    
    invoice = payment.invoice
    
    if status == 'OK':
        payment.status = 'paid'
        payment.confirmed_at = timezone.now()
        payment.confirmed_by = request.user
        payment.save()
        
        invoice.payment_status = 'paid'
        invoice.save()
        
        messages.success(request, f'✅ پرداخت فاکتور {invoice.invoice_id} با موفقیت انجام شد')
    else:
        payment.status = 'failed'
        payment.save()
        messages.error(request, 'پرداخت ناموفق بود')
    
    return redirect('customers:invoice_detail', invoice_id=invoice.invoice_id)