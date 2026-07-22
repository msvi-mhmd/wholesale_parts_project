import jdatetime
from datetime import datetime, timedelta, time
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
import time as system_time
import logging

from .api_client import AccountingAPIClient
from .models import AccountingCustomerMapping, AccountingSyncLog
from invoices.models import Invoice, InvoiceStatus, InvoiceItem

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY = 5


def get_last_sync_date():
    last_log = AccountingSyncLog.objects.filter(
        sync_type='invoices',
        status='completed'
    ).order_by('-completed_at').first()
    
    if last_log and last_log.last_synced_code:
        return last_log.last_synced_code
    return None


def save_last_sync_date(sync_date_jalali):
    last_log = AccountingSyncLog.objects.filter(
        sync_type='invoices',
        status='completed'
    ).order_by('-completed_at').first()
    
    if last_log:
        last_log.last_synced_code = sync_date_jalali
        last_log.save()
    else:
        AccountingSyncLog.objects.create(
            sync_type='invoices',
            status='completed',
            last_synced_code=sync_date_jalali,
            new_items_count=0,
            completed_at=timezone.now()
        )


def jalali_to_gregorian(jalali_date_str):
    try:
        parts = jalali_date_str.split('/')
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return jdatetime.date(y, m, d).togregorian()
    except:
        pass
    return None

from django.utils import timezone

def convert_jalali_to_gregorian(jalali_date_str):
    """
    تبدیل تاریخ شمسی به میلادی با منطقه زمانی
    مثال: 1404/04/12 -> 2025-07-03 00:00:00+03:30
    """
    if not jalali_date_str:
        return None
    
    try:
        jalali_date_str = jalali_date_str.strip()
        parts = jalali_date_str.split('/')
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y = y + 1300 if y > 30 else y + 1400
            jalali_date = jdatetime.date(y, m, d)
            gregorian_date = jalali_date.togregorian()
            
            dt = datetime.combine(gregorian_date, datetime.min.time())
            return timezone.make_aware(dt)
    except Exception as e:
        print(f"⚠️ Error converting date: {jalali_date_str} - {str(e)}")
    return None


def gregorian_to_jalali(date_obj):
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    jalali = jdatetime.date.fromgregorian(date=date_obj)
    return jalali.strftime('%Y/%m/%d')


def generate_invoice_id(accounting_invoice_id=None):
    if accounting_invoice_id:
        return f"INV-{str(accounting_invoice_id).zfill(8)}"
    else:
        timestamp = str(int(system_time.time() * 1000))[-8:]
        return f"INV-{timestamp}"


def fetch_invoices_with_retry(api, request_data):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = api._post('get-factors', data=request_data)
            
            if not result.get('success'):
                if attempt < MAX_RETRIES:
                    system_time.sleep(RETRY_DELAY)
                    continue
                else:
                    return [], False
            
            data = result.get('data')
            
            if isinstance(data, list):
                invoices = data
            elif isinstance(data, dict):
                invoices = data.get('Data', []) or data.get('data', [])
            else:
                invoices = []
            
            return invoices, True
            
        except Exception:
            if attempt < MAX_RETRIES:
                system_time.sleep(RETRY_DELAY)
            else:
                return [], False
    
    return [], False


def sync_invoices_from_nikan():
    log = AccountingSyncLog.objects.create(
        sync_type='invoices',
        status='processing'
    )
    
    try:
        api = AccountingAPIClient()
        
        last_sync_date = get_last_sync_date()
        
        if last_sync_date:
            result = sync_invoices_incremental(api, log, last_sync_date)
        else:
            result = sync_invoices_full(api, log)
        
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.new_items_count = result.get('saved_count', 0)
        log.failed_items_count = result.get('error_count', 0)
        log.save()
        
        result['success'] = True
        return result
        
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        log.save()
        return {'success': False, 'error': str(e)}


