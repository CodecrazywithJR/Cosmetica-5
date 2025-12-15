from django.contrib import admin
from .models import Sale, SaleLine


class SaleLineInline(admin.TabularInline):
    """Inline admin for sale lines."""
    model = SaleLine
    extra = 1
    fields = ['product_name', 'product_code', 'quantity', 'unit_price', 'discount', 'line_total']
    readonly_fields = ['line_total']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['sale_number', 'patient', 'status', 'subtotal', 'total', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['sale_number', 'patient__first_name', 'patient__last_name']
    readonly_fields = ['id', 'subtotal', 'total', 'created_at', 'updated_at', 'paid_at']
    inlines = [SaleLineInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'sale_number', 'patient', 'appointment', 'status')
        }),
        ('Financial', {
            'fields': ('currency', 'subtotal', 'tax', 'discount', 'total')
        }),
        ('Notes', {
            'fields': ('notes', 'cancellation_reason', 'refund_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'paid_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SaleLine)
class SaleLineAdmin(admin.ModelAdmin):
    list_display = ['id', 'sale', 'product_name', 'quantity', 'unit_price', 'discount', 'line_total']
    list_filter = ['created_at']
    search_fields = ['product_name', 'product_code', 'sale__sale_number']
    readonly_fields = ['id', 'line_total', 'created_at', 'updated_at']
