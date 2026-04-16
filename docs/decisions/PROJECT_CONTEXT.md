Contenido completo:
# PROJECT CONTEXT — Dermatology & Aesthetic ERP SaaS

## 1. Project Vision

This project aims to build a **full ERP SaaS platform for dermatology and aesthetic medicine clinics**.

The objective is **not** to create a simple EMR or appointment management tool.

The system must manage the **entire operational lifecycle of a clinic**, including:

- clinical operations
- scheduling
- billing and sales
- treatment plans
- inventory management
- accounting
- analytics

The system must scale from:

- a single-doctor clinic
to
- multi-clinic organizations with multiple practitioners and staff.

The ERP is designed as a **vertical SaaS platform specialized for dermatology and aesthetic medicine clinics**.

---

# 2. Product Philosophy

Most clinic software focuses on:

- patient charts
- appointments
- basic billing

This project instead aims to build a **true ERP for clinics**, where operational, clinical, and financial data are integrated.

Key goals:

- full operational visibility
- real profitability analysis
- integrated clinical and financial workflows
- elimination of external accounting and inventory systems.

---

# 3. Multi-Tenant Architecture

The platform is **multi-tenant SaaS**.

Each customer is represented by a **LegalEntity**.
LegalEntity (tenant)
├ Clinics
├ Users
├ Patients
├ Treatments
├ Inventory
└ Financial data

Key principles:

- Patients belong to the **LegalEntity**, not a specific clinic.
- Clinics represent **physical locations**.
- Users operate within a LegalEntity context.

Tenant context is injected through:
X-Active-Legal-Entity

Superusers can operate across tenants.

---

# 4. Domain Architecture

The system follows a **domain-based ERP architecture**.

Main domains:
Core Platform
Scheduling
Clinical EMR
Billing
Inventory
Accounting
Analytics

Each domain owns its own data models and business logic.

---

# 5. Core Clinical Workflow

The official clinical workflow of the ERP is:
Appointment
↓
Encounter
↓
Treatments performed
↓
Encounter finalized
↓
Proposal generated
↓
Proposal sent
↓
Proposal accepted
↓
Sale created
↓
TreatmentPlan created
↓
Treatment sessions executed

Important rules:

- Proposals **always originate from Encounters**
- TreatmentPlans **always originate from Proposal.accept()**
- TreatmentPlans are **never created manually**

---

# 6. Key Domain Models

Core entities include:

### Core Platform

- LegalEntity
- Clinic
- User
- Role
- Practitioner

### Scheduling

- Appointment
- PractitionerSchedule
- PractitionerBlock

### Clinical EMR

- Patient
- Encounter
- EncounterTreatment
- ClinicalPhotos
- Consents
- Documents

### Billing

- Proposal
- Sale
- Invoice
- Payment
- TreatmentPlan
- TreatmentSession

### Inventory

- Product
- StockLocation
- StockMovement

### Accounting

- ChartOfAccounts
- Journal
- JournalEntry
- JournalLine
- BankTransaction

---

# 7. Technology Stack

Backend
Python
Django
Django REST Framework
PostgreSQL

Frontend
Next.js
React
React Query
next-intl

Infrastructure
Docker
pytest
multi-tenant isolation

---

# 8. Internationalization

The system is **fully multilingual**.

Supported languages:

- English
- Spanish
- French
- Russian
- Ukrainian
- Armenian

Rules:

- No hardcoded UI strings
- All UI labels must use **next-intl**
- Translation keys must exist for all supported languages.

---

# 9. UX Philosophy

The system must be usable by doctors during clinical work.

Principles:

- minimal friction
- minimal mandatory fields
- fast workflows
- photo upload support
- avoid bureaucratic forms

Patient view will evolve toward **Patient 360**:
Overview
Encounters
Proposals
Treatment Plans
Sales
Documents

---

# 10. Project Status

The system already includes:

- backend architecture
- multi-tenant infrastructure
- clinical modules
- billing models
- appointment scheduling integration
- authentication and RBAC
- test suite (pytest)

Current development stage:
Backend stabilization and ERP expansion

Remaining work includes:

- fixing failing tests
- ensuring domain invariants
- auditing dangerous deletes
- continuing ERP feature development.

---

# 11. Project Principle

Every architectural decision must satisfy:
Does this scale?

The system must support:

- single-clinic operations
- multi-clinic organizations
- multi-country deployments

without structural refactoring.
