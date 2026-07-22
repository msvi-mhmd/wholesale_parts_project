# blog/admin.py
from django.contrib import admin
from .models import BlogCategory, BlogPost

@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'created_at', 'is_published']
    list_filter = ['category', 'is_published', 'created_at']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ['title']}