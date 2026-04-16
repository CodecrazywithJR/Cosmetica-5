ERP MASTER ARCHITECTURE

Purpose
-------

This document defines the global architecture of the Dermatology & Aesthetic ERP SaaS.

It describes the core principles, domain boundaries, and architectural rules that govern the system.

All future development must respect this architecture.

The system is designed as a vertically integrated ERP platform for dermatology and aesthetic medicine clinics.

The platform manages the full lifecycle of clinical and financial operations.


Core Principles
---------------

1. Vertical specialization

This ERP is not a generic medical system.

It is specifically designed for dermatology and aesthetic clinics.

Examples of domain-specific workflows include:

• injectable treatments
• laser procedures
• treatment packages with multiple sessions
• photo documentation of treatments
• stock consumption during procedures


2. ERP-level integration

Most clinic software focuses only on appointments and patient charts.

This system integrates:

• clinical workflows
• scheduling
• billing
• inventory
• accounting
• analytics

All operational events must be traceable to financial outcomes.


3. Multi-tenant SaaS architecture

Each customer is represented by a LegalEntity.

A LegalEntity may operate multiple clinics.

Structure:

LegalEntity
    ├── Clinics
    ├── Users
    ├── Patients
    ├── Treatments
    ├── Financial data


4. Strict domain separation

The system is divided into domains.

Each domain owns its data model and business logic.

Domains must communicate through explicit events or services.


System Domains
--------------

Core Platform
Scheduling
Clinical EMR
Billing
Inventory
Accounting
Analytics


Core Platform
-------------

Responsible for:

• multi-tenant architecture
• legal entities
• clinics
• users
• authentication
• roles and permissions
• audit logs


Scheduling
----------

Manages appointment booking and practitioner availability.

Key entities:

Appointment
PractitionerSchedule
PractitionerBlock


Clinical EMR
------------

Manages patient medical records.

Entities include:

Patient
Encounter
ClinicalMedia
Consents
Documents


Billing
-------

Manages commercial transactions.

Entities include:

Proposal
Sale
Invoice
Payment


Inventory
---------

Tracks physical products used during treatments.

Entities include:

Product
StockLocation
StockMovement


Accounting
----------

Implements a double-entry accounting engine.

Entities include:

ChartOfAccounts
Journal
JournalEntry
JournalLine


Analytics
---------

Provides operational and financial insights.

Examples:

• treatment profitability
• practitioner productivity
• clinic utilization


Canonical Clinical Workflow
---------------------------

The system follows a strict workflow:

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
Proposal accepted
    ↓
Sale created
    ↓
Treatment plan executed


Multi-Language Requirement
--------------------------

The system is fully multilingual.

Supported languages include:

English
Spanish
French
Russian
Ukrainian
Armenian


Technology Stack
----------------

Backend

Python
Django
Django REST Framework
PostgreSQL

Frontend

Next.js
React
React Query
Next-Intl

Infrastructure

Docker
pytest
multi-tenant ORM isolation


Long-Term Vision
----------------

The long-term goal is to build a complete ERP platform for aesthetic medicine clinics that can operate internationally and support multi-country accounting.