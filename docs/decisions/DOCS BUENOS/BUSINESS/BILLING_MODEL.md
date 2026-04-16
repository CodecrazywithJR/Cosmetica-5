BILLING MODEL

Purpose
-------

The billing model manages commercial transactions between clinic and patient.


Commercial Workflow
-------------------

Consultation
↓
Proposal
↓
Patient accepts
↓
Sale
↓
Invoice
↓
Payment


Proposal
--------

Represents an offer made to a patient.

Contains:

• treatments
• quantities
• pricing


Proposal States
---------------

draft
sent
accepted
cancelled
expired


Sale
----

Created when proposal is accepted.

Represents commercial transaction.


Invoice
-------

Legal fiscal document.

Generated from Sale.


Payment
-------

Represents money received.

May include:

• cash
• card
• bank transfer


Refunds
-------

Refunds reverse financial transactions.


Design Rules
------------

• proposals originate from encounters
• accepting a proposal creates a sale
• billing events generate accounting entries