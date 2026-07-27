# accounting/tasks.py
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from .api_client import AccountingAPIClient
from .models import AccountingSyncLog, AccountingCustomerMapping, AccountingProductMapping
from products.models import Product, ProductBrand, MainCategory, SubCategory
from customers.models import Customer
from accounts.models import User
from invoices.models import Invoice, InvoiceStatus, InvoiceItem
from payments.models import Payment, PaymentType

logger = logging.getLogger(__name__)


@shared_task
def sync_all_with_accounting():
    """
    همگام‌سازی کامل با سیستم حسابداری
    شامل: محصولات، مشتریان، فاکتورها و پرداخت‌ها
    """
    logger.info("========== شروع همگام‌سازی کامل با حسابداری ==========")
    
    results = {
        'products': {'success': False, 'message': ''},
        'customers': {'success': False, 'message': ''},
        'invoices': {'success': False, 'message': ''},
        'payments': {'success': False, 'message': ''},
    }
    
    api_client = AccountingAPIClient()
    
    # ============================
    # ۱. همگام‌سازی محصولات
    # ============================
    try:
        logger.info("🔄 شروع همگام‌سازی محصولات...")
        product_result = sync_products_task(api_client)
        results['products'] = product_result
        logger.info(f"  محصولات: {product_result.get('message', '')}")
    except Exception as e:
        logger.error(f"  خطا در همگام‌سازی محصولات: {str(e)}")
        results['products'] = {'success': False, 'message': str(e)}
    
    # ============================
    # ۲. همگام‌سازی مشتریان
    # ============================
    try:
        logger.info("🔄 شروع همگام‌سازی مشتریان...")
        customer_result = sync_customers_task(api_client)
        results['customers'] = customer_result
        logger.info(f"  مشتریان: {customer_result.get('message', '')}")
    except Exception as e:
        logger.error(f"  خطا در همگام‌سازی مشتریان: {str(e)}")
        results['customers'] = {'success': False, 'message': str(e)}
    
    # ============================
    # ۳. همگام‌سازی فاکتورها
    # ============================
    try:
        logger.info("🔄 شروع همگام‌سازی فاکتورها...")
        invoice_result = sync_invoices_task(api_client)
        results['invoices'] = invoice_result
        logger.info(f"  فاکتورها: {invoice_result.get('message', '')}")
    except Exception as e:
        logger.error(f"  خطا در همگام‌سازی فاکتورها: {str(e)}")
        results['invoices'] = {'success': False, 'message': str(e)}
    
    # ============================
    # ۴. همگام‌سازی پرداخت‌ها
    # ============================
    try:
        logger.info("🔄 شروع همگام‌سازی پرداخت‌ها...")
        payment_result = sync_payments_task(api_client)
        results['payments'] = payment_result
        logger.info(f"  پرداخت‌ها: {payment_result.get('message', '')}")
    except Exception as e:
        logger.error(f"  خطا در همگام‌سازی پرداخت‌ها: {str(e)}")
        results['payments'] = {'success': False, 'message': str(e)}
    
    logger.info("========== همگام‌سازی کامل پایان یافت ==========")
    
    return results


