# accounting/models.py
from django.db import models
from django.utils import timezone


class AccountingSyncLog(models.Model):
    """لاگ همگام‌سازی با سیستم حسابداری"""
    SYNC_TYPE_CHOICES = (
        ('customers', 'مشتریان'),
        ('products', 'محصولات'),
        ('invoices', 'فاکتورها'),
        ('payments', 'پرداخت‌ها'),
        ('full', 'همگام‌سازی کامل'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'در انتظار'),
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
    )
    
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPE_CHOICES, verbose_name='نوع همگام‌سازی')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    
    last_synced_code = models.CharField(max_length=50, blank=True, null=True, verbose_name='آخرین کد همگام‌سازی')
    new_items_count = models.PositiveIntegerField(default=0, verbose_name='تعداد آیتم‌های جدید')
    failed_items_count = models.PositiveIntegerField(default=0, verbose_name='تعداد آیتم‌های ناموفق')
    
    error_message = models.TextField(blank=True, verbose_name='پیام خطا')
    
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ شروع')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تکمیل')
    
    def __str__(self):
        return f"{self.get_sync_type_display()} - {self.started_at.strftime('%Y/%m/%d %H:%M')}"
    
    class Meta:
        verbose_name = 'لاگ همگام‌سازی'
        verbose_name_plural = 'لاگ‌های همگام‌سازی'
        ordering = ['-started_at']


class AccountingCustomerMapping(models.Model):
    """نگاشت مشتریان بین سیستم ما و سیستم حسابداری"""
    customer = models.OneToOneField('customers.Customer', on_delete=models.CASCADE, related_name='accounting_mapping', verbose_name='مشتری')
    accounting_code = models.CharField(max_length=50, unique=True, verbose_name='کد مشتری در حسابداری')
    last_sync_at = models.DateTimeField(auto_now=True, verbose_name='آخرین همگام‌سازی')
    
    def __str__(self):
        return f"{self.customer.user.get_full_name()} - {self.accounting_code}"
    
    class Meta:
        verbose_name = 'نگاشت مشتری حسابداری'
        verbose_name_plural = 'نگاشت‌های مشتری حسابداری'


class AccountingProductMapping(models.Model):
    """نگاشت محصولات بین سیستم ما و سیستم حسابداری"""
    product = models.OneToOneField('products.Product', on_delete=models.CASCADE, related_name='accounting_mapping', verbose_name='محصول')
    accounting_code = models.CharField(max_length=50, unique=True, verbose_name='کد محصول در حسابداری')
    technical_code = models.CharField(max_length=50, blank=True, null=True, verbose_name='شماره فنی')
    last_sync_at = models.DateTimeField(auto_now=True, verbose_name='آخرین همگام‌سازی')
    
    def __str__(self):
        return f"{self.product.name} - {self.accounting_code}"
    
    class Meta:
        verbose_name = 'نگاشت محصول حسابداری'
        verbose_name_plural = 'نگاشت‌های محصول حسابداری'


class AccountingNotification(models.Model):
    """نوتیفیکیشن‌های مربوط به خطاهای حسابداری"""
    
    TYPE_CHOICES = (
        ('payment_failed', 'خطا در ثبت پرداخت'),
        ('invoice_failed', 'خطا در ثبت فاکتور'),
        ('sync_failed', 'خطا در همگام‌سازی'),
    )
    
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='نوع خطا')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    message = models.TextField(verbose_name='پیام')
    related_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='شناسه مرتبط')
    related_model = models.CharField(max_length=100, blank=True, null=True, verbose_name='مدل مرتبط')
    
    is_read = models.BooleanField(default=False, verbose_name='خوانده شده')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ خواندن')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'نوتیفیکیشن حسابداری'
        verbose_name_plural = 'نوتیفیکیشن‌های حسابداری'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.title}"
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


# accounting/models.py - اضافه کردن مدل جدید

