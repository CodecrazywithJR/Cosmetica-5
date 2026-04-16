INVENTORY MODEL

Purpose
-------

Inventory tracks products used during treatments.


Examples
--------

Botox vial
Dermal filler syringe
Laser cartridge


Product
-------

Represents physical product.

Fields:

id
name
sku
description
is_active


Stock Location
--------------

Represents storage location.

Examples:

Main clinic storage
Procedure room
Pharmacy cabinet


Stock Movement
--------------

Tracks inventory changes.

Movement types:

IN
OUT
ADJUSTMENT


Example Movements
-----------------

Stock purchase → IN
Treatment consumption → OUT
Manual correction → ADJUSTMENT


Stock Consumption
-----------------

Treatments may consume products.

Example:

Botox injection
→ consumes 0.5 vial


Traceability
------------

All stock movements must be traceable.

Stock history must never be deleted.