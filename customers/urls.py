# customers/urls.py
from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # پنل کاربری
    path('panel/', views.customer_panel, name='customer_panel'),
    path('statement/', views.customer_statement, name='statement'),
    path('club/', views.club, name='club'),
    path('change-password/', views.change_password, name='change_password'),
    
    # سبد خرید
    path('cart/', views.cart_view, name='cart'),
    path('cart/count/', views.cart_count_api, name='cart_count'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/', views.update_cart_quantity, name='update_cart'),
    
    # تسویه حساب
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/confirm/', views.confirm_order, name='confirm_order'),
    
    # فاکتورها
    path('invoices/', views.invoice_history, name='invoice_history'),
    path('invoices/<str:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<str:invoice_id>/print/', views.invoice_print, name='invoice_print'),
    
    # پرداخت فاکتور
    path('invoices/<str:invoice_id>/pay/', views.pay_invoice, name='pay_invoice'),
    path('process-invoice-payment/<str:invoice_id>/', views.process_invoice_payment, name='process_invoice_payment'),
    path('verify-invoice-online-payment/', views.verify_invoice_online_payment, name='verify_invoice_online_payment'),
    
    # پرداخت‌ها
    path('payments/', views.payment_history, name='payment_history'),
    path('payments/add/', views.add_payment, name='add_payment'),
    path('payments/<int:payment_id>/detail/', views.payment_detail_api, name='payment_detail_api'),
    
    # پرداخت آنلاین (افزایش اعتبار)
    path('online-payment/', views.online_payment, name='online_payment'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),
    
    # امتیازات و بدهی
    path('points/redeem/', views.redeem_points, name='redeem_points'),
    path('debt/pay/', views.pay_debt, name='pay_debt'),
]