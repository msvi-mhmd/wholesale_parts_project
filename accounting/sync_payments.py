import jdatetime
from datetime import datetime, time
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from concurrent.futures import ThreadPoolExecutor, as_completed
import time as system_time
import threading

from .api_client import AccountingAPIClient
from .models import AccountingCustomerMapping, AccountingSyncLog
from payments.models import Payment, PaymentType
from customers.models import Customer
from invoices.models import Invoice
from django.db.models import Sum


MAX_WORKERS = 20
REQUESTS_PER_MINUTE = 55
DELAY_BETWEEN_REQUESTS = 60 / REQUESTS_PER_MINUTE
lock = threading.Lock()
last_request_time = 0


def rate_limited_request(api, endpoint, data):
    global last_request_time
    
    with lock:
        current_time = system_time.time()
        time_since_last = current_time - last_request_time
        
        if time_since_last < DELAY_BETWEEN_REQUESTS:
            sleep_time = DELAY_BETWEEN_REQUESTS - time_since_last
            system_time.sleep(sleep_time)
        
        result = api._post(endpoint, data=data)
        last_request_time = system_time.time()
        return result


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


def sync_payments_from_nikan():
    log = AccountingSyncLog.objects.create(
        sync_type='payments',
        status='processing'
    )
    
    try:
        api = AccountingAPIClient()
        
        mappings = list(AccountingCustomerMapping.objects.select_related('customer').all())
        
        if not mappings:
            log.status = 'completed'
            log.completed_at = timezone.now()
            log.new_items_count = 0
            log.save()
            return {'success': True, 'saved_count': 0}
        
        all_ledgers = []
        failed_customers = []
        processed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(fetch_customer_ledger, mapping, api): mapping
                for mapping in mappings
            }
            
            try:
                for future in as_completed(futures):
                    mapping = futures[future]
                    try:
                        result = future.result(timeout=60)
                        if result['entries']:
                            all_ledgers.append({
                                'customer': mapping.customer,
                                'cust_id': int(mapping.accounting_code),
                                'entries': result['entries']
                            })
                        if result['failed']:
                            failed_customers.append(mapping.accounting_code)
                        
                        processed += 1
                            
                    except Exception:
                        failed_customers.append(mapping.accounting_code)
                        
            except KeyboardInterrupt:
                for f in futures:
                    f.cancel()
                raise
            
            executor.shutdown(wait=True)
        
        if not all_ledgers:
            log.status = 'completed'
            log.completed_at = timezone.now()
            log.new_items_count = 0
            log.save()
            return {'success': True, 'saved_count': 0}
        
        saved_count, skipped_count, error_count = process_payments(all_ledgers)
        debt_count = process_debts(all_ledgers)
        
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.new_items_count = saved_count + debt_count
        log.failed_items_count = error_count
        log.save()
        
        return {
            'success': True,
            'saved_count': saved_count,
            'debt_count': debt_count,
            'skipped_count': skipped_count,
            'error_count': error_count,
            'processed_customers': processed,
            'failed_customers': failed_customers,
        }
        
    except KeyboardInterrupt:
        log.status = 'failed'
        log.error_message = 'Cancelled by user'
        log.save()
        return {'success': False, 'error': 'Cancelled by user'}
        
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        log.save()
        return {'success': False, 'error': str(e)}


def fetch_customer_ledger(mapping, api):
    result = {'entries': [], 'failed': False}
    
    try:
        customer = mapping.customer
        cust_id = int(mapping.accounting_code)
        
        response = rate_limited_request(api, 'customer-accounting-book', data={
            'CustomerId': cust_id,
            'RowCount': 10000,
        })
        
        if not response.get('success'):
            result['failed'] = True
            return result
        
        data = response.get('data')
        
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get('Data', []) or data.get('data', [])
        else:
            entries = []
        
        result['entries'] = entries
                
    except Exception:
        result['failed'] = True
    
    return result


def process_payments(all_ledgers):
    saved_count = 0
    skipped_count = 0
    error_count = 0
    
    payment_type, _ = PaymentType.objects.get_or_create(
        code='ACCOUNTING_SYNC',
        defaults={'name': 'همگام‌سازی از حسابداری'}
    )
    
    for ledger_data in all_ledgers:
        customer = ledger_data['customer']
        entries = ledger_data['entries']
        
        for entry in entries:
            try:
                amount = entry.get('Docd_Bes', 0)
                
                if not amount or amount <= 0:
                    continue
                
                doc_no = entry.get('DocH_DocNo')
                if not doc_no:
                    continue
                
                if Payment.objects.filter(confirmation_code=str(doc_no)).exists():
                    skipped_count += 1
                    continue
                
                # ===== تبدیل تاریخ شمسی به میلادی =====
                doc_date = entry.get('DocH_Date', '')
                date_obj = timezone.now()
                
                
                if doc_date:
                    try:
                        parts = doc_date.split('/')
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
                
                
                with transaction.atomic():
                    Payment.objects.create(
                        customer=customer,
                        amount=Decimal(str(amount)),
                        payment_type=payment_type,
                        confirmation_code=str(doc_no),
                        is_confirmed=True,
                        status='confirmed',
                        confirmed_date=date_obj,
                        date=date_obj,
                        payment_category='wallet',
                        method='online',
                        notes=f'همگام‌سازی از حسابداری - سند: {doc_no}'
                    )
                    
                    customer.credit += Decimal(str(amount))
                    customer.total_payments += Decimal(str(amount))
                    customer.save()
                    
                    saved_count += 1
                    
            except Exception as e:
                
                error_count += 1
    
    return saved_count, skipped_count, error_count


def process_debts(all_ledgers):
    debt_count = 0
    
    for ledger_data in all_ledgers:
        customer = ledger_data['customer']
        entries = ledger_data['entries']
        
        total_bed = Decimal('0')
        for entry in entries:
            bed = entry.get('Docd_Bed', 0)
            if bed and bed > 0:
                total_bed += Decimal(str(bed))
        
        total_invoices = Invoice.objects.filter(
            customer=customer,
            status__code='CONFIRMED'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        debt_before = total_bed - total_invoices
        if debt_before < 0:
            debt_before = Decimal('0')
        
        customer.debt_before_1404_02 = debt_before
        customer.save()
        
        if debt_before > 0:
            debt_count += 1
            
    return debt_count