from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'price', 'stock_quantity', 'is_active']
    list_filter = ['is_active', 'category', 'brand']
    search_fields = ['name', 'sku', 'brand']
