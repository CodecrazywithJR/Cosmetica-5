from django.contrib import admin
from .models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'total', 'status', 'created_at']
    list_filter = ['status', 'created_at']
