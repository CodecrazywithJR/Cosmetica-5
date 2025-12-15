"""
Authz models: auth_user, auth_role, auth_user_role, practitioner
Based on DOMAIN_MODEL.md section 2
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


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
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Required for admin access
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


class Practitioner(models.Model):
    """
    Practitioners (doctors, dermatologists) linked to users.
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - user_id: FK -> auth_user (unique)
    - display_name
    - specialty: default "Dermatology"
    - is_active: bool default true
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='practitioner'
    )
    display_name = models.CharField(max_length=255)
    specialty = models.CharField(max_length=100, default='Dermatology')
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
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.specialty})"

