from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, UserRole, Practitioner, UserAuditLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'must_change_password', 'created_at']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'must_change_password']
    search_fields = ['email', 'first_name', 'last_name']  # Required for autocomplete_fields
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login']
    
    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'must_change_password', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'is_active', 'is_staff', 'must_change_password'),
        }),
    )
    
    ordering = ['email']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']  # Required for autocomplete_fields
    readonly_fields = ['id', 'created_at']


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']
    list_filter = ['role']
    search_fields = ['user__email']
    autocomplete_fields = ['user', 'role']


@admin.register(Practitioner)
class PractitionerAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'specialty', 'user', 'is_active', 'created_at']
    list_filter = ['is_active', 'specialty']
    search_fields = ['display_name', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['user']


@admin.register(UserAuditLog)
class UserAuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action', 'actor_user', 'target_user']
    list_filter = ['action', 'created_at']
    search_fields = ['actor_user__email', 'target_user__email']
    readonly_fields = ['id', 'created_at', 'actor_user', 'target_user', 'action', 'metadata']
    
    def has_add_permission(self, request):
        # Audit logs should not be manually created
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Audit logs should not be deleted
        return False

