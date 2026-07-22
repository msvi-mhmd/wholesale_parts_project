from django.db import models

# Create your models here.
# sliders/models.py
from django.db import models
from django.utils.text import slugify
from django.urls import reverse


class Slider(models.Model):
    """مدل اسلایدر برای صفحه اصلی"""
    
    POSITION_CHOICES = (
        ('hero', 'اسلایدر اصلی (هیرو)'),
        ('banner', 'بنر تبلیغاتی'),
    )
    
    title = models.CharField(max_length=200, verbose_name='عنوان اسلایدر')
    subtitle = models.CharField(max_length=300, blank=True, null=True, verbose_name='زیرنویس')
    image = models.ImageField(upload_to='sliders/', verbose_name='تصویر اسلایدر')
    link = models.CharField(max_length=500, blank=True, null=True, verbose_name='لینک دکمه')
    link_text = models.CharField(max_length=100, blank=True, null=True, default='مشاهده', verbose_name='متن دکمه')
    
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='hero', verbose_name='موقعیت')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')
    
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    
    class Meta:
        verbose_name = 'اسلایدر'
        verbose_name_plural = 'اسلایدرها'
        ordering = ['position', 'order', 'created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_position_display()}"
    
    def get_absolute_url(self):
        return self.link or '#'