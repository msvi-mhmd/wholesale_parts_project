# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register-request/', views.register_request, name='register_request'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
]