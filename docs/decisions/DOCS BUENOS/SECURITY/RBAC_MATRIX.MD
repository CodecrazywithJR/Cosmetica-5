ROLE BASED ACCESS CONTROL MATRIX

Roles
-----

admin
practitioner
reception
accounting
marketing
superuser


Admin
-----

Full access to all modules.

Capabilities:

• manage users
• manage clinics
• manage treatments
• access all patient data
• manage billing


Practitioner
------------

Clinical role.

Capabilities:

• view patients
• create encounters
• edit encounters
• add treatments
• upload clinical photos

Restrictions:

• cannot manage users
• cannot access accounting


Reception
---------

Operational role.

Capabilities:

• register patients
• schedule appointments
• view patient basic data

Restrictions:

• cannot access clinical notes
• cannot access financial data
• cannot edit encounters


Accounting
----------

Financial role.

Capabilities:

• view sales
• view invoices
• view payments
• access accounting reports

Restrictions:

• cannot access clinical data


Marketing
---------

Business development role.

Capabilities:

• view anonymized statistics
• view marketing sources
• manage campaigns

Restrictions:

• cannot access patient medical data


Superuser
---------

System-level administrator.

Capabilities:

• cross-tenant access
• manage LegalEntities
• override restrictions
• system maintenance