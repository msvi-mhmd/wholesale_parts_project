# employees/models.py
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator

class EmployeePermission(models.Model):
    """دسترسی‌های کارمندان"""
    PERMISSION_CHOICES = (
        # مدیریت مشتریان
        ('view_customers', 'مشاهده مشتریان'),
        ('add_customers', 'افزودن مشتری'),
        ('edit_customers', 'ویرایش مشتریان'),
        ('delete_customers', 'حذف مشتریان'),
        
        # مدیریت محصولات
        ('view_products', 'مشاهده محصولات'),
        ('add_products', 'افزودن محصول'),
        ('edit_products', 'ویرایش محصولات'),
        ('delete_products', 'حذف محصولات'),
        ('import_products', 'وارد کردن انبوه محصولات'),
        
        # مدیریت فاکتورها
        ('view_invoices', 'مشاهده فاکتورها'),
        ('add_invoices', 'افزودن فاکتور'),
        ('edit_invoices', 'ویرایش فاکتورها'),
        ('delete_invoices', 'حذف فاکتورها'),
        ('confirm_invoices', 'تایید فاکتورها'),
        
        # مدیریت پرداخت‌ها
        ('view_payments', 'مشاهده پرداخت‌ها'),
        ('add_payments', 'افزودن پرداخت'),
        ('edit_payments', 'ویرایش پرداخت‌ها'),
        ('delete_payments', 'حذف پرداخت‌ها'),
        ('confirm_payments', 'تایید پرداخت‌ها'),
        
        # مدیریت کارمندان
        ('view_employees', 'مشاهده کارمندان'),
        ('add_employees', 'افزودن کارمند'),
        ('edit_employees', 'ویرایش کارمندان'),
        ('delete_employees', 'حذف کارمندان'),
        ('manage_permissions', 'مدیریت دسترسی‌ها'),
        
        # گزارشات
        ('view_reports', 'مشاهده گزارشات'),
        ('export_reports', 'خروجی گرفتن از گزارشات'),
        
        # همگام‌سازی قیمت‌ها
        ('sync_prices', 'همگام‌سازی اطلاعات با  سیستم حسابداری'),
        
        # مدیریت برندها و دسته‌بندی
        ('view_brands', 'مشاهده برندها'),
        ('edit_brands', 'ویرایش برندها'),
        ('view_categories', 'مشاهده دسته‌بندی'),
        ('edit_categories', 'ویرایش دسته‌بندی'),
        ('view_cars', 'مشاهده خودروها'),
        ('edit_cars', 'ویرایش خودروها'),
    )
    
    name = models.CharField(max_length=50, choices=PERMISSION_CHOICES, unique=True)
    code = models.CharField(max_length=50, unique=True)
    module = models.CharField(max_length=50, blank=True, null=True, verbose_name='ماژول')
    def __str__(self):
        return self.get_name_display()
    
    class Meta:
        verbose_name = 'دسترسی کارمند'
        verbose_name_plural = 'دسترسی‌های کارمندان'
        ordering = ['module', 'name']

# employees/models.py
class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='employee_profile'
    )
    
    national_id = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name='کد ملی',
        validators=[RegexValidator(r'^\d{10}$', 'کد ملی باید 10 رقم باشد')]
    )
    phone = models.CharField(max_length=11, verbose_name='شماره تلفن')
    position = models.CharField(max_length=100, verbose_name='سمت')
    
    # ===== دسترسی‌های بخش‌ها (ترو/فالس) =====
    access_customers = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت مشتریان')
    access_products = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت محصولات')
    access_invoices = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت فاکتورها')
    access_payments = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت پرداخت‌ها')
    access_employees = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت کارمندان')
    access_reports = models.BooleanField(default=False, verbose_name='دسترسی به گزارشات')
    access_sync = models.BooleanField(default=False, verbose_name='دسترسی به همگام‌سازی قیمت‌ها')
    access_brands_categories = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت برندها و دسته‌بندی')
    access_blog = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت محتوا (بلاگ)')
    access_comments = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت نظرات')
    access_website = models.BooleanField(default=False, verbose_name='دسترسی به مدیریت وبسایت')
    
    # اطلاعات شخصی
    first_name = models.CharField(max_length=100, verbose_name='نام')
    last_name = models.CharField(max_length=100, verbose_name='نام خانوادگی')
    email = models.EmailField(blank=True, verbose_name='ایمیل')
    address = models.TextField(blank=True, verbose_name='آدرس')
    
    # تاریخ
    hired_date = models.DateField(auto_now_add=True, verbose_name='تاریخ استخدام')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.position}"
    
    def get_access_list(self):
        """دریافت لیست دسترسی‌های فعال"""
        access_list = []
        if self.access_customers:
            access_list.append('customers')
        if self.access_products:
            access_list.append('products')
        if self.access_invoices:
            access_list.append('invoices')
        if self.access_payments:
            access_list.append('payments')
        if self.access_employees:
            access_list.append('employees')
        if self.access_reports:
            access_list.append('reports')
        if self.access_sync:
            access_list.append('sync')
        if self.access_brands_categories:
            access_list.append('brands_categories')
        if self.access_blog:
            access_list.append('blog')
        return access_list
    
    class Meta:
        verbose_name = 'کارمند'
        verbose_name_plural = 'کارمندان'