class AccountingCounter(models.Model):
    """نگهداری آخرین شماره‌های همگام‌سازی شده با نیکان"""
    
    COUNTER_TYPES = (
        ('customer', 'شماره مشتری'),
        ('product', 'شماره محصول'),
        ('invoice', 'شماره فاکتور'),
        ('payment', 'شماره پرداخت'),
    )
    
    counter_type = models.CharField(max_length=20, choices=COUNTER_TYPES, unique=True, verbose_name='نوع شمارنده')
    last_number = models.PositiveIntegerField(default=0, verbose_name='آخرین شماره')
    last_sync_at = models.DateTimeField(auto_now=True, verbose_name='آخرین همگام‌سازی')
    
    def __str__(self):
        return f"{self.get_counter_type_display()}: {self.last_number}"
    
    class Meta:
        verbose_name = 'شمارنده حسابداری'
        verbose_name_plural = 'شمارنده‌های حسابداری'

# accounting/models.py - اضافه کردن مدل جدید

class SyncQueue(models.Model):
    """صف همگام‌سازی با نیکان"""
    
    QUEUE_TYPES = (
        ('customer', 'مشتری'),
        ('product', 'محصول'),
        ('invoice', 'فاکتور'),
        ('payment', 'پرداخت'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'در انتظار'),
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
    )
    
    queue_type = models.CharField(max_length=20, choices=QUEUE_TYPES, verbose_name='نوع')
    object_id = models.PositiveIntegerField(verbose_name='شناسه شیء')
    data = models.JSONField(default=dict, verbose_name='داده‌های درخواست')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    attempt_count = models.PositiveIntegerField(default=0, verbose_name='تعداد تلاش')
    error_message = models.TextField(blank=True, null=True, verbose_name='پیام خطا')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پردازش')
    
    class Meta:
        verbose_name = 'آیتم صف همگام‌سازی'
        verbose_name_plural = 'آیتم‌های صف همگام‌سازی'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_queue_type_display()} - {self.object_id} - {self.get_status_display()}"
    
    
# accounting/api_client.py - اضافه کردن متد

def sync_counters(self):
    """همگام‌سازی شمارنده‌ها با نیکان"""
    from .models import AccountingCounter
    
    # همگام‌سازی شماره مشتری
    last_customer = self.get_last_customer_code()
    if last_customer:
        counter, _ = AccountingCounter.objects.get_or_create(
            counter_type='customer',
            defaults={'last_number': last_customer}
        )
        counter.last_number = max(counter.last_number, last_customer)
        counter.save()
    
    # همگام‌سازی شماره محصول
    last_product = self.get_last_product_code()
    if last_product:
        counter, _ = AccountingCounter.objects.get_or_create(
            counter_type='product',
            defaults={'last_number': last_product}
        )
        counter.last_number = max(counter.last_number, last_product)
        counter.save()
    
    # همگام‌سازی شماره فاکتور
    last_invoice = self.get_last_invoice_number()
    if last_invoice:
        counter, _ = AccountingCounter.objects.get_or_create(
            counter_type='invoice',
            defaults={'last_number': last_invoice}
        )
        counter.last_number = max(counter.last_number, last_invoice)
        counter.save()
    
    return {
        'success': True,
        'customer': last_customer,
        'product': last_product,
        'invoice': last_invoice
    }

def get_next_customer_code(self):
    """دریافت شماره مشتری بعدی"""
    from .models import AccountingCounter
    counter, _ = AccountingCounter.objects.get_or_create(
        counter_type='customer',
        defaults={'last_number': 0}
    )
    next_number = counter.last_number + 1
    counter.last_number = next_number
    counter.save()
    return next_number

def get_next_product_code(self):
    """دریافت شماره محصول بعدی"""
    from .models import AccountingCounter
    counter, _ = AccountingCounter.objects.get_or_create(
        counter_type='product',
        defaults={'last_number': 0}
    )
    next_number = counter.last_number + 1
    counter.last_number = next_number
    counter.save()
    return next_number

def get_next_invoice_number(self):
    """دریافت شماره فاکتور بعدی"""
    from .models import AccountingCounter
    counter, _ = AccountingCounter.objects.get_or_create(
        counter_type='invoice',
        defaults={'last_number': 0}
    )
    next_number = counter.last_number + 1
    counter.last_number = next_number
    counter.save()
    return next_number

def get_next_payment_number(self):
    """دریافت شماره پرداخت بعدی"""
    from .models import AccountingCounter
    counter, _ = AccountingCounter.objects.get_or_create(
        counter_type='payment',
        defaults={'last_number': 0}
    )
    next_number = counter.last_number + 1
    counter.last_number = next_number
    counter.save()
    return next_number