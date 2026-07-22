import requests
import json
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from decimal import Decimal
from datetime import datetime


class AccountingAPIClient:
    """کلاینت ارتباط با API حسابداری دراک (Derak) - نسخه کامل و نهایی"""
    
    def __init__(self):
        self.base_url = settings.ACCOUNTING_API.get('BASE_URL', 'https://derak.nikansoft.com/api')
        self.api_key = settings.ACCOUNTING_API.get('API_KEY', '')
        self.username = settings.ACCOUNTING_API.get('USERNAME', '')
        self.password = settings.ACCOUNTING_API.get('PASSWORD', '')
        self.timeout = settings.ACCOUNTING_API.get('TIMEOUT', 120)
        self.token = None
        self.debug = False
    
    def _log(self, msg):
        if self.debug:
            print(f"[DEBUG] {msg}")
    
    def _get_headers(self):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'live-data': 'true'
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers
    
    def _handle_response(self, response):
        try:
            data = response.json()
        except Exception:
            return {
                'success': False,
                'error': f'خطا در دریافت پاسخ: {response.text[:200]}',
                'status_code': response.status_code
            }
        
        if 'IsSuccess' in data:
            if data.get('IsSuccess'):
                return {
                    'success': True,
                    'data': data.get('Data'),
                    'request_id': data.get('RequestId'),
                    'raw': data
                }
            else:
                return {
                    'success': False,
                    'error': data.get('ErrorMessage', 'خطای ناشناخته'),
                    'error_code': data.get('ErrorCode'),
                    'request_id': data.get('RequestId'),
                    'raw': data
                }
        
        return {'success': True, 'data': data, 'raw': data}
    
    def _get_token(self):
        try:
            url = f"{self.base_url}/token"
            
            data = {
                'apikey': self.api_key,
                'username': self.username,
                'password': self.password
            }
            
            response = requests.post(
                url,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('IsSuccess'):
                    self.token = result.get('Data', {}).get('AccessToken')
                    if self.token:
                        cache.set('derak_api_token', self.token, 60 * 25)
                        return True
            
            return False
        except Exception:
            return False
    
    def _ensure_token(self):
        cached_token = cache.get('derak_api_token')
        if cached_token:
            self.token = cached_token
            return True
        
        return self._get_token()
    
    def _post(self, endpoint, data=None, save_request=False, invoice_id=None):
        try:
            if not self._ensure_token():
                return {'success': False, 'error': 'عدم دسترسی به توکن امنیتی'}
            
            if not endpoint.startswith('v1.0/') and endpoint != 'token':
                url = f"{self.base_url}/v1.0/{endpoint}"
            else:
                url = f"{self.base_url}/{endpoint}"
            
            headers = self._get_headers()
            
            # ===== ذخیره درخواست کامل قبل از ارسال =====
            if save_request and endpoint == 'create-factor':
                request_data = {
                    'method': 'POST',
                    'url': url,
                    'headers': headers,
                    'body': data or {}
                }
                self.save_full_request_to_file(request_data, invoice_id=invoice_id)
            
            response = requests.post(
                url,
                headers=headers,
                json=data or {},
                timeout=self.timeout
            )
            result = self._handle_response(response)
            
            if result is None:
                return {'success': False, 'error': 'نتیجه پاسخ None است'}
            
            return result
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'خطا در ارتباط با سرور (Timeout)'}
        except Exception as e:
            return {'success': False, 'error': f'خطا در ارتباط با سرور: {str(e)}'}


    def save_full_request_to_file(self, request_data, invoice_id=None):
        """ذخیره کامل درخواست با هدر در فایل JSON"""
        try:
            import json
            import os
            from django.conf import settings
            from django.utils import timezone
            
            log_dir = os.path.join(settings.BASE_DIR, 'logs', 'invoice_requests')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            invoice_id_str = f"_{invoice_id}" if invoice_id else ""
            filename = f"full_request_{timestamp}{invoice_id_str}.json"
            filepath = os.path.join(log_dir, filename)
            
            # ===== تبدیل data به فرمت قابل ذخیره =====
            data = {
                'timestamp': timezone.now().isoformat(),
                'invoice_id': invoice_id,
                'request': request_data,
                'response': None
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            return filepath
        except Exception as e:
            print(f"Error saving request: {e}")
            return None
    # ============================
    # ۱. محصولات
    # ============================
    
    def get_products(self, timestamp=None, name=None, level_id=None, barcode=None, row_count=30000):
        params = {
            'RowCount': row_count,
            'WithFloatSepration': True
        }
        
        if level_id is None and timestamp is None and name is None and barcode is None:
            params['LevelId'] = '-1'
        
        if timestamp:
            params['TimeStamp'] = timestamp
        if name:
            params['Name'] = name
        if level_id is not None:
            params['LevelId'] = level_id
        if barcode:
            params['Barcode'] = barcode
        
        result = self._post('get-products', data=params)
        
        if not result:
            return {'success': False, 'error': 'نتیجه دریافت محصولات None است'}
        
        if result.get('success'):
            data = result.get('data')
            
            if data is None:
                return {
                    'success': True,
                    'products': [],
                    'count': 0,
                    'total': 0
                }
            
            last_timestamp = None
            if isinstance(data, list) and data:
                last_item = data[-1] if data else {}
                last_timestamp = last_item.get('TimeStamp')
            elif isinstance(data, dict):
                products = data.get('Data', []) or data.get('data', [])
                if products:
                    last_item = products[-1] if products else {}
                    last_timestamp = last_item.get('TimeStamp')
                if not last_timestamp:
                    last_timestamp = data.get('TimeStamp')
            
            if last_timestamp:
                cache.set('nikan_last_product_timestamp', last_timestamp, 60 * 60 * 24 * 7)
            
            if isinstance(data, list):
                return {
                    'success': True,
                    'products': data,
                    'count': len(data),
                    'total': len(data),
                    'last_timestamp': last_timestamp,
                }
            
            if isinstance(data, dict):
                products = data.get('Data', []) or data.get('data', [])
                return {
                    'success': True,
                    'products': products,
                    'count': len(products),
                    'total': data.get('Total', len(products)),
                    'last_timestamp': last_timestamp,
                }
            
            return {
                'success': True,
                'products': [],
                'count': 0,
                'total': 0,
                'last_timestamp': last_timestamp,
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'خطا در دریافت محصولات'),
                'error_code': result.get('error_code')
            }
    
    def get_last_product_timestamp(self):
        try:
            return cache.get('nikan_last_product_timestamp')
        except:
            return None

    def get_updated_products(self, last_sync_date):
        if isinstance(last_sync_date, datetime):
            timestamp = last_sync_date.isoformat()
        else:
            timestamp = str(last_sync_date)
        return self.get_products(timestamp=timestamp)
    
    def create_product(self, product_data):
        result = self._post('create-product', data=product_data)
        
        if not result:
            return {'success': False, 'error': 'نتیجه ایجاد محصول None است'}
        
        if result.get('success'):
            data = result.get('data', {})
            return {
                'success': True,
                'product_code': data.get('ResultLots_Code'),
                'product_id': data.get('ResultLots_LCode'),
                'data': data
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'خطا در ایجاد محصول'),
                'error_code': result.get('error_code')
            }
    
    def get_product_groups(self, level=0, code=None):
        data = {'Level': level}
        if code:
            data['Code'] = code
        return self._post('get-product-groups', data=data)
    
    def get_floating_items(self, floating_type=1):
        return self._post('get-floating-items', data={'FloatingType': floating_type})
    
    def get_last_product_code(self):
        try:
            result = self.get_products(row_count=1)
            if result and result.get('success'):
                products = result.get('products', [])
                if products:
                    return int(products[0].get('Lots_Code', 0))
        except:
            pass
        return 0

    # ============================
    # ۲. مشتریان
    # ============================
    
    def get_customers(self, customer_id=None, customer_name=None, customer_type=None, row_count=1000):
        params = {'RowCount': row_count}
        
        if customer_id is None and customer_type is None and customer_name is None:
            params['CustomerId'] = 0
        
        if customer_id is not None:
            params['CustomerId'] = customer_id
        if customer_name:
            params['CustomerName'] = customer_name
        if customer_type is not None:
            params['CustomerType'] = customer_type
        
        result = self._post('get-customers', data=params)
        
        if not result:
            return {'success': False, 'error': 'نتیجه دریافت مشتریان None است'}
        
        if result.get('success'):
            data = result.get('data')
            
            if data is None:
                return {
                    'success': True,
                    'customers': [],
                    'count': 0,
                    'total': 0
                }
            
            required_fields = ['CustId', 'Accs_Code', 'CustName', 'Mobile', 'Tel1', 'CustAddr', 'Mandeh']
            
            if isinstance(data, list):
                customers = []
                for item in data:
                    filtered = {}
                    for field in required_fields:
                        filtered[field] = item.get(field)
                    filtered['phone'] = item.get('Mobile') or item.get('Tel1')
                    customers.append(filtered)
                return {
                    'success': True,
                    'customers': customers,
                    'count': len(customers),
                    'total': len(data)
                }
            
            if isinstance(data, dict):
                items = data.get('Data', []) or data.get('data', [])
                customers = []
                for item in items:
                    filtered = {}
                    for field in required_fields:
                        filtered[field] = item.get(field)
                    filtered['phone'] = item.get('Mobile') or item.get('Tel1')
                    customers.append(filtered)
                return {
                    'success': True,
                    'customers': customers,
                    'count': len(customers),
                    'total': data.get('Total', len(customers))
                }
            
            return {
                'success': True,
                'customers': [],
                'count': 0,
                'total': 0
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'خطا در دریافت مشتریان'),
                'error_code': result.get('error_code')
            }
    
    def create_customer(self, customer_data):
        try:
            result = self._post('create-customer', data=customer_data)
            
            if result is None:
                return {'success': False, 'error': 'نتیجه ایجاد مشتری None است'}
            
            if not result.get('success'):
                return {
                    'success': False,
                    'error': result.get('error', 'خطا در ایجاد مشتری'),
                    'error_code': result.get('error_code')
                }
            
            return {
                'success': True,
                'message': 'مشتری با موفقیت در نیکان ثبت شد'
            }
                    
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
        


    def get_customer_ledger(self, customer_id=0, row_count=100):
        return self._post('customer-accounting-book', data={
            'CustomerId': customer_id,
            'RowCount': row_count
        })
    
    def get_last_customer_code(self):
        try:
            result = self.get_customers(row_count=1)
            if result and result.get('success'):
                customers = result.get('customers', [])
                if customers:
                    return int(customers[0].get('CustId', 0))
        except:
            pass
        return 0

    # ============================
    # ۳. فاکتورها
    # ============================
    
    def get_factors(self, **params):
        result = self._post('get-factors', data=params)
        
        if not result:
            return {'success': False, 'error': 'نتیجه دریافت فاکتورها None است'}
        
        if result.get('success'):
            data = result.get('data')
            if data is None:
                return {
                    'success': True,
                    'invoices': [],
                    'count': 0,
                    'total': 0
                }
            
            if isinstance(data, list):
                return {
                    'success': True,
                    'invoices': data,
                    'count': len(data),
                    'total': len(data)
                }
            
            if isinstance(data, dict):
                invoices = data.get('Data', []) or data.get('data', [])
                return {
                    'success': True,
                    'invoices': invoices,
                    'count': len(invoices),
                    'total': data.get('Total', len(invoices))
                }
            
            return {
                'success': True,
                'invoices': [],
                'count': 0,
                'total': 0
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'خطا در دریافت فاکتورها'),
                'error_code': result.get('error_code')
            }
    
    def create_invoice(self, invoice_data):
        if 'Type' not in invoice_data:
            invoice_data['Type'] = 6
        
        result = self._post('create-factor', data=invoice_data)
        
        if not result:
            return {'success': False, 'error': 'نتیجه ثبت فاکتور None است'}
        
        if result.get('success'):
            data = result.get('data', {})
            return {
                'success': True,
                'invoice_id': data.get('HFac_No'),
                'invoice_code': data.get('HFac_Code'),
                'data': data
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'خطا در ثبت فاکتور'),
                'error_code': result.get('error_code')
            }
    
    def confirm_factor(self, hfac_code, accept_amount, accept_receipt_no, confirmed=True):
        return self._post('get-final-save-factor', data={
            'Hfac_Code': hfac_code,
            'Accept_Amount': accept_amount,
            'Accept_ReceiptNo': accept_receipt_no,
            'Confirmed': confirmed
        })
    
    def get_last_invoice_number(self):
        try:
            result = self.get_factors(row_count=1)
            if result and result.get('success'):
                data = result.get('data', {})
                factors = data.get('Data', []) or data.get('data', [])
                if factors:
                    return int(factors[0].get('Fac_No', 0))
        except:
            pass
        return 0

    # ============================
    # ۴. پرداخت‌ها
    # ============================
    
    from decimal import Decimal

    def create_payment(self, payment_data):
        try:
            amount = Decimal(str(payment_data.get('Amount', 0)))
            
            document_items = [
                {
                    'Order': 1,
                    'Center1CustId': int(payment_data.get('CustId')),
                    'Description': payment_data.get('Note', 'پرداخت'),
                    'Debtor': 0.0,
                    'Creditor': float(amount),
                },
                {
                    'Order': 2,
                    'MainAccCode' : '111-1112-11127',
                    'Description': payment_data.get('Note', 'پرداخت'),
                    'Debtor': float(amount),
                    'Creditor': 0.0,
                },
            ]
            
            result = self._post('create-document', data=document_items)
            
            if result is None:
                return {'success': False, 'error': 'نتیجه ثبت پرداخت None است'}
            
            if result.get('success'):
                data = result.get('data', {})
                return {
                    'success': True,
                    'document_no': data.get('DoCH_DocNO'),
                    'document_id': data.get('DocHID_ID'),
                    'data': data
                }
            
            return {
                'success': False,
                'error': result.get('error', 'خطا در ثبت پرداخت'),
                'error_code': result.get('error_code')
            }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    # ============================
    # ۵. شمارنده‌ها (Counters)
    # ============================
    
    def sync_counters(self):
        from .models import AccountingCounter
        
        try:
            last_customer = self.get_last_customer_code()
            if last_customer:
                counter, _ = AccountingCounter.objects.get_or_create(
                    counter_type='customer',
                    defaults={'last_number': last_customer}
                )
                if last_customer > counter.last_number:
                    counter.last_number = last_customer
                    counter.save()
        except Exception:
            pass
        
        try:
            last_product = self.get_last_product_code()
            if last_product:
                counter, _ = AccountingCounter.objects.get_or_create(
                    counter_type='product',
                    defaults={'last_number': last_product}
                )
                if last_product > counter.last_number:
                    counter.last_number = last_product
                    counter.save()
        except Exception:
            pass
        
        try:
            last_invoice = self.get_last_invoice_number()
            if last_invoice:
                counter, _ = AccountingCounter.objects.get_or_create(
                    counter_type='invoice',
                    defaults={'last_number': last_invoice}
                )
                if last_invoice > counter.last_number:
                    counter.last_number = last_invoice
                    counter.save()
        except Exception:
            pass
        
        return {'success': True}
    
    def get_next_customer_code(self):
        from .models import AccountingCounter
        self.sync_counters()
        counter, _ = AccountingCounter.objects.get_or_create(
            counter_type='customer',
            defaults={'last_number': 0}
        )
        next_number = counter.last_number + 1
        counter.last_number = next_number
        counter.save()
        return next_number
    
    def get_next_product_code(self):
        from .models import AccountingCounter
        self.sync_counters()
        counter, _ = AccountingCounter.objects.get_or_create(
            counter_type='product',
            defaults={'last_number': 0}
        )
        next_number = counter.last_number + 1
        counter.last_number = next_number
        counter.save()
        return next_number
    
    def get_next_invoice_number(self):
        from .models import AccountingCounter
        self.sync_counters()
        counter, _ = AccountingCounter.objects.get_or_create(
            counter_type='invoice',
            defaults={'last_number': 0}
        )
        next_number = counter.last_number + 1
        counter.last_number = next_number
        counter.save()
        return next_number
    
    def get_next_payment_number(self):
        from .models import AccountingCounter
        self.sync_counters()
        counter, _ = AccountingCounter.objects.get_or_create(
            counter_type='payment',
            defaults={'last_number': 0}
        )
        next_number = counter.last_number + 1
        counter.last_number = next_number
        counter.save()
        return next_number

    # ============================
    # ۶. صف همگام‌سازی (Queue)
    # ============================
    
    def create_customer_with_queue(self, customer_data, customer_id):
        from .models import SyncQueue
        
        SyncQueue.objects.filter(
            queue_type='customer',
            object_id=customer_id,
            status='pending'
        ).delete()
        
        return SyncQueue.objects.create(
            queue_type='customer',
            object_id=customer_id,
            data=customer_data,
            status='pending'
        )
    
    def _process_customer_sync(self, queue_item):
        from customers.models import Customer
        
        customer = Customer.objects.get(id=queue_item.object_id)
        data = queue_item.data
        
        result = self.create_customer(data)
        
        if result and result.get('success'):
            customer.nikan_customer_code = str(result.get('customer_id'))
            customer.nikan_sync_status = 'synced'
            customer.nikan_sync_at = timezone.now()
            customer.save()
            return {'success': True, 'message': f'مشتری {customer.user.get_full_name()} همگام‌سازی شد'}
        else:
            return {'success': False, 'error': result.get('error', 'خطا در همگام‌سازی') if result else 'نتیجه None است'}
    
    def _process_product_sync(self, queue_item):
        from products.models import Product
        
        product = Product.objects.get(id=queue_item.object_id)
        data = queue_item.data
        
        result = self.create_product(data)
        
        if result and result.get('success'):
            product.nikan_product_code = str(result.get('product_code'))
            product.nikan_sync_status = 'synced'
            product.nikan_sync_at = timezone.now()
            product.save()
            return {'success': True, 'message': f'محصول {product.name} همگام‌سازی شد'}
        else:
            return {'success': False, 'error': result.get('error', 'خطا در همگام‌سازی') if result else 'نتیجه None است'}
    
    def _process_invoice_sync(self, queue_item):
        from invoices.models import Invoice
        
        invoice = Invoice.objects.get(id=queue_item.object_id)
        data = queue_item.data
        
        result = self.create_invoice(data)
        
        if result and result.get('success'):
            invoice.nikan_invoice_number = str(result.get('invoice_id'))
            invoice.nikan_sync_status = 'synced'
            invoice.nikan_sync_at = timezone.now()
            invoice.save()
            return {'success': True, 'message': f'فاکتور {invoice.invoice_id} همگام‌سازی شد'}
        else:
            return {'success': False, 'error': result.get('error', 'خطا در همگام‌سازی') if result else 'نتیجه None است'}
    
    def _process_payment_sync(self, queue_item):
        from payments.models import Payment
        
        payment = Payment.objects.get(id=queue_item.object_id)
        
        if payment.payment_category != 'invoice':
            return {'success': True, 'message': 'پرداخت غیرمرتبط با حسابداری'}
        
        if payment.payment_id and not payment.payment_id.startswith('PAY-TEMP'):
            return {'success': True, 'message': 'شماره قبلاً گرفته شده'}
        
        try:
            self.sync_counters()
            next_number = self.get_next_payment_number()
            new_payment_id = f"PAY-{str(next_number).zfill(8)}"
            
            payment.payment_id = new_payment_id
            payment.save()
            
            return {'success': True, 'message': f'شماره پرداخت {new_payment_id} از نیکان دریافت شد'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def process_sync_queue(self, limit=10):
        from .models import SyncQueue
        
        pending_items = SyncQueue.objects.filter(
            status='pending'
        ).order_by('created_at')[:limit]
        
        results = []
        
        for item in pending_items:
            try:
                item.status = 'processing'
                item.save()
                
                if item.queue_type == 'customer':
                    result = self._process_customer_sync(item)
                elif item.queue_type == 'product':
                    result = self._process_product_sync(item)
                elif item.queue_type == 'invoice':
                    result = self._process_invoice_sync(item)
                elif item.queue_type == 'payment':
                    result = self._process_payment_sync(item)
                else:
                    result = {'success': False, 'error': 'نوع نامعتبر'}
                
                if result and result.get('success'):
                    item.status = 'completed'
                    item.processed_at = timezone.now()
                    item.save()
                    results.append({
                        'id': item.id,
                        'type': item.queue_type,
                        'status': 'completed',
                        'message': result.get('message', 'موفق')
                    })
                else:
                    item.attempt_count += 1
                    item.error_message = result.get('error', 'خطای ناشناخته') if result else 'نتیجه None است'
                    
                    if item.attempt_count >= 3:
                        item.status = 'failed'
                    else:
                        item.status = 'pending'
                    
                    item.save()
                    results.append({
                        'id': item.id,
                        'type': item.queue_type,
                        'status': 'failed' if item.status == 'failed' else 'retry',
                        'error': item.error_message
                    })
                    
            except Exception as e:
                item.attempt_count += 1
                item.error_message = str(e)
                if item.attempt_count >= 3:
                    item.status = 'failed'
                else:
                    item.status = 'pending'
                item.save()
                results.append({
                    'id': item.id,
                    'type': item.queue_type,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return results
    
    def get_pending_sync_count(self):
        from .models import SyncQueue
        return SyncQueue.objects.filter(status='pending').count()

    # ============================
    # ۷. بررسی اتصال
    # ============================
    
    def check_connection(self):
        try:
            if not self._ensure_token():
                return {
                    'success': False,
                    'connected': False,
                    'error': 'عدم دسترسی به توکن امنیتی'
                }
            
            result = self._post('check-service-connected')
            
            if result is None:
                return {
                    'success': False,
                    'connected': False,
                    'error': 'نتیجه اتصال None است'
                }
            
            if result.get('success'):
                data = result.get('data')
                if isinstance(data, bool):
                    is_connected = data
                elif isinstance(data, dict):
                    is_connected = data.get('connected', False) or data.get('IsConnected', False)
                else:
                    is_connected = str(data).lower() == 'true' if data else False
                
                return {
                    'success': True,
                    'connected': is_connected,
                    'message': 'اتصال به سیستم حسابداری برقرار است' if is_connected else 'اتصال به سیستم حسابداری برقرار نیست'
                }
            else:
                return {
                    'success': False,
                    'connected': False,
                    'error': result.get('error', 'خطا در بررسی اتصال'),
                    'error_code': result.get('error_code')
                }
        except Exception as e:
            return {
                'success': False,
                'connected': False,
                'error': str(e)
            }

    # ============================
    # ۸. همگام‌سازی مشتریان
    # ============================
    
    def sync_customers(self, customer_type=None):
        from .models import AccountingSyncLog, AccountingCustomerMapping
        from customers.models import Customer
        from accounts.models import User
        from django.utils import timezone
        
        log = AccountingSyncLog.objects.create(
            sync_type='customers',
            status='processing'
        )
        
        try:
            connection = self.check_connection()
            if not connection or not connection.get('connected', False):
                log.status = 'failed'
                log.error_message = 'اتصال به نیکان برقرار نیست'
                log.save()
                return {'success': False, 'error': 'اتصال به نیکان برقرار نیست'}
            
            result = self.get_customers(customer_type=customer_type, row_count=5000)
            
            if not result or not result.get('success'):
                log.status = 'failed'
                log.error_message = result.get('error', 'خطا در دریافت مشتریان') if result else 'نتیجه None است'
                log.save()
                return {'success': False, 'error': result.get('error', 'خطا در دریافت مشتریان') if result else 'نتیجه None است'}
            
            customers = result.get('customers', [])
            
            if not customers:
                log.status = 'completed'
                log.completed_at = timezone.now()
                log.new_items_count = 0
                log.save()
                return {'success': True, 'new_count': 0, 'message': 'هیچ مشتری در نیکان یافت نشد'}
            
            new_count = 0
            updated_count = 0
            failed_count = 0
            skipped_no_phone = 0
            
            for customer_data in customers:
                try:
                    customer_code = str(customer_data.get('CustId', ''))
                    if not customer_code:
                        continue
                    
                    phone = customer_data.get('phone') or customer_data.get('Mobile') or customer_data.get('Tel1')
                    
                    if not phone:
                        skipped_no_phone += 1
                        continue
                    
                    phone = ''.join(filter(str.isdigit, str(phone)))
                    if not phone.startswith('0') and len(phone) == 10:
                        phone = f"0{phone}"
                    
                    if len(phone) < 10:
                        skipped_no_phone += 1
                        continue
                    
                    mapping = AccountingCustomerMapping.objects.filter(
                        accounting_code=customer_code
                    ).first()
                    
                    if mapping:
                        customer = mapping.customer
                        user = customer.user
                        
                        name = customer_data.get('CustName', '')
                        
                        if name:
                            name_parts = name.split(' ', 1)
                            user.first_name = name_parts[0] if name_parts else ''
                            user.last_name = name_parts[1] if len(name_parts) > 1 else ''
                        
                        if phone and user.phone != phone:
                            user.phone = phone
                        
                        if customer_data.get('CustAddr'):
                            user.address = customer_data.get('CustAddr')
                        
                        user.save()
                        updated_count += 1
                    else:
                        name = customer_data.get('CustName', '')
                        name_parts = name.split(' ', 1)
                        
                        user = User.objects.filter(phone=phone).first()
                        
                        if not user:
                            user = User.objects.create_user(
                                username=phone,
                                password=phone,
                                first_name=name_parts[0] if name_parts else '',
                                last_name=name_parts[1] if len(name_parts) > 1 else '',
                                phone=phone,
                                national_id=None,
                                user_type='customer',
                                is_active=True,
                                address=customer_data.get('CustAddr', '')
                            )
                        
                        customer = Customer.objects.create(
                            user=user,
                            credit=0,
                            max_credit=0,
                            nikan_customer_code=customer_code
                        )
                        
                        AccountingCustomerMapping.objects.create(
                            customer=customer,
                            accounting_code=customer_code
                        )
                        
                        new_count += 1
                        
                except Exception as e:
                    failed_count += 1
                    continue
            
            log.status = 'completed'
            log.completed_at = timezone.now()
            log.new_items_count = new_count
            log.failed_items_count = failed_count + skipped_no_phone
            log.save()
            
            return {
                'success': True,
                'new_count': new_count,
                'updated_count': updated_count,
                'failed_count': failed_count,
                'skipped_no_phone': skipped_no_phone,
                'total': len(customers),
                'message': f'{new_count} مشتری جدید، {updated_count} مشتری بروزرسانی شد، {skipped_no_phone} مشتری بدون تلفن رد شدند'
            }
            
        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            log.save()
            return {'success': False, 'error': str(e)}
        

        # ============================
    # ۹. همگام‌سازی محصولات
    # ============================

    def sync_products(self, last_sync=None):
        from .models import AccountingSyncLog, AccountingProductMapping
        from products.models import Product, ProductBrand, MainCategory, SubCategory, Car, CarBrand
        from django.utils import timezone
        from django.utils.text import slugify
        import uuid
        
        log = AccountingSyncLog.objects.create(
            sync_type='products',
            status='processing'
        )
        
        try:
            connection = self.check_connection()
            if not connection or not connection.get('connected', False):
                log.status = 'failed'
                log.error_message = 'اتصال به نیکان برقرار نیست'
                log.save()
                return {'success': False, 'error': 'اتصال به نیکان برقرار نیست'}
            
            if not last_sync:
                last_sync = self.get_last_product_timestamp()
            
            result = self.get_products(timestamp=last_sync, row_count=30000)
            
            if not result:
                log.status = 'failed'
                log.error_message = 'نتیجه دریافت محصولات None است'
                log.save()
                return {'success': False, 'error': 'خطا در دریافت محصولات'}
            
            if not result.get('success'):
                log.status = 'failed'
                log.error_message = result.get('error', 'خطا در دریافت محصولات')
                log.save()
                return {'success': False, 'error': result.get('error')}
            
            products = result.get('products', [])
            new_timestamp = result.get('last_timestamp')
            
            new_count = 0
            updated_count = 0
            failed_count = 0
            
            for product_data in products:
                try:
                    product_code = str(product_data.get('LotsId', ''))
                    
                    if not product_code:
                        continue
                    
                    mapping = AccountingProductMapping.objects.filter(
                        accounting_code=product_code
                    ).first()
                    
                    if mapping:
                        product = mapping.product
                        
                        new_price = product_data.get('DefPrice1', 0)
                        if new_price and product.price != new_price:
                            product.price = new_price
                        
                        new_stock = product_data.get('Lots_Count', 0)
                        if product.left_in_stock != new_stock:
                            product.left_in_stock = new_stock
                        
                        new_name = product_data.get('LotsName', '')
                        if new_name and product.name != new_name:
                            product.name = new_name
                        
                        product.save()
                        updated_count += 1
                    else:
                        # ایجاد محصول جدید
                        product_name = product_data.get('LotsName', 'بدون نام')[:200]
                        
                        # برند
                        brand_name = product_data.get('Level1_Name', 'متفرقه').strip()
                        if not brand_name:
                            brand_name = 'متفرقه'
                        
                        brand, created = ProductBrand.objects.get_or_create(
                            name=brand_name[:100],
                            defaults={
                                'country': 'ایران',
                                'city': 'تهران',
                                'slug': f"brand-{uuid.uuid4().hex[:8]}"
                            }
                        )
                        
                        # دسته اصلی
                        main_cat_name = product_data.get('Level3_Name', 'متفرقه')[:100]
                        main_cat, created = MainCategory.objects.get_or_create(
                            name=main_cat_name
                        )
                        
                        # زیردسته
                        sub_cat_name = product_data.get('Level2_Name', 'متفرقه')[:100]
                        sub_cat, created = SubCategory.objects.get_or_create(
                            name=sub_cat_name,
                            defaults={'main_category': main_cat}
                        )
                        
                        # خودرو
                        car_name = product_data.get('Level2_Name', '').strip()
                        car = None
                        if car_name:
                            car_brand_name = product_data.get('Level1_Name', 'متفرقه').strip()
                            car_brand, _ = CarBrand.objects.get_or_create(
                                name=car_brand_name[:100],
                                defaults={'country': 'ایران'}
                            )
                            
                            car, _ = Car.objects.get_or_create(
                                car_brand=car_brand,
                                name=car_name[:100],
                                defaults={'model': ''}
                            )
                        
                        # slug
                        slug = str(product_code)
                        counter = 1
                        original_slug = slug
                        while Product.objects.filter(slug=slug).exists():
                            slug = f"{original_slug}-{counter}"
                            counter += 1
                        
                        # ایجاد محصول
                        price = product_data.get('DefPrice1', 0)
                        left_in_stock = product_data.get('Lots_Count', 0) if price > 0 else 0
                        
                        product = Product.objects.create(
                            name=product_name,
                            slug=slug,
                            product_code=product_code,
                            main_category=main_cat,
                            sub_category=sub_cat,
                            brand=brand,
                            price=price,
                            left_in_stock=left_in_stock,
                            point_of_buy=0,
                            is_active=True
                        )
                        
                        if car:
                            product.suitable_car.add(car)
                        
                        AccountingProductMapping.objects.create(
                            product=product,
                            accounting_code=product_code,
                            technical_code=product_data.get('Lots_Tno', '')
                        )
                        
                        new_count += 1
                        
                except Exception as e:
                    failed_count += 1
                    continue
            
            log.status = 'completed'
            log.completed_at = timezone.now()
            log.new_items_count = new_count
            log.failed_items_count = failed_count
            log.last_synced_code = new_timestamp
            log.save()
            
            return {
                'success': True,
                'new_count': new_count,
                'updated_count': updated_count,
                'failed_count': failed_count,
                'total': len(products),
                'message': f'{new_count} محصول جدید، {updated_count} محصول بروزرسانی شد'
            }
            
        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            log.save()
            return {'success': False, 'error': str(e)}