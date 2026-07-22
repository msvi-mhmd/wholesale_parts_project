# payments/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class PaymentType(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='نام')
    code = models.CharField(max_length=20, unique=True, verbose_name='کد')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'نوع پرداخت'
        verbose_name_plural = 'انواع پرداخت'


class BankAccount(models.Model):
    """حساب‌های بانکی شرکت برای واریز"""
    bank_name = models.CharField(max_length=100, verbose_name='نام بانک')
    account_number = models.CharField(max_length=50, verbose_name='شماره حساب')
    card_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='شماره کارت')
    shaba_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='شماره شبا')
    account_holder = models.CharField(max_length=200, verbose_name='صاحب حساب')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"
    
    class Meta:
        verbose_name = 'حساب بانکی'
        verbose_name_plural = 'حساب‌های بانکی'


class InvoicePayment(models.Model):
    """پرداخت‌های مربوط به فاکتور"""
    PAYMENT_METHOD_CHOICES = (
        ('wallet', 'پرداخت از کیف پول'),
        ('online', 'پرداخت آنلاین'),
        ('card_to_card', 'کارت به کارت'),
        ('bank_transfer', 'حواله بانکی'),
        ('cheque', 'ثبت چک'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده'),
        ('failed', 'ناموفق'),
        ('awaiting_approval', 'در انتظار تایید'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    )
    
    invoice = models.ForeignKey('invoices.Invoice', on_delete=models.CASCADE, related_name='payments', verbose_name='فاکتور')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='invoice_payments', verbose_name='مشتری')
    
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, verbose_name='روش پرداخت')
    amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='مبلغ')
    
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='حساب مقصد')
    confirmation_code = models.CharField(max_length=100, blank=True, null=True, verbose_name='کد پیگیری')
    payment_date = models.DateField(null=True, blank=True, verbose_name='تاریخ پرداخت')
    payment_time = models.TimeField(null=True, blank=True, verbose_name='ساعت پرداخت')
    receipt_image = models.ImageField(upload_to='payments/receipts/', blank=True, null=True, verbose_name='تصویر رسید')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    
    accounting_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='شماره در حسابداری')
    sent_to_accounting = models.BooleanField(default=False, verbose_name='ارسال به حسابداری')
    sent_to_accounting_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ارسال به حسابداری')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تایید')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_invoice_payments', verbose_name='تایید کننده')
    
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    
    def __str__(self):
        return f"{self.invoice.invoice_id} - {self.method} - {self.amount}"
    
    class Meta:
        verbose_name = 'پرداخت فاکتور'
        verbose_name_plural = 'پرداخت‌های فاکتور'
        ordering = ['-created_at']


class Payment(models.Model):
    """پرداخت‌های معمولی (افزایش اعتبار)"""
    STATUS_CHOICES = (
        ('pending', 'در انتظار تایید'),
        ('confirmed', 'تایید شده'),
        ('rejected', 'رد شده'),
    )
    
    PAYMENT_CATEGORY_CHOICES = (
        ('wallet', 'شارژ کیف پول'),
        ('invoice', 'پرداخت فاکتور'),
        ('debt', 'پرداخت بدهی'),
    )
    
    PAYMENT_METHOD_CHOICES = [
        ('online', 'آنلاین'),
        ('wallet', 'کیف پول'),
        ('cash', 'نقدی'),
        ('cheque', 'چک'),
        ('pos', 'کارتخوان'),
        ('transfer', 'انتقال بانکی'),
    ]

    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    needs_approval = models.BooleanField(default=False)  # فقط برای روش‌های غیرآنلاین
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_payments')
    
    accounting_document_no = models.CharField(max_length=50, blank=True, null=True)

    
    payment_category = models.CharField(
        max_length=20, 
        choices=PAYMENT_CATEGORY_CHOICES, 
        default='wallet',
        verbose_name='دسته‌بندی پرداخت'
    )

    payment_id = models.CharField(max_length=50, unique=True, verbose_name='شماره پرداخت')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='payments', verbose_name='مشتری')
    amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='مبلغ')
    payment_type = models.ForeignKey(PaymentType, on_delete=models.PROTECT, verbose_name='نوع پرداخت')
    confirmation_code = models.CharField(max_length=100, blank=True, verbose_name='کد پیگیری')
    is_confirmed = models.BooleanField(default=False, verbose_name='تایید شده')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_payments')
    confirmed_date = models.DateTimeField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True, verbose_name='تاریخ پرداخت')
    payment_time = models.TimeField(null=True, blank=True, verbose_name='ساعت پرداخت')
    date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ ثبت')
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True, verbose_name='تصویر رسید')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    
    def save(self, *args, **kwargs):
        if not self.payment_id:
            # ===== پرداخت فاکتور =====
            if self.payment_category == 'invoice':
                try:
                    from accounting.api_client import AccountingAPIClient
                    from accounting.models import SyncQueue
                    
                    api_client = AccountingAPIClient()
                    
                    # بررسی اتصال به نیکان
                    connection_status = api_client.check_connection()
                    
                    if connection_status.get('connected', False):
                        # اگر وصل بود، شماره بگیر
                        if hasattr(api_client, 'sync_counters'):
                            api_client.sync_counters()
                            next_number = api_client.get_next_payment_number()
                            self.payment_id = f"PAY-{str(next_number).zfill(8)}"
                        else:
                            import random
                            self.payment_id = f"PAY-{str(random.randint(10000000, 99999999))}"
                    else:
                        # اگر وصل نبود، یه شماره موقت بذار و به صف اضافه کن
                        import random
                        self.payment_id = f"PAY-TEMP-{str(random.randint(10000000, 99999999))}"
                        
                        # اضافه کردن به صف برای دریافت شماره بعداً
                        SyncQueue.objects.get_or_create(
                            queue_type='payment',
                            object_id=self.id,
                            defaults={
                                'data': {'payment_id': self.id},
                                'status': 'pending'
                            }
                        )
                except:
                    # اگر هر خطایی رخ داد
                    import random
                    self.payment_id = f"PAY-{str(random.randint(10000000, 99999999))}"
            else:
                # ===== شارژ کیف پول یا پرداخت بدهی =====
                import random
                self.payment_id = f"WALLET-{str(random.randint(10000000, 99999999))}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.payment_id} - {self.amount} ریال"
    
    class Meta:
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'
        ordering = ['-date']