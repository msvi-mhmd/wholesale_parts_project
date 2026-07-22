# wholesale_parts/views.py
from django.shortcuts import render
from django.db.models import Q, F, Sum, Value
from django.db.models.functions import Coalesce
from products.models import Product, MainCategory, ProductBrand
from invoices.models import Invoice
from blog.models import BlogPost
from sliders.models import Slider

def homepage(request):
    # محصولات ویژه (پرفروش‌ترین)
    featured_products = Product.objects.filter(
        is_active=True, 
        is_featured=True
    ).order_by('-sold_number')[:12]
    
    # محصولات تخفیف‌دار
    discounted_products = Product.objects.filter(
        is_active=True,
        off_price__isnull=False,
        off_price__gt=0
    ).order_by('-price')[:12]
    
    # پرفروش‌ترین محصولات
    best_sellers = Product.objects.filter(
        is_active=True
    ).order_by('-sold_number')[:12]
    
    # پرفروش‌ترین برندها
    top_brands = ProductBrand.objects.filter(
        products__is_active=True
    ).annotate(
        total_sold=Coalesce(Sum('products__sold_number'), Value(0))
    ).order_by('-total_sold')[:8]
    
    # نمایش قیمت برای کاربران لاگین شده
    show_price = request.user.is_authenticated
    

    
    try:
        green_brand = ProductBrand.objects.get(name='GISP')
        green_brand_products = Product.objects.filter(
            brand=green_brand,
            is_active=True
        ).order_by('-sold_number')[:12]
    except ProductBrand.DoesNotExist:
        green_brand = ProductBrand.objects.first()
        if green_brand:
            green_brand_products = Product.objects.filter(
                brand=green_brand,
                is_active=True
            ).order_by('-sold_number')[:12]
        else:
            green_brand = None
            green_brand_products = []
    

    try:
        yellow_brand = ProductBrand.objects.get(id=2) 
        yellow_brand_products = Product.objects.filter(
            brand=yellow_brand,
            is_active=True
        ).order_by('-sold_number')[:12]
    except ProductBrand.DoesNotExist:
        second_brand = ProductBrand.objects.all()[1:2].first()
        if second_brand:
            yellow_brand = second_brand
            yellow_brand_products = Product.objects.filter(
                brand=yellow_brand,
                is_active=True
            ).order_by('-sold_number')[:12]
        else:
            yellow_brand = None
            yellow_brand_products = []

    #کتگوری ها
    categories_for_grid = MainCategory.objects.filter(subcategories__isnull=False).distinct()[:4]
    
    #بلاگ ها
    latest_blog_posts = BlogPost.objects.filter(is_published=True).order_by('-created_at')[:5]

    hero_sliders = Slider.objects.filter(
        position='hero', 
        is_active=True
    ).order_by('order')

    context = {
        'featured_products': featured_products,
        'discounted_products': discounted_products,
        'best_sellers': best_sellers,
        'top_brands': top_brands,
        'show_price': show_price,
        'green_brand': green_brand,
        'green_brand_products': green_brand_products,
        'yellow_brand': yellow_brand,
        'yellow_brand_products': yellow_brand_products,
        'categories_for_grid': categories_for_grid,
        'latest_blog_posts': latest_blog_posts,
        'hero_sliders': hero_sliders,
    }
    return render(request, 'landing.html', context)

from django.shortcuts import render
from settings.models import SiteSetting

def about_page(request):
    settings_dict = {}
    for setting in SiteSetting.objects.filter(setting_type='about'):
        if setting.image:
            settings_dict[setting.key] = setting.image.url
        else:
            settings_dict[setting.key] = setting.value or ''

    team_members = []
    for i in range(1, 4):
        name = SiteSetting.objects.filter(key=f'about_team{i}_name').first()
        position = SiteSetting.objects.filter(key=f'about_team{i}_position').first()
        image = SiteSetting.objects.filter(key=f'about_team{i}_image').first()
        team_members.append({
            'name': name.value if name else '',
            'position': position.value if position else '',
            'image': image.image.url if image and image.image else None,
        })

    context = {
        'settings': settings_dict,
        'team_members': team_members,
    }
    return render(request, 'about.html', context)


