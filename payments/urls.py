# payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.payment_list, name='payment_list'),
    path('<int:payment_id>/', views.payment_detail, name='payment_detail'),
]