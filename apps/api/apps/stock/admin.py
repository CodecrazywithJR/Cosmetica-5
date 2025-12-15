"""Stock admin with batch and location support."""
from django.contrib import admin
from .models import StockLocation, StockBatch, StockMove, StockOnHand


@admin.register(StockLocation)
class StockLocationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'location_type', 'is_active', 'created_at']
    list_filter = ['location_type', 'is_active']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = [
        'batch_number', 'product', 'expiry_date', 'is_expired',
        'received_at', 'created_at'
    ]
    list_filter = ['expiry_date', 'received_at', 'created_at']
    search_fields = ['batch_number', 'product__sku', 'product__name']
    autocomplete_fields = ['product']
    date_hierarchy = 'expiry_date'
    ordering = ['expiry_date', 'batch_number']
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'product', 'location', 'batch', 'move_type',
        'quantity', 'created_at', 'created_by'
    ]
    list_filter = ['move_type', 'location', 'created_at']
    search_fields = [
        'product__name', 'product__sku',
        'batch__batch_number',
        'reason', 'reference_type', 'reference_id'
    ]
    autocomplete_fields = ['product', 'location', 'batch']
    readonly_fields = ['created_at', 'created_by']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Movement Details', {
            'fields': ('product', 'location', 'batch', 'move_type', 'quantity')
        }),
        ('Reference', {
            'fields': ('reference_type', 'reference_id', 'reason'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StockOnHand)
class StockOnHandAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'location', 'batch', 'quantity_on_hand',
        'batch_expiry', 'updated_at'
    ]
    list_filter = ['location', 'updated_at']
    search_fields = [
        'product__name', 'product__sku',
        'batch__batch_number',
        'location__name', 'location__code'
    ]
    autocomplete_fields = ['product', 'location', 'batch']
    readonly_fields = ['updated_at']
    ordering = ['product', 'location', 'batch']
    
    def batch_expiry(self, obj):
        if obj.batch and obj.batch.expiry_date:
            return obj.batch.expiry_date
        return '-'
    batch_expiry.admin_order_field = 'batch__expiry_date'
    
    # Prevent manual editing - this is calculated
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
