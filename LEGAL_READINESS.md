# Legal Entity & French Invoicing Readiness

**Status**: 🟡 Data Model Ready / Fiscal Logic Deferred  
**Date**: 2025-12-22  
**Purpose**: Document current legal infrastructure and path to French compliance

---

## 📋 TL;DR

✅ **What We Have**: Legal entity master data model  
❌ **What We Don't Have**: Fiscal calculation, legal numbering, compliant invoices  
🎯 **Goal**: Separate "legal fact" from "fiscal behavior" for clean architecture  

---

## 🎯 Purpose of This Document

This document explains:
1. What `LegalEntity` represents and why it exists NOW
2. What fiscal features are explicitly deferred and why
3. How future French invoicing compliance will be added
4. Relationship between Legal, Clinical, and Sales domains

**Audience**: Developers, Product Managers, Accountants, Auditors

---

## 🏛️ Legal Entity Model: What It IS

### Core Concept

`LegalEntity` represents **the establishment that issues commercial documents** (receipts, invoices in future).

**Think of it as**: Digital identity card for the business.

### Current Implementation

**Location**: `apps/legal/models.py`

**Fields**:
```python
# Identification
legal_name          # Raison sociale (e.g., "Clinique Dermatologique Paris SAS")
trade_name          # Nom commercial (e.g., "DermaCare Paris")

# Address (required for invoices)
address_line_1      # "123 Avenue des Champs-Élysées"
address_line_2      # "Bâtiment A, 3ème étage" (optional)
postal_code         # "75008"
city                # "Paris"
country_code        # "FR" (ISO 3166-1)

# French Business Identifiers (nullable - can be added later)
siren               # 9 digits - Company ID
siret               # 14 digits - Establishment ID
vat_number          # "FR12345678901" - Intra-community VAT

# Operational Settings
currency            # "EUR" (ISO 4217)
timezone            # "Europe/Paris" (IANA)
invoice_footer_text # Optional legal notices

# Status
is_active           # Can this entity issue new documents?
```

### What You CAN Do With LegalEntity

✅ **Master Data Management**:
- View legal entity details in Django Admin
- Update address, identifiers, footer text
- Activate/deactivate entity

✅ **Association with Sales**:
- Every `Sale` references a `LegalEntity`
- Query sales by legal entity: `Sale.objects.filter(legal_entity=entity)`

✅ **Display Information**:
- Show entity name on receipts (future)
- Show address on invoices (future)
- Show SIRET on documents (future)

### What You CANNOT Do With LegalEntity

❌ **Calculate Taxes**: No TVA calculation logic  
❌ **Generate Invoice Numbers**: No sequential numbering  
❌ **Create PDFs**: No document generation  
❌ **Validate Fiscal Rules**: No exemption logic  
❌ **Report to Tax Authority**: No fiscal reporting  

---

## 🚫 What Legal Entity Is NOT

### Not a Tax Calculator

```python
# ❌ THIS DOES NOT EXIST (and should not be added to LegalEntity)
entity.calculate_tva(amount)  # NO
entity.get_tax_rate(product)  # NO
entity.apply_exemption(sale)  # NO
```

**Why Not?**: Tax logic belongs in separate fiscal module (future `apps.fiscal`)

### Not an Invoice Generator

```python
# ❌ THIS DOES NOT EXIST
entity.create_invoice(sale)          # NO
entity.get_next_invoice_number()     # NO
entity.generate_pdf(invoice)         # NO
```

**Why Not?**: Invoicing is complex (numbering, PDF, email) and deferred

### Not a Fiscal Period Manager

```python
# ❌ THIS DOES NOT EXIST
entity.get_current_fiscal_period()   # NO
entity.close_fiscal_month()          # NO
entity.generate_tvadeclaration()     # NO
```

**Why Not?**: Accounting/fiscal periods are separate concern

---

## 🔗 Relationships with Other Domains

### Legal ↔ Sales

```python
# Every sale MUST reference a legal entity
sale = Sale.objects.get(id=sale_id)
print(sale.legal_entity.legal_name)      # ✅ Works
print(sale.legal_entity.full_address)    # ✅ Works

# Query sales by entity
entity_sales = Sale.objects.filter(legal_entity=entity)
```

**Why**: Future invoices need to know who issued the sale

**Current Behavior**: All existing sales assigned to default entity via data migration

### Legal ↔ Clinical

**Current**: NO direct relationship

**Future**: Might need relationship for:
- Determining which entity bills which patient (multi-establishment)
- Medical service tax exemptions (requires patient type, service type)

**Design Decision**: Keep separate until need is clear

### Legal ↔ Stock

**Current**: NO relationship

**Future**: Might need for:
- Multi-warehouse scenarios (each warehouse = different entity)
- Stock valuation by legal entity

