# sliders/admin.py
from django.contrib import admin
from .models import Slider

@admin.register(Slider)
class SliderAdmin(admin.ModelAdmin):
    list_display = ['title', 'position', 'order', 'is_active', 'created_at']
    list_filter = ['position', 'is_active']
    search_fields = ['title', 'subtitle']
    ordering = ['position', 'order']