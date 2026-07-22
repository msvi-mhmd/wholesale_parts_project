# search/urls.py
from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    path('', views.global_search, name='global_search'),
    path('products/', views.search_products, name='search_products'),
    path('customers/', views.search_customers, name='search_customers'),
]