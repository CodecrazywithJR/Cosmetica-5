from django.contrib import admin

from .models import TreatmentPlan


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = [
        'package_name',
        'patient',
        'status',
        'completed_sessions',
        'planned_sessions',
        'total_price_snapshot',
        'created_at',
    ]
    list_filter = ['status', 'currency']
    search_fields = ['package_name', 'patient__first_name', 'patient__last_name']
    readonly_fields = [
        'id', 'created_at', 'updated_at',
        'activated_at', 'completed_at', 'cancelled_at',
    ]
    raw_id_fields = ['patient', 'practitioner', 'proposal', 'proposal_line', 'sale']

    def has_delete_permission(self, request, obj=None):
        """Treatment plans cannot be deleted to preserve clinical records."""
        return False
