# products/models.py
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone

class CarBrand(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='نام برند خودرو')
    country = models.CharField(max_length=100, verbose_name='کشور سازنده')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'برند خودرو'
        verbose_name_plural = 'برندهای خودرو'

class Car(models.Model):
    car_brand = models.ForeignKey(CarBrand, on_delete=models.CASCADE, related_name='cars', verbose_name='برند خودرو')
    name = models.CharField(max_length=100, verbose_name='نام خودرو')
    model = models.CharField(max_length=20, verbose_name='سال تولید', blank=True)
    
    def __str__(self):
        if self.model and self.model.strip():
            return f"{self.car_brand.name} {self.name} ({self.model})"
        else:
            # اگر سال تولید وارد نشده بود، فقط نام و برند رو نمایش بده
            return f"{self.car_brand.name} {self.name}"

    class Meta:
        verbose_name = 'خودرو'
        verbose_name_plural = 'خودروها'
        unique_together = ['car_brand', 'name', 'model']

class MainCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='نام دسته اصلی')
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name='تصویر دسته‌بندی')
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'دسته اصلی'
        verbose_name_plural = 'دسته‌های اصلی'

class SubCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='نام زیردسته')
    slug = models.SlugField(unique=True, blank=True)
    main_category = models.ForeignKey(MainCategory, on_delete=models.CASCADE, related_name='subcategories', verbose_name='دسته اصلی')
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.main_category.name} - {self.name}"
    
    class Meta:
        verbose_name = 'زیردسته'
        verbose_name_plural = 'زیردسته‌ها'

class ProductBrand(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='نام برند')
    slug = models.SlugField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, verbose_name='تلفن')
    country = models.CharField(max_length=100, verbose_name='کشور')
    city = models.CharField(max_length=100, verbose_name='شهر')
    street = models.CharField(max_length=200, blank=True, verbose_name='آدرس')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    logo = models.ImageField(upload_to='brands/', blank=True, null=True, verbose_name='لوگو')
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            counter = 1
            while Product.objects.filter(slug=self.slug).exists():
                self.slug = f"{slugify(self.name)}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'برند محصول'
        verbose_name_plural = 'برندهای محصول'

