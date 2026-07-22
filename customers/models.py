from django.db import models
from django.conf import settings
from decimal import Decimal


class CustomerLevel(models.Model):
    name = models.CharField(max_length=50, verbose_name='نام سطح')
    min_credit = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='حداقل اعتبار مورد نیاز')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='درصد تخفیف')
    priority = models.PositiveIntegerField(default=0, verbose_name='اولویت')
    
    def __str__(self):
        return f"{self.name} ({self.discount_percent}% تخفیف)"
    
    class Meta:
        verbose_name = 'سطح مشتری'
        verbose_name_plural = 'سطوح مشتریان'
        ordering = ['priority']


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='customer_profile'
    )
    
    # ===== شماره داخلی سایت =====
    customer_code = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True, 
        null=True,
        verbose_name='کد مشتری (سایت)'
    )
    
    # ===== شماره در نیکان =====
    nikan_customer_code = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True, 
        null=True,
        verbose_name='کد مشتری (نیکان)'
    )
    
    # ===== وضعیت همگام‌سازی با نیکان =====
    SYNC_STATUS_CHOICES = (
        ('pending', 'در انتظار همگام‌سازی'),
        ('synced', 'همگام‌سازی شده'),
        ('failed', 'همگام‌سازی ناموفق'),
    )
    
    nikan_sync_status = models.CharField(
        max_length=20, 
        choices=SYNC_STATUS_CHOICES, 
        default='pending',
        verbose_name='وضعیت همگام‌سازی با نیکان'
    )
    nikan_sync_attempts = models.PositiveIntegerField(default=0, verbose_name='تعداد تلاش‌ها')
    nikan_sync_error = models.TextField(blank=True, null=True, verbose_name='خطای همگام‌سازی')
    nikan_sync_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ همگام‌سازی')
    
    # ===== اعتبار =====
    max_credit = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='اعتبار حداکثر')
    credit = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='اعتبار فعلی')
    
    # ===== سطح مشتری =====
    customer_level = models.ForeignKey(
        'CustomerLevel', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='customers',
        verbose_name='سطح مشتری'
    )
    
    # ===== بدهی قبل از ۱۴۰۴/۰۲ =====
    debt_before_1404_02 = models.DecimalField(
        max_digits=15, 
        decimal_places=0, 
        default=0,
        verbose_name='بدهی قبل از ۱۴۰۴/۰۲'
    )
    
    # ===== امتیازات =====
    total_points = models.PositiveIntegerField(default=0, verbose_name='امتیاز کل')
    used_points = models.PositiveIntegerField(default=0, verbose_name='امتیاز استفاده شده')
    
    # ===== آمار =====
    total_purchases = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='کل خرید')
    total_payments = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='کل پرداخت‌ها')
    
    # ===== دعوت شدگان =====
    invitations_count = models.PositiveIntegerField(default=0, verbose_name='تعداد دعوت‌شدگان')
    
    # ===== تاریخ =====
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ================================================================
    # PROPERTIES
    # ================================================================
    
    @property
    def debt(self):
        """
        بدهی جاری = (کل فاکتورهای تایید شده + بدهی قبل از ۱۴۰۴/۰۲) - کل پرداخت‌های تایید شده
        اگر مثبت شد = بدهی
        """
        from invoices.models import Invoice
        from payments.models import Payment
        from django.db.models import Sum
        
        total_invoices = Invoice.objects.filter(
            customer=self,
            status__code='CONFIRMED'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        total_payments = Payment.objects.filter(
            customer=self,
            is_confirmed=True,
            status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total = total_invoices + self.debt_before_1404_02 - total_payments
        
        return max(Decimal('0'), total)
    
    @property
    def receivable(self):
        """
        بستانکاری = کل پرداخت‌ها - (کل فاکتورها + بدهی قبل از ۱۴۰۴/۰۲)
        اگر مثبت شد = بستانکاری
        """
        from invoices.models import Invoice
        from payments.models import Payment
        from django.db.models import Sum
        
        total_invoices = Invoice.objects.filter(
            customer=self,
            status__code='CONFIRMED'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        total_payments = Payment.objects.filter(
            customer=self,
            is_confirmed=True,
            status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total = total_payments - (total_invoices + self.debt_before_1404_02)
        
        return max(Decimal('0'), total)
    
    @property
    def available_credit(self):
        """اعتبار باقی مانده قابل سفارش = max_credit - بدهی"""
        return max(Decimal('0'), self.max_credit - self.debt)
    
    @property
    def total_invoices_amount(self):
        """مجموع کل سفارشات تایید شده"""
        from invoices.models import Invoice
        from django.db.models import Sum
        return Invoice.objects.filter(
            customer=self,
            status__code='CONFIRMED'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    @property
    def total_payments_amount(self):
        """مجموع کل پرداخت‌های تایید شده"""
        from payments.models import Payment
        from django.db.models import Sum
        return Payment.objects.filter(
            customer=self,
            is_confirmed=True,
            status='confirmed'
        ).exclude(
            payment_category='debt'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    @property
    def total_available(self):
        """مجموع موجودی قابل استفاده = اعتبار فعلی"""
        return self.credit
    
    @property
    def available_points(self):
        """امتیاز قابل استفاده"""
        return self.total_points - self.used_points


    def can_purchase(self, amount):
        """بررسی توان خرید = اعتبار باقی مانده >= مبلغ سفارش"""
        return self.available_credit >= amount
    
    def deduct_from_account(self, amount):
        """کسر از اعتبار بعد از تایید سفارش"""
        if amount > self.available_credit:
            return False
        
        self.credit -= amount
        self.save()
        return True
    
    def add_to_credit(self, amount):
        """افزایش اعتبار (بعد از تایید پرداخت)"""
        self.credit += amount
        self.save()
        return True
    
    def add_to_account(self, amount):
        """افزایش اعتبار مشتری"""
        from decimal import Decimal
        self.credit += Decimal(str(amount))
        self.save()
        return True
    
    def save(self, *args, **kwargs):
        if not self.customer_code:
            import random
            self.customer_code = f"CUS-{str(random.randint(10000, 99999))}"
        
        if not self.nikan_customer_code and self.nikan_sync_status != 'synced':
            self.nikan_sync_status = 'pending'
        
        super().save(*args, **kwargs)
    
    @property
    def is_synced_with_nikan(self):
        return self.nikan_sync_status == 'synced'
    
    def update_level(self):
        levels = CustomerLevel.objects.filter(min_credit__lte=self.total_purchases).order_by('-priority')
        if levels.exists():
            self.customer_level = levels.first()
        else:
            self.customer_level = None
        self.save()
    
    def add_points(self, points):
        self.total_points += points
        self.save()
    
    def use_points(self, points):
        if self.available_points >= points:
            self.used_points += points
            self.save()
            return True
        return False
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.user.phone}"
    
    class Meta:
        verbose_name = 'مشتری'
        verbose_name_plural = 'مشتریان'


class CustomerPointHistory(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='point_history')
    points = models.IntegerField(verbose_name='تعداد امتیاز')
    reason = models.CharField(max_length=200, verbose_name='دلیل')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.customer} - {self.points} امتیاز"
    
    class Meta:
        verbose_name = 'تاریخچه امتیاز'
        verbose_name_plural = 'تاریخچه امتیازات'
        ordering = ['-created_at']