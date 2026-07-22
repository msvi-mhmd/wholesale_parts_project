# sliders/urls.py
from django.urls import path
from . import views

app_name = 'sliders'

urlpatterns = [
    path('', views.slider_list, name='slider_list'),
    path('create/', views.slider_create, name='slider_create'),
    path('<int:slider_id>/edit/', views.slider_edit, name='slider_edit'),
    path('<int:slider_id>/delete/', views.slider_delete, name='slider_delete'),
    path('<int:slider_id>/toggle/', views.slider_toggle_status, name='slider_toggle'),
    path('reorder/', views.slider_reorder, name='slider_reorder'),
]