**Design Decision**: Not needed now

---

## 🇫🇷 French Invoicing Compliance: Current vs. Future

### Current State (2025-12-22)

| Requirement | Status | Notes |
|------------|--------|-------|
| **Legal Entity Data** | ✅ Modeled | SIREN/SIRET/VAT fields exist (nullable) |
| **Sale → Entity Link** | ✅ Implemented | FK from Sale to LegalEntity |
| **Admin Interface** | ✅ Available | Master data management only |
| **TVA Calculation** | ❌ Not Implemented | Explicitly deferred |
| **Invoice Numbering** | ❌ Not Implemented | No sequence management |
| **PDF Generation** | ❌ Not Implemented | No templates, no rendering |
| **Medical Exemptions** | ❌ Not Implemented | No tax exemption rules |
| **Legal Archiving** | ❌ Not Implemented | No 10-year retention |
| **Electronic Invoicing** | ❌ Not Implemented | No Chorus Pro integration |

### Path to French Compliance

#### Phase 1: Data Model (DONE ✅)

**Completed**:
- [x] LegalEntity model with French identifiers
- [x] Sale → LegalEntity relationship
- [x] Default entity data migration
- [x] Admin interface

**Deliverable**: Single source of truth for legal entity data

#### Phase 2: Fiscal Logic (FUTURE ❌)

**To Implement** (when invoicing is needed):

1. **Tax Rates Module** (`apps.fiscal.models.TaxRate`):
   ```python
   class TaxRate:
       name = "TVA 20%"
       rate = 0.20
       valid_from = date(2014, 1, 1)
       valid_to = None
       applies_to = ["products", "general_services"]
   ```

2. **Tax Exemptions** (`apps.fiscal.models.TaxExemption`):
   ```python
   class TaxExemption:
       code = "MED_EXEMPT"  # Medical services Article 261-4
       description = "Soins médicaux dispensés par médecins"
       applies_to_services = ["consultation", "surgery"]
   ```

3. **Tax Calculator Service** (`apps.fiscal.services.TaxCalculator`):
   ```python
   calculator = TaxCalculator(legal_entity=entity)
   result = calculator.calculate(
       amount_ht=100.00,
       product_type="cosmetic_product"
   )
   # Returns: {amount_ht: 100, tva: 20, amount_ttc: 120}
   ```

**Estimated Effort**: 2-3 weeks

**Blocked By**: Need accountant input on:
- Which services qualify for medical exemption?
- How to handle mixed transactions (medical + cosmetic)?
- Which accounting software to integrate with?

#### Phase 3: Legal Invoicing (FUTURE ❌)

**To Implement**:

1. **Invoice Number Sequence** (`apps.invoicing.models.InvoiceSequence`):
   ```python
   class InvoiceSequence:
       year = 2025
       prefix = "FA-2025-"
       last_number = 1247
       
       def get_next():
           # Atomically increment
           # Validate no gaps
           # Return "FA-2025-1248"
   ```

2. **Legal Invoice Model** (`apps.invoicing.models.Invoice`):
   ```python
   class Invoice:
       number = "FA-2025-1248"  # Séquentiel chronologique
       issue_date = date(2025, 12, 22)
       due_date = date(2026, 1, 22)
       legal_entity = FK(LegalEntity)  # Issuer
       client_name = "Mme. Dupont"
       client_address = "..."
       lines = JSONField([
           {product: "Consultation", qty: 1, price_ht: 80, tva_rate: 0, tva: 0},
           {product: "Crème", qty: 2, price_ht: 50, tva_rate: 0.20, tva: 10}
       ])
       total_ht = 180.00
       total_tva = 10.00
       total_ttc = 190.00
       pdf_path = "invoices/2025/12/FA-2025-1248.pdf"
   ```

3. **PDF Generator** (`apps.invoicing.services.InvoicePDFGenerator`):
   - Template with legal entity header
   - Line items with TVA breakdown
   - Mentions légales (late payment penalties, etc.)
   - Digital signature (future)

**Estimated Effort**: 3-4 weeks

**Blocked By**: Need decisions on:
- PDF library (WeasyPrint, ReportLab, xhtml2pdf)?
- Invoice template design
- Email delivery vs. patient portal download
- Electronic signature requirements

#### Phase 4: Electronic Invoicing (FUTURE ❌)

**Context**: French law requires electronic B2B invoicing:
- 2024: Large companies
- 2025: Medium companies
- 2026: Small companies (likely applies to clinic)

**To Implement**:
- Chorus Pro integration (government platform)
- UBL or Factur-X format
- Real-time validation
- Archiving for 10 years

**Estimated Effort**: 4-6 weeks (after Phase 2 & 3)

**Blocked By**:
- Clinic's company size classification
- Accountant's preferred electronic invoicing platform
- Government certification requirements

