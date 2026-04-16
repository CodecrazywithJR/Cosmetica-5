TENANT ISOLATION

The system is multi-tenant.

Tenant = LegalEntity.

All business data belongs to a LegalEntity.

Examples:

Patients
Appointments
Encounters
Sales
Inventory
Accounting

Tenant context is determined through:

X-Active-Legal-Entity header.

Superusers may bypass tenant restrictions.