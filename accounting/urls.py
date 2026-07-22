# accounting/urls.py
from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    # داشبورد و همگام‌سازی
    path('sync/', views.sync_dashboard, name='sync_dashboard'),
    path('sync/customers/', views.sync_customers, name='sync_customers'),
    path('sync/products/', views.sync_products, name='sync_products'),
    path('sync/logs/', views.sync_logs, name='sync_logs'),
    path('sync/invoices/', views.sync_invoices, name='sync_invoices'),
    path('sync/payments/', views.sync_payments, name='sync_payments'),
    
    # ارسال فاکتور به حسابداری (از پنل مدیریت)
    path('send-invoice/<int:invoice_id>/', views.send_invoice_to_accounting, name='send_invoice'),
    
    # ===== APIهای جدید =====
    path('api/check-connection/', views.check_connection_api, name='check_connection'),
    path('api/get-products/', views.get_products_api, name='get_products'),
    path('api/get-customers/', views.get_customers_api, name='get_customers'),
    path('api/create-customer/', views.create_customer_api, name='create_customer'),
    path('api/create-invoice/', views.create_invoice_api, name='create_invoice'),
    path('api/create-payment/', views.create_payment_api, name='create_payment'),
    
    path('test-connection/', views.test_connection, name='test_connection'),
]