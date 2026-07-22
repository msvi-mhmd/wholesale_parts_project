# products/views.py
from django.shortcuts import render, get_object_or_404, redirect 
from django.http import JsonResponse
from django.db.models import Q, F, Case, When, Value, IntegerField, Avg
from django.core.paginator import Paginator
from .models import Product, MainCategory, SubCategory, ProductBrand, Car, ProductComment
from .utils import extract_words, rank_products_by_relevance, calculate_similarity_score
from .forms import ProductCommentForm  
from django.contrib import messages

# products/views.py
def product_list(request , slug=None):
    products = Product.objects.filter(is_active=True)
    
    # فیلترهای جستجو
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '')
    brand_slug = request.GET.get('brand', '')
    car_id = request.GET.get('car', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    in_stock = request.GET.get('in_stock', '')
    sort = request.GET.get('sort', '-created_at')
    
    # ========== جستجوی هوشمند ==========
    if query:
        query_words = extract_words(query)
        
        if query_words:
            search_conditions = Q()
            for word in query_words:
                search_conditions |= Q(name__icontains=word)
                search_conditions |= Q(aliases__name__icontains=word)
            
            # جستجوی عبارت کامل
            search_conditions |= Q(name__icontains=query)
            search_conditions |= Q(aliases__name__icontains=query)
            
            products = products.filter(search_conditions).distinct()
        
        # مرتب‌سازی هوشمند بر اساس شباهت
        products = rank_products_by_relevance(products, query)
        
        # تبدیل به QuerySet برای صفحه‌بندی
        product_ids = [p.id for p in products]
        if product_ids:
            preserved = Case(*[When(id=id, then=Value(pos)) for pos, id in enumerate(product_ids)])
            products = Product.objects.filter(id__in=product_ids).order_by(preserved)
        else:
            products = Product.objects.none()
    
    # ========== فیلترهای دیگر ==========
    if slug:
        category_slug = slug
        
    if category_slug:
        main_cat = MainCategory.objects.filter(slug=category_slug).first()
        if main_cat:
            products = products.filter(main_category=main_cat)
        else:
            sub_cat = SubCategory.objects.filter(slug=category_slug).first()
            if sub_cat:
                products = products.filter(sub_category=sub_cat)    
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)
    
    if car_id:
        products = products.filter(suitable_car__id=car_id)
    
    if min_price:
        products = products.filter(price__gte=min_price)
    
    if max_price:
        products = products.filter(price__lte=max_price)
    
    if in_stock == 'true':
        products = products.filter(left_in_stock__gt=0)
    
    # مرتب‌سازی معمولی (اگر جستجو نبوده باشد)
    if not query:
        valid_sorts = ['price', '-price', 'name', '-name', '-sold_number', '-created_at', '-view_count']
        if sort in valid_sorts:
            products = products.order_by(sort)
        else:
            products = products.order_by('-created_at')
    
    # ===== تفکیک محصولات موجود و ناموجود =====
    # محصولات موجود
    in_stock_products = products.filter(left_in_stock__gt=0)
    # محصولات ناموجود
    out_of_stock_products = products.filter(left_in_stock=0)
    
    # ترکیب: اول موجود، بعد ناموجود
    combined_products = list(in_stock_products) + list(out_of_stock_products)

    # صفحه‌بندی
    paginator = Paginator(combined_products, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # فیلترهای جانبی
    categories = MainCategory.objects.filter(subcategories__products__is_active=True).distinct()
    brands = ProductBrand.objects.filter(products__is_active=True).distinct()
    cars = Car.objects.filter(products__is_active=True).distinct()
    
    show_price = request.user.is_authenticated
    
    context = {
        'products': page_obj,
        'categories': categories,
        'brands': brands,
        'cars': cars,
        'query': query,
        'sort': sort,
        'show_price': show_price,
        'all_categories': categories,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    # اطمینان از اینکه قیمت عدد است
    if hasattr(product.price, 'value'):
        product.price = product.price.value
        if product.off_price:
            product.off_price = product.off_price.value
    else:
        # اگر رشته بود، کاماها رو حذف کن
        if isinstance(product.price, str):
            product.price = int(product.price.replace(',', ''))
        if product.off_price and isinstance(product.off_price, str):
            product.off_price = int(product.off_price.replace(',', ''))


    # افزایش بازدید
    product.view_count = F('view_count') + 1
    product.save(update_fields=['view_count'])
    
    # محصولات مشابه
    similar_products = Product.objects.filter(
        Q(sub_category=product.sub_category) | 
        Q(brand=product.brand)
    ).exclude(
        id=product.id
    ).filter(
        is_active=True
    ).distinct()[:10]
    
    # نمایش قیمت فقط برای کاربران لاگین شده
    show_price = request.user.is_authenticated
    
    context = {
        'product': product,
        'similar_products': similar_products,
        'show_price': show_price,
    }
    return render(request, 'products/product_detail.html', context)


def brand_list(request):
    """صفحه لیست همه برندها"""
    brands = ProductBrand.objects.filter(products__is_active=True).distinct()
    
    context = {
        'brands': brands,
    }
    return render(request, 'products/brand_list.html', context)

# products/views.py - اضافه کردن این تابع

def brand_products(request, slug):
    """نمایش محصولات یک برند خاص"""
    from .models import ProductBrand
    brand = get_object_or_404(ProductBrand, slug=slug)
    products = Product.objects.filter(brand=brand, is_active=True)
    
    show_price = request.user.is_authenticated
    
    context = {
        'brand': brand,
        'products': products,
        'show_price': show_price,
    }
    return render(request, 'products/brand_products.html', context)

# products/views.py
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # افزایش بازدید
    product.view_count = F('view_count') + 1
    product.save(update_fields=['view_count'])
    
    # محصولات مشابه بر اساس دسته و برند
    similar_products = Product.objects.filter(
        Q(sub_category=product.sub_category) | 
        Q(brand=product.brand)
    ).exclude(
        id=product.id
    ).filter(
        is_active=True
    ).distinct()[:10]
    
    # نمایش قیمت فقط برای کاربران لاگین شده
    show_price = request.user.is_authenticated
     # ===== کامنت‌ها =====
    # دریافت کامنت‌های تایید شده
    comments = ProductComment.objects.filter(
        product=product,
        status='approved',
        parent__isnull=True
    ).order_by('-created_at')
    
    # محاسبه میانگین امتیازات
    avg_rating = ProductComment.objects.filter(
        product=product,
        status='approved'
    ).aggregate(avg=Avg('rating'))['avg'] or 0
    
    # تعداد کامنت‌ها
    comments_count = comments.count()
    
    # فرم کامنت
    comment_form = ProductCommentForm()
    
    # پردازش فرم
    if request.method == 'POST' and 'submit_comment' in request.POST:
        if not request.user.is_authenticated:
            messages.error(request, 'برای ثبت نظر ابتدا وارد حساب کاربری خود شوید')
            return redirect('accounts:login')
        
        if request.user.user_type != 'customer':
            messages.error(request, 'فقط مشتریان می‌توانند نظر ثبت کنند')
            return redirect('products:product_detail', slug=product.slug)
        
        form = ProductCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.product = product
            comment.user = request.user
            comment.status = 'pending'  # نیاز به تایید
            comment.save()
            
            messages.success(request, 'نظر شما با موفقیت ثبت شد و پس از تایید نمایش داده می‌شود.')
            return redirect('products:product_detail', slug=product.slug)
    
    # پردازش پاسخ به کامنت
    if request.method == 'POST' and 'submit_reply' in request.POST:
        if not request.user.is_authenticated or request.user.user_type not in ['admin', 'employee']:
            messages.error(request, 'شما دسترسی لازم را ندارید')
            return redirect('products:product_detail', slug=product.slug)
        
        parent_id = request.POST.get('parent_id')
        reply_text = request.POST.get('reply_text')
        
        if parent_id and reply_text:
            parent = get_object_or_404(ProductComment, id=parent_id)
            reply = ProductComment.objects.create(
                product=product,
                user=request.user,
                comment=reply_text,
                status='approved',  # پاسخ کارمند/ادمین نیاز به تایید ندارد
                parent=parent,
                rating=5
            )
            messages.success(request, 'پاسخ شما با موفقیت ثبت شد.')
        else:
            messages.error(request, 'خطا در ثبت پاسخ')
        
        return redirect('products:product_detail', slug=product.slug)
    
    context = {
        'product': product,
        'similar_products': similar_products,
        'show_price': show_price,
        'comments': comments,
        'comments_count': comments_count,
        'avg_rating': avg_rating,
        'comment_form': comment_form,
    }
    return render(request, 'products/product_detail.html', context)


def search_suggestions(request):
    """API برای جستجوی لحظه‌ای محصولات"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # جستجو در نام محصول، برند، شماره محصول و نام‌های جایگزین
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(brand__name__icontains=query) |
        Q(product_code__icontains=query) |
        Q(alt_code__icontains=query) |
        Q(aliases__name__icontains=query)
    ).filter(
        is_active=True
    ).distinct()[:8]
    
    # نمایش قیمت فقط برای کاربران لاگین شده
    show_price = request.user.is_authenticated
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'slug': product.slug,
            'brand': product.brand.name,
            'price': str(product.final_price) if show_price else None,
            'has_price': show_price,
            'image': product.images.first().image.url if product.images.exists() else None,
            'url': product.get_absolute_url(),
            'product_code': product.product_code,
        })
    
    return JsonResponse({'results': results, 'query': query})