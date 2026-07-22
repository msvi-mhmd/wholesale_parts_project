
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator

class TicketCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name='نام دسته‌بندی')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'دسته‌بندی تیکت'
        verbose_name_plural = 'دسته‌بندی‌های تیکت'
        ordering = ['order', 'name']

class Ticket(models.Model):
    STATUS_CHOICES = (
        ('open', 'باز'),
        ('in_progress', 'در حال بررسی'),
        ('answered', 'پاسخ داده شده'),
        ('closed', 'بسته شده'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'کم'),
        ('normal', 'معمولی'),
        ('high', 'بالا'),
        ('urgent', 'فوری'),
    )
    
    ticket_id = models.CharField(max_length=20, unique=True, verbose_name='شماره تیکت')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tickets', verbose_name='کاربر')
    category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='دسته‌بندی')
    
    title = models.CharField(max_length=200, verbose_name='عنوان')
    message = models.TextField(verbose_name='پیام')
    attachment = models.FileField(upload_to='tickets/', blank=True, null=True, verbose_name='پیوست')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name='وضعیت')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal', verbose_name='اولویت')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بسته شدن')
    answered_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پاسخ')
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_tickets',
        verbose_name='اختصاص یافته به'
    )
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            import uuid
            self.ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.ticket_id} - {self.title}"
    
    class Meta:
        verbose_name = 'تیکت'
        verbose_name_plural = 'تیکت‌ها'
        ordering = ['-created_at']

class TicketReply(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='replies', verbose_name='تیکت')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ticket_replies', verbose_name='کاربر')
    message = models.TextField(verbose_name='پیام')
    attachment = models.FileField(upload_to='tickets/replies/', blank=True, null=True, verbose_name='پیوست')
    is_internal = models.BooleanField(default=False, verbose_name='داخلی (فقط برای پشتیبانی)')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ارسال')
    
    def __str__(self):
        return f"{self.ticket.ticket_id} - {self.user.username} - {self.created_at.strftime('%Y/%m/%d %H:%M')}"
    
    class Meta:
        verbose_name = 'پاسخ تیکت'
        verbose_name_plural = 'پاسخ‌های تیکت'
        ordering = ['created_at']