---

## 📊 Architecture Diagram

### Current State

```
┌─────────────────────────────────────────────────────────────┐
│                         Django Backend                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │ LegalEntity  │◄────────│    Sale      │                  │
│  │ (Master Data)│  FK     │ (Transaction)│                  │
│  └──────────────┘         └──────────────┘                  │
│         │                        │                           │
│         │ No Fiscal Logic        │ No Invoice Logic          │
│         │ No Numbering           │ Just Sale Data            │
│         │                        │                           │
│         └────────────────────────┘                           │
│                                                               │
│  Status: ✅ Data Model Only                                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Future State (Phase 2 + 3)

```
┌─────────────────────────────────────────────────────────────┐
│                         Django Backend                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐                                            │
│  │ LegalEntity  │◄──────────────────┐                        │
│  │ (Master Data)│                   │                        │
│  └──────────────┘                   │ FK                     │
│         ▲                            │                        │
│         │                            │                        │
│         │ References                 │                        │
│         │                            │                        │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │   Invoice    │◄────────│    Sale      │                  │
│  │  (Legal Doc) │ Creates │ (Transaction)│                  │
│  └──────────────┘         └──────────────┘                  │
│         │                        │                           │
│         │ Uses                   │ Uses                      │
│         ▼                        ▼                           │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │ InvoiceSeq   │         │ TaxCalculator│                  │
│  │ (Numbering)  │         │ (Fiscal Logic)│                 │
│  └──────────────┘         └──────────────┘                  │
│                                  │                           │
│                                  │ Uses                      │
│                                  ▼                           │
│                           ┌──────────────┐                  │
│                           │  TaxRate     │                  │
│                           │  TaxExemption│                  │
│                           └──────────────┘                  │
│                                                               │
│  Status: ❌ Not Implemented (Future Work)                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Guardrails: Preventing Scope Creep

### Code-Level Protection

**In `apps/legal/models.py`**:
```python
"""
⚠️ CRITICAL: NO FISCAL LOGIC HERE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This module contains ONLY legal entity data structures.
DO NOT add:
- TVA/VAT calculation logic
- Tax exemption rules
- Invoice numbering schemes
- PDF generation logic
- Fiscal reporting logic

See: docs/decisions/ADR-002-legal-entity-minimal.md
See: LEGAL_READINESS.md
"""
```

### Documentation Cross-References

- Model docstrings link to ADR-002
- Admin comments emphasize "master data only"
- This document (`LEGAL_READINESS.md`) explains boundaries

### Code Review Checklist

When reviewing PRs touching `apps.legal`:

- [ ] Does it add fiscal calculation? → ❌ Reject, move to `apps.fiscal`
- [ ] Does it add invoice numbering? → ❌ Reject, move to `apps.invoicing`
- [ ] Does it add PDF generation? → ❌ Reject, move to `apps.invoicing`
- [ ] Is it master data (name, address, identifiers)? → ✅ OK
- [ ] Does it reference ADR-002? → ✅ Required

---

## 🔍 How to Verify Current State

### Check LegalEntity Exists

```bash
cd apps/api
python manage.py shell

from apps.legal.models import LegalEntity

# Should exist and have one entity
entities = LegalEntity.objects.all()
print(f"Found {entities.count()} legal entity(ies)")

# Default entity should exist
default = LegalEntity.objects.first()
print(f"Legal Name: {default.legal_name}")
print(f"Country: {default.country_code}")
print(f"Currency: {default.currency}")
```

### Check Sale → LegalEntity Relationship

```bash
from apps.sales.models import Sale

# All sales should have legal_entity
sales_without_entity = Sale.objects.filter(legal_entity__isnull=True).count()
print(f"Sales without legal entity: {sales_without_entity}")  # Should be 0

# Query sales by entity
entity = LegalEntity.objects.first()
entity_sales = entity.sales.all()
print(f"Sales for {entity.legal_name}: {entity_sales.count()}")
```

### Check NO Fiscal Logic

```bash
# These should NOT exist:
from apps.legal.models import TaxRate          # ❌ ImportError (correct!)
from apps.legal.models import TaxExemption     # ❌ ImportError (correct!)
from apps.legal.models import InvoiceSequence  # ❌ ImportError (correct!)

# LegalEntity should have NO methods like:
entity = LegalEntity.objects.first()
entity.calculate_tva()         # ❌ AttributeError (correct!)
entity.get_next_invoice_number()  # ❌ AttributeError (correct!)
```

---

## 📚 Frequently Asked Questions

### Q: Why not implement full invoicing now?

**A**: Three reasons:
1. **Complexity**: French fiscal rules are extensive (takes 3-4 weeks)
2. **Uncertainty**: Don't know accountant requirements yet
3. **Focus**: Team prioritizing clinical domain

