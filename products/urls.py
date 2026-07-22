# products/urls.py
from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('category/', views.product_list, name='category_products_default'),
    path('category/<slug:slug>/', views.product_list, name='category_products'),
    path('brand/<slug:slug>/', views.brand_products, name='brand_products'),
    path('brands/', views.brand_list, name='brand_list'),  # اضافه کردن این خط
    path('search/', views.product_list, name='search'),
    path('<slug:slug>/', views.product_detail, name='product_detail'),
    path('api/search-suggestions/', views.search_suggestions, name='search_suggestions'),
]