#!/usr/bin/env python
"""
Demo script for stock module RBAC permissions.

Shows that:
1. Reception users get 403 on stock endpoints
2. ClinicalOps users get 200 on stock endpoints
3. Superusers get 200 on stock endpoints

Usage:
    cd apps/api
    python ../../scripts/demo_stock_rbac.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../apps/api'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework import status
from apps.authz.models import User


def demo_rbac():
    """Demonstrate stock RBAC in action."""
    
    print("\n" + "="*70)
    print("STOCK MODULE RBAC DEMONSTRATION")
    print("="*70)
    
    # Create groups if they don't exist
    print("\n1. Ensuring RBAC groups exist...")
    reception_group, created = Group.objects.get_or_create(name='Reception')
    clinicalops_group, created = Group.objects.get_or_create(name='ClinicalOps')
    print(f"   ✓ Reception group: {'created' if created else 'exists'}")
    print(f"   ✓ ClinicalOps group: {'created' if created else 'exists'}")
    
    # Create test users
    print("\n2. Creating test users...")
    reception_user, created = User.objects.get_or_create(
        email='demo_reception@test.com',
        defaults={'password': 'test123'}
    )
    reception_user.groups.add(reception_group)
    print(f"   ✓ Reception user: demo_reception@test.com")
    
    clinicalops_user, created = User.objects.get_or_create(
        email='demo_clinicalops@test.com',
        defaults={'password': 'test123'}
    )
    clinicalops_user.groups.add(clinicalops_group)
    print(f"   ✓ ClinicalOps user: demo_clinicalops@test.com")
    
    superuser = User.objects.filter(is_superuser=True).first()
    if not superuser:
        superuser, _ = User.objects.get_or_create(
            email='demo_admin@test.com',
            defaults={'password': 'test123', 'is_superuser': True, 'is_staff': True}
        )
    print(f"   ✓ Superuser: {superuser.email}")
    
    # Test endpoints
    print("\n3. Testing stock endpoints access...")
    endpoints = [
        ('GET', '/api/stock/locations/', 'List Stock Locations'),
        ('GET', '/api/stock/batches/', 'List Stock Batches'),
        ('GET', '/api/stock/moves/', 'List Stock Moves'),
        ('GET', '/api/stock/on-hand/', 'List Stock On-Hand'),
    ]
    
    client = APIClient()
    
    print("\n   Reception User (should get 403 on all):")
    client.force_authenticate(user=reception_user)
    for method, endpoint, description in endpoints:
        response = client.get(endpoint) if method == 'GET' else client.post(endpoint)
        status_emoji = "❌ 403" if response.status_code == 403 else f"⚠️  {response.status_code}"
        print(f"      {status_emoji} {description}")
    
    print("\n   ClinicalOps User (should get 200 on all):")
    client.force_authenticate(user=clinicalops_user)
    for method, endpoint, description in endpoints:
        response = client.get(endpoint) if method == 'GET' else client.post(endpoint)
        status_emoji = "✅ 200" if response.status_code == 200 else f"⚠️  {response.status_code}"
        print(f"      {status_emoji} {description}")
    
    print("\n   Superuser (should get 200 on all):")
    client.force_authenticate(user=superuser)
    for method, endpoint, description in endpoints:
        response = client.get(endpoint) if method == 'GET' else client.post(endpoint)
        status_emoji = "✅ 200" if response.status_code == 200 else f"⚠️  {response.status_code}"
        print(f"      {status_emoji} {description}")
    
    print("\n" + "="*70)
    print("RBAC DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nSummary:")
    print("  • Reception users CANNOT access stock (403 Forbidden)")
    print("  • ClinicalOps users CAN access stock (200 OK)")
    print("  • Superusers CAN access stock (200 OK)")
    print("\nFor full test suite:")
    print("  pytest apps/api/tests/test_stock_permissions.py -v")
    print("\n")


if __name__ == '__main__':
    demo_rbac()
