# reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_dashboard, name='index'),
    path('sales/', views.sales_report, name='sales_report'),
    path('payments/', views.payments_report, name='payments_report'),
    path('products/', views.products_report, name='products_report'),
    path('customers/', views.customers_report, name='customers_report'),
    path('export/<str:report_type>/', views.export_to_excel, name='export_excel'),
    
]