@shared_task
def sync_products_task(api_client=None):
    """همگام‌سازی محصولات از حسابداری"""
    if api_client is None:
        api_client = AccountingAPIClient()
    
    # دریافت آخرین زمان همگام‌سازی
    last_sync_log = AccountingSyncLog.objects.filter(
        sync_type='products',
        status='completed'
    ).order_by('-completed_at').first()
    
    last_sync_time = last_sync_log.completed_at if last_sync_log else None
    
    try:
        # دریافت محصولات تغییر کرده
        if last_sync_time:
            result = api_client.get_updated_products(last_sync_time.isoformat())
        else:
            result = api_client.get_products(row_count=5000)
        
        if not result.get('success'):
            return {'success': False, 'message': result.get('error', 'خطا در دریافت محصولات')}
        
        products = result.get('products', [])
        new_count = 0
        updated_count = 0
        
        # ایجاد لاگ همگام‌سازی
        log = AccountingSyncLog.objects.create(
            sync_type='products',
            status='processing'
        )
        
        for product_data in products:
            try:
                product_code = product_data.get('Lots_Code') or str(product_data.get('LotsId', ''))
                if not product_code:
                    continue
                
                # بررسی وجود محصول در سیستم
                mapping = AccountingProductMapping.objects.filter(
                    accounting_code=product_code
                ).first()
                
                if mapping:
                    # بروزرسانی محصول موجود
                    product = mapping.product
                    updated = False
                    
                    # بروزرسانی قیمت
                    new_price = product_data.get('DefPrice1', 0)
                    if new_price and product.price != new_price:
                        product.price = new_price
                        updated = True
                    
                    # بروزرسانی موجودی
                    new_stock = product_data.get('Lots_Count', 0)
                    if product.left_in_stock != new_stock:
                        product.left_in_stock = new_stock
                        updated = True
                    
                    # بروزرسانی نام
                    new_name = product_data.get('LotsName', '')
                    if new_name and product.name != new_name:
                        product.name = new_name
                        updated = True
                    
                    if updated:
                        product.save()
                        updated_count += 1
                else:
                    # ایجاد محصول جدید
                    product = create_product_from_api_data(product_data)
                    if product:
                        # ایجاد نگاشت
                        AccountingProductMapping.objects.create(
                            product=product,
                            accounting_code=product_code,
                            technical_code=product_data.get('Tno', '')
                        )
                        new_count += 1
                        
            except Exception as e:
                logger.error(f"خطا در پردازش محصول: {e}")
                continue
        
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.new_items_count = new_count
        log.failed_items_count = len(products) - new_count - updated_count
        log.save()
        
        return {
            'success': True,
            'message': f'{new_count} محصول جدید، {updated_count} محصول بروزرسانی شد'
        }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


@shared_task
def sync_customers_task(api_client=None):
    """همگام‌سازی مشتریان از حسابداری"""
    if api_client is None:
        api_client = AccountingAPIClient()
    
    try:
        result = api_client.get_customers(row_count=5000)
        
        if not result.get('success'):
            return {'success': False, 'message': result.get('error', 'خطا در دریافت مشتریان')}
        
        customers = result.get('customers', [])
        new_count = 0
        updated_count = 0
        
        log = AccountingSyncLog.objects.create(
            sync_type='customers',
            status='processing'
        )
        
        for customer_data in customers:
            try:
                customer_code = str(customer_data.get('Id', ''))
                if not customer_code:
                    continue
                
                mapping = AccountingCustomerMapping.objects.filter(
                    accounting_code=customer_code
                ).first()
                
                if mapping:
                    # بروزرسانی مشتری موجود
                    customer = mapping.customer
                    user = customer.user
                    
                    new_name = customer_data.get('Name', '')
                    if new_name:
                        name_parts = new_name.split(' ', 1)
                        user.first_name = name_parts[0]
                        user.last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    new_phone = customer_data.get('Mobile1', '') or customer_data.get('Tel1', '')
                    if new_phone and user.phone != new_phone:
                        user.phone = new_phone
                    
                    user.save()
                    updated_count += 1
                else:
                    # ایجاد مشتری جدید
                    customer = create_customer_from_api_data(customer_data)
                    if customer:
                        AccountingCustomerMapping.objects.create(
                            customer=customer,
                            accounting_code=customer_code
                        )
                        new_count += 1
                        
            except Exception as e:
                logger.error(f"خطا در پردازش مشتری: {e}")
                continue
        
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.new_items_count = new_count
        log.failed_items_count = len(customers) - new_count - updated_count
        log.save()
        
        return {
            'success': True,
            'message': f'{new_count} مشتری جدید، {updated_count} مشتری بروزرسانی شد'
        }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