class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='نام محصول')
    slug = models.SlugField(unique=True, blank=False, null=True)
    
    # شماره‌های محصول
    product_code = models.CharField(
        max_length=20, 
        unique=True, 
        null=True, 
        blank=True, 
        verbose_name='کد محصول (نیکان)'
    )

    alt_code = models.CharField(max_length=20, null=True, blank=True, verbose_name='شماره جایگزین')

    # دسته‌بندی
    main_category = models.ForeignKey(MainCategory, on_delete=models.CASCADE, related_name='products', verbose_name='دسته اصلی')
    sub_category = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='products', verbose_name='زیردسته')
    
    # قیمت
    price = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='قیمت (ریال)')
    off_price = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='قیمت تخفیف‌خورده')
    
    # موجودی
    left_in_stock = models.PositiveIntegerField(default=0, verbose_name='موجودی انبار')
    
    # ویژگی‌ها
    brand = models.ForeignKey(ProductBrand, on_delete=models.CASCADE, related_name='products', verbose_name='برند')
    suitable_car = models.ManyToManyField(Car, related_name='products', blank=True, verbose_name='خودروی مناسب')
    specialty = models.CharField(max_length=200, blank=True, verbose_name='تخصص/نوع')
    
    # امتیاز محصول
    point_of_buy = models.PositiveIntegerField(default=0, verbose_name='امتیاز خرید محصول')
    
    # آمار
    sold_number = models.PositiveIntegerField(default=0, verbose_name='تعداد فروش رفته')
    view_count = models.PositiveIntegerField(default=0, verbose_name='تعداد بازدید')
    
    # توضیحات
    short_description = models.TextField(max_length=500, blank=True, verbose_name='توضیح مختصر')
    full_description = models.TextField(blank=True, verbose_name='توضیحات کامل')
    
    # تاریخ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # وضعیت
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    is_featured = models.BooleanField(default=False, verbose_name='محصول ویژه')
    
    def save(self, *args, **kwargs):
        # ایجاد خودکار product_code اگر خالی باشد
        if not self.product_code:
            from accounting.api_client import AccountingAPIClient
            api_client = AccountingAPIClient()
            api_client.sync_counters()
            next_code = api_client.get_next_product_code()
            self.product_code = str(next_code).zfill(6)
        
        # ایجاد slug
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            self.slug = base_slug
            counter = 1
            while Product.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)
    
    @property
    def final_price(self):
        """قیمت نهایی بعد از تخفیف"""
        if self.off_price and self.off_price > 0:
            return self.off_price
        return self.price
    
    @property
    def discount_percent(self):
        """درصد تخفیف"""
        if self.off_price and self.off_price > 0:
            return int((1 - self.off_price / self.price) * 100)
        return 0
    
    @property
    def is_in_stock(self):
        return self.left_in_stock > 0
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('products:product_detail', args=[self.slug])
    
    @classmethod
    def search_products(cls, query):
        """جستجوی محصولات با نام‌های اصلی و جایگزین"""
        from django.db.models import Q
        
        # جستجو در نام اصلی و برند
        products = cls.objects.filter(
            Q(name__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(specialty__icontains=query)
        )
        
        # جستجو در نام‌های جایگزین
        alias_products = cls.objects.filter(
            aliases__name__icontains=query
        ).distinct()
        
        # ترکیب نتایج
        return (products | alias_products).distinct()
    
    def get_thumb_url(self):
        """دریافت URL تصویر کوچک محصول"""
        first_image = self.images.first()
        if first_image and first_image.thumb:
            return first_image.thumb.url
        elif first_image and first_image.image:
            return first_image.image.url
        return '/static/images/no-image.png'
    
    def get_main_image_url(self):
        """دریافت URL تصویر اصلی محصول"""
        first_image = self.images.filter(is_main=True).first() or self.images.first()
        if first_image and first_image.image:
            return first_image.image.url
        return '/static/images/no-image.png'

    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'
        ordering = ['-sold_number', '-created_at']



class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name='محصول')
    image = models.ImageField(upload_to='products/', verbose_name='تصویر')
    thumb = models.ImageField(upload_to='products/thumbs/', blank=True, null=True, verbose_name='تصویر کوچک')
    is_main = models.BooleanField(default=False, verbose_name='تصویر اصلی')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')
    
    def save(self, *args, **kwargs):
        if self.is_main:
            ProductImage.objects.filter(product=self.product, is_main=True).update(is_main=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"تصویر {self.product.name}"
    
    class Meta:
        verbose_name = 'تصویر محصول'
        verbose_name_plural = 'تصاویر محصولات'
        ordering = ['order', '-is_main']


class ProductAlias(models.Model):
    """نام‌های جایگزین برای محصول (برای جستجو)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='aliases', verbose_name='محصول')
    name = models.CharField(max_length=200, verbose_name='نام جایگزین')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.product.name} -> {self.name}"
    
    class Meta:
        verbose_name = 'نام جایگزین محصول'
        verbose_name_plural = 'نام‌های جایگزین محصولات'
        unique_together = ['product', 'name']  # جلوگیری از تکرار



# products/models.py
class ProductComment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'در انتظار تایید'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments', verbose_name='محصول')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='product_comments', verbose_name='کاربر')
    
    title = models.CharField(max_length=200, blank=True, null=True, verbose_name='عنوان')
    comment = models.TextField(verbose_name='متن نظر')
    rating = models.PositiveSmallIntegerField(default=5, choices=[(i, i) for i in range(1, 6)], verbose_name='امتیاز')
    
    # وضعیت
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    
    # تاریخ
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ ویرایش')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بررسی')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_comments',
        verbose_name='بررسی کننده'
    )
    
    # پاسخ به کامنت
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name='پاسخ به')
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.product.name}"
    
    def approve(self, reviewer):
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.save()
    
    def reject(self, reviewer):
        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.save()
    
    class Meta:
        verbose_name = 'نظر محصول'
        verbose_name_plural = 'نظرات محصولات'
        ordering = ['-created_at']