# employees/urls.py
from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    # پنل اصلی
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('employee-panel/', views.employee_panel, name='employee_panel'),
    
    # مدیریت مشتریان
    path('customers/', views.manage_customers, name='manage_customers'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/search/', views.search_customers, name='search_customers'),
    
    # مدیریت محصولات
    path('products/', views.manage_products, name='manage_products'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<int:product_id>/edit/', views.edit_product, name='edit_product'),
    path('products/import/', views.import_products, name='import_products'),
    path('products/search/', views.search_products, name='search_products'),
    
    # مدیریت فاکتورها
    path('invoices/', views.manage_invoices, name='manage_invoices'),
    path('invoices/pending/', views.pending_invoices, name='pending_invoices'),
    path('invoices/confirmed/', views.confirmed_invoices, name='confirmed_invoices'),
    path('invoices/<int:invoice_id>/confirm/', views.confirm_invoice, name='confirm_invoice'),
    path('invoices/<int:invoice_id>/reject/', views.reject_invoice, name='reject_invoice'),
    path('invoices/<int:invoice_id>/edit/', views.edit_invoice, name='edit_invoice'),
    path('invoices/search/', views.search_invoices, name='search_invoices'),
    path('invoices/<str:invoice_id>/view/', views.invoice_detail_admin, name='invoice_detail_admin'),
    path('invoices/<int:invoice_id>/send-to-accounting/', views.send_invoice_to_accounting, name='send_invoice_to_accounting'),
    path('invoices/<int:invoice_id>/print-warehouse/', views.print_warehouse_invoice, name='print_warehouse_invoice'),
    path('invoice-payments/', views.manage_invoice_payments, name='manage_invoice_payments'),
    path('invoice-payments/<int:payment_id>/reject/', views.reject_invoice_payment, name='reject_invoice_payment'),
    path('invoice-payments/<int:payment_id>/confirm/', views.confirm_invoice_payment, name='confirm_invoice_payment'),  # اضافه شد
    path('invoice-payments/<int:payment_id>/send-accounting/', views.send_invoice_payment_to_accounting, name='send_invoice_payment_to_accounting'),
    path('invoices/<int:invoice_id>/add-discount/', views.add_manual_discount, name='add_manual_discount'),
    
    # ویرایش فاکتور (API)
    path('invoices/<int:invoice_id>/update-item/', views.update_invoice_item, name='update_invoice_item'),
    path('invoices/<int:invoice_id>/add-item/', views.add_invoice_item, name='add_invoice_item'),
    path('invoices/search-products/', views.search_products_for_invoice, name='search_products_for_invoice'),
    
    # مدیریت پرداخت‌ها
    path('payments/', views.manage_payments, name='manage_payments'),
    path('payments/pending/', views.pending_payments, name='pending_payments'),
    path('payments/confirmed/', views.confirmed_payments, name='confirmed_payments'),
    path('payments/<int:payment_id>/confirm/', views.confirm_payment, name='confirm_payment'),
    path('payments/<int:payment_id>/reject/', views.reject_payment, name='reject_payment'),
    path('payments/search/', views.search_payments, name='search_payments'),
    path('payments/<int:payment_id>/detail/', views.payment_detail_api_admin, name='payment_detail_api_admin'),
    
    # مدیریت کارمندان
    path('employees/', views.manage_employees, name='manage_employees'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('employees/<int:employee_id>/edit/', views.edit_employee, name='edit_employee'),
    path('employees/<int:employee_id>/permissions/', views.edit_employee_permissions, name='edit_employee_permissions'),
    path('employees/search/', views.search_employees, name='search_employees'),
    
    # مدیریت برندها و دسته‌بندی
    path('brands/', views.manage_brands, name='manage_brands'),
    path('brands/edit/', views.edit_brand_modal, name='edit_brand_modal'),
    path('categories/', views.manage_categories, name='manage_categories'),
    path('cars/', views.manage_cars, name='manage_cars'),
    
    # مدیریت درخواست‌های ثبت‌نام
    path('registration-requests/', views.manage_registration_requests, name='manage_registration_requests'),
    path('registration-requests/<int:request_id>/view/', views.view_registration_request, name='view_registration_request'),

    # مدیریت نظرات
    path('comments/', views.manage_comments, name='manage_comments'),
    path('comments/<int:comment_id>/approve/', views.approve_comment, name='approve_comment'),
    path('comments/<int:comment_id>/reject/', views.reject_comment, name='reject_comment'),

    # تغییر نام کاربری و رمز عبور
    path('change-username/', views.change_username, name='change_username'),
    path('change-password/', views.change_password, name='change_password'),
    
]