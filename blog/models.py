# blog/models.py
from django.db import models
from django.utils.text import slugify
from django.urls import reverse

class BlogCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name='نام دسته')
    slug = models.SlugField(unique=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'دسته بلاگ'
        verbose_name_plural = 'دسته‌های بلاگ'

class BlogPost(models.Model):
    title = models.CharField(max_length=200, verbose_name='عنوان')
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(BlogCategory, on_delete=models.CASCADE, related_name='posts', verbose_name='دسته')
    image = models.ImageField(upload_to='blog/', verbose_name='تصویر شاخص')
    summary = models.TextField(max_length=300, verbose_name='خلاصه')
    content = models.TextField(verbose_name='متن کامل')
    author = models.CharField(max_length=100, default='مدیریت', verbose_name='نویسنده')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ انتشار')
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True, verbose_name='منتشر شده')
    view_count = models.PositiveIntegerField(default=0, verbose_name='تعداد بازدید')
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            counter = 1
            while BlogPost.objects.filter(slug=self.slug).exists():
                self.slug = f"{slugify(self.title)}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('blog:detail', args=[self.slug])
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = 'پست بلاگ'
        verbose_name_plural = 'پست‌های بلاگ'
        ordering = ['-created_at']