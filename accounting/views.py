# accounting/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required , user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.conf import settings
import json

from .api_client import AccountingAPIClient
from .models import AccountingSyncLog, AccountingCustomerMapping, AccountingProductMapping
from invoices.models import Invoice
from customers.models import Customer
from payments.models import Payment
from employees.views import is_admin_or_employee


# ============================
# ویوهای داشبورد و همگام‌سازی
# ============================

def check_sync_access(user):
    """بررسی دسترسی کارمند به همگام‌سازی"""
    if user.user_type == 'admin':
        return True
    elif user.user_type == 'employee':
        try:
            employee = user.employee_profile
            return employee.access_sync
        except:
            return False
    return False

@login_required
@user_passes_test(is_admin_or_employee)
def sync_dashboard(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    customers_count = AccountingCustomerMapping.objects.count()
    products_count = AccountingProductMapping.objects.count()
    
    # ===== تعداد فاکتورهای همگام‌سازی شده =====
    invoices_count = Invoice.objects.filter(
        sent_to_accounting=True
    ).count()
    
    # ===== تعداد پرداخت‌های همگام‌سازی شده =====
    payments_count = Payment.objects.filter(
        confirmation_code__isnull=False
    ).exclude(
        confirmation_code=''
    ).exclude(
        payment_category='debt'  # بدهی‌ها رو حذف کن
    ).count()
    
    last_customer_sync = AccountingSyncLog.objects.filter(
        sync_type='customers', 
        status='completed'
    ).order_by('-completed_at').first()
    
    last_product_sync = AccountingSyncLog.objects.filter(
        sync_type='products', 
        status='completed'
    ).order_by('-completed_at').first()
    
    last_invoice_sync = AccountingSyncLog.objects.filter(
        sync_type='invoices', 
        status='completed'
    ).order_by('-completed_at').first()
    
    last_payment_sync = AccountingSyncLog.objects.filter(
        sync_type='payments', 
        status='completed'
    ).order_by('-completed_at').first()
    
    logs = AccountingSyncLog.objects.all().order_by('-started_at')[:10]
    
    context = {
        'customers_count': customers_count,
        'products_count': products_count,
        'invoices_count': invoices_count,
        'payments_count': payments_count,
        'last_customer_sync': last_customer_sync,
        'last_product_sync': last_product_sync,
        'last_invoice_sync': last_invoice_sync,
        'last_payment_sync': last_payment_sync,
        'logs': logs,
    }
    return render(request, 'accounting/sync_dashboard.html', context)

@login_required
@user_passes_test(is_admin_or_employee)
def sync_customers(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """همگام‌سازی مشتریان از سیستم حسابداری"""
    if request.method == 'POST':
        api_client = AccountingAPIClient()
        result = api_client.sync_customers()
        
        if result.get('success'):
            messages.success(
                request, 
                f"✅ همگام‌سازی مشتریان با موفقیت انجام شد. "
                f"{result.get('new_count', 0)} مشتری جدید اضافه شدند."
            )
        else:
            messages.error(request, f"❌ خطا در همگام‌سازی مشتریان: {result.get('error')}")
        
        return redirect('accounting:sync_dashboard')
    
    logs = AccountingSyncLog.objects.filter(sync_type='customers').order_by('-started_at')[:10]
    context = {
        'logs': logs,
    }
    return render(request, 'accounting/sync_customers.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def sync_products(request):

    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """همگام‌سازی محصولات از سیستم حسابداری"""
    if request.method == 'POST':
        api_client = AccountingAPIClient()
        result = api_client.sync_products()
        
        if result.get('success'):
            messages.success(
                request, 
                f"✅ همگام‌سازی محصولات با موفقیت انجام شد. "
                f"{result.get('new_count', 0)} محصول جدید اضافه شدند."
            )
        else:
            messages.error(request, f"❌ خطا در همگام‌سازی محصولات: {result.get('error')}")
        
        return redirect('accounting:sync_dashboard')
    
    logs = AccountingSyncLog.objects.filter(sync_type='products').order_by('-started_at')[:10]
    context = {
        'logs': logs,
    }
    return render(request, 'accounting/sync_products.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def sync_logs(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """مشاهده لاگ‌های همگام‌سازی"""
    logs = AccountingSyncLog.objects.all().order_by('-started_at')
    
    sync_type = request.GET.get('type', '')
    if sync_type:
        logs = logs.filter(sync_type=sync_type)
    
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'logs': page_obj,
        'sync_type': sync_type,
    }
    return render(request, 'accounting/sync_logs.html', context)


# ============================
# ویوهای ارسال فاکتور
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def send_invoice_to_accounting(request, invoice_id):

    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """ارسال فاکتور به سیستم حسابداری"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.status.code != 'CONFIRMED':
        messages.error(request, 'فقط فاکتورهای تایید شده قابل ارسال هستند')
        return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)
    
    if invoice.sent_to_accounting:
        messages.warning(request, 'این فاکتور قبلاً به سیستم حسابداری ارسال شده است')
        return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)
    
    if not settings.ACCOUNTING_API.get('ENABLED', False):
        messages.error(request, 'سیستم حسابداری غیرفعال است')
        return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)
    
    customer = invoice.customer
    
    try:
        # بررسی وجود نگاشت مشتری
        customer_mapping = AccountingCustomerMapping.objects.filter(customer=customer).first()
        if not customer_mapping:
            messages.error(request, 'این مشتری در سیستم حسابداری ثبت نشده است. لطفاً ابتدا مشتری را همگام‌سازی کنید.')
            return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)
        
        # آماده‌سازی داده برای ارسال
        invoice_data = {
            'CustomerId': int(customer_mapping.accounting_code),
            'Type': 1,  # فاکتور فروش
            'PaidByCash': True,
            'PaidByCashAmount': float(invoice.total),
            'Discount': float(invoice.discount),
            'Description': f'فاکتور شماره {invoice.invoice_id}',
            'Items': []
        }
        
        # اضافه کردن آیتم‌های فاکتور
        for item in invoice.invoice_items.all():
            # بررسی وجود نگاشت محصول
            product_mapping = AccountingProductMapping.objects.filter(product=item.product).first()
            product_code = int(product_mapping.accounting_code) if product_mapping else 0
            
            invoice_data['Items'].append({
                'ProductCode': product_code,
                'DefCount': float(item.quantity),
                'DefPrice': float(item.price),
                'DiscountAmount': 0,
                'DiscountPercent': 0
            })
        
        # ارسال به API
        api_client = AccountingAPIClient()
        result = api_client.create_invoice(invoice_data)
        
        if result.get('success'):
            accounting_number = result.get('invoice_id')
            invoice.accounting_invoice_number = accounting_number
            invoice.sent_to_accounting = True
            invoice.sent_to_accounting_at = timezone.now()
            invoice.save()
            
            messages.success(request, f'✅ فاکتور با شماره {accounting_number} به سیستم حسابداری ارسال شد')
        else:
            error_msg = result.get('error', 'خطای ناشناخته')
            messages.error(request, f'❌ خطا در ارسال به سیستم حسابداری: {error_msg}')
            
    except Exception as e:
        messages.error(request, f'❌ خطا در ارتباط با سیستم حسابداری: {str(e)}')
    
    return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)


# ============================
# APIهای جدید
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def check_connection_api(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """بررسی اتصال به سیستم حسابداری"""
    api_client = AccountingAPIClient()
    result = api_client.check_connection()
    return JsonResponse(result)


@login_required
@user_passes_test(is_admin_or_employee)
def get_products_api(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """دریافت لیست محصولات از حسابداری"""
    name = request.GET.get('name', '')
    level_id = request.GET.get('level_id', '')
    barcode = request.GET.get('barcode', '')
    row_count = int(request.GET.get('row_count', 100))
    timestamp = request.GET.get('timestamp', '')
    
    api_client = AccountingAPIClient()
    
    if timestamp:
        result = api_client.get_updated_products(timestamp)
    else:
        result = api_client.get_products(
            name=name,
            level_id=level_id,
            barcode=barcode,
            row_count=row_count
        )
    
    return JsonResponse(result)


@login_required
@user_passes_test(is_admin_or_employee)
def get_customers_api(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """دریافت لیست مشتریان از حسابداری"""
    name = request.GET.get('name', '')
    customer_type = request.GET.get('customer_type')
    row_count = int(request.GET.get('row_count', 100))
    
    api_client = AccountingAPIClient()
    result = api_client.get_customers(
        customer_name=name,
        customer_type=customer_type,
        row_count=row_count
    )
    
    return JsonResponse(result)


@login_required
@user_passes_test(is_admin_or_employee)
def create_customer_api(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """ایجاد مشتری در حسابداری (API)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    api_client = AccountingAPIClient()
    result = api_client.create_customer(data)
    
    return JsonResponse(result)


@login_required
@user_passes_test(is_admin_or_employee)
def create_invoice_api(request):

    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """ثبت فاکتور نهایی در حسابداری (API)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    api_client = AccountingAPIClient()
    result = api_client.create_invoice(data)
    
    return JsonResponse(result)


@login_required
@user_passes_test(is_admin_or_employee)
def create_payment_api(request):

    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """ثبت پرداخت در حسابداری (API)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    api_client = AccountingAPIClient()
    result = api_client.create_payment(data)
    
    return JsonResponse(result)


@login_required
@user_passes_test(is_admin_or_employee)
def test_connection(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """تست اتصال به سیستم حسابداری (صفحه HTML)"""
    api_client = AccountingAPIClient()
    result = api_client.check_connection()
    
    output = []
    output.append("=== تست اتصال به دراک ===")
    output.append(f"Base URL: {api_client.base_url}")
    output.append(f"API Key: {api_client.api_key[:20]}..." if api_client.api_key else "API Key: Not set")
    output.append(f"Username: {api_client.username}")
    
    output.append("\n--- نتیجه ---")
    output.append(f"Success: {result.get('success')}")
    output.append(f"Connected: {result.get('connected')}")
    output.append(f"Message: {result.get('message')}")
    if result.get('error'):
        output.append(f"Error: {result.get('error')}")
    
    return HttpResponse("<br>".join(output))


# accounting/views.py - اضافه کردن این تابع

@login_required
@user_passes_test(is_admin_or_employee)
def sync_invoices(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """همگام‌سازی فاکتورها از نیکان"""
    
    if request.method == 'POST':
        try:
            from .sync_invoices import sync_invoices_from_nikan
            result = sync_invoices_from_nikan()
            
            if result.get('success'):
                messages.success(
                    request, 
                    f"✅ همگام‌سازی فاکتورها با موفقیت انجام شد. "
                    f"{result.get('saved_count', 0)} فاکتور جدید اضافه شدند."
                )
            else:
                messages.error(request, f"❌ خطا در همگام‌سازی فاکتورها: {result.get('error')}")
                
        except Exception as e:
            messages.error(request, f"❌ خطا در همگام‌سازی فاکتورها: {str(e)}")
        
        return redirect('accounting:sync_dashboard')
    
    # نمایش لاگ‌های همگام‌سازی فاکتورها
    logs = AccountingSyncLog.objects.filter(sync_type='invoices').order_by('-started_at')[:10]
    
    context = {
        'logs': logs,
    }
    return render(request, 'accounting/sync_invoices.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def sync_payments(request):
    if not check_sync_access(request.user):
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('employees:employee_panel')
    
    """همگام‌سازی پرداخت‌ها از نیکان"""
    
    if request.method == 'POST':
        from .sync_payments import sync_payments_from_nikan
        result = sync_payments_from_nikan()
        
        if result.get('success'):
            messages.success(
                request, 
                f"✅ همگام‌سازی پرداخت‌ها با موفقیت انجام شد. "
                f"{result.get('saved_count', 0)} پرداخت جدید اضافه شدند."
            )
        else:
            messages.error(request, f"❌ خطا در همگام‌سازی پرداخت‌ها: {result.get('error')}")
        
        return redirect('accounting:sync_dashboard')
    
    logs = AccountingSyncLog.objects.filter(sync_type='payments').order_by('-started_at')[:10]
    
    context = {
        'logs': logs,
    }
    return render(request, 'accounting/sync_payments.html', context)