"""
User Administration ViewSet.
"""
from django.db import transaction
from django.db import models
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.authz.models import User, UserAuditLog, UserAuditActionChoices
from apps.authz.serializers_users import (
    UserListSerializer,
    UserDetailSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    PasswordResetSerializer,
    PasswordChangeSerializer,
)
from apps.authz.permissions import IsAdmin


class UserAdminViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User Administration endpoints (Admin only).
    
    Endpoints:
    - GET /api/v1/users/ - List users with search
    - GET /api/v1/users/{id}/ - Get user detail
    - POST /api/v1/users/ - Create user
    - PATCH /api/v1/users/{id}/ - Update user
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
        """Get all users with filters."""
        queryset = User.objects.prefetch_related('user_roles__role', 'practitioner').all()
        
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
        
        # Add warnings if any
        if hasattr(serializer, '_calendly_warnings'):
            response_data['warnings'] = serializer._calendly_warnings
        
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
        action = UserAuditActionChoices.DEACTIVATE_USER if (
            'is_active' in changed_fields and not after_state['is_active']
        ) else UserAuditActionChoices.ACTIVATE_USER if (
            'is_active' in changed_fields and after_state['is_active']
        ) else UserAuditActionChoices.UPDATE_USER
        
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
        
        # Add warnings if any
        if hasattr(serializer, '_calendly_warnings'):
            response_data['warnings'] = serializer._calendly_warnings
        
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
    
    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