def sync_invoices_full(api, log):
    saved_count = 0
    skipped_count = 0
    error_count = 0
    no_customer_count = 0
    total_items = 0
    last_successful_date_jalali = None
    
    end_date = timezone.now().date()
    current_date = end_date
    
    empty_days_count = 0
    MAX_EMPTY_DAYS = 100
    day_count = 0
    
    while True:
        jalali_date = jdatetime.date.fromgregorian(date=current_date)
        day_str = f"{jalali_date.year}_{jalali_date.month:02d}_{jalali_date.day:02d}"
        
        invoices_data, success = fetch_invoices_for_day(api, current_date)
        
        if success and invoices_data:
            day_result = process_invoices_batch(invoices_data)
            
            saved_count += day_result['saved_count']
            skipped_count += day_result['skipped_count']
            error_count += day_result['error_count']
            no_customer_count += day_result['no_customer_count']
            total_items += day_result['total_items']
            
            last_successful_date_jalali = gregorian_to_jalali(current_date)
            empty_days_count = 0
            
        else:
            empty_days_count += 1
            
            if empty_days_count >= MAX_EMPTY_DAYS:
                break
        
        current_date = current_date - timedelta(days=1)
        day_count += 1
        
        if current_date.year < 1400:
            break
        
        system_time.sleep(0.3)
    
    if last_successful_date_jalali:
        save_last_sync_date(last_successful_date_jalali)
    
    return {
        'saved_count': saved_count,
        'skipped_count': skipped_count,
        'no_customer_count': no_customer_count,
        'error_count': error_count,
        'total_items': total_items,
        'last_sync_date': last_successful_date_jalali,
        'days_processed': day_count,
    }


def sync_invoices_incremental(api, log, last_sync_date):
    saved_count = 0
    skipped_count = 0
    error_count = 0
    no_customer_count = 0
    total_items = 0
    last_successful_date_jalali = last_sync_date
    
    start_date = jalali_to_gregorian(last_sync_date)
    
    if not start_date:
        start_date = timezone.now().date() - timedelta(days=30)
    
    end_date = timezone.now().date()
    
    start_date = start_date + timedelta(days=1)
    
    if start_date > end_date:
        return {
            'saved_count': 0,
            'skipped_count': 0,
            'no_customer_count': 0,
            'error_count': 0,
            'total_items': 0,
            'last_sync_date': last_sync_date,
        }
    
    current_date = start_date
    day_count = 0
    empty_days_count = 0
    MAX_EMPTY_DAYS = 100
    
    while current_date <= end_date:
        invoices_data, success = fetch_invoices_for_day(api, current_date)
        
        if success and invoices_data:
            day_result = process_invoices_batch(invoices_data)
            
            saved_count += day_result['saved_count']
            skipped_count += day_result['skipped_count']
            error_count += day_result['error_count']
            no_customer_count += day_result['no_customer_count']
            total_items += day_result['total_items']
            
            last_successful_date_jalali = gregorian_to_jalali(current_date)
            empty_days_count = 0
            
        else:
            empty_days_count += 1
            
            if empty_days_count >= MAX_EMPTY_DAYS and current_date < end_date:
                break
        
        current_date = current_date + timedelta(days=1)
        day_count += 1
        
        system_time.sleep(0.3)
    
    if last_successful_date_jalali:
        save_last_sync_date(last_successful_date_jalali)
    else:
        save_last_sync_date(last_sync_date)
    
    return {
        'saved_count': saved_count,
        'skipped_count': skipped_count,
        'no_customer_count': no_customer_count,
        'error_count': error_count,
        'total_items': total_items,
        'last_sync_date': last_successful_date_jalali or last_sync_date,
        'days_processed': day_count,
    }


def fetch_invoices_for_day(api, date_obj):
    jalali_date = jdatetime.date.fromgregorian(date=date_obj)
    date_str = jalali_date.strftime('%Y/%m/%d')
    
    
    
    request_data = {
        'Type': 1,
        'ReportType': 0,
        'Filter_FromRegDate': date_str,
        'Filter_ToRegDate': date_str,
        'RowCount': 5000,
    }
    
    return fetch_invoices_with_retry(api, request_data)


