# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone


class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'مدیر ارشد'),
        ('employee', 'کارمند'),
        ('customer', 'مشتری'),
        ('pending', 'در انتظار تایید'),
    )
    
    phone_regex = RegexValidator(
        regex=r'^09\d{9}$',
        message='شماره تلفن باید با 09 شروع شود و 11 رقم باشد'
    )
    
    national_id = models.CharField(
        max_length=10, 
        unique=True, 
        null=True,
        blank=True,
        verbose_name='کد ملی',
        validators=[RegexValidator(r'^\d{10}$', 'کد ملی باید 10 رقم باشد')]
    )
    phone = models.CharField(
        validators=[phone_regex], 
        max_length=11, 
        unique=True, 
        verbose_name='شماره تلفن'
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='pending',verbose_name='نوع کاربر')
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=200, blank=True)
    
    # برای سیستم معرف
    invited_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='invitations')
    invitation_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.invitation_code:
            import uuid
            self.invitation_code = str(uuid.uuid4())[:8]
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.national_id}"
    
    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'


# accounts/models.py
class RegistrationRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'در انتظار بررسی'),
        ('viewed', 'مشاهده شده'),
    )
    
    # اطلاعات شخصی
    national_id = models.CharField(
        max_length=10,
        validators=[RegexValidator(r'^\d{10}$', 'کد ملی باید 10 رقم باشد')],
        verbose_name='کد ملی'
    )
    first_name = models.CharField(max_length=100, verbose_name='نام')
    last_name = models.CharField(max_length=100, verbose_name='نام خانوادگی')
    phone = models.CharField(
        max_length=11,
        validators=[RegexValidator(r'^09\d{9}$', 'شماره تلفن باید با 09 شروع شود')],
        verbose_name='شماره تلفن'
    )
    email = models.EmailField(blank=True, null=True, verbose_name='ایمیل')
    city = models.CharField(max_length=100, blank=True, verbose_name='شهر')
    street = models.CharField(max_length=200, blank=True, verbose_name='خیابان')
    address = models.TextField(blank=True, verbose_name='آدرس دقیق')
    
    # کد معرف
    invitation_code = models.CharField(max_length=20, blank=True, null=True, verbose_name='کد معرف')
    
    # وضعیت
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    is_viewed = models.BooleanField(default=False, verbose_name='مشاهده شده')
    
    # تاریخ
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت درخواست')
    viewed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ مشاهده')
    
    # یادداشت
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.national_id}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def mark_as_viewed(self):
        """علامت‌گذاری به عنوان مشاهده شده"""
        if not self.is_viewed:
            self.is_viewed = True
            self.viewed_at = timezone.now()
            self.status = 'viewed'
            self.save()
    
    class Meta:
        verbose_name = 'درخواست ثبت‌نام'
        verbose_name_plural = 'درخواست‌های ثبت‌نام'
        ordering = ['-created_at']