def terms_and_conditions(request):
    """صفحه قوانین و مقررات"""
    return render(request, 'terms_and_conditions.html')

def registration_guide(request):
    """صفحه شرایط ثبت نام و آموزش ثبت درخواست ثبت نام"""
    return render(request, 'registration_guide.html')

def history(request):
    """صفحه تاریخچه شرکت"""
    return render(request, 'history.html')

def support(request):
    """صفحه پشتیبانی"""
    return render(request, 'support.html')


# wholesale_parts/views.py
def faq(request):
    """صفحه سوالات متداول"""
    faqs = [
        {
            'question': 'چگونه می‌توانم در سایت ثبت‌نام کنم؟',
            'answer': 'برای ثبت‌نام در سایت، به صفحه "درخواست ثبت‌نام" مراجعه کنید و فرم را پر کنید. پس از بررسی اطلاعات توسط کارشناسان، حساب کاربری شما فعال خواهد شد.'
        },
        {
            'question': 'آیا خرید از سایت فقط برای مغازه‌داران است؟',
            'answer': 'بله، این سایت مخصوص فروش عمده لوازم یدکی به مغازه‌داران، تعمیرکاران و کسب‌وکارهای مرتبط با صنعت خودرو طراحی شده است.'
        },
        {
            'question': 'چگونه می‌توانم اعتبار خود را افزایش دهم؟',
            'answer': 'برای افزایش اعتبار، به بخش "تاریخچه پرداخت‌ها" در پنل کاربری خود بروید و با استفاده از روش‌های پرداخت موجود، درخواست افزایش اعتبار ثبت کنید.'
        },
        {
            'question': 'حداکثر اعتبار من چقدر است؟',
            'answer': 'حداکثر اعتبار شما توسط ادمین تعیین می‌شود و می‌توانید در پنل کاربری خود آن را مشاهده کنید.'
        },
        {
            'question': 'چگونه می‌توانم سفارش خود را ثبت کنم؟',
            'answer': 'پس از ورود به حساب کاربری، محصولات مورد نظر را به سبد خرید اضافه کنید و سپس با تکمیل فرآیند تسویه حساب، سفارش خود را ثبت کنید.'
        },
        {
            'question': 'مدت زمان تایید فاکتور چقدر است؟',
            'answer': 'فاکتورهای ثبت شده در اسرع وقت و حداکثر ظرف ۲۴ ساعت کاری توسط کارشناسان بررسی و تأیید می‌شوند.'
        },
        {
            'question': 'آیا امکان مرجوع کردن کالا وجود دارد؟',
            'answer': 'در صورت وجود مشکل در کالا، لطفاً با پشتیبانی تماس بگیرید. کارشناسان ما راهنمایی لازم را ارائه خواهند داد.'
        },
        {
            'question': 'هزینه ارسال چگونه محاسبه می‌شود؟',
            'answer': 'هزینه ارسال بر اساس وزن و حجم کالا و همچنین مقصد محاسبه می‌شود. هزینه دقیق پس از ثبت سفارش به شما اعلام خواهد شد.'
        },
        {
            'question': 'چگونه می‌توانم کد معرف دریافت کنم؟',
            'answer': 'کد معرف شما پس از ثبت‌نام و فعال‌سازی حساب کاربری، در پنل کاربری شما نمایش داده می‌شود.'
        },
        {
            'question': 'امتیازهای باشگاه مشتریان چگونه محاسبه می‌شود؟',
            'answer': 'به ازای هر ۱۰۰۰ تومان خرید، ۱ امتیاز به حساب شما اضافه می‌شود. امتیازها را می‌توانید برای دریافت تخفیف و جوایز استفاده کنید.'
        },
    ]
    
    context = {
        'faqs': faqs,
    }
    return render(request, 'faq.html', context)

