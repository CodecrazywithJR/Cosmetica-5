"""Admin configuration for legal entities."""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import LegalEntity


@admin.register(LegalEntity)
class LegalEntityAdmin(admin.ModelAdmin):
    """
    Admin interface for LegalEntity.
    
    Note: This is for master data management ONLY.
    NO fiscal logic, NO invoice generation from here.
    """
    
    list_display = [
        'legal_name',
        'trade_name',
        'siret',
        'city',
        'country_code',
        'is_active',
        'created_at',
    ]
    
    list_filter = [
        'is_active',
        'country_code',
        'created_at',
    ]
    
    search_fields = [
        'legal_name',
        'trade_name',
        'siren',
        'siret',
        'vat_number',
        'city',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'full_address',
    ]
    
    fieldsets = (
        (_('Identification'), {
            'fields': (
                'id',
                'legal_name',
                'trade_name',
                'is_active',
            )
        }),
        (_('Address'), {
            'fields': (
                'address_line_1',
                'address_line_2',
                'postal_code',
                'city',
                'country_code',
                'full_address',
            )
        }),
        (_('Business Registration (France)'), {
            'fields': (
                'siren',
                'siret',
                'vat_number',
            ),
            'description': _(
                'French business identifiers. '
                'Leave empty if not yet registered or if entity is outside France.'
            )
        }),
        (_('Operational Settings'), {
            'fields': (
                'currency',
                'timezone',
            )
        }),
        (_('Document Customization'), {
            'fields': (
                'invoice_footer_text',
            ),
            'classes': ('collapse',),
            'description': _(
                'Optional text to include on invoices. '
                'Example: payment terms, legal notices, contact information.'
            )
        }),
        (_('Audit'), {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        """Show inactive entities last."""
        qs = super().get_queryset(request)
        return qs.order_by('-is_active', 'legal_name')
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion of legal entities that are referenced by sales.
        
        Note: We check for FK relationships to prevent orphaned sales.
        """
        if obj and hasattr(obj, 'sales') and obj.sales.exists():
            return False
        return super().has_delete_permission(request, obj)
