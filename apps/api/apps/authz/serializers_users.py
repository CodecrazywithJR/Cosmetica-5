"""
User Administration Serializers.
"""
import secrets
import string
from rest_framework import serializers
from apps.authz.models import (
    User,
    Role,
    RoleChoices,
    UserRole,
    Practitioner,
    PractitionerRoleChoices
)

SPECIAL_CHARS = '!@#$%^&*'


class UserRoleSerializer(serializers.Serializer):
    """Serializer for user role information."""
    role_name = serializers.CharField()
    role_display = serializers.CharField()


class UserListSerializer(serializers.ModelSerializer):
    """
    Serializer for User list view (Admin only).
    
    Used for:
    - GET /api/v1/users/ - List all users
    """
    roles = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    is_practitioner = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'is_active',
            'must_change_password',
            'roles',
            'is_practitioner',
            'last_login',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_roles(self, obj):
        """Get user roles as list of role names."""
        return list(obj.user_roles.values_list('role__name', flat=True))
    
    def get_full_name(self, obj):
        """Get full name or email if names not set."""
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email
    
    def get_is_practitioner(self, obj):
        """Check if user has a practitioner record."""
        return hasattr(obj, 'practitioner')


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for User detail view (Admin only).
    
    Used for:
    - GET /api/v1/users/{id}/ - Get user detail
    """
    roles = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    practitioner = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'is_active',
            'is_staff',
            'must_change_password',
            'roles',
            'practitioner',
            'last_login',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_roles(self, obj):
        """Get user roles as list of role names."""
        return list(obj.user_roles.values_list('role__name', flat=True))
    
    def get_full_name(self, obj):
        """Get full name or email if names not set."""
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email
    
    def get_practitioner(self, obj):
        """Get practitioner info if exists."""
        if hasattr(obj, 'practitioner'):
            p = obj.practitioner
            return {
                'id': str(p.id),
                'display_name': p.display_name,
                'role_type': p.role_type,
                'specialty': p.specialty,
                'is_active': p.is_active,
            }
        return None


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for User creation (Admin only).
    
    Used for:
    - POST /api/v1/users/ - Create new user
    
    Generates a temporary password and sets must_change_password=True.
    """
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleChoices.choices),
        required=True,
        help_text='List of role names to assign'
    )
    password = serializers.CharField(write_only=True, required=False)
    practitioner_data = serializers.DictField(required=False, write_only=True, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'roles',
            'password',
            'practitioner_data',
        ]
        read_only_fields = ['id']
    
    def validate_email(self, value):
        """Ensure email is unique."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        """Enforce LE rules on user creation."""
        request = self.context.get('request')
        if request and hasattr(request.user, 'legal_entity'):
            le = request.user.legal_entity
            # Block if acting user's LE is inactive
            if le and not le.is_active:
                raise serializers.ValidationError(
                    'Cannot create users: this legal entity is currently inactive.'
                )
            # Non-superuser acting user must have an LE to assign
            if not request.user.is_superuser and not le:
                raise serializers.ValidationError(
                    'Cannot create users: you do not belong to a legal entity.'
                )
        return attrs

    def validate_roles(self, value):
        """Validate roles exist."""
        if not value:
            raise serializers.ValidationError("At least one role is required.")
        
        valid_roles = [choice[0] for choice in RoleChoices.choices]
        for role_name in value:
            if role_name not in valid_roles:
                raise serializers.ValidationError(
                    f"Invalid role '{role_name}'. Valid roles: {', '.join(valid_roles)}"
                )
        return value
    
    def validate_practitioner_data(self, value):
        """Validate practitioner data if provided."""
        if value:
            required_fields = ['display_name']
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"practitioner_data must include '{field}'")
        return value
    
    def create(self, validated_data):
        """Create user with roles and optional practitioner record."""
        roles_data = validated_data.pop('roles')
        practitioner_data = validated_data.pop('practitioner_data', None)
        password = validated_data.pop('password', None)
        
        # Generate secure temporary password if not provided
        if not password:
            password = self._generate_temporary_password()
        
        # Validate password length
        if len(password) < 8 or len(password) > 16:
            raise serializers.ValidationError({
                'password': 'Password must be between 8 and 16 characters.'
            })
        
        # Inherit legal_entity from acting user (tenant isolation)
        request = self.context.get('request')
        if request and hasattr(request.user, 'legal_entity_id'):
            if request.user.legal_entity_id and 'legal_entity' not in validated_data:
                validated_data['legal_entity'] = request.user.legal_entity
        
        # Create user with must_change_password=True
        user = User.objects.create_user(
            password=password,
            must_change_password=True,
            **validated_data
        )
        
        # Assign roles
        for role_name in roles_data:
            role = Role.objects.get(name=role_name)
            UserRole.objects.create(user=user, role=role)
        
        # Create practitioner record if data provided
        if practitioner_data:
            Practitioner.objects.create(
                user=user,
                display_name=practitioner_data.get('display_name'),
                role_type=practitioner_data.get('role_type', PractitionerRoleChoices.PRACTITIONER),
                specialty=practitioner_data.get('specialty', 'Dermatology'),
                is_active=practitioner_data.get('is_active', True)
            )
        
        # Store temporary password for response (will be shown once)
        user._temporary_password = password
        
        return user
    
    def _generate_temporary_password(self):
        """Generate a secure temporary password meeting policy requirements."""
        # Password policy: 8-16 chars, mix of upper, lower, digits, special
        length = 12
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + SPECIAL_CHARS
        
        # Ensure at least one of each type
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(SPECIAL_CHARS),
        ]
        
        # Fill the rest randomly
        password += [secrets.choice(chars) for _ in range(length - 4)]
        
        # Shuffle to avoid predictable patterns
        import random
        random.shuffle(password)
        
        return ''.join(password)


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for User update (Admin only).
    
    Used for:
    - PATCH /api/v1/users/{id}/ - Update user
    """
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleChoices.choices),
        required=False,
        help_text='List of role names to assign'
    )
    practitioner_data = serializers.DictField(required=False, write_only=True, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'is_active',
            'roles',
            'practitioner_data',
        ]
    
    def validate_email(self, value):
        """Ensure email is unique (except for current user)."""
        if self.instance and self.instance.email != value:
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_roles(self, value):
        """Validate roles exist."""
        if value is not None:
            valid_roles = [choice[0] for choice in RoleChoices.choices]
            for role_name in value:
                if role_name not in valid_roles:
                    raise serializers.ValidationError(
                        f"Invalid role '{role_name}'. Valid roles: {', '.join(valid_roles)}"
                    )
        return value
    
    def validate_practitioner_data(self, value):
        """Validate practitioner data if provided."""
        return value
    
    def validate(self, attrs):
        """Validate last-admin-per-LegalEntity and self-deactivation rules."""
        request = self.context.get('request')
        acting_user = request.user if request else None

        if 'is_active' in attrs or 'roles' in attrs:
            is_deactivating = attrs.get('is_active') is False and self.instance.is_active
            is_removing_admin = (
                'roles' in attrs
                and RoleChoices.ADMIN not in attrs.get('roles', [])
                and self.instance.user_roles.filter(role__name=RoleChoices.ADMIN).exists()
            )

            if is_deactivating or is_removing_admin:
                self._check_self_deactivation(acting_user)
                self._check_last_admin(acting_user)

        return attrs

    def _check_self_deactivation(self, acting_user):
        """Rule: Admin cannot deactivate themselves."""
        if (
            acting_user
            and acting_user.id == self.instance.id
            and not acting_user.is_superuser
        ):
            raise serializers.ValidationError(
                'Admin cannot deactivate or remove admin role from themselves.'
            )

    def _check_last_admin(self, acting_user):
        """Rule: Last admin per LegalEntity."""
        admin_role = Role.objects.get(name=RoleChoices.ADMIN)
        le = self.instance.legal_entity
        admin_qs = User.objects.filter(
            is_active=True,
            user_roles__role=admin_role,
        )
        if le:
            admin_qs = admin_qs.filter(legal_entity=le)
        admin_qs = admin_qs.exclude(id=self.instance.id)

        if admin_qs.count() == 0 and not (acting_user and acting_user.is_superuser):
            raise serializers.ValidationError(
                'Cannot deactivate or remove admin role from the '
                'last active administrator of this legal entity. '
                'Only a superuser can perform this action.'
            )

        return attrs
    
    def update(self, instance, validated_data):
        """Update user and roles."""
        roles_data = validated_data.pop('roles', None)
        practitioner_data = validated_data.pop('practitioner_data', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update roles if provided
        if roles_data is not None:
            # Remove old roles
            instance.user_roles.all().delete()
            # Add new roles
            for role_name in roles_data:
                role = Role.objects.get(name=role_name)
                UserRole.objects.create(user=instance, role=role)
        
        # Update practitioner record if data provided
        if practitioner_data is not None:
            if hasattr(instance, 'practitioner'):
                # Update existing practitioner
                practitioner = instance.practitioner
                for attr, value in practitioner_data.items():
                    setattr(practitioner, attr, value)
                practitioner.save()
            elif practitioner_data:  # Only create if not None/empty
                # Create new practitioner record
                Practitioner.objects.create(
                    user=instance,
                    display_name=practitioner_data.get('display_name', instance.email),
                    role_type=practitioner_data.get('role_type', PractitionerRoleChoices.PRACTITIONER),
                    specialty=practitioner_data.get('specialty', 'Dermatology'),
                    is_active=practitioner_data.get('is_active', True)
                )
        
        return instance


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializer for admin password reset.
    
    Used for:
    - POST /api/v1/users/{id}/reset-password/ - Admin resets user password
    
    Generates a new temporary password and sets must_change_password=True.
    """
    user_id = serializers.UUIDField(required=True)
    
    def validate_user_id(self, value):
        """Validate user exists."""
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return value
    
    def save(self):
        """Reset password and return temporary password."""
        user_id = self.validated_data['user_id']
        user = User.objects.get(id=user_id)
        
        # Generate secure temporary password
        temp_password = self._generate_temporary_password()
        
        # Set password and must_change_password flag
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password'])
        
        return {
            'user': user,
            'temporary_password': temp_password
        }
    
    def _generate_temporary_password(self):
        """Generate a secure temporary password meeting policy requirements."""
        length = 12
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + SPECIAL_CHARS
        
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(SPECIAL_CHARS),
        ]
        
        password += [secrets.choice(chars) for _ in range(length - 4)]
        
        import random
        random.shuffle(password)
        
        return ''.join(password)


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change.
    
    Used for:
    - POST /api/v1/users/change-password/ - User changes own password
    - POST /api/v1/users/{id}/change-password/ - Admin changes user password
    
    Clears must_change_password flag after successful change.
    """
    old_password = serializers.CharField(required=False, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8, max_length=16)
    
    def validate_new_password(self, value):
        """Validate new password meets requirements."""
        if len(value) < 8 or len(value) > 16:
            raise serializers.ValidationError("Password must be between 8 and 16 characters.")
        return value
    
    def validate(self, attrs):
        """Validate old password if user is changing their own password."""
        user = self.context.get('user')
        is_self_change = self.context.get('is_self_change', False)
        
        if is_self_change and 'old_password' in attrs:
            if not user.check_password(attrs['old_password']):
                raise serializers.ValidationError({'old_password': 'Current password is incorrect.'})
        
        return attrs
    
    def save(self):
        """Change password and clear must_change_password flag."""
        user = self.context['user']
        new_password = self.validated_data['new_password']
        
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])
        
        return user