def process_invoices_batch(invoices_data):
    saved_count = 0
    skipped_count = 0
    error_count = 0
    no_customer_count = 0
    total_items = 0
    
    if not invoices_data:
        return {
            'saved_count': 0,
            'skipped_count': 0,
            'no_customer_count': 0,
            'error_count': 0,
            'total_items': 0,
        }
    
    confirmed_status, _ = InvoiceStatus.objects.get_or_create(
        code='CONFIRMED',
        defaults={'name': 'Confirmed', 'is_final': True}
    )
    
    customer_cache = {}
    customer_ids = set()
    
    for inv_data in invoices_data:
        cust_id = inv_data.get('CustId')
        if cust_id:
            customer_ids.add(str(cust_id))
    
    if customer_ids:
        mappings = AccountingCustomerMapping.objects.filter(
            accounting_code__in=list(customer_ids)
        ).select_related('customer')
        
        for mapping in mappings:
            customer_cache[mapping.accounting_code] = mapping.customer
    
    fac_nos = [str(inv.get('Fac_No')) for inv in invoices_data if inv.get('Fac_No')]
    existing_ids = set()
    if fac_nos:
        existing_ids = set(
            Invoice.objects.filter(
                accounting_invoice_id__in=fac_nos
            ).values_list('accounting_invoice_id', flat=True)
        )
    
    invoices_to_create = []
    items_data = []
    
    for inv_data in invoices_data:
        try:
            fac_no = str(inv_data.get('Fac_No'))
            if not fac_no:
                continue
            
            if fac_no in existing_ids:
                skipped_count += 1
                continue
            
            cust_id = str(inv_data.get('CustId'))
            customer = customer_cache.get(cust_id)
            
            if not customer:
                no_customer_count += 1
                continue
            
            # ===== تبدیل تاریخ شمسی به میلادی =====
            fac_date = inv_data.get('Fac_Date', '')
            date_obj = timezone.now()
            
            
            
            if fac_date:
                try:
                    parts = fac_date.split('/')
                    if len(parts) == 3:
                        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                        if y < 100:
                            y = y + 1300 if y > 30 else y + 1400
                        jalali_date = jdatetime.date(y, m, d)
                        gregorian_date = jalali_date.togregorian()
                        date_obj = datetime.combine(gregorian_date, datetime.min.time())
                        date_obj = timezone.make_aware(date_obj)
                    
                except Exception as e:
                    
                    date_obj = timezone.now()
            
            total = Decimal(str(inv_data.get('HFac_Payable', 0)))
            subtotal = Decimal(str(inv_data.get('HFac_TotalAmount', 0)))
            discount = Decimal(str(inv_data.get('HFac_Discount', 0)))
            
            invoice_id = generate_invoice_id(fac_no)
            
            invoice = Invoice(
                invoice_id=invoice_id,
                customer=customer,
                accounting_invoice_id=fac_no,
                subtotal=subtotal,
                discount=discount,
                total=total,
                status=confirmed_status,
                payment_status='paid',
                sent_to_accounting=True,
                sent_to_accounting_at=timezone.now(),
                date=date_obj,
                notes=inv_data.get('Hfac_Note', '')
            )
            invoices_to_create.append(invoice)
            
            details = inv_data.get('Details', [])
            for detail in details:
                product_code = str(detail.get('Lots_LCode', ''))
                if not product_code:
                    continue
                
                quantity = detail.get('DFac_Count', 0)
                price = detail.get('DFac_Phi', 0)
                amount = detail.get('DFac_Amount', 0)
                points = int(amount) // 1000 if amount else 0
                
                items_data.append({
                    'invoice_ref': invoice,
                    'product_code': product_code,
                    'quantity': int(quantity),
                    'price': Decimal(str(price)),
                    'points_earned': points
                })
            
            total_items += len(details)
            saved_count += 1
            
        except Exception as e:
            
            error_count += 1
    
    created_invoices = []
    if invoices_to_create:
        created_invoices = Invoice.objects.bulk_create(invoices_to_create)
        
    
    if created_invoices and items_data:
        invoice_id_map = {}
        for inv in created_invoices:
            invoice_id_map[inv.accounting_invoice_id] = inv.id
        
        final_items = []
        for item in items_data:
            invoice_ref = item['invoice_ref']
            invoice_id = invoice_id_map.get(invoice_ref.accounting_invoice_id)
            if invoice_id:
                final_items.append(
                    InvoiceItem(
                        invoice_id=invoice_id,
                        product_code=item['product_code'],
                        quantity=item['quantity'],
                        price=item['price'],
                        points_earned=item['points_earned']
                    )
                )
        
        if final_items:
            InvoiceItem.objects.bulk_create(final_items)
            
    
    return {
        'saved_count': saved_count,
        'skipped_count': skipped_count,
        'no_customer_count': no_customer_count,
        'error_count': error_count,
        'total_items': total_items,
    }