@shared_task
def sync_invoices_task(api_client=None):
    """همگام‌سازی فاکتورها از حسابداری"""
    if api_client is None:
        api_client = AccountingAPIClient()
    
    try:
        # دریافت فاکتورهای 7 روز اخیر
        from_date = (timezone.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
        
        result = api_client.get_factors(
            FromDate=from_date,
            ReportType=0,  # با جزئیات
            RowCount=1000
        )
        
        if not result.get('success'):
            return {'success': False, 'message': result.get('error', 'خطا در دریافت فاکتورها')}
        
        invoices = result.get('invoices', [])
        new_count = 0
        
        log = AccountingSyncLog.objects.create(
            sync_type='invoices',
            status='processing'
        )
        
        for invoice_data in invoices:
            try:
                # بررسی وجود فاکتور در سیستم
                invoice_number = str(invoice_data.get('Fac_No', ''))
                if not invoice_number:
                    continue
                
                # اگر فاکتور قبلاً ثبت شده، رد شود
                if Invoice.objects.filter(invoice_id__icontains=invoice_number).exists():
                    continue
                
                # دریافت مشتری از نگاشت
                customer_id = invoice_data.get('CustId', 0)
                customer_mapping = AccountingCustomerMapping.objects.filter(
                    accounting_code=str(customer_id)
                ).first()
                
                if not customer_mapping:
                    continue
                
                customer = customer_mapping.customer
                
                # ایجاد فاکتور
                invoice = create_invoice_from_api_data(invoice_data, customer)
                if invoice:
                    new_count += 1
                    
            except Exception as e:
                logger.error(f"خطا در پردازش فاکتور: {e}")
                continue
        
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.new_items_count = new_count
        log.save()
        
        return {
            'success': True,
            'message': f'{new_count} فاکتور جدید ثبت شد'
        }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


@shared_task
def sync_payments_task(api_client=None):
    """همگام‌سازی پرداخت‌ها از حسابداری"""
    if api_client is None:
        api_client = AccountingAPIClient()
    
    try:
        # دریافت دفتر حساب مشتریان برای شناسایی پرداخت‌ها
        result = api_client.get_customer_ledger(row_count=1000)
        
        if not result.get('success'):
            return {'success': False, 'message': result.get('error', 'خطا در دریافت پرداخت‌ها')}
        
        ledger = result.get('ledger', [])
        new_count = 0
        
        log = AccountingSyncLog.objects.create(
            sync_type='payments',
            status='processing'
        )
        
        # ایجاد یا بروزرسانی پرداخت‌ها
        for entry in ledger:
            try:
                # شناسایی تراکنش‌های بستانکار (پرداخت مشتری)
                if entry.get('Flag') == 'بستانکار' and entry.get('Docd_Bes', 0) > 0:
                    # بررسی وجود پرداخت
                    doc_no = str(entry.get('DocH_DocNo', ''))
                    if not doc_no:
                        continue
                    
                    # اگر پرداخت قبلاً ثبت شده، رد شود
                    if Payment.objects.filter(confirmation_code=doc_no).exists():
                        continue
                    
                    # یافتن مشتری
                    customer_id = entry.get('CustId', 0)
                    customer_mapping = AccountingCustomerMapping.objects.filter(
                        accounting_code=str(customer_id)
                    ).first()
                    
                    if not customer_mapping:
                        continue
                    
                    customer = customer_mapping.customer
                    
                    # ایجاد پرداخت
                    payment_type, _ = PaymentType.objects.get_or_create(
                        code='ACCOUNTING_SYNC',
                        defaults={'name': 'همگام‌سازی از حسابداری'}
                    )
                    
                    Payment.objects.create(
                        customer=customer,
                        amount=entry.get('Docd_Bes', 0),
                        payment_type=payment_type,
                        confirmation_code=doc_no,
                        is_confirmed=True,
                        status='confirmed',
                        notes=f'همگام‌سازی خودکار از حسابداری - سند: {doc_no}'
                    )
                    
                    new_count += 1
                    
            except Exception as e:
                logger.error(f"خطا در پردازش پرداخت: {e}")
                continue
        
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.new_items_count = new_count
        log.save()
        
        return {
            'success': True,
            'message': f'{new_count} پرداخت جدید ثبت شد'
        }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


# ============================
# توابع کمکی
# ============================

def create_product_from_api_data(data):
    """ایجاد محصول از داده‌های API"""
    try:
        # دریافت یا ایجاد برند
        brand_name = data.get('Level1_Name', 'متفرقه')
        brand, _ = ProductBrand.objects.get_or_create(
            name=brand_name[:100],
            defaults={'country': 'ایران', 'city': 'تهران'}
        )
        
        # دریافت یا ایجاد دسته‌بندی اصلی
        main_cat_name = data.get('Level2_Name', 'متفرقه')
        main_cat, _ = MainCategory.objects.get_or_create(name=main_cat_name[:100])
        
        # دریافت یا ایجاد زیردسته
        sub_cat_name = data.get('Level3_Name', 'متفرقه')
        sub_cat, _ = SubCategory.objects.get_or_create(
            name=sub_cat_name[:100],
            defaults={'main_category': main_cat}
        )
        
        # ایجاد محصول
        product = Product.objects.create(
            name=data.get('LotsName', 'بدون نام')[:200],
            product_code=data.get('Lots_Code', ''),
            main_category=main_cat,
            sub_category=sub_cat,
            brand=brand,
            price=data.get('DefPrice1', 0),
            left_in_stock=data.get('Lots_Count', 0),
            point_of_buy=0,
            is_active=True
        )
        
        return product
    except Exception as e:
        logger.error(f"خطا در ایجاد محصول: {e}")
        return None


def create_customer_from_api_data(data):
    """ایجاد مشتری از داده‌های API"""
    try:
        name = data.get('Name', '')
        name_parts = name.split(' ', 1)
        
        phone = data.get('Mobile1', '') or data.get('Tel1', '')
        if not phone:
            phone = f"09{data.get('Id', '')[:9]}"
        
        # ایجاد کاربر
        user = User.objects.create_user(
            username=phone,
            password=User.objects.make_random_password(),
            first_name=name_parts[0] if name_parts else '',
            last_name=name_parts[1] if len(name_parts) > 1 else '',
            phone=phone,
            user_type='customer',
            is_active=True
        )
        
        # ایجاد پروفایل مشتری
        customer = Customer.objects.create(
            user=user,
            credit=0,
            max_credit=0,
            wallet=0
        )
        
        return customer
    except Exception as e:
        logger.error(f"خطا در ایجاد مشتری: {e}")
        return None


def create_invoice_from_api_data(data, customer):
    """ایجاد فاکتور از داده‌های API"""
    try:
        # دریافت وضعیت
        status, _ = InvoiceStatus.objects.get_or_create(
            code='CONFIRMED',
            defaults={'name': 'تایید شده', 'is_final': True}
        )
        
        # جمع‌آوری آیتم‌ها
        details = data.get('Details', [])
        total = data.get('HFac_Payable', 0)
        subtotal = data.get('HFac_TotalAmount', 0)
        discount = data.get('HFac_Discount', 0)
        
        # ایجاد فاکتور
        invoice = Invoice.objects.create(
            customer=customer,
            items={'products': details},
            subtotal=subtotal,
            discount=discount,
            total=total,
            status=status,
            payment_status='paid' if total <= 0 else 'pending',
            notes=data.get('Hfac_Note', 'همگام‌سازی از حسابداری')
        )
        
        # ایجاد آیتم‌های فاکتور
        for item in details:
            try:
                product_code = str(item.get('Lots_LCode', ''))
                mapping = AccountingProductMapping.objects.filter(
                    accounting_code=product_code
                ).first()
                
                if mapping:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=mapping.product,
                        quantity=item.get('DFac_Count', 0),
                        price=item.get('DFac_Phi', 0),
                        points_earned=0
                    )
            except Exception as e:
                logger.error(f"خطا در ایجاد آیتم فاکتور: {e}")
                continue
        
        return invoice
    except Exception as e:
        logger.error(f"خطا در ایجاد فاکتور: {e}")
        return None
    

# accounting/tasks.py - اضافه کردن تسک

from celery import shared_task
from .api_client import AccountingAPIClient

@shared_task
def process_sync_queue():
    """پردازش صف همگام‌سازی با نیکان"""
    api_client = AccountingAPIClient()
    results = api_client.process_sync_queue(limit=20)
    return results