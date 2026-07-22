from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    path('', views.settings_dashboard, name='settings_dashboard'),
    path('hero/', views.edit_hero, name='edit_hero'),
    path('about/', views.edit_about, name='edit_about'),
]