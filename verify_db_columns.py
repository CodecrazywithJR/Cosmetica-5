import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import logging
logging.disable(logging.CRITICAL)
django.setup()

from django.db import connection

cursor = connection.cursor()

# First check table exists
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE '%patient%'")
tables = cursor.fetchall()
print(f"=== PATIENT TABLES: {tables} ===")

cursor.execute("""
SELECT column_name, data_type, is_nullable, character_maximum_length, column_default
FROM information_schema.columns 
WHERE table_name='patient' 
AND column_name IN (
    'document_type', 'document_number', 'nationality',
    'emergency_contact_name', 'emergency_contact_phone',
    'privacy_policy_accepted', 'privacy_policy_accepted_at',
    'terms_accepted', 'terms_accepted_at'
)
ORDER BY column_name
""")

print("=== DATABASE COLUMNS ===")
rows = cursor.fetchall()
print(f"Found {len(rows)} columns")
for row in rows:
    col_name, data_type, nullable, max_len, default = row
    print(f"{col_name}: {data_type}", end="")
    if max_len:
        print(f"({max_len})", end="")
    print(f" NULL={nullable}", end="")
    if default:
        print(f" DEFAULT={default}", end="")
    print()
