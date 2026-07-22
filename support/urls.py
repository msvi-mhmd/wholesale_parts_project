# support/urls.py
from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # ===== مسیرهای مشتریان =====
    path('', views.ticket_list, name='ticket_list'),
    path('create/', views.create_ticket, name='create_ticket'),
    path('<str:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('<str:ticket_id>/reply/', views.ticket_reply, name='ticket_reply'),
    path('<str:ticket_id>/close/', views.ticket_close, name='ticket_close'),
    
    # ===== مسیرهای مدیریت =====
    path('admin/list/', views.admin_ticket_list, name='admin_ticket_list'),
    path('admin/<str:ticket_id>/status/', views.admin_ticket_status_update, name='admin_ticket_status_update'),
    path('admin/<str:ticket_id>/delete/', views.admin_ticket_delete, name='admin_ticket_delete'),
]