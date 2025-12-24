from django.contrib import admin
from .models import Sale, SaleLine


class SaleLineInline(admin.TabularInline):
    """
    Inline admin for sale lines.
    
    SECURITY: Prevent editing lines when sale is in terminal status.
    """
    model = SaleLine
    extra = 1
    fields = ['product_name', 'product_code', 'quantity', 'unit_price', 'discount', 'line_total']
    readonly_fields = ['line_total']
    
    def has_add_permission(self, request, obj=None):
        """Prevent adding lines to terminal status sales."""
        if obj and obj.is_terminal_status:
            return False
        return super().has_add_permission(request, obj)
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing lines of terminal status sales."""
        if obj and obj.is_terminal_status:
            return False
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting lines from terminal status sales."""
        if obj and obj.is_terminal_status:
            return False
        return super().has_delete_permission(request, obj)


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
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make financial fields readonly for terminal status sales.
        
        SECURITY: Prevents editing paid/cancelled/refunded sales.
        """
        readonly = list(self.readonly_fields)
        
        if obj and obj.is_terminal_status:
            # Terminal status: make most fields readonly
            readonly.extend(['patient', 'appointment', 'status', 'currency', 'tax', 'discount', 'notes'])
            # Allow only reason fields to be edited
        
        return readonly
    
    def has_change_permission(self, request, obj=None):
        """
        Allow viewing terminal sales but prevent structural changes.
        Actual field protection is in get_readonly_fields.
        """
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion of terminal status sales.
        Only superuser can delete.
        """
        if obj and obj.is_terminal_status:
            return request.user.is_superuser
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        """
        Enforce full_clean() validation.
        
        SECURITY: Prevents admin bypass of business rules.
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(SaleLine)
class SaleLineAdmin(admin.ModelAdmin):
    list_display = ['id', 'sale', 'product_name', 'quantity', 'unit_price', 'discount', 'line_total']
    list_filter = ['created_at']
    search_fields = ['product_name', 'product_code', 'sale__sale_number']
    readonly_fields = ['id', 'line_total', 'created_at', 'updated_at']
    
    def has_change_permission(self, request, obj=None):
        """
        Prevent editing lines of terminal status sales.
        
        SECURITY: Lines of paid/cancelled/refunded sales are immutable.
        """
        if obj and obj.sale and obj.sale.is_terminal_status:
            return False
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deleting lines from terminal status sales.
        """
        if obj and obj.sale and obj.sale.is_terminal_status:
            return False
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        """
        Enforce full_clean() validation.
        
        SECURITY: Prevents admin bypass of business rules.
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)