By modeling legal entity NOW, we avoid refactoring 1000+ sales later.

### Q: Can I issue legal invoices with current system?

**A**: ❌ **NO**. Current system lacks:
- TVA calculation
- Legal sequential numbering
- Required invoice fields (client address, line item details, etc.)
- PDF generation
- 10-year archiving

**Current System**: Receipts/proofs of sale only (not legal invoices)

### Q: When will invoicing be ready?

**A**: Depends on business priorities. Estimated timeline:
- Phase 2 (Fiscal Logic): 2-3 weeks
- Phase 3 (Legal Invoicing): 3-4 weeks
- **Total**: 5-7 weeks after start

**Blocker**: Need accountant input on exemptions and integration requirements

### Q: What if I need multiple establishments?

**A**: Model already supports it!

```python
# Create second entity
entity2 = LegalEntity.objects.create(
    legal_name="Clinique Paris 15ème",
    address_line_1="...",
    siret="12345678901235",  # Different SIRET
    ...
)

# Assign specific sales to entity2
sale.legal_entity = entity2
sale.save()
```

**Missing**: UI for selecting entity per sale (future work)

### Q: What about medical service tax exemptions?

**A**: Not implemented yet (Phase 2).

French medical services CAN be exempt from TVA under Article 261-4 of Code Général des Impôts, BUT:
- Requires specific conditions (practitioner qualifications, service type)
- Needs accountant confirmation for this clinic
- Deferred until fiscal module is built

### Q: How does this relate to accounting software?

**A**: LegalEntity is independent of accounting software.

**Future Integration Path**:
- Export sales/invoices to CSV
- Import into accountant's software (e.g., Ciel, Sage, QuickBooks)
- OR: Direct API integration (if accountant uses cloud software)

**Not Blocking**: Accountant can manually enter for now

---

## 🎯 Success Criteria

### Current Phase (Data Model) ✅

- [x] LegalEntity model exists with all required fields
- [x] Sale → LegalEntity FK exists
- [x] Default entity created via data migration
- [x] Admin interface available
- [x] NO fiscal logic in LegalEntity
- [x] Documentation (ADR-002, this doc) complete

### Future Phase 2 (Fiscal Logic) ❌

- [ ] TaxRate model with date-based rates
- [ ] TaxExemption model with medical service rules
- [ ] TaxCalculator service with unit tests
- [ ] Accountant approval of exemption logic
- [ ] Integration tests with real-world scenarios

### Future Phase 3 (Legal Invoicing) ❌

- [ ] InvoiceSequence with gap detection
- [ ] Invoice model with all legally required fields
- [ ] PDF generator with approved template
- [ ] Email delivery system
- [ ] 10-year archiving solution
- [ ] Compliance review by accountant/lawyer

---

## 📞 Who to Ask

### Technical Questions

**LegalEntity model, admin, migrations**:
- Check: `apps/legal/models.py` docstrings
- Check: ADR-002
- Ask: Development team

### Business/Fiscal Questions

**Tax rates, exemptions, invoice requirements**:
- Ask: Clinic's accountant/comptable
- Reference: Code Général des Impôts Articles 261-4, 289
- Reference: BOFiP documentation

### Compliance Questions

**Legal invoice requirements, archiving, electronic invoicing**:
- Ask: Clinic's accountant or legal counsel
- Check: ADR-002 (French regulations quick reference)

---

## 📅 Timeline & Next Steps

### ✅ Completed (2025-12-22)

- LegalEntity data model
- Sale relationship
- Admin interface
- Documentation (ADR-002, this doc)

### ⏳ Pending (Priority TBD)

1. **Phase 2: Fiscal Logic** (2-3 weeks)
   - Prerequisite: Accountant meeting to clarify exemptions
   - Deliverable: Tax calculation with unit tests

2. **Phase 3: Legal Invoicing** (3-4 weeks)
   - Prerequisite: Phase 2 complete
   - Deliverable: PDF invoices with sequential numbering

3. **Phase 4: Electronic Invoicing** (4-6 weeks)
   - Prerequisite: Phase 3 complete + government mandate timeline
   - Deliverable: Chorus Pro integration

---

## 🔗 Related Documentation

- **ADR-002**: `docs/decisions/ADR-002-legal-entity-minimal.md` (full architectural decision)
- **STABILITY.md**: `docs/STABILITY.md` (current system status)
- **Model Code**: `apps/legal/models.py` (implementation with docstrings)
- **Admin Code**: `apps/legal/admin.py` (admin interface)

---

**Last Updated**: 2025-12-22  
**Status**: Data Model Ready, Fiscal Logic Deferred  
**Next Review**: When invoicing requirements are clarified  
**Maintainer**: Development Team
