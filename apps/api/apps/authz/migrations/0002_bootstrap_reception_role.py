# Generated for Reception role bootstrap

from django.db import migrations


def create_reception_role(apps, schema_editor):
    """
    Create Reception role if it doesn't exist.
    Idempotent - safe to run multiple times.
    """
    Role = apps.get_model('authz', 'Role')
    
    # Create or get Reception role
    role, created = Role.objects.get_or_create(
        name='reception',
        defaults={'name': 'reception'}
    )
    
    if created:
        print("✓ Created Reception role")
    else:
        print("✓ Reception role already exists")


def reverse_create_reception_role(apps, schema_editor):
    """
    Reverse migration - delete Reception role.
    Only deletes if no users are assigned to it.
    """
    Role = apps.get_model('authz', 'Role')
    UserRole = apps.get_model('authz', 'UserRole')
    
    try:
        role = Role.objects.get(name='reception')
        
        # Check if any users have this role
        if UserRole.objects.filter(role=role).exists():
            print("⚠ Cannot delete Reception role - users are assigned to it")
        else:
            role.delete()
            print("✓ Deleted Reception role")
    except Role.DoesNotExist:
        print("✓ Reception role doesn't exist")


class Migration(migrations.Migration):

    dependencies = [
        ('authz', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_reception_role,
            reverse_create_reception_role
        ),
    ]
