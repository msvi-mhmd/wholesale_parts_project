# products/admin.py
from django.contrib import admin
from django.utils.text import slugify

from .models import (
    CarBrand, Car, MainCategory, SubCategory, 
    ProductBrand, Product, ProductImage,ProductAlias
)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3

class ProductAliasInline(admin.TabularInline):
    model = ProductAlias
    extra = 3
    verbose_name = 'نام جایگزین'
    verbose_name_plural = 'نام‌های جایگزین'

@admin.register(CarBrand)
class CarBrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'country']
    search_fields = ['name', 'country']

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ['name', 'car_brand', 'model']
    list_filter = ['car_brand']
    search_fields = ['name', 'car_brand__name']

@admin.register(MainCategory)
class MainCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'main_category', 'slug']
    list_filter = ['main_category']
    prepopulated_fields = {'slug': ['name']}

@admin.register(ProductBrand)
class ProductBrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'city', 'phone']
    search_fields = ['name', 'country']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'price', 'final_price', 'left_in_stock', 'sold_number']
    list_filter = ['brand', 'main_category', 'sub_category', 'is_active', 'is_featured']
    search_fields = ['name', 'brand__name', 'specialty']
    prepopulated_fields = {'slug': ['name']}
    inlines = [ProductImageInline, ProductAliasInline]
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('product_code','name', 'slug', 'main_category', 'sub_category', 'brand')
        }),
        ('قیمت و موجودی', {
            'fields': ('price', 'off_price', 'left_in_stock')
        }),
        ('ویژگی‌ها', {
            'fields': ('suitable_car', 'specialty', 'point_of_buy')
        }),
        ('توضیحات', {
            'fields': ('short_description', 'full_description')
        }),
        ('وضعیت', {
            'fields': ('is_active', 'is_featured')
        }),
    )
    filter_horizontal = ['suitable_car']