from django.contrib import admin
from .models import StockMove


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'move_type', 'quantity', 'created_at', 'created_by']
    list_filter = ['move_type', 'created_at']
    search_fields = ['product__name', 'reference']
    autocomplete_fields = ['product']
