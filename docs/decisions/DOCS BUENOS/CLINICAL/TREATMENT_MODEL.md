TREATMENT MODEL

Purpose
-------

The Treatment model defines the catalog of services that a clinic can offer.

In dermatology and aesthetic medicine, treatments are not simple services. They may involve:

• medical procedures
• product consumption
• multiple sessions
• variable duration
• practitioner capabilities

The treatment model must support these requirements.


Core Concept
------------

A Treatment represents a medical or aesthetic procedure that can be performed during an Encounter.

Examples:

Botox injection
Dermal filler
Laser hair removal
Skin consultation
Chemical peel


Treatment Entity
----------------

Treatment

Fields:

id
name
description
category
default_duration_minutes
default_price
requires_stock
is_active

Notes:

• name must be unique per LegalEntity
• default_price may be overridden during Encounter
• treatments may be disabled using is_active


Treatment Categories
--------------------

Treatments are grouped into categories.

Example:

Injectables
Laser
Consultation
Skin treatments


TreatmentCategory

Fields:

id
name
description
is_active


Treatment Duration
------------------

Treatments have a default duration used for scheduling.

Example:

Botox → 30 minutes
Laser → 45 minutes
Consultation → 20 minutes

This value is used to compute appointment availability.


Treatment Stock Consumption
---------------------------

Some treatments consume inventory products.

Example:

Botox injection
    consumes 0.5 vial

Laser session
    consumes cartridge usage


TreatmentStockRule

Fields:

treatment_id
product_id
quantity


Multi-Session Treatments
------------------------

Some treatments are sold as packages.

Example:

Laser hair removal
6 sessions

When sold, these create a:

TreatmentPlan


TreatmentPlan Execution
-----------------------

TreatmentPlan

Tracks number of sessions.

Fields:

total_sessions
completed_sessions
remaining_sessions


Practitioner Capability
-----------------------

Not all practitioners can perform all treatments.

PractitionerTreatment

Fields:

practitioner_id
treatment_id
is_certified


Design Principles
-----------------

The treatment catalog must remain simple but flexible.

Rules:

• treatments belong to LegalEntity
• treatments may require stock
• treatments may be used in packages
• treatments may be disabled without deleting history