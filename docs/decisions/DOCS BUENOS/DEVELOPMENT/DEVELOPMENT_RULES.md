DEVELOPMENT RULES

Purpose
-------

This document defines mandatory development rules for contributors and AI assistants.


Architecture Respect
--------------------

Developers must respect domain architecture.

Do not introduce cross-domain coupling.


Backend Source of Truth
-----------------------

Business states are defined in backend models.

Frontend must never invent states.


State Transitions
-----------------

State changes must be performed via dedicated endpoints.

Example:

POST /proposals/{id}/send
POST /proposals/{id}/accept


Multi-Tenant Safety
-------------------

All business data must belong to a LegalEntity.

Never create data without tenant context.


Internationalization
--------------------

Visible UI text must use next-intl.

Hardcoded strings are forbidden.


Transactions
------------

Critical operations must use database transactions.

Example:

Proposal.accept()

must create:

• Sale
• SaleLines
• TreatmentPlans


Soft Delete Policy
------------------

Certain entities must never be hard deleted.

These include:

Patient
Encounter
Sale
JournalEntry