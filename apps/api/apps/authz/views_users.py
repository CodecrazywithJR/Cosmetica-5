"""
User Administration ViewSet.
"""
from django.db import transaction
from django.db import models
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.authz.models import User, UserAuditLog, UserAuditActionChoices, RoleChoices
from apps.authz.serializers_users import (
    UserListSerializer,
    UserDetailSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    PasswordResetSerializer,
    PasswordChangeSerializer,
)
from apps.authz.permissions import IsAdmin
from apps.core.tenant import TenantQuerySetMixin


class UserAdminViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    ViewSet for User Administration endpoints (Admin only).
    
    Endpoints:
    - GET /api/v1/users/ - List users with search
    - GET /api/v1/users/{id}/ - Get user detail
    - POST /api/v1/users/ - Create user
    - PATCH /api/v1/users/{id}/ - Update user
    - DELETE /api/v1/users/{id}/ - Soft delete user (Admin)
    - POST /api/v1/users/{id}/reset-password/ - Reset user password (Admin)
    - POST /api/v1/users/change-password/ - Change own password
    - POST /api/v1/users/{id}/change-password/ - Change another user's password (Admin)
    
    Query parameters for list:
    - ?q=search_term - Search by email, first_name, last_name
    - ?is_active=true|false - Filter by active status
    - ?role=admin|practitioner|reception|marketing|accounting - Filter by role
    
    RBAC:
    - Admin: Full access to all endpoints
    - Others: No access (protected by IsAdmin permission)
    """
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        """Get all users with filters, always scoped to the current tenant."""
        from apps.core.tenant_context import get_current_tenant
        tenant = get_current_tenant()
        queryset = User.objects.prefetch_related(
            'user_roles__role', 'practitioner'
        ).filter(legal_entity=tenant)
        
        # Search by email, first_name, last_name
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                models.Q(email__icontains=q) |
                models.Q(first_name__icontains=q) |
                models.Q(last_name__icontains=q)
            )
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(user_roles__role__name=role).distinct()
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'retrieve':
            return UserDetailSerializer
        elif self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'reset_password':
            return PasswordResetSerializer
        elif self.action == 'change_password':
            return PasswordChangeSerializer
        return UserListSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create new user with audit log."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # Create audit log
        UserAuditLog.objects.create(
            actor_user=request.user,
            target_user=user,
            action=UserAuditActionChoices.CREATE_USER,
            metadata={
                'created_fields': serializer.validated_data,
                'roles': list(user.user_roles.values_list('role__name', flat=True)),
                'has_practitioner': hasattr(user, 'practitioner'),
                'ip_address': self._get_client_ip(request),
            }
        )
        
        # Prepare response
        response_data = UserDetailSerializer(user).data
        response_data['temporary_password'] = getattr(user, '_temporary_password', None)
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update user with audit log."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Capture before state
        before_state = {
            'email': instance.email,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'is_active': instance.is_active,
            'roles': list(instance.user_roles.values_list('role__name', flat=True)),
        }
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Capture after state
        after_state = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'roles': list(user.user_roles.values_list('role__name', flat=True)),
        }
        
        # Identify changed fields
        changed_fields = {}
        for key in before_state:
            if before_state[key] != after_state[key]:
                changed_fields[key] = {
                    'before': before_state[key],
                    'after': after_state[key]
                }
        
        # Create audit log
        if 'is_active' in changed_fields and not after_state['is_active']:
            action = UserAuditActionChoices.DEACTIVATE_USER
        elif 'is_active' in changed_fields and after_state['is_active']:
            action = UserAuditActionChoices.ACTIVATE_USER
        else:
            action = UserAuditActionChoices.UPDATE_USER
        
        UserAuditLog.objects.create(
            actor_user=request.user,
            target_user=user,
            action=action,
            metadata={
                'changed_fields': changed_fields,
                'before': before_state,
                'after': after_state,
                'ip_address': self._get_client_ip(request),
            }
        )
        
        # Prepare response
        response_data = UserDetailSerializer(user).data
        
        return Response(response_data)
    
    @action(detail=True, methods=['post'], url_path='reset-password')
    @transaction.atomic
    def reset_password(self, request, pk=None):
        """
        Admin resets user password.
        
        Generates a new temporary password and sets must_change_password=True.
        Returns the temporary password (shown once).
        """
        user = self.get_object()
        
        serializer = PasswordResetSerializer(data={'user_id': pk})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        # Create audit log
        UserAuditLog.objects.create(
            actor_user=request.user,
            target_user=user,
            action=UserAuditActionChoices.RESET_PASSWORD,
            metadata={
                'ip_address': self._get_client_ip(request),
                'must_change_password': True,
            }
        )
        
        return Response({
            'message': 'Password reset successfully',
            'user_id': str(user.id),
            'email': user.email,
            'temporary_password': result['temporary_password'],
            'must_change_password': True,
        })
    
    @action(detail=False, methods=['post'], url_path='change-password', permission_classes=[permissions.IsAuthenticated])
    @transaction.atomic
    def change_password_self(self, request):
        """
        User changes their own password.
        
        Requires old_password for verification.
        Clears must_change_password flag.
        """
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'user': request.user, 'is_self_change': True}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create audit log
        UserAuditLog.objects.create(
            actor_user=request.user,
            target_user=user,
            action=UserAuditActionChoices.CHANGE_PASSWORD,
            metadata={
                'self_change': True,
                'ip_address': self._get_client_ip(request),
            }
        )
        
        return Response({
            'message': 'Password changed successfully',
            'must_change_password': False,
        })
    
    @action(detail=True, methods=['post'], url_path='change-password')
    @transaction.atomic
    def change_password_admin(self, request, pk=None):
        """
        Admin changes user password.
        
        Does not require old_password.
        Clears must_change_password flag.
        """
        user = self.get_object()
        
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'user': user, 'is_self_change': False}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create audit log
        UserAuditLog.objects.create(
            actor_user=request.user,
            target_user=user,
            action=UserAuditActionChoices.CHANGE_PASSWORD,
            metadata={
                'admin_change': True,
                'ip_address': self._get_client_ip(request),
            }
        )
        
        return Response({
            'message': 'Password changed successfully',
            'user_id': str(user.id),
            'email': user.email,
            'must_change_password': False,
        })
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Soft delete user (set is_active=False).
        
        This is NOT a physical deletion - user remains in database for audit trail.
        Deactivated users:
        - Cannot log in
        - Do not appear in active user lists (unless ?is_active=false filter used)
        - Preserve all historical data (encounters, appointments, audit logs)
        
        Business Rule (see PROJECT_DECISIONS.md):
        - Soft delete is the ONLY allowed deletion method for users
        - Physical deletion is NEVER permitted (violates audit requirements)
        """
        user = self.get_object()
        
        # Check if user is already inactive
        if not user.is_active:
            return Response(
                {'error': 'User is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Last admin per LegalEntity protection
        if user.user_roles.filter(role__name=RoleChoices.ADMIN).exists():
            from apps.authz.models import Role
            admin_role = Role.objects.get(name=RoleChoices.ADMIN)
            le = user.legal_entity
            admin_qs = User.objects.filter(
                is_active=True,
                user_roles__role=admin_role,
            )
            if le:
                admin_qs = admin_qs.filter(legal_entity=le)
            admin_qs = admin_qs.exclude(id=user.id)

            if admin_qs.count() == 0 and not request.user.is_superuser:
                return Response(
                    {'error': 'Cannot deactivate the last active admin of this legal entity. Only a superuser can.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Admin cannot deactivate themselves (unless superuser)
        if request.user.id == user.id and not request.user.is_superuser:
            return Response(
                {'error': 'Admin cannot deactivate themselves.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Perform soft delete
        user.is_active = False
        user.save(update_fields=['is_active', 'updated_at'])
        
        # Create audit log
        UserAuditLog.objects.create(
            actor_user=request.user,
            target_user=user,
            action=UserAuditActionChoices.DEACTIVATE_USER,
            metadata={
                'soft_delete': True,
                'ip_address': self._get_client_ip(request),
            }
        )
        
        return Response({
            'message': 'User deactivated successfully',
            'user_id': str(user.id),
            'email': user.email,
            'is_active': False,
        }, status=status.HTTP_200_OK)
    
    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
