CODE STYLE GUIDELINES

TypeScript
----------

UUIDs must always be typed as string.

Example:

id: string


Backend Models
--------------

Business logic should live in:

• model methods
• service layer

Avoid large viewset logic.


Naming Conventions
------------------

Use explicit domain names.

Example:

EncounterTreatment
TreatmentPlanSession


Avoid abbreviations.


API Design
----------

Use RESTful endpoints.

Examples:

GET /patients
POST /encounters
POST /proposals/{id}/accept


Testing
-------

All business rules must have tests.

Use pytest.


Comments
--------

Explain domain logic.

Avoid trivial comments.