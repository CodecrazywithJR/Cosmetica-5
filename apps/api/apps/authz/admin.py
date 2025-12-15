from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, UserRole, Practitioner


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'is_active', 'is_staff', 'is_superuser', 'created_at']
    list_filter = ['is_active', 'is_staff', 'is_superuser']
    search_fields = ['email']  # Required for autocomplete_fields
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login']
    
    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_active', 'is_staff'),
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

