# search/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from products.models import Product
from customers.models import Customer

def global_search(request):
    """جستجوی سراسری در سایت"""
    query = request.GET.get('q', '')
    results = {
        'products': [],
        'customers': [],
    }
    
    if query:
        results['products'] = Product.objects.filter(
            Q(name__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(specialty__icontains=query),
            is_active=True
        )[:10]
        
        if request.user.is_authenticated and request.user.user_type in ['admin', 'employee']:
            results['customers'] = Customer.objects.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__national_id__icontains=query) |
                Q(user__phone__icontains=query)
            )[:10]
    
    return render(request, 'search/results.html', {'query': query, 'results': results})

def search_products(request):
    """API جستجوی محصولات"""
    from django.http import JsonResponse
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(brand__name__icontains=query),
        is_active=True
    ).select_related('brand')[:10]
    
    results = [{
        'id': p.id,
        'name': p.name,
        'brand': p.brand.name,
        'price': str(p.price),
        'image': p.images.first().image.url if p.images.exists() else None
    } for p in products]
    
    return JsonResponse({'results': results})

def search_customers(request):
    """API جستجوی مشتریان (فقط برای ادمین و کارمندان)"""
    from django.http import JsonResponse
    from django.contrib.auth.decorators import login_required
    
    if not request.user.is_authenticated or request.user.user_type not in ['admin', 'employee']:
        return JsonResponse({'results': []})
    
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    customers = Customer.objects.filter(
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query) |
        Q(user__national_id__icontains=query) |
        Q(user__phone__icontains=query)
    ).select_related('user')[:10]
    
    results = [{
        'id': c.id,
        'name': f"{c.user.first_name} {c.user.last_name}",
        'national_id': c.user.national_id,
        'phone': c.user.phone,
        'credit': str(c.credit)
    } for c in customers]
    
    return JsonResponse({'results': results})