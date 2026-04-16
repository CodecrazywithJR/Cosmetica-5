"""
Legal Entity serializers — System Plane.

Only accessible by superusers.
No multi-tenant filtering applied.
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
    PractitionerRoleChoices,
)
from apps.legal.models import LegalEntity


class LegalEntityListSerializer(serializers.ModelSerializer):
    """Read-only serializer for listing legal entities."""

    user_count = serializers.SerializerMethodField()

    class Meta:
        model = LegalEntity
        fields = [
            'id',
            'legal_name',
            'trade_name',
            'country_code',
            'city',
            'legal_email',
            'is_active',
            'user_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_user_count(self, obj):
        return obj.users.count()


class LegalEntityDetailSerializer(serializers.ModelSerializer):
    """Read-only serializer for legal entity detail."""

    user_count = serializers.SerializerMethodField()

    class Meta:
        model = LegalEntity
        fields = [
            'id',
            'legal_name',
            'trade_name',
            'address_line_1',
            'address_line_2',
            'postal_code',
            'city',
            'country_code',
            'siren',
            'siret',
            'vat_number',
            'currency',
            'timezone',
            'invoice_footer_text',
            'legal_email',
            'phone',
            'is_active',
            'user_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_user_count(self, obj):
        return obj.users.count()


class LegalEntityCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a LegalEntity + initial admin user.

    Required fields:
    - legal_name
    - country_code
    - legal_email
    - admin_email

    Within transaction.atomic():
    1. Create LegalEntity
    2. Create admin User (with temp password, must_change_password=True)
    3. Assign roles: admin + practitioner
    4. Create Practitioner record
    5. Return legal_entity_id, admin_user_id, temporary_password
    """

    # LegalEntity fields
    legal_name = serializers.CharField(max_length=255)
    trade_name = serializers.CharField(max_length=255, required=False, default='')
    address_line_1 = serializers.CharField(max_length=255, required=False, default='')
    address_line_2 = serializers.CharField(max_length=255, required=False, default='')
    postal_code = serializers.CharField(max_length=10, required=False, default='')
    city = serializers.CharField(max_length=100, required=False, default='')
    country_code = serializers.CharField(max_length=2)
    siren = serializers.CharField(max_length=9, required=False, allow_blank=True, default='')
    siret = serializers.CharField(max_length=14, required=False, allow_blank=True, default='')
    vat_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    currency = serializers.CharField(max_length=3, required=False, default='EUR')
    timezone = serializers.CharField(max_length=50, required=False, default='Europe/Paris')
    legal_email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=30, required=False, default='')

    # Admin user fields
    admin_email = serializers.EmailField(max_length=255)
    admin_first_name = serializers.CharField(max_length=150, required=False, default='')
    admin_last_name = serializers.CharField(max_length=150, required=False, default='')

    def validate_admin_email(self, value):
        """admin_email must be globally unique."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )
        return value

    def validate(self, attrs):
        """Ensure required roles exist in DB."""
        for role_name in [RoleChoices.ADMIN, RoleChoices.PRACTITIONER]:
            if not Role.objects.filter(name=role_name).exists():
                raise serializers.ValidationError(
                    f"Role '{role_name}' does not exist. "
                    f"Run bootstrap or create it first."
                )
        return attrs

    # ------------------------------------------------------------------

    def create(self, validated_data):
        """Atomic creation of LegalEntity + admin user + roles + practitioner."""
        from django.db import transaction

        # Split fields
        admin_email = validated_data.pop('admin_email')
        admin_first_name = validated_data.pop('admin_first_name', '')
        admin_last_name = validated_data.pop('admin_last_name', '')

        le_fields = {
            k: v for k, v in validated_data.items()
            if k in {
                'legal_name', 'trade_name', 'address_line_1', 'address_line_2',
                'postal_code', 'city', 'country_code', 'siren', 'siret',
                'vat_number', 'currency', 'timezone', 'legal_email', 'phone',
            }
        }
        # Convert empty strings to None for nullable unique fields
        for field in ('siren', 'siret', 'vat_number'):
            if not le_fields.get(field):
                le_fields[field] = None

        temp_password = self._generate_temporary_password()

        with transaction.atomic():
            # 1. Create LegalEntity
            legal_entity = LegalEntity.objects.create(**le_fields)

            # 2. Create admin user
            user = User.objects.create_user(
                email=admin_email,
                password=temp_password,
                first_name=admin_first_name,
                last_name=admin_last_name,
                is_active=True,
                must_change_password=True,
                legal_entity=legal_entity,
            )

            # 3. Assign roles: admin + practitioner
            admin_role = Role.objects.get(name=RoleChoices.ADMIN)
            practitioner_role = Role.objects.get(name=RoleChoices.PRACTITIONER)
            UserRole.objects.create(user=user, role=admin_role)
            UserRole.objects.create(user=user, role=practitioner_role)

            # 4. Create Practitioner record
            display = f'{admin_first_name} {admin_last_name}'.strip() or admin_email
            Practitioner.objects.create(
                user=user,
                display_name=display,
                role_type=PractitionerRoleChoices.PRACTITIONER,
                specialty='General',
                is_active=True,
            )

            # 5. Audit log
            from apps.authz.models import UserAuditLog, UserAuditActionChoices
            UserAuditLog.objects.create(
                actor_user=self.context['request'].user,
                target_user=user,
                action=UserAuditActionChoices.CREATE_USER,
                metadata={
                    'source': 'system_plane_legal_entity_create',
                    'legal_entity_id': str(legal_entity.id),
                    'roles': ['admin', 'practitioner'],
                    'has_practitioner': True,
                },
            )

        # Attach extras for response
        legal_entity._admin_user = user
        legal_entity._temporary_password = temp_password
        return legal_entity

    @staticmethod
    def _generate_temporary_password():
        length = 12
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + '!@#$%^&*'
        pwd = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice('!@#$%^&*'),
        ]
        pwd += [secrets.choice(chars) for _ in range(length - 4)]
        import random
        random.shuffle(pwd)
        return ''.join(pwd)


class LegalEntityUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating a LegalEntity.

    - id is read-only (cannot change)
    - DELETE not exposed
    """

    class Meta:
        model = LegalEntity
        fields = [
            'legal_name',
            'trade_name',
            'address_line_1',
            'address_line_2',
            'postal_code',
            'city',
            'country_code',
            'siren',
            'siret',
            'vat_number',
            'currency',
            'timezone',
            'invoice_footer_text',
            'legal_email',
            'phone',
        ]

    def validate(self, attrs):
        """Prevent changing id via payload injection."""
        if self.context['request'].data.get('id'):
            raise serializers.ValidationError(
                {'id': 'Cannot change id.'}
            )
        return attrs
