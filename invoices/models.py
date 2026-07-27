# invoices/models.py
from django.db import models
from django.conf import settings
from decimal import Decimal
from django.utils import timezone

class InvoiceStatus(models.Model):
    """وضعیت‌های فاکتور"""
    name = models.CharField(max_length=50, unique=True, verbose_name='نام وضعیت')
    code = models.CharField(max_length=20, unique=True, verbose_name='کد وضعیت')
    is_final = models.BooleanField(default=False, verbose_name='وضعیت نهایی')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'وضعیت فاکتور'
        verbose_name_plural = 'وضعیت‌های فاکتور'


class Invoice(models.Model):
    
    STATUS_CHOICES = [
        ('PENDING', 'در انتظار تایید'),
        ('CONFIRMED', 'تایید شده'),
        ('REJECTED', 'رد شده'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'پرداخت نشده'),
        ('paid', 'پرداخت شده'),
        ('partial', 'جزئی'),
    ]

    invoice_id = models.CharField(max_length=50, unique=True, editable=False)
    accounting_invoice_id = models.CharField(max_length=50, blank=True, null=True, verbose_name='شماره فاکتور در حسابداری')
    sent_to_accounting = models.BooleanField(default=False)
    sent_to_accounting_at = models.DateTimeField(null=True, blank=True)

    status = models.ForeignKey('InvoiceStatus', on_delete=models.PROTECT)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    manual_discount = models.DecimalField(
        max_digits=15, 
        decimal_places=0, 
        default=0,
        verbose_name='تخفیف دستی (ادمین)'
    )

    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='invoices', verbose_name='مشتری')
    
    # محتوای فاکتور
    items = models.JSONField(default=dict, verbose_name='اقلام فاکتور')
    
    # مبالغ
    subtotal = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='جمع کل')
    discount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='تخفیف')
    total = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='مبلغ نهایی')

    
    # ارسال به سیستم حسابداری
    accounting_invoice_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name='شماره فاکتور در سیستم حسابداری'
    )
    sent_to_accounting = models.BooleanField(
        default=False, 
        verbose_name='ارسال به سیستم حسابداری'
    )
    sent_to_accounting_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='تاریخ ارسال به سیستم حسابداری'
    )
    
    # فیلدهای مربوط به پرداخت
    payment_attempts = models.IntegerField(default=0, verbose_name='تعداد تلاش‌های پرداخت')
    last_payment_attempt = models.DateTimeField(null=True, blank=True, verbose_name='آخرین تلاش برای پرداخت')
    payment_notes = models.TextField(blank=True, verbose_name='یادداشت‌های پرداخت')
    
    # تاریخ
    date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ ثبت')
    
    confirmed_date = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تایید')
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='confirmed_invoices',
        verbose_name='تاییدکننده'
    )
    
    # یادداشت
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    
    def save(self, *args, **kwargs):
        # ===== اگر invoice_id خالی بود =====
        if not self.invoice_id or self.invoice_id == '':
            
            # ===== فاکتور از نیکان آمده =====
            if self.accounting_invoice_id:
                self.invoice_id = f"INV-{self.accounting_invoice_id.zfill(8)}"
            else:
                # ===== فاکتور جدید (سایت) =====
                import time
                self.invoice_id = f"INV-{str(int(time.time() * 1000))[-8:]}"
        
        super().save(*args, **kwargs)
    

    def calculate_total_points(self):
        """محاسبه امتیاز کل فاکتور از آیتم‌ها"""
        total = 0
        for item in self.invoice_items.all():
            total += item.points_earned
        return total

    @property
    def is_paid(self):
        """آیا فاکتور پرداخت شده است؟"""
        return self.payment_status == 'paid'
    
    @property
    def is_sent_to_accounting(self):
        return self.sent_to_accounting
    
    
    def mark_as_paid(self):
        """علامت‌گذاری فاکتور به عنوان پرداخت شده"""
        self.payment_status = 'paid'
        self.save()
    
    def __str__(self):
        return f"{self.invoice_id} - {self.customer.user.get_full_name()}"
    
    class Meta:
        verbose_name = 'فاکتور'
        verbose_name_plural = 'فاکتورها'
        ordering = ['-date']



class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='invoice_items', 
        verbose_name='فاکتور'
    )
    
    product_code = models.CharField(max_length=50,default = '0', verbose_name='کد محصول در نیکان')
    
    quantity = models.PositiveIntegerField(default=1, verbose_name='تعداد')
    price = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='قیمت واحد')
    points_earned = models.PositiveIntegerField(default=0, verbose_name='امتیاز کسب شده')
    
    def get_product(self):
        """دریافت محصول با کد محصول"""
        from products.models import Product
        from accounting.models import AccountingProductMapping
        
        # ۱. جستجو در نگاشت
        mapping = AccountingProductMapping.objects.filter(accounting_code=self.product_code).first()
        if mapping:
            return mapping.product
        
        # ۲. جستجو در خود محصول
        product = Product.objects.filter(product_code=self.product_code).first()
        if product:
            return product
        
        return None
    
    def __str__(self):
        product = self.get_product()
        if product:
            return f"{product.name} x {self.quantity}"
        return f"{self.product_code} x {self.quantity}"
    
    class Meta:
        verbose_name = 'آیتم فاکتور'
        verbose_name_plural = 'آیتم‌های فاکتور'