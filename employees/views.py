# employees/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, Count, F, Value
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_POST
from decimal import Decimal
import json
import pandas as pd
import jdatetime

from accounts.models import User, RegistrationRequest
from customers.models import Customer, CustomerLevel, CustomerPointHistory
from products.models import Product, ProductBrand, MainCategory, SubCategory, Car, CarBrand, ProductImage, ProductAlias, ProductComment
from invoices.models import Invoice, InvoiceStatus, InvoiceItem
from payments.models import Payment, PaymentType, InvoicePayment, BankAccount
from .models import Employee, EmployeePermission
from accounting.api_client import AccountingAPIClient
from accounting.models import AccountingCustomerMapping, AccountingProductMapping, AccountingNotification
from support.models import Ticket


# ============================
# دکوراتور کمکی
# ============================
import json
import os
from django.conf import settings
from django.utils import timezone

def save_invoice_request_to_file(invoice_data, result=None, error=None, invoice_id=None, headers=None):
    """ذخیره کامل درخواست ثبت فاکتور با هدر در فایل JSON"""
    try:
        log_dir = os.path.join(settings.BASE_DIR, 'logs', 'invoice_requests')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        invoice_id_str = f"_{invoice_id}" if invoice_id else ""
        filename = f"invoice_request_{timestamp}{invoice_id_str}.json"
        filepath = os.path.join(log_dir, filename)
        
        data = {
            'timestamp': timezone.now().isoformat(),
            'invoice_id': invoice_id,
            'headers': headers,
            'request_data': invoice_data,
            'result': result,
            'error': error
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    except Exception:
        return None
    


def is_admin_or_employee(user):
    return user.is_authenticated and user.user_type in ['admin', 'employee']


# ============================
# پنل‌های اصلی
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def admin_panel(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('accounts:dashboard_redirect')
    
    total_customers = Customer.objects.count()
    total_products = Product.objects.filter(is_active=True).count()
    pending_invoices = Invoice.objects.filter(status__code='PENDING').count()
    paid_not_sent_count = Invoice.objects.filter(status__code='CONFIRMED', payment_status='paid', sent_to_accounting=False).count()
    pending_payments = Payment.objects.filter(is_confirmed=False).count()
    total_employees = Employee.objects.filter(is_active=True).count()
    pending_requests_count = RegistrationRequest.objects.filter(status='pending', is_viewed=False).count()
    pending_comments_count = ProductComment.objects.filter(status='pending').count()
    
    today = timezone.now().date()
    today_sales = Invoice.objects.filter(
        date__date=today,
        status__code='CONFIRMED'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    this_month = timezone.now().replace(day=1)
    monthly_sales = Invoice.objects.filter(
        date__gte=this_month,
        status__code='CONFIRMED'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    open_tickets_count = Ticket.objects.filter(status='open').count()
    total_tickets_count = Ticket.objects.count()

    context = {
        'total_customers': total_customers,
        'total_products': total_products,
        'pending_invoices': pending_invoices,
        'pending_payments': pending_payments,
        'total_employees': total_employees,
        'today_sales': today_sales,
        'monthly_sales': monthly_sales,
        'pending_requests_count': pending_requests_count,
        'pending_comments_count': pending_comments_count,
        'paid_not_sent_count': paid_not_sent_count,
        'stats': {
            'open': open_tickets_count,
            'total': total_tickets_count,
        },
    }
    return render(request, 'employees/admin_panel.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def employee_panel(request):
    if request.user.user_type != 'employee':
        return redirect('accounts:dashboard_redirect')
    
    employee = request.user.employee_profile
    
    total_customers = None
    total_products = None
    pending_invoices = None
    pending_payments = None
    pending_comments_count = 0
    
    if employee.access_customers:
        total_customers = Customer.objects.count()
    
    if employee.access_products:
        total_products = Product.objects.filter(is_active=True).count()
    
    if employee.access_invoices:
        pending_invoices = Invoice.objects.filter(status__code='PENDING').count()
    
    if employee.access_payments:
        pending_payments = Payment.objects.filter(is_confirmed=False).count()
    
    if employee.access_comments:
        pending_comments_count = ProductComment.objects.filter(status='pending').count()
    
    pending_requests_count = RegistrationRequest.objects.filter(status='pending', is_viewed=False).count()
    pending_invoices_count = Invoice.objects.filter(status__code='PENDING').count()
    pending_payments_count = Payment.objects.filter(is_confirmed=False).count()
    
    context = {
        'employee': employee,
        'total_customers': total_customers,
        'total_products': total_products,
        'pending_invoices': pending_invoices,
        'pending_payments': pending_payments,
        'pending_requests_count': pending_requests_count,
        'pending_invoices_count': pending_invoices_count,
        'pending_payments_count': pending_payments_count,
        'pending_comments_count': pending_comments_count,
        'has_website_access': employee.access_website,
    }
    return render(request, 'employees/employee_panel.html', context)


# ============================
# مدیریت مشتریان
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def manage_customers(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_customers:
            messages.error(request, 'شما دسترسی مشاهده مشتریان را ندارید')
            return redirect('employees:employee_panel')
    
    customers = Customer.objects.select_related('user', 'customer_level').all()
    
    search = request.GET.get('search', '')
    if search:
        customers = customers.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__national_id__icontains=search) |
            Q(user__phone__icontains=search)
        )
    
    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    pending_requests_count = RegistrationRequest.objects.filter(status='pending', is_viewed=False).count()
    
    context = {
        'customers': page_obj,
        'search': search,
        'pending_requests_count': pending_requests_count,
    }
    return render(request, 'employees/manage_customers.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    invoices = customer.invoices.all().order_by('-date')[:10]
    payments = customer.payments.all().order_by('-date')[:10]
    
    context = {
        'customer': customer,
        'invoices': invoices,
        'payments': payments,
    }
    return render(request, 'employees/customer_detail.html', context)



@login_required
@user_passes_test(is_admin_or_employee)
def add_customer(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_customers:
            messages.error(request, 'شما دسترسی افزودن مشتری را ندارید')
            return redirect('employees:employee_panel')
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        address = request.POST.get('address', '')
        
        if not first_name or not last_name or not phone:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید')
            return redirect('employees:add_customer')
        
        if not settings.ACCOUNTING_API.get('ENABLED', False):
            messages.error(request, 'سیستم حسابداری غیرفعال است')
            return redirect('employees:add_customer')
        
        try:
            from accounting.api_client import AccountingAPIClient
            
            api_client = AccountingAPIClient()
            connection = api_client.check_connection()
            
            if not connection or not connection.get('connected', False):
                messages.error(request, 'سیستم حسابداری در دسترس نیست')
                return redirect('employees:add_customer')
            
            customer_data = {
                'Name': f"{first_name} {last_name}",
                'Mobile1': phone,
                'Address': address or '',
            }
            
            result = api_client.create_customer(customer_data)
            
            if result and result.get('success'):
                messages.success(
                    request, 
                    f'  مشتری {first_name} {last_name} با موفقیت در نیکان ثبت شد.'
                )
            else:
                error_msg = result.get('error', 'خطا در ثبت مشتری') if result else 'نتیجه None است'
                messages.error(request, f'  ثبت مشتری در نیکان ناموفق بود: {error_msg}')
                
        except Exception as e:
            messages.error(request, f'  خطا در ارتباط با نیکان: {str(e)}')
        
        return redirect('employees:add_customer')
    
    customer_levels = CustomerLevel.objects.all()
    context = {
        'customer_levels': customer_levels,
    }
    return render(request, 'employees/add_customer.html', context)




@login_required
@user_passes_test(is_admin_or_employee)
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_customers:
            messages.error(request, 'شما دسترسی ویرایش مشتری را ندارید')
            return redirect('employees:employee_panel')
    
    if request.method == 'POST':
        user = customer.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.phone = request.POST.get('phone')
        user.email = request.POST.get('email')
        user.city = request.POST.get('city')
        user.street = request.POST.get('street')
        user.address = request.POST.get('address')
        user.save()
        
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
            user.save()
            messages.info(request, f'رمز عبور مشتری تغییر کرد. رمز جدید: {new_password}')
        
        customer.credit = request.POST.get('credit')
        customer.customer_level_id = request.POST.get('customer_level')
        customer.save()
        
        messages.success(request, 'اطلاعات مشتری با موفقیت به‌روزرسانی شد')
        return redirect('employees:customer_detail', customer_id=customer.id)
    
    customer_levels = CustomerLevel.objects.all()
    context = {
        'customer': customer,
        'customer_levels': customer_levels,
    }
    return render(request, 'employees/edit_customer.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def search_customers(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    customers = Customer.objects.select_related('user').filter(
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query) |
        Q(user__national_id__icontains=query) |
        Q(user__phone__icontains=query)
    )[:10]
    
    results = []
    for customer in customers:
        results.append({
            'id': customer.id,
            'name': f"{customer.user.first_name} {customer.user.last_name}",
            'national_id': customer.user.national_id,
            'phone': customer.user.phone,
            'credit': str(customer.credit),
            'debt': str(customer.debt),
        })
    
    return JsonResponse({'results': results})


# ============================
# مدیریت محصولات
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def manage_products(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_products:
            messages.error(request, 'شما دسترسی مشاهده محصولات را ندارید')
            return redirect('employees:employee_panel')
    
    products = Product.objects.select_related('brand', 'main_category', 'sub_category').all()
    
    search = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    brand_id = request.GET.get('brand', '')
    status = request.GET.get('status', '')
    
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(brand__name__icontains=search) |
            Q(specialty__icontains=search)
        )
    
    if category_id:
        products = products.filter(main_category_id=category_id)
    
    if brand_id:
        products = products.filter(brand_id=brand_id)
    
    if status == 'active':
        products = products.filter(is_active=True)
    elif status == 'inactive':
        products = products.filter(is_active=False)
    elif status == 'out_of_stock':
        products = products.filter(left_in_stock=0)
    
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = MainCategory.objects.all()
    brands = ProductBrand.objects.all()
    
    context = {
        'products': page_obj,
        'categories': categories,
        'brands': brands,
        'search': search,
    }
    return render(request, 'employees/manage_products.html', context)



@login_required
@user_passes_test(is_admin_or_employee)
def add_product(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_products:
            messages.error(request, 'شما دسترسی افزودن محصول را ندارید')
            return redirect('employees:employee_panel')
    
    # ===== درخواست GET =====
    if request.method == 'GET':
        categories = MainCategory.objects.prefetch_related('subcategories').all()
        brands = ProductBrand.objects.all()
        cars = Car.objects.select_related('car_brand').all()
        
        context = {
            'categories': categories,
            'brands': brands,
            'cars': cars,
        }
        return render(request, 'employees/add_product.html', context)
    
    # ===== درخواست POST =====
    if request.method == 'POST':
        name = request.POST.get('name')
        product_code = request.POST.get('product_code')
        price = request.POST.get('price')
        left_in_stock = request.POST.get('left_in_stock', 0)
        brand_id = request.POST.get('brand')
        main_category_id = request.POST.get('main_category')
        sub_category_id = request.POST.get('sub_category')
        point_of_buy = request.POST.get('point_of_buy', 0)
        specialty = request.POST.get('specialty', '')
        short_description = request.POST.get('short_description', '')
        full_description = request.POST.get('full_description', '')
        is_active = request.POST.get('is_active') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        
        # اعتبارسنجی
        if not name or not price:
            messages.error(request, 'لطفاً نام و قیمت محصول را وارد کنید')
            return redirect('employees:add_product')
        
        # ===== ۱. ارسال به نیکان =====
        accounting_success = False
        accounting_error = None
        accounting_product_code = None
        
        if settings.ACCOUNTING_API.get('ENABLED', False):
            try:
                from accounting.api_client import AccountingAPIClient
                
                api_client = AccountingAPIClient()
                
                connection = api_client.check_connection()
                
                if connection.get('connected', False):
                    product_data = {
                        'Name': name,
                        'LCode': int(product_code) if product_code and product_code.isdigit() else 0,
                        'Class': 0,
                        'MainUnitCode': 1,
                        'GUnit': False,
                        'DefaultDepotCode': 1,
                        'Taxable': False,
                        'SalePrice1': float(price) if price else 0,
                    }
                    
                    result = api_client.create_product(product_data)
                    
                    if result.get('success'):
                        accounting_product_code = str(result.get('product_id'))
                        accounting_success = True
                    else:
                        accounting_error = result.get('error', 'خطا در ثبت محصول در حسابداری')
                else:
                    accounting_error = 'سیستم حسابداری در دسترس نیست'
                    
            except Exception as e:
                accounting_error = str(e)
        else:
            accounting_error = 'سیستم حسابداری غیرفعال است'
        
        # ===== ۲. اگر ثبت در نیکان موفق بود =====
        if accounting_success:
            # ایجاد محصول در سیستم خودمان
            product = Product.objects.create(
                name=name,
                product_code=accounting_product_code,
                price=price,
                left_in_stock=left_in_stock,
                brand_id=brand_id,
                main_category_id=main_category_id,
                sub_category_id=sub_category_id,
                point_of_buy=point_of_buy,
                specialty=specialty,
                short_description=short_description,
                full_description=full_description,
                is_active=is_active,
                is_featured=is_featured
            )
            
            # ایجاد نگاشت
            from accounting.models import AccountingProductMapping
            AccountingProductMapping.objects.create(
                product=product,
                accounting_code=accounting_product_code
            )
            
            messages.success(request, f'  محصول {name} با موفقیت اضافه شد.')
            return redirect('employees:manage_products')
        else:
            # ===== ۳. اگر ثبت در نیکان ناموفق بود =====
            messages.error(
                request, 
                f'  ثبت محصول در حسابداری ناموفق بود. لطفاً از برقراری ارتباط با سیستم حسابداری اطمینان حاصل کرده و مجددا تلاش کنید.\n'
                f'خطا: {accounting_error}'
            )
            return redirect('employees:add_product')




@login_required
@user_passes_test(is_admin_or_employee)
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_products:
            messages.error(request, 'شما دسترسی ویرایش محصول را ندارید')
            return redirect('employees:employee_panel')
    
    if request.method == 'POST':
        new_name = request.POST.get('name')
        new_slug = request.POST.get('slug')
        new_product_code = request.POST.get('product_code')
        new_alt_code = request.POST.get('alt_code')
        
        if new_slug and new_slug != product.slug:
            from django.utils.text import slugify
            new_slug = slugify(new_slug)
            if Product.objects.filter(slug=new_slug).exclude(id=product.id).exists():
                messages.error(request, 'این اسلاگ قبلاً استفاده شده است')
                return redirect('employees:edit_product', product_id=product.id)
            product.slug = new_slug
        
        if new_product_code and new_product_code != product.product_code:
            if Product.objects.filter(product_code=new_product_code).exclude(id=product.id).exists():
                messages.error(request, 'این شماره محصول قبلاً استفاده شده است')
                return redirect('employees:edit_product', product_id=product.id)
            product.product_code = new_product_code
        
        product.name = new_name
        product.alt_code = new_alt_code if new_alt_code else None
        product.main_category_id = request.POST.get('main_category')
        product.sub_category_id = request.POST.get('sub_category')
        product.brand_id = request.POST.get('brand')
        product.price = request.POST.get('price')
        product.off_price = request.POST.get('off_price') or None
        product.left_in_stock = request.POST.get('left_in_stock', 0)
        product.point_of_buy = request.POST.get('point_of_buy', 0)
        product.specialty = request.POST.get('specialty', '')
        product.short_description = request.POST.get('short_description', '')
        product.full_description = request.POST.get('full_description', '')
        product.is_active = request.POST.get('is_active') == 'on'
        product.is_featured = request.POST.get('is_featured') == 'on'
        product.save()
        
        from products.models import ProductAlias
        
        deleted_aliases_str = request.POST.get('deleted_aliases', '')
        if deleted_aliases_str:
            deleted_aliases = [int(x) for x in deleted_aliases_str.split(',') if x.strip()]
            for alias_id in deleted_aliases:
                ProductAlias.objects.filter(id=alias_id, product=product).delete()
        
        aliases = request.POST.getlist('aliases')
        alias_ids = request.POST.getlist('alias_ids')
        
        for i, alias_name in enumerate(aliases):
            if alias_name and alias_name.strip():
                alias_name = alias_name.strip()
                alias_id = None
                if i < len(alias_ids) and alias_ids[i]:
                    try:
                        alias_id = int(alias_ids[i])
                    except (ValueError, TypeError):
                        alias_id = None
                
                if alias_id:
                    alias = ProductAlias.objects.filter(id=alias_id, product=product).first()
                    if alias:
                        alias.name = alias_name
                        alias.save()
                else:
                    if not ProductAlias.objects.filter(product=product, name=alias_name).exists():
                        ProductAlias.objects.create(
                            product=product,
                            name=alias_name
                        )
        
        suitable_cars = request.POST.getlist('suitable_cars')
        product.suitable_car.set(suitable_cars)
        
        new_images = request.FILES.getlist('new_images')
        if new_images:
            from products.image_processor import process_product_images
            processed_images = process_product_images(product, new_images)
            
            current_count = product.images.count()
            for i, img_data in enumerate(processed_images):
                ProductImage.objects.create(
                    product=product,
                    image=img_data['main'],
                    thumb=img_data['thumb'],
                    order=current_count + i
                )
        
        delete_images = request.POST.getlist('delete_images')
        ProductImage.objects.filter(id__in=delete_images).delete()
        
        messages.success(request, f'محصول {product.name} با موفقیت به‌روزرسانی شد')
        return redirect('employees:manage_products')
    
    categories = MainCategory.objects.prefetch_related('subcategories').all()
    brands = ProductBrand.objects.all()
    cars = Car.objects.select_related('car_brand').all()
    
    context = {
        'product': product,
        'categories': categories,
        'brands': brands,
        'cars': cars,
    }
    return render(request, 'employees/edit_product.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def import_products(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_products:
            messages.error(request, 'شما دسترسی افزودن محصول را ندارید')
            return redirect('employees:employee_panel')
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            if excel_file.name.endswith('.csv'):
                df = pd.read_csv(excel_file, encoding='utf-8')
            else:
                df = pd.read_excel(excel_file)
            
            success_count = 0
            error_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    brand_name = row.get('brand')
                    if brand_name and pd.notna(brand_name):
                        brand, _ = ProductBrand.objects.get_or_create(
                            name=brand_name,
                            defaults={'country': 'ایران', 'city': 'تهران'}
                        )
                    else:
                        brand = ProductBrand.objects.first()
                        if not brand:
                            brand = ProductBrand.objects.create(
                                name='متفرقه',
                                country='ایران',
                                city='تهران'
                            )
                    
                    main_cat_name = row.get('main_category')
                    if main_cat_name and pd.notna(main_cat_name):
                        main_cat, _ = MainCategory.objects.get_or_create(name=main_cat_name)
                        
                        sub_cat_name = row.get('sub_category')
                        if sub_cat_name and pd.notna(sub_cat_name):
                            sub_cat, _ = SubCategory.objects.get_or_create(
                                name=sub_cat_name,
                                defaults={'main_category': main_cat}
                            )
                        else:
                            sub_cat = main_cat.subcategories.first()
                            if not sub_cat:
                                sub_cat = SubCategory.objects.create(
                                    name='متفرقه',
                                    main_category=main_cat
                                )
                    else:
                        main_cat, _ = MainCategory.objects.get_or_create(name='متفرقه')
                        sub_cat, _ = SubCategory.objects.get_or_create(
                            name='متفرقه',
                            defaults={'main_category': main_cat}
                        )
                    
                    price = row.get('price', 0)
                    if pd.notna(price):
                        price = int(price)
                    else:
                        price = 0
                    
                    off_price = row.get('off_price')
                    if off_price and pd.notna(off_price):
                        off_price = int(off_price)
                    else:
                        off_price = None
                    
                    left_in_stock = row.get('left_in_stock', 0)
                    if pd.notna(left_in_stock):
                        left_in_stock = int(left_in_stock)
                    else:
                        left_in_stock = 0
                    
                    specialty = row.get('specialty', '')
                    if pd.isna(specialty):
                        specialty = ''
                    
                    product = Product.objects.create(
                        name=row.get('name'),
                        main_category=main_cat,
                        sub_category=sub_cat,
                        brand=brand,
                        price=price,
                        off_price=off_price,
                        left_in_stock=left_in_stock,
                        point_of_buy=row.get('point_of_buy', 0) if pd.notna(row.get('point_of_buy', 0)) else 0,
                        specialty=specialty,
                        short_description=row.get('short_description', '') if pd.notna(row.get('short_description', '')) else '',
                        full_description=row.get('full_description', '') if pd.notna(row.get('full_description', '')) else '',
                        is_active=True
                    )
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"ردیف {index + 2}: {str(e)}")
            
            if success_count > 0:
                messages.success(request, f'{success_count} محصول با موفقیت وارد شدند')
            if errors:
                messages.warning(request, f'{error_count} خطا رخ داد: {" | ".join(errors[:3])}')
                
        except Exception as e:
            messages.error(request, f'خطا در خواندن فایل: {str(e)}')
        
        return redirect('employees:manage_products')
    
    return render(request, 'employees/import_products.html')


@login_required
@user_passes_test(is_admin_or_employee)
def search_products(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(brand__name__icontains=query)
    ).select_related('brand')[:10]
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'brand': product.brand.name,
            'price': str(product.price),
            'stock': product.left_in_stock,
            'image': product.images.first().image.url if product.images.exists() else None
        })
    
    return JsonResponse({'results': results})


# ============================
# مدیریت فاکتورها
# ============================

# employees/views.py
@login_required
@user_passes_test(is_admin_or_employee)
def add_manual_discount(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.status.code != 'PENDING':
        messages.error(request, 'فقط فاکتورهای در انتظار تایید قابل ویرایش هستند')
        return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)
    
    if request.method == 'POST':
        discount = request.POST.get('discount_amount')
        try:
            discount = int(discount)
            if discount < 0:
                messages.error(request, 'مبلغ تخفیف نمیتواند منفی باشد')
            elif discount > invoice.total:
                messages.error(request, 'تخفیف نمیتواند از مبلغ فاکتور بیشتر باشد')
            else:
                invoice.manual_discount = discount
                invoice.discount += discount
                invoice.total -= discount
                invoice.save()
                messages.success(request, f'  تخفیف {discount:,} ریال با موفقیت اعمال شد')
        except ValueError:
            messages.error(request, 'لطفاً مبلغ معتبر وارد کنید')
    
    return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)


@login_required
@user_passes_test(is_admin_or_employee)
def manage_invoices(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_invoices:
            messages.error(request, 'شما دسترسی مشاهده فاکتورها را ندارید')
            return redirect('employees:employee_panel')
    
    invoices = Invoice.objects.select_related('customer__user', 'status').all().order_by('-date')
    
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    
    date_from = None
    date_to = None
    
    if date_from_str:
        try:
            parts = date_from_str.split('-')
            if len(parts) == 3:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100:
                    y = y + 1300 if y > 30 else y + 1400
                g_date = jdatetime.date(y, m, d).togregorian()
                date_from = g_date
        except:
            pass
    
    if date_to_str:
        try:
            parts = date_to_str.split('-')
            if len(parts) == 3:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100:
                    y = y + 1300 if y > 30 else y + 1400
                g_date = jdatetime.date(y, m, d).togregorian()
                date_to = g_date
        except:
            pass
    
    if status_filter:
        invoices = invoices.filter(status__code=status_filter)
    
    if search:
        invoices = invoices.filter(
            Q(invoice_id__icontains=search) |
            Q(customer__user__first_name__icontains=search) |
            Q(customer__user__last_name__icontains=search) |
            Q(customer__user__national_id__icontains=search) |
            Q(customer__user__phone__icontains=search)
        )
    
    if date_from:
        invoices = invoices.filter(date__date__gte=date_from)
    
    if date_to:
        invoices = invoices.filter(date__date__lte=date_to)
    
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_amount = invoices.aggregate(total=Sum('total'))['total'] or 0
    pending_count = Invoice.objects.filter(status__code='PENDING').count()
    confirmed_count = Invoice.objects.filter(status__code='CONFIRMED').count()
    
    context = {
        'invoices': page_obj,
        'total_amount': total_amount,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
        'status_filter': status_filter,
        'search': search,
    }
    return render(request, 'employees/manage_invoices.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def pending_invoices(request):
    invoices = Invoice.objects.filter(status__code='PENDING').select_related('customer__user')
    context = {
        'invoices': invoices,
        'title': 'فاکتورهای در انتظار تایید',
    }
    return render(request, 'employees/pending_invoices.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def confirmed_invoices(request):
    invoices = Invoice.objects.filter(status__code='CONFIRMED').select_related('customer__user')
    context = {
        'invoices': invoices,
        'title': 'فاکتورهای تایید شده',
    }
    return render(request, 'employees/confirmed_invoices.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def confirm_invoice(request, invoice_id):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_invoices:
            messages.error(request, 'شما دسترسی تایید فاکتور را ندارید')
            return redirect('employees:employee_panel')
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.status.code != 'PENDING':
        messages.error(request, 'این فاکتور قبلاً تایید یا رد شده است')
        return redirect('employees:manage_invoices')
    
    customer = invoice.customer
    
    # ===== ۱. بررسی موجودی (قبل از هر کاری) =====
    for item in invoice.invoice_items.all():
        # ===== پیدا کردن محصول با product_code =====
        from accounting.models import AccountingProductMapping
        from products.models import Product
        
        product = None
        mapping = AccountingProductMapping.objects.filter(accounting_code=item.product_code).first()
        if mapping:
            product = mapping.product
        
        if not product:
            product = Product.objects.filter(product_code=item.product_code).first()
        
        if product and product.left_in_stock < item.quantity:
            messages.error(request, f'⚠️ موجودی {product.name} کافی نیست')
            return redirect('employees:manage_invoices')
    
    # ===== ۲. ارسال به حسابداری نیکان (قبل از تایید) =====
    accounting_success = False
    accounting_error = None
    
    if settings.ACCOUNTING_API.get('ENABLED', False):
        try:
            from accounting.api_client import AccountingAPIClient
            from accounting.models import AccountingCustomerMapping, AccountingProductMapping
            from products.models import Product
            
            api_client = AccountingAPIClient()
            
            connection = api_client.check_connection()
            
            if connection.get('connected', False):
                # دریافت نگاشت مشتری
                customer_mapping = AccountingCustomerMapping.objects.filter(customer=customer).first()
                
                if not customer_mapping:
                    accounting_error = 'مشتری در سیستم حسابداری ثبت نشده است. لطفاً ابتدا مشتری را همگام‌سازی کنید.'
                else:
                    # ===== آماده‌سازی آیتم‌های فاکتور =====
                    items = []
                    for item in invoice.invoice_items.all():
                        product_code = item.product_code
                        
                        # ===== پیدا کردن محصول و کد نیکان =====
                        nikan_product_code = product_code
                        
                        # ۱. جستجو در نگاشت
                        mapping = AccountingProductMapping.objects.filter(accounting_code=product_code).first()
                        if mapping:
                            nikan_product_code = mapping.accounting_code
                        
                        # ۲. اگر در نگاشت نبود، از خود product_code استفاده کن
                        items.append({
                            'ProductCode': int(nikan_product_code) if nikan_product_code and str(nikan_product_code).isdigit() else 0,
                            'DefCount': int(item.quantity),
                            'DefPrice': int(item.price),
                            'DefUnit': 1,
                        })
                    
                    # ===== ارسال فاکتور =====
                    invoice_data = {
                        'Type': 1,
                        'CustomerId': int(customer_mapping.accounting_code),
                        'PaidByCash': False,
                        'PaidByCredit': True,
                        'PaidByCheque': False,
                        'PaidByPos': False,
                        'PaidByCreditAmount': int(invoice.total),
                        'Discount': int(invoice.discount),
                        'Description': f'فاکتور وبسایت | شماره {invoice.invoice_id} - {customer.user.get_full_name()}',
                        'Items': items
                    }
                    
                    
                    result = api_client._post('create-factor', data=invoice_data, save_request=True, invoice_id=invoice.id)
                    
                    if result.get('success'):
                        invoice.sent_to_accounting = True
                        invoice.sent_to_accounting_at = timezone.now()
                        invoice.accounting_invoice_id = str(result.get('invoice_id'))
                        accounting_success = True
                    else:
                        accounting_error = result.get('error', 'خطا در ثبت فاکتور در حسابداری')
            else:
                accounting_error = 'سیستم حسابداری در دسترس نیست'
                
        except Exception as e:
            accounting_error = str(e)
    else:
        accounting_error = 'سیستم حسابداری غیرفعال است'
    
    # ===== ۳. اگر ثبت در نیکان موفق بود =====
    if accounting_success:
        # ۳.۱ کاهش موجودی
        for item in invoice.invoice_items.all():
            # ===== پیدا کردن محصول =====
            from accounting.models import AccountingProductMapping
            from products.models import Product
            
            product = None
            mapping = AccountingProductMapping.objects.filter(accounting_code=item.product_code).first()
            if mapping:
                product = mapping.product
            
            if not product:
                product = Product.objects.filter(product_code=item.product_code).first()
            
            if product:
                product.left_in_stock -= item.quantity
                product.sold_number += item.quantity
                product.save()
        
        # ۳.۲ تغییر وضعیت فاکتور
        confirmed_status, _ = InvoiceStatus.objects.get_or_create(
            code='CONFIRMED',
            defaults={'name': 'تایید شده', 'is_final': True}
        )
        invoice.status = confirmed_status
        invoice.confirmed_date = timezone.now()
        invoice.confirmed_by = request.user
        invoice.payment_status = 'pending'
        invoice.save()
        
        # ۳.۳ امتیاز

        # ===== بررسی اینکه آیا از امتیاز استفاده شده =====
        pending_points = request.session.get('pending_points_usage', {})
        if pending_points and pending_points.get('invoice_id') == invoice.id:
            points_to_deduct = pending_points.get('points_used', 0)
            if points_to_deduct > 0:
                customer.used_points += points_to_deduct
                customer.save()
                CustomerPointHistory.objects.create(
                    customer=customer,
                    points=-points_to_deduct,
                    reason=f'استفاده از امتیاز در فاکتور {invoice.invoice_id}'
                )
                # پاک کردن session
                request.session.pop('pending_points_usage', None)


        total_points = 0
        for item in invoice.invoice_items.all():
            item_points = int(((item.price * item.quantity) // 10000) * 25)
            total_points += item_points
            item.points_earned = item_points
            item.save()
        
        if total_points > 0:
            customer.add_points(total_points)
            CustomerPointHistory.objects.create(
                customer=customer,
                points=total_points,
                reason=f'امتیاز خرید از فاکتور {invoice.invoice_id}'
            )
        
        messages.success(
            request, 
            f'  فاکتور {invoice.invoice_id} تایید و به حسابداری ارسال شد.'
        )
    else:
        # ===== ۴. اگر ثبت در نیکان ناموفق بود =====
        messages.error(
            request, 
            f'  ثبت فاکتور در حسابداری ناموفق بود. لطفاً از برقراری ارتباط با سیستم حسابداری اطمینان حاصل کرده و مجددا تلاش کنید.\n'
            f'خطا: {accounting_error}'
        )
        
        from accounting.models import AccountingNotification
        AccountingNotification.objects.create(
            notification_type='invoice_failed',
            title=f'خطا در ارسال فاکتور {invoice.invoice_id} به حسابداری',
            message=f'فاکتور تایید نشد.\nمبلغ: {invoice.total:,.0f} ریال\nمشتری: {customer.user.get_full_name()}\nخطا: {accounting_error}',
            related_id=str(invoice.id),
            related_model='Invoice'
        )
    
    return redirect('employees:manage_invoices')


@login_required
@user_passes_test(is_admin_or_employee)
def reject_invoice(request, invoice_id):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_invoices:
            messages.error(request, 'شما دسترسی رد فاکتور را ندارید')
            return redirect('employees:employee_panel')
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.status.code != 'PENDING':
        messages.error(request, 'این فاکتور قبلاً تایید یا رد شده است')
        return redirect('employees:manage_invoices')
    
    reason = request.POST.get('reason', 'بدون دلیل')
    
    rejected_status, _ = InvoiceStatus.objects.get_or_create(
        code='REJECTED',
        defaults={'name': 'رد شده', 'is_final': True}
    )
    invoice.status = rejected_status
    invoice.notes = f"رد شده به دلیل: {reason}"
    invoice.save()
    
    messages.warning(request, f'  فاکتور {invoice.invoice_id} رد شد')
    return redirect('employees:manage_invoices')


@login_required
@user_passes_test(is_admin_or_employee)
def edit_invoice(request, invoice_id):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_invoices:
            messages.error(request, 'شما دسترسی ویرایش فاکتور را ندارید')
            return redirect('employees:employee_panel')
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.status.code == 'CONFIRMED':
        messages.error(request, 'فاکتور تایید شده قابل ویرایش نیست')
        return redirect('employees:manage_invoices')
    
    if request.method == 'POST':
        new_total = Decimal(request.POST.get('total', invoice.total))
        discount = Decimal(request.POST.get('discount', invoice.discount))
        
        invoice.total = new_total
        invoice.discount = discount
        invoice.notes = request.POST.get('notes', invoice.notes)
        invoice.save()
        
        messages.success(request, f'فاکتور {invoice.invoice_id} با موفقیت ویرایش شد')
        return redirect('employees:manage_invoices')
    
    context = {
        'invoice': invoice,
    }
    return render(request, 'employees/edit_invoice.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def search_invoices(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    invoices = Invoice.objects.filter(
        Q(invoice_id__icontains=query) |
        Q(customer__user__first_name__icontains=query) |
        Q(customer__user__last_name__icontains=query) |
        Q(customer__user__national_id__icontains=query)
    ).select_related('customer__user', 'status')[:20]
    
    results = []
    for invoice in invoices:
        results.append({
            'id': invoice.id,
            'invoice_id': invoice.invoice_id,
            'customer_name': f"{invoice.customer.user.first_name} {invoice.customer.user.last_name}",
            'total': str(invoice.total),
            'status': invoice.status.name,
            'date': invoice.date.strftime('%Y/%m/%d')
        })
    
    return JsonResponse({'results': results})


@login_required
@user_passes_test(is_admin_or_employee)
def invoice_detail_admin(request, invoice_id):
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id)
    context = {'invoice': invoice}
    return render(request, 'employees/invoice_detail_admin.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def send_invoice_to_accounting(request, invoice_id):
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
        invoice_data = {
            'invoice_number': invoice.invoice_id,
            'date': invoice.date.isoformat(),
            'customer': {
                'code': customer.user.national_id,
                'name': f"{customer.user.first_name} {customer.user.last_name}",
                'phone': customer.user.phone,
            },
            'items': [],
            'total_amount': float(invoice.total),
            'discount': float(invoice.discount),
            'tax': 0,
        }
        
        for item in invoice.invoice_items.all():
            invoice_data['items'].append({
                'product_code': item.product.product_code or '',
                'product_name': item.product.name,
                'quantity': item.quantity,
                'unit_price': float(item.price),
                'total_price': float(item.price * item.quantity),
            })
        
        api_client = AccountingAPIClient()
        result = api_client.create_invoice(invoice_data)
        
        if result.get('success'):
            accounting_number = result.get('invoice_id')
            invoice.accounting_invoice_number = accounting_number
            invoice.sent_to_accounting = True
            invoice.sent_to_accounting_at = timezone.now()
            invoice.save()
            
            messages.success(request, f'  فاکتور با شماره {accounting_number} به سیستم حسابداری ارسال شد')
        else:
            error_msg = result.get('error', 'خطای ناشناخته')
            messages.error(request, f'  خطا در ارسال به سیستم حسابداری: {error_msg}')
            
    except Exception as e:
        messages.error(request, f'  خطا در ارتباط با سیستم حسابداری: {str(e)}')
    
    return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)


# ============================
# مدیریت پرداخت فاکتورها (InvoicePayment)
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def manage_invoice_payments(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_payments:
            messages.error(request, 'شما دسترسی مشاهده پرداخت‌ها را ندارید')
            return redirect('employees:employee_panel')
    
    payments = InvoicePayment.objects.select_related('invoice', 'customer__user', 'bank_account').all()
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    pending_count = InvoicePayment.objects.filter(status='awaiting_approval').count()
    paid_count = InvoicePayment.objects.filter(status='paid').count()
    failed_count = InvoicePayment.objects.filter(status='failed').count()
    
    context = {
        'payments': page_obj,
        'pending_count': pending_count,
        'paid_count': paid_count,
        'failed_count': failed_count,
        'status_filter': status_filter,
    }
    return render(request, 'employees/manage_invoice_payments.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def confirm_invoice_payment(request, payment_id):
    """تایید پرداخت فاکتور توسط ادمین (کارت به کارت/حواله)"""
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_payments:
            messages.error(request, 'شما دسترسی تایید پرداخت را ندارید')
            return redirect('employees:employee_panel')
    
    payment = get_object_or_404(InvoicePayment, id=payment_id)
    
    if payment.status != 'awaiting_approval':
        messages.error(request, 'این پرداخت قابل تایید نیست')
        return redirect('employees:manage_invoice_payments')
    
    # تایید پرداخت
    payment.status = 'approved'
    payment.confirmed_at = timezone.now()
    payment.confirmed_by = request.user
    payment.save()
    
    # بروزرسانی فاکتور
    invoice = payment.invoice
    invoice.payment_status = 'paid'
    invoice.save()
    
    # ارسال به حسابداری
    accounting_success = False
    
    try:
        api_client = AccountingAPIClient()
        customer = invoice.customer
        
        customer_mapping = AccountingCustomerMapping.objects.filter(customer=customer).first()
        
        if customer_mapping:
            items = []
            for item in invoice.invoice_items.all():
                product_mapping = AccountingProductMapping.objects.filter(product=item.product).first()
                items.append({
                    'ProductCode': int(product_mapping.accounting_code) if product_mapping else 0,
                    'DefCount': float(item.quantity),
                    'DefPrice': float(item.price),
                })
            
            invoice_data = {
                'CustomerId': int(customer_mapping.accounting_code),
                'Type': 1,
                'PaidByCash': True,
                'PaidByCashAmount': float(invoice.total),
                'Discount': float(invoice.discount),
                'Description': f'فاکتور شماره {invoice.invoice_id}',
                'Items': items
            }
            
            result = api_client.create_invoice(invoice_data)
            
            if result.get('success'):
                invoice.sent_to_accounting = True
                invoice.sent_to_accounting_at = timezone.now()
                invoice.accounting_invoice_id = str(result.get('invoice_id'))
                invoice.save()
                
                payment.sent_to_accounting = True
                payment.sent_to_accounting_at = timezone.now()
                payment.save()
                
                accounting_success = True
                messages.success(request, '  پرداخت تایید و به حسابداری ارسال شد')
            else:
                messages.warning(request, f'⚠️ پرداخت تایید شد اما ارسال به حسابداری ناموفق بود: {result.get("error")}')
        else:
            messages.warning(request, '⚠️ مشتری در حسابداری ثبت نشده است')
            
    except Exception as e:
        messages.error(request, f'  خطا در ارسال به حسابداری: {str(e)}')
    
    return redirect('employees:manage_invoice_payments')


@login_required
@user_passes_test(is_admin_or_employee)
def reject_invoice_payment(request, payment_id):
    payment = get_object_or_404(InvoicePayment, id=payment_id)
    
    if payment.status != 'awaiting_approval':
        messages.error(request, 'این پرداخت قابل رد نیست')
        return redirect('employees:manage_invoice_payments')
    
    payment.status = 'rejected'
    payment.save()
    
    messages.warning(request, '  پرداخت رد شد')
    return redirect('employees:manage_invoice_payments')


@login_required
@user_passes_test(is_admin_or_employee)
def send_invoice_payment_to_accounting(request, payment_id):
    payment = get_object_or_404(InvoicePayment, id=payment_id)
    
    if payment.sent_to_accounting:
        messages.warning(request, 'این پرداخت قبلاً به حسابداری ارسال شده است')
        return redirect('employees:manage_invoice_payments')
    
    accounting_success = send_payment_to_accounting(payment.invoice, payment.amount, payment.method)
    
    if accounting_success:
        payment.sent_to_accounting = True
        payment.sent_to_accounting_at = timezone.now()
        payment.save()
        
        if payment.status == 'approved':
            payment.invoice.payment_status = 'paid'
            payment.invoice.save()
        
        messages.success(request, '  پرداخت به حسابداری ارسال شد')
    else:
        messages.error(request, '  خطا در ارسال به حسابداری')
    
    return redirect('employees:manage_invoice_payments')


def send_payment_to_accounting(invoice, amount, method):
    if not settings.ACCOUNTING_API.get('ENABLED', False):
        return True
    
    try:
        api_client = AccountingAPIClient()
        data = {
            'invoice_number': invoice.invoice_id,
            'amount': float(amount),
            'payment_method': method,
            'payment_date': timezone.now().isoformat(),
            'customer': {
                'code': invoice.customer.user.national_id,
                'name': f"{invoice.customer.user.first_name} {invoice.customer.user.last_name}"
            }
        }
        result = api_client.create_payment(data)
        return result.get('success', False)
    except:
        return False


# ============================
# مدیریت پرداخت‌ها (Payment)
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def manage_payments(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_payments:
            messages.error(request, 'شما دسترسی مشاهده پرداخت‌ها را ندارید')
            return redirect('employees:employee_panel')
    
    payments = Payment.objects.select_related('customer__user', 'payment_type').all()
    
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if status_filter == 'confirmed':
        payments = payments.filter(is_confirmed=True)
    elif status_filter == 'pending':
        payments = payments.filter(is_confirmed=False)
    
    if search:
        payments = payments.filter(
            Q(payment_id__icontains=search) |
            Q(customer__user__first_name__icontains=search) |
            Q(customer__user__last_name__icontains=search) |
            Q(customer__user__national_id__icontains=search) |
            Q(confirmation_code__icontains=search)
        )
    
    if date_from:
        payments = payments.filter(date__date__gte=date_from)
    
    if date_to:
        payments = payments.filter(date__date__lte=date_to)
    
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_pending = Payment.objects.filter(is_confirmed=False).aggregate(total=Sum('amount'))['total'] or 0
    total_confirmed = Payment.objects.filter(is_confirmed=True).aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'payments': page_obj,
        'total_pending': total_pending,
        'total_confirmed': total_confirmed,
        'status_filter': status_filter,
        'search': search,
    }
    return render(request, 'employees/manage_payments.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def pending_payments(request):
    payments = Payment.objects.filter(is_confirmed=False).select_related('customer__user', 'payment_type')
    context = {
        'payments': payments,
        'title': 'پرداخت‌های در انتظار تایید',
    }
    return render(request, 'employees/pending_payments.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def confirmed_payments(request):
    payments = Payment.objects.filter(is_confirmed=True).select_related('customer__user', 'payment_type')
    context = {
        'payments': payments,
        'title': 'پرداخت‌های تایید شده',
    }
    return render(request, 'employees/confirmed_payments.html', context)




@login_required
@user_passes_test(is_admin_or_employee)
def confirm_payment(request, payment_id):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_payments:
            messages.error(request, 'شما دسترسی تایید پرداخت را ندارید')
            return redirect('employees:employee_panel')
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.is_confirmed:
        messages.error(request, 'این پرداخت قبلاً تایید شده است')
        return redirect('employees:manage_payments')
    
    # ===== ۱. ارسال به سیستم حسابداری نیکان =====
    accounting_success = False
    accounting_error = None
    
    if settings.ACCOUNTING_API.get('ENABLED', False):
        try:
            from accounting.api_client import AccountingAPIClient
            
            api_client = AccountingAPIClient()
            connection = api_client.check_connection()
            
            if connection and connection.get('connected', False):
                customer = payment.customer
                
                if customer.nikan_customer_code:
                    try:
                        payment_data = {
                            'Amount': int(payment.amount),
                            'Note': f'پرداخت از سوی مشتری {customer.user.get_full_name()} - کد پیگیری: {payment.confirmation_code}',
                            'CustId': int(customer.nikan_customer_code)
                        }
                        
                        result = api_client.create_payment(payment_data)
                        
                        if result.get('success'):
                            payment.sent_to_accounting = True
                            payment.sent_to_accounting_at = timezone.now()
                            payment.accounting_document_no = str(result.get('document_no'))
                            accounting_success = True
                        else:
                            accounting_error = result.get('error', 'خطا در ثبت پرداخت در حسابداری')
                    except Exception as e:
                        accounting_error = str(e)
                else:
                    accounting_error = 'مشتری در سیستم حسابداری ثبت نشده است'
            else:
                accounting_error = 'سیستم حسابداری در دسترس نیست'
                
        except Exception as e:
            accounting_error = str(e)
    else:
        accounting_error = 'سیستم حسابداری غیرفعال است'
    
    # ===== ۲. اگر ارسال به حسابداری موفق بود =====
    if accounting_success:
        payment.is_confirmed = True
        payment.status = 'confirmed'
        payment.confirmed_by = request.user
        payment.confirmed_date = timezone.now()
        payment.save()
        
        customer = payment.customer
        customer.credit += payment.amount
        customer.total_payments += payment.amount
        customer.save()
        customer.update_level()
        
        messages.success(
            request, 
            f'  پرداخت {payment.payment_id} تایید شد. مبلغ {payment.amount:,.0f} ریال به حساب مشتری اضافه شد و به حسابداری ارسال شد.'
        )
    else:
        messages.error(
            request, 
            f'  ثبت در حسابداری ناموفق بود: {accounting_error}'
        )
    
    return redirect('employees:manage_payments')




@login_required
@user_passes_test(is_admin_or_employee)
def reject_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.is_confirmed:
        messages.error(request, 'این پرداخت قبلاً تایید شده است')
        return redirect('employees:manage_payments')
    
    payment.status = 'rejected'
    payment.save()
    
    messages.warning(request, f'  پرداخت {payment.payment_id} رد شد')
    return redirect('employees:manage_payments')


@login_required
@user_passes_test(is_admin_or_employee)
def search_payments(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    payments = Payment.objects.filter(
        Q(payment_id__icontains=query) |
        Q(customer__user__first_name__icontains=query) |
        Q(customer__user__last_name__icontains=query) |
        Q(customer__user__national_id__icontains=query) |
        Q(confirmation_code__icontains=query)
    ).select_related('customer__user', 'payment_type')[:20]
    
    results = []
    for payment in payments:
        results.append({
            'id': payment.id,
            'payment_id': payment.payment_id,
            'customer_name': f"{payment.customer.user.first_name} {payment.customer.user.last_name}",
            'amount': str(payment.amount),
            'status': 'تایید شده' if payment.is_confirmed else 'در انتظار تایید',
            'date': payment.date.strftime('%Y/%m/%d')
        })
    
    return JsonResponse({'results': results})


@login_required
@user_passes_test(is_admin_or_employee)
def payment_detail_api_admin(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status == 'confirmed':
        status_text = 'تایید شده'
    elif payment.status == 'rejected':
        status_text = 'رد شده'
    else:
        status_text = 'در انتظار تایید'
    
    return JsonResponse({
        'success': True,
        'payment_id': payment.payment_id,
        'customer_name': f"{payment.customer.user.first_name} {payment.customer.user.last_name}",
        'date': payment.date.strftime('%Y/%m/%d'),
        'amount': f"{payment.amount:,.0f}",
        'payment_type': payment.payment_type.name,
        'confirmation_code': payment.confirmation_code or '-',
        'status': payment.status,
        'status_text': status_text,
        'notes': payment.notes or '',
        'receipt_image': payment.receipt_image.url if payment.receipt_image else None,
    })


# ============================
# مدیریت کارمندان
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def manage_employees(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'شما دسترسی مدیریت کارمندان را ندارید')
        return redirect('employees:employee_panel')
    
    employees = Employee.objects.select_related('user').all()
    
    search = request.GET.get('search', '')
    if search:
        employees = employees.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(national_id__icontains=search) |
            Q(position__icontains=search)
        )
    
    paginator = Paginator(employees, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'employees': page_obj,
        'search': search,
    }
    return render(request, 'employees/manage_employees.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def add_employee(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'شما دسترسی افزودن کارمند را ندارید')
        return redirect('employees:employee_panel')
    
    if request.method == 'POST':
        national_id = request.POST.get('national_id')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        position = request.POST.get('position', '')
        address = request.POST.get('address', '')
        
        access_customers = request.POST.get('access_customers') == 'on'
        access_products = request.POST.get('access_products') == 'on'
        access_invoices = request.POST.get('access_invoices') == 'on'
        access_payments = request.POST.get('access_payments') == 'on'
        access_employees = request.POST.get('access_employees') == 'on'
        access_reports = request.POST.get('access_reports') == 'on'
        access_sync = request.POST.get('access_sync') == 'on'
        access_brands_categories = request.POST.get('access_brands_categories') == 'on'
        access_blog = request.POST.get('access_blog') == 'on'
        access_comments = request.POST.get('access_comments') == 'on'
        access_website = request.POST.get('access_website') == 'on'
        
        if not position:
            messages.error(request, 'لطفاً سمت کارمند را وارد کنید')
            return redirect('employees:add_employee')
        
        if User.objects.filter(national_id=national_id).exists():
            messages.error(request, 'کد ملی تکراری است')
            return redirect('employees:add_employee')
        
        if User.objects.filter(phone=phone).exists():
            messages.error(request, 'شماره تلفن تکراری است')
            return redirect('employees:add_employee')
        
        user = User.objects.create_user(
            username=phone,
            password=phone,
            national_id=national_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            address=address,
            user_type='employee',
            is_active=True
        )
        
        temp_password = phone
        user.set_password(temp_password)
        user.save()
        
        employee = Employee.objects.create(
            user=user,
            national_id=national_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            position=position,
            address=address,
            is_active=True,
            access_customers=access_customers,
            access_products=access_products,
            access_invoices=access_invoices,
            access_payments=access_payments,
            access_employees=access_employees,
            access_reports=access_reports,
            access_sync=access_sync,
            access_brands_categories=access_brands_categories,
            access_blog=access_blog,
            access_comments=access_comments,
            access_website=access_website,
        )
        
        active_access_count = sum([
            access_customers, access_products, access_invoices, 
            access_payments, access_employees, access_reports,
            access_sync, access_brands_categories, access_blog, access_comments
        ])
        
        messages.success(
            request, 
            f'کارمند {first_name} {last_name} با موفقیت اضافه شد. '
            f'نام کاربری: {phone} | رمز عبور: {phone} | تعداد دسترسی‌ها: {active_access_count}'
        )
        return redirect('employees:manage_employees')
    
    permissions = EmployeePermission.objects.all().order_by('module', 'name')
    
    grouped_permissions = {}
    for perm in permissions:
        module = perm.module or 'سایر'
        if module not in grouped_permissions:
            grouped_permissions[module] = []
        grouped_permissions[module].append(perm)
    
    context = {
        'grouped_permissions': grouped_permissions,
    }
    return render(request, 'employees/add_employee.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def edit_employee(request, employee_id):
    if request.user.user_type != 'admin':
        messages.error(request, 'شما دسترسی ویرایش کارمند را ندارید')
        return redirect('employees:employee_panel')
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        employee.first_name = request.POST.get('first_name')
        employee.last_name = request.POST.get('last_name')
        employee.phone = request.POST.get('phone')
        employee.email = request.POST.get('email')
        employee.position = request.POST.get('position')
        employee.address = request.POST.get('address', '')
        employee.is_active = request.POST.get('is_active') == 'on'
        
        employee.access_customers = request.POST.get('access_customers') == 'on'
        employee.access_products = request.POST.get('access_products') == 'on'
        employee.access_invoices = request.POST.get('access_invoices') == 'on'
        employee.access_payments = request.POST.get('access_payments') == 'on'
        employee.access_employees = request.POST.get('access_employees') == 'on'
        employee.access_reports = request.POST.get('access_reports') == 'on'
        employee.access_sync = request.POST.get('access_sync') == 'on'
        employee.access_brands_categories = request.POST.get('access_brands_categories') == 'on'
        employee.access_blog = request.POST.get('access_blog') == 'on'
        employee.access_comments = request.POST.get('access_comments') == 'on'
        employee.access_website = request.POST.get('access_website') == 'on'
        
        employee.save()
        
        user = employee.user
        user.first_name = employee.first_name
        user.last_name = employee.last_name
        user.phone = employee.phone
        user.email = employee.email
        user.address = employee.address
        user.is_active = employee.is_active
        user.save()
        
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
            user.save()
            messages.info(request, f'رمز عبور تغییر کرد. رمز جدید: {new_password}')
        
        messages.success(request, f'اطلاعات کارمند {employee.first_name} {employee.last_name} به‌روزرسانی شد')
        return redirect('employees:manage_employees')
    
    context = {
        'employee': employee,
    }
    return render(request, 'employees/edit_employee.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def edit_employee_permissions(request, employee_id):
    if request.user.user_type != 'admin':
        messages.error(request, 'شما دسترسی ویرایش دسترسی کارمند را ندارید')
        return redirect('employees:employee_panel')
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        permissions = request.POST.getlist('permissions')
        employee.permissions.set(permissions)
        employee.save()
        
        messages.success(request, f'دسترسی‌های کارمند {employee.first_name} {employee.last_name} به‌روزرسانی شد')
        return redirect('employees:manage_employees')
    
    all_permissions = EmployeePermission.objects.all()
    
    context = {
        'employee': employee,
        'all_permissions': all_permissions,
    }
    return render(request, 'employees/edit_employee_permissions.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def search_employees(request):
    if request.user.user_type != 'admin':
        return JsonResponse({'results': []})
    
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    employees = Employee.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(national_id__icontains=query) |
        Q(position__icontains=query)
    )[:10]
    
    results = []
    for emp in employees:
        results.append({
            'id': emp.id,
            'name': f"{emp.first_name} {emp.last_name}",
            'national_id': emp.national_id,
            'position': emp.position,
            'phone': emp.phone,
        })
    
    return JsonResponse({'results': results})


# ============================
# مدیریت برندها و دسته‌بندی
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def manage_brands(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_brands_categories:
            messages.error(request, 'شما دسترسی مشاهده برندها را ندارید')
            return redirect('employees:employee_panel')
    
    brands = ProductBrand.objects.all()
    
    if request.method == 'POST':
        if 'add_brand' in request.POST:
            if request.user.user_type == 'admin' or employee.access_brands_categories:
                name = request.POST.get('name')
                country = request.POST.get('country')
                city = request.POST.get('city')
                phone = request.POST.get('phone')
                description = request.POST.get('description', '')
                logo = request.FILES.get('logo')
                
                if not name or not name.strip():
                    messages.error(request, 'لطفاً نام برند را وارد کنید')
                    return redirect('employees:manage_brands')
                
                if ProductBrand.objects.filter(name=name.strip()).exists():
                    messages.error(request, f'برند "{name}" قبلاً ثبت شده است')
                else:
                    ProductBrand.objects.create(
                        name=name.strip(),
                        country=country or '',
                        city=city or '',
                        phone=phone or '',
                        description=description,
                        logo=logo
                    )
                    messages.success(request, f'برند {name} با موفقیت اضافه شد')
            else:
                messages.error(request, 'شما دسترسی افزودن برند را ندارید')
        
        elif 'edit_brand' in request.POST:
            brand_id = request.POST.get('brand_id')
            if brand_id:
                brand = get_object_or_404(ProductBrand, id=brand_id)
                new_name = request.POST.get('name')
                
                if new_name and new_name.strip() != brand.name:
                    if ProductBrand.objects.filter(name=new_name.strip()).exclude(id=brand_id).exists():
                        messages.error(request, f'برند "{new_name}" قبلاً ثبت شده است')
                        return redirect('employees:manage_brands')
                
                brand.name = new_name
                brand.country = request.POST.get('country')
                brand.city = request.POST.get('city')
                brand.phone = request.POST.get('phone')
                brand.street = request.POST.get('street')
                brand.description = request.POST.get('description')
                
                if request.FILES.get('logo'):
                    brand.logo = request.FILES.get('logo')
                
                brand.save()
                messages.success(request, f'برند {brand.name} با موفقیت ویرایش شد')
        
        return redirect('employees:manage_brands')
    
    context = {
        'brands': brands,
    }
    return render(request, 'employees/manage_brands.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def edit_brand_modal(request):
    if request.method != 'POST':
        return redirect('employees:manage_brands')
    
    brand_id = request.POST.get('brand_id')
    brand = get_object_or_404(ProductBrand, id=brand_id)
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_brands_categories:
            messages.error(request, 'شما دسترسی ویرایش برند را ندارید')
            return redirect('employees:manage_brands')
    
    brand.name = request.POST.get('name')
    brand.country = request.POST.get('country')
    brand.city = request.POST.get('city')
    brand.phone = request.POST.get('phone')
    brand.street = request.POST.get('street')
    brand.description = request.POST.get('description')
    
    if request.FILES.get('logo'):
        brand.logo = request.FILES.get('logo')
    
    brand.save()
    
    messages.success(request, f'برند {brand.name} با موفقیت ویرایش شد')
    return redirect('employees:manage_brands')


@login_required
@user_passes_test(is_admin_or_employee)
def manage_categories(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_brands_categories:
            messages.error(request, 'شما دسترسی مشاهده دسته‌بندی را ندارید')
            return redirect('employees:employee_panel')
    
    main_categories = MainCategory.objects.prefetch_related('subcategories').all()
    
    if request.method == 'POST':
        if request.user.user_type == 'admin' or employee.access_brands_categories:
            if 'add_main_category' in request.POST:
                name = request.POST.get('main_category_name')
                
                if not name or not name.strip():
                    messages.error(request, 'لطفاً نام دسته را وارد کنید')
                    return redirect('employees:manage_categories')
                
                if MainCategory.objects.filter(name=name.strip()).exists():
                    messages.error(request, f'دسته "{name}" قبلاً ثبت شده است')
                else:
                    MainCategory.objects.create(name=name.strip())
                    messages.success(request, f'دسته اصلی {name} اضافه شد')
            
            elif 'add_sub_category' in request.POST:
                name = request.POST.get('sub_category_name')
                main_cat_id = request.POST.get('main_category_id')
                
                if not name or not name.strip():
                    messages.error(request, 'لطفاً نام زیردسته را وارد کنید')
                    return redirect('employees:manage_categories')
                
                if main_cat_id:
                    main_cat = get_object_or_404(MainCategory, id=main_cat_id)
                    
                    if SubCategory.objects.filter(name=name.strip(), main_category=main_cat).exists():
                        messages.error(request, f'زیردسته "{name}" قبلاً برای دسته {main_cat.name} ثبت شده است')
                    else:
                        SubCategory.objects.create(name=name.strip(), main_category=main_cat)
                        messages.success(request, f'زیردسته {name} اضافه شد')
        else:
            messages.error(request, 'شما دسترسی ویرایش دسته‌بندی را ندارید')
        
        return redirect('employees:manage_categories')
    
    context = {
        'main_categories': main_categories,
    }
    return render(request, 'employees/manage_categories.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def manage_cars(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_brands_categories:
            messages.error(request, 'شما دسترسی مشاهده خودروها را ندارید')
            return redirect('employees:employee_panel')
    
    car_brands = CarBrand.objects.prefetch_related('cars').all()
    
    if request.method == 'POST':
        if request.user.user_type == 'admin' or employee.access_brands_categories:
            if 'add_car_brand' in request.POST:
                name = request.POST.get('car_brand_name')
                country = request.POST.get('country')
                
                if not name or not name.strip():
                    messages.error(request, 'لطفاً نام برند را وارد کنید')
                    return redirect('employees:manage_cars')
                
                if CarBrand.objects.filter(name=name.strip()).exists():
                    messages.error(request, f'برند خودرو "{name}" قبلاً ثبت شده است')
                else:
                    CarBrand.objects.create(name=name.strip(), country=country or 'ایران')
                    messages.success(request, f'برند خودرو {name} اضافه شد')
            
            elif 'add_car' in request.POST:
                name = request.POST.get('car_name')
                model = request.POST.get('model')
                brand_id = request.POST.get('car_brand_id')
                
                if not name or not name.strip():
                    messages.error(request, 'لطفاً نام خودرو را وارد کنید')
                    return redirect('employees:manage_cars')
                
                if brand_id:
                    brand = get_object_or_404(CarBrand, id=brand_id)
                    
                    if Car.objects.filter(name=name.strip(), car_brand=brand).exists():
                        messages.error(request, f'خودرو "{name}" قبلاً برای برند {brand.name} ثبت شده است')
                    else:
                        Car.objects.create(name=name.strip(), model=model or '', car_brand=brand)
                        messages.success(request, f'خودرو {name} اضافه شد')
        else:
            messages.error(request, 'شما دسترسی ویرایش خودروها را ندارید')
        
        return redirect('employees:manage_cars')
    
    context = {
        'car_brands': car_brands,
    }
    return render(request, 'employees/manage_cars.html', context)


# ============================
# مدیریت درخواست‌های ثبت‌نام
# ============================
# employees/views.py - اصلاح تابع manage_registration_requests

@login_required
@user_passes_test(is_admin_or_employee)
def manage_registration_requests(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_customers:
            messages.error(request, 'شما دسترسی مشاهده درخواست‌ها را ندارید')
            return redirect('employees:employee_panel')
    
    # دریافت همه درخواست‌ها (نه فقط مشاهده نشده)
    requests_list = RegistrationRequest.objects.all().order_by('-created_at')
    
    # فیلتر بر اساس وضعیت
    status_filter = request.GET.get('status', '')
    if status_filter:
        if status_filter == 'pending':
            requests_list = requests_list.filter(is_viewed=False)
        elif status_filter == 'viewed':
            requests_list = requests_list.filter(is_viewed=True)
    
    paginator = Paginator(requests_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # تعداد درخواست‌های جدید (مشاهده نشده)
    pending_count = RegistrationRequest.objects.filter(is_viewed=False).count()
    
    context = {
        'requests': page_obj,
        'pending_count': pending_count,
        'status_filter': status_filter,
    }
    return render(request, 'employees/manage_registration_requests.html', context)
# employees/views.py - اصلاح تابع view_registration_request

@login_required
@user_passes_test(is_admin_or_employee)
def view_registration_request(request, request_id):
    """مشاهده جزئیات درخواست ثبت‌نام"""
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_customers:
            messages.error(request, 'شما دسترسی مشاهده درخواست‌ها را ندارید')
            return redirect('employees:employee_panel')
    
    reg_request = get_object_or_404(RegistrationRequest, id=request_id)
    
    # علامت‌گذاری به عنوان مشاهده شده
    reg_request.mark_as_viewed()
    
    context = {
        'request': reg_request,
    }
    return render(request, 'employees/registration_request_detail.html', context)


# ============================
# مدیریت نظرات
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def manage_comments(request):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_comments:
            messages.error(request, 'شما دسترسی مشاهده نظرات را ندارید')
            return redirect('employees:employee_panel')
    
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    comments_list = ProductComment.objects.select_related('product', 'user').all()
    
    if status_filter:
        comments_list = comments_list.filter(status=status_filter)
    
    if search:
        comments_list = comments_list.filter(
            Q(product__name__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(comment__icontains=search)
        )
    
    paginator = Paginator(comments_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    pending_count = ProductComment.objects.filter(status='pending').count()
    approved_count = ProductComment.objects.filter(status='approved').count()
    rejected_count = ProductComment.objects.filter(status='rejected').count()
    
    context = {
        'comments': page_obj,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'status_filter': status_filter,
        'search': search,
    }
    return render(request, 'employees/manage_comments.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def approve_comment(request, comment_id):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_comments:
            messages.error(request, 'شما دسترسی تایید نظر را ندارید')
            return redirect('employees:employee_panel')
    
    comment = get_object_or_404(ProductComment, id=comment_id)
    
    if comment.status != 'pending':
        messages.error(request, 'این نظر قبلاً بررسی شده است')
        return redirect('employees:manage_comments')
    
    comment.approve(request.user)
    messages.success(request, 'نظر با موفقیت تایید شد')
    return redirect('employees:manage_comments')


@login_required
@user_passes_test(is_admin_or_employee)
def reject_comment(request, comment_id):
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_comments:
            messages.error(request, 'شما دسترسی رد نظر را ندارید')
            return redirect('employees:employee_panel')
    
    comment = get_object_or_404(ProductComment, id=comment_id)
    
    if comment.status != 'pending':
        messages.error(request, 'این نظر قبلاً بررسی شده است')
        return redirect('employees:manage_comments')
    
    comment.reject(request.user)
    messages.warning(request, 'نظر رد شد')
    return redirect('employees:manage_comments')


# ============================
# چاپ پیش فاکتور انبار
# ============================

@login_required
@user_passes_test(is_admin_or_employee)
def print_warehouse_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_invoices:
            messages.error(request, 'شما دسترسی مشاهده فاکتورها را ندارید')
            return redirect('employees:employee_panel')
    
    if invoice.status.code not in ['CONFIRMED', 'PENDING']:
        messages.error(request, 'این فاکتور قابل چاپ نیست')
        return redirect('employees:invoice_detail_admin', invoice_id=invoice.invoice_id)
    
    html_string = render_to_string('employees/warehouse_invoice_print.html', {
        'invoice': invoice,
        'company_name': 'پخش لوازم یدکی پرشین گلف',
        'company_phone': ' ۰۹۱۷۵۹۲۷۲۶۲',
        'company_address': 'بندرعباس، بلوار علی ابن ابی طالب، رو به روی خانه شیوا',
        'user': request.user,
    })
    
    return HttpResponse(html_string)


# ============================
# ویرایش فاکتور (API)
# ============================

# employees/views.py - اصلاح update_invoice_item

@login_required
@user_passes_test(is_admin_or_employee)
@require_POST
def update_invoice_item(request, invoice_id):
    """
    بروزرسانی تعداد یک آیتم در فاکتور (API)
    """
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_invoices:
            return JsonResponse({'success': False, 'error': 'شما دسترسی ویرایش فاکتور را ندارید'})
    
    if invoice.status.code != 'PENDING':
        return JsonResponse({'success': False, 'error': 'فقط فاکتورهای در انتظار تایید قابل ویرایش هستند'})
    
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = data.get('quantity')
        
        if not item_id or quantity is None:
            return JsonResponse({'success': False, 'error': 'اطلاعات کامل نیست'})
        
        item = get_object_or_404(InvoiceItem, id=item_id, invoice=invoice)
        
        if quantity <= 0:
            item.delete()
        else:
            item.quantity = quantity
            item.points_earned = int((item.price * quantity) / 1000)
            item.save()
        
        invoice.subtotal = sum(item.price * item.quantity for item in invoice.invoice_items.all())
        invoice.total = invoice.subtotal - invoice.discount
        invoice.save()
        
        return JsonResponse({
            'success': True,
            'subtotal': f"{invoice.subtotal:,.0f}",
            'total': f"{invoice.total:,.0f}",
            'item_count': invoice.invoice_items.count(),
            'message': 'آیتم با موفقیت بروزرسانی شد'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    


@login_required
@user_passes_test(is_admin_or_employee)
@require_POST
def add_invoice_item(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.user.user_type == 'employee':
        employee = request.user.employee_profile
        if not employee.access_invoices:
            return JsonResponse({'success': False, 'error': 'شما دسترسی ویرایش فاکتور را ندارید'})
    
    if invoice.status.code != 'PENDING':
        return JsonResponse({'success': False, 'error': 'فقط فاکتورهای در انتظار تایید قابل ویرایش هستند'})
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        if not product_id:
            return JsonResponse({'success': False, 'error': 'محصول انتخاب نشده است'})
        
        product = get_object_or_404(Product, id=product_id, is_active=True)

        price = product.final_price
        points_earned = product.point_of_buy * quantity
         # ===== دریافت product_code از محصول =====
        product_code = product.product_code
        
        if not product_code:
            return JsonResponse({'success': False, 'error': 'این محصول کد ندارد'})
        existing_item = invoice.invoice_items.filter(product_code=product_code).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.points_earned = product.point_of_buy * existing_item.quantity
            existing_item.save()

        else:
            InvoiceItem.objects.create(
                invoice=invoice,
                product_code=product_code,
                quantity=quantity,
                price=price,
                points_earned=points_earned
            )
        
        invoice.subtotal = sum(item.price * item.quantity for item in invoice.invoice_items.all())
        invoice.total = invoice.subtotal - invoice.discount
        invoice.save()
        
        items_data = []
        for item in invoice.invoice_items.all():
            items_data.append({
                'product_id': item.product.id,
                'name': item.product.name,
                'quantity': item.quantity,
                'price': str(item.price),
                'total': str(item.price * item.quantity),
                'points': item.points_earned
            })
        invoice.items = {'products': items_data}
        invoice.save(update_fields=['items'])
        
        items_html = render_to_string('employees/_invoice_items_table.html', {
            'invoice': invoice
        })
        
        return JsonResponse({
            'success': True,
            'subtotal': f"{invoice.subtotal:,.0f}",
            'total': f"{invoice.total:,.0f}",
            'item_count': invoice.invoice_items.count(),
            'items_html': items_html,
            'message': 'محصول با موفقیت اضافه شد'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_admin_or_employee)
def search_products_for_invoice(request):
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(brand__name__icontains=query) |
        Q(product_code__icontains=query) |
        Q(alt_code__icontains=query) |
        Q(aliases__name__icontains=query),
        is_active=True
    ).select_related('brand').distinct()[:10]
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'brand': product.brand.name,
            'product_code': product.product_code,
            'price': f"{product.final_price:,.0f}",
            'stock': product.left_in_stock,
            'image': product.images.first().image.url if product.images.exists() else None,
        })
    
    return JsonResponse({'results': results})


# employees/views.py - اضافه کردن این توابع

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from accounts.models import User


@login_required
@user_passes_test(is_admin_or_employee)
def change_username(request):
    """تغییر نام کاربری (فقط ادمین و کارمند)"""
    
    if request.method == 'POST':
        new_username = request.POST.get('username', '').strip()
        current_password = request.POST.get('current_password', '')
        
        if not new_username:
            messages.error(request, 'لطفاً نام کاربری جدید را وارد کنید')
            return redirect('employees:change_username')
        
        # بررسی وجود نام کاربری تکراری
        if User.objects.exclude(id=request.user.id).filter(username=new_username).exists():
            messages.error(request, 'این نام کاربری قبلاً ثبت شده است')
            return redirect('employees:change_username')
        
        # بررسی رمز عبور فعلی
        if not request.user.check_password(current_password):
            messages.error(request, 'رمز عبور فعلی اشتباه است')
            return redirect('employees:change_username')
        
        # تغییر نام کاربری
        request.user.username = new_username
        request.user.save()
        
        messages.success(request, f'  نام کاربری با موفقیت به "{new_username}" تغییر کرد')
        return redirect('employees:change_username')
    
    context = {
        'user': request.user,
    }
    return render(request, 'employees/change_username.html', context)


@login_required
@user_passes_test(is_admin_or_employee)
def change_password(request):
    """تغییر رمز عبور (فقط ادمین و کارمند)"""
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # جلوگیری از خروج کاربر
            update_session_auth_hash(request, user)
            messages.success(request, '  رمز عبور با موفقیت تغییر کرد')
            return redirect('employees:change_password')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'employees/change_password.html', context)