"""
Authz models: auth_user, auth_role, auth_user_role, practitioner
Based on DOMAIN_MODEL.md section 2
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


# ============================================================================
# Enums
# ============================================================================

class PractitionerRoleChoices(models.TextChoices):
    """
    Practitioner role types for clinical staff classification.
    
    - PRACTITIONER: Doctors, dermatologists (can perform procedures)
    - ASSISTANT: Clinical assistants (support practitioners)
    - CLINICAL_MANAGER: Clinical operations manager (oversees clinical staff)
    """
    PRACTITIONER = 'practitioner', 'Practitioner'
    ASSISTANT = 'assistant', 'Assistant'
    CLINICAL_MANAGER = 'clinical_manager', 'Clinical Manager'


# ============================================================================
# User Management
# ============================================================================

class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for authentication.
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - email: unique
    - password_hash: handled by AbstractBaseUser
    - is_active: bool
    - last_login_at: nullable (from AbstractBaseUser as last_login)
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True, help_text='First name of the user')
    last_name = models.CharField(max_length=150, blank=True, help_text='Last name of the user')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Required for admin access
    must_change_password = models.BooleanField(
        default=False,
        help_text='If true, user must change password on next login'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email'], name='idx_user_email'),
            models.Index(fields=['is_active'], name='idx_user_active'),
        ]
    
    def __str__(self):
        return self.email


class RoleChoices(models.TextChoices):
    """Fixed role names from DOMAIN_MODEL.md"""
    ADMIN = 'admin', 'Admin'
    PRACTITIONER = 'practitioner', 'Practitioner'
    RECEPTION = 'reception', 'Reception'
    MARKETING = 'marketing', 'Marketing'
    ACCOUNTING = 'accounting', 'Accounting'


class Role(models.Model):
    """
    System roles.
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - name: unique (admin|practitioner|reception|marketing|accounting)
    - created_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        choices=RoleChoices.choices
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'auth_role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.get_name_display()


class UserRole(models.Model):
    """
    Many-to-many relationship between users and roles.
    
    Fields from DOMAIN_MODEL.md:
    - user_id: FK -> auth_user
    - role_id: FK -> auth_role
    - Unique (user_id, role_id)
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    
    class Meta:
        db_table = 'auth_user_role'
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
        unique_together = [('user', 'role')]
        indexes = [
            models.Index(fields=['user'], name='idx_user_role_user'),
            models.Index(fields=['role'], name='idx_user_role_role'),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.role.name}"

# ============================================================================
# User Administration Audit Log
# ============================================================================

class UserAuditActionChoices(models.TextChoices):
    """Actions that can be audited for user administration."""
    CREATE_USER = 'create_user', 'Create User'
    UPDATE_USER = 'update_user', 'Update User'
    RESET_PASSWORD = 'reset_password', 'Reset Password'
    CHANGE_PASSWORD = 'change_password', 'Change Password'
    DEACTIVATE_USER = 'deactivate_user', 'Deactivate User'
    ACTIVATE_USER = 'activate_user', 'Activate User'


class UserAuditLog(models.Model):
    """
    Audit trail for user administration actions.
    
    Tracks administrative actions on users for security and compliance.
    Based on the pattern from ClinicalAuditLog.
    
    Fields:
    - id: UUID PK
    - created_at: timestamp of action
    - actor_user: admin who made the change
    - target_user: user being modified
    - action: create_user|update_user|reset_password|change_password
    - metadata: JSON with before/after values, changed fields, IP, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    actor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions',
        help_text='Admin user who performed the action'
    )
    
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        help_text='User who was affected by the action'
    )
    
    action = models.CharField(
        max_length=20,
        choices=UserAuditActionChoices.choices
    )
    
    metadata = models.JSONField(
        default=dict,
        help_text='Changed fields, before/after values, IP address, user agent, etc.'
    )
    
    class Meta:
        db_table = 'user_audit_log'
        verbose_name = 'User Audit Log'
        verbose_name_plural = 'User Audit Logs'
        indexes = [
            models.Index(fields=['created_at'], name='idx_user_audit_created'),
            models.Index(fields=['actor_user'], name='idx_user_audit_actor'),
            models.Index(fields=['target_user'], name='idx_user_audit_target'),
            models.Index(fields=['action'], name='idx_user_audit_action'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        actor = self.actor_user.email if self.actor_user else 'system'
        target = self.target_user.email if self.target_user else 'unknown'
        return f"{self.action} on {target} by {actor}"

class Practitioner(models.Model):
    """
    Practitioners (doctors, dermatologists, clinical staff) linked to users.
    
    Fields from DOMAIN_MODEL.md + Fase 2.2 requirements:
    - id: UUID PK
    - user_id: FK -> auth_user (unique)
    - display_name: string
    - role_type: enum (PRACTITIONER, ASSISTANT, CLINICAL_MANAGER)
    - specialty: string (default "Dermatology")
    - is_active: bool default true
    - created_at, updated_at
    
    BUSINESS RULES:
    - Only PRACTITIONER role can perform clinical procedures
    - ASSISTANT can support but not lead encounters
    - CLINICAL_MANAGER can oversee but typically doesn't perform procedures
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='practitioner'
    )
    display_name = models.CharField(max_length=255)
    role_type = models.CharField(
        max_length=20,
        choices=PractitionerRoleChoices.choices,
        default=PractitionerRoleChoices.PRACTITIONER,
        help_text='Type of clinical role (practitioner, assistant, clinical_manager)'
    )
    specialty = models.CharField(max_length=100, default='Dermatology')
    calendly_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Personal Calendly scheduling URL for this practitioner. If null, system uses CALENDLY_DEFAULT_URL from settings.'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'practitioner'
        verbose_name = 'Practitioner'
        verbose_name_plural = 'Practitioners'
        indexes = [
            models.Index(fields=['is_active'], name='idx_practitioner_active'),
            models.Index(fields=['display_name'], name='idx_practitioner_name'),
            models.Index(fields=['role_type'], name='idx_practitioner_role'),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.get_role_type_display()})"

