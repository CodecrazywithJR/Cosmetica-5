# ADR-002: Minimal Legal Entity Model (No Fiscal Logic)

**Status**: ✅ Accepted and Implemented  
**Date**: 2025-12-22  
**Decision Makers**: Development Team  
**Supersedes**: N/A  
**Related**: `LEGAL_READINESS.md`, `docs/STABILITY.md`

---

## Context

### Business Context

The clinic is located in **France** and will need to issue legal invoices compliant with French regulations (Code Général des Impôts) in the future. However, the team is currently focused on the **clinical domain** and does not want to be blocked by complex fiscal implementation.

### Technical Context

- Backend: Django 4.2.8 + Django REST Framework
- Current stable domains: Sales, Stock, Refunds, Observability, Clinical
- Sales model exists but has no legal entity association
- Risk: If legal structure is not modeled now, future fiscal compliance will require major refactoring

### Problem Statement

**Tension**: We need to model the "legal fact" (who issues the document) NOW, but we explicitly DO NOT want to implement fiscal behavior (TVA calculation, legal numbering, exemptions, PDF generation) YET.

**Question**: How do we prepare for future French invoicing compliance without implementing complex fiscal logic today?

---

## Decision

**We will create a minimal `LegalEntity` model that represents ONLY the legal issuer data, with ZERO fiscal logic.**

### Scope: What We ARE Building

✅ **Legal Entity Master Data**:
- Legal identification (raison sociale, nom commercial)
- Address (required for invoices)
- French business identifiers (SIREN, SIRET, VAT number) as nullable fields
- Operational settings (currency, timezone)
- Document customization (footer text)

✅ **Relationship to Sales**:
- `Sale.legal_entity` ForeignKey (required)
- Data migration to assign default legal entity to existing sales

✅ **Admin Interface**:
- Basic Django Admin for master data management
- NO invoice generation from admin

### Scope: What We Are NOT Building

❌ **NO Fiscal Logic**:
- NO TVA/VAT calculation
- NO tax exemption rules (medical services, etc.)
- NO fiscal rate management
- NO tax reporting

❌ **NO Invoice Numbering**:
- NO legal numbering sequences
- NO chronological validation
- NO gap detection
- NO certification/timestamp

❌ **NO Document Generation**:
- NO PDF generation
- NO invoice templates
- NO receipt printing
- NO email sending

❌ **NO Accounting Integration**:
- NO double-entry bookkeeping
- NO chart of accounts
- NO fiscal periods
- NO audit trail requirements (beyond basic Django audit)

---

## Rationale

### Why Model Legal Entity Now?

1. **Future-Proofing Without Blocking**: Clinical domain can advance while legal structure is in place
2. **Prevent Major Refactoring**: Adding legal entity to 1000+ sales records later is painful
3. **Single Source of Truth**: Centralized legal entity data (not scattered in settings/config)
4. **Explicit Deferral**: By modeling the entity WITHOUT fiscal logic, we make the split explicit

### Why NOT Implement Fiscal Logic Now?

1. **Complexity**: French fiscal rules are extensive (TVA rates, exemptions, professional status, etc.)
2. **Risk of Over-Engineering**: We don't yet know exact requirements (accountant preferences, software integration)
3. **Focus**: Team is focused on clinical domain - fiscal can wait
4. **Regulatory Changes**: French tax law changes annually; implementing too early = more maintenance

### Design Principles

1. **Data, Not Behavior**: LegalEntity stores facts, not business rules
2. **Nullable Identifiers**: SIREN/SIRET/VAT can be null (gradual data entry)
3. **Single Entity Assumption**: Initially one entity (multi-entity is possible future extension)
4. **No Magic**: No automatic numbering, no hidden state machines

---

## Consequences

### Positive

✅ **Clinical Domain Unblocked**: No need to wait for fiscal implementation  
✅ **Clean Architecture**: Legal and fiscal concerns separated  
✅ **Future Flexibility**: Can add fiscal behavior without changing legal model  
✅ **Gradual Adoption**: SIREN/SIRET can be added when available  
✅ **Clear Boundaries**: Comments and docs make scope explicit  

### Negative/Risks

⚠️ **Incomplete Solution**: Invoices cannot be legally issued yet (THIS IS INTENTIONAL)  
⚠️ **Developer Confusion**: Devs might try to add fiscal logic to this model (MITIGATED: warnings in code/docs)  
⚠️ **Future Work Required**: Eventually need separate fiscal module (THIS IS THE PLAN)  

### Neutral

🔹 **Single Entity**: Multi-establishment clinics will need enhancement (not a current requirement)  
🔹 **No API Exposure**: Only admin access (frontend integration deferred)  

---

## Alternatives Considered

### Alternative 1: Implement Full French Fiscal Compliance Now

**Description**: Build complete TVA calculation, legal numbering, PDF generation, etc.

**Rejected Because**:
- ❌ Too complex for current needs
- ❌ Blocks clinical domain work
- ❌ Risk of over-engineering without knowing accountant requirements
- ❌ French tax law changes annually (premature optimization)

**Estimated Effort**: 3-4 weeks  
**Decision**: Not worth it for current stage

### Alternative 2: Defer Everything (No Legal Entity Model)

**Description**: Wait until invoicing is actually needed, then model everything

**Rejected Because**:
- ❌ Refactoring 1000+ sales records is painful
- ❌ Risk of forgetting legal structure exists
- ❌ Forces fiscal and legal concerns together (bad separation)
- ❌ No single source of truth for legal entity data

**Risk**: High technical debt accumulation

### Alternative 3: Use Django Sites Framework

**Description**: Use `django.contrib.sites` to represent legal entity

**Rejected Because**:
- ❌ Sites framework is for multi-domain websites, not legal entities
- ❌ No fields for SIREN/SIRET/VAT
- ❌ No invoice-specific fields
- ❌ Wrong abstraction level

### Alternative 4: Store Legal Entity Data in Settings

**Description**: Keep legal entity data in Django settings or environment variables

**Rejected Because**:
- ❌ Not a database model (can't FK from Sale)
- ❌ No audit trail
- ❌ No admin interface
- ❌ Hard to extend to multi-entity

---

## Implementation

### Model Structure

```python
class LegalEntity(models.Model):
    # Identification
    legal_name          # Raison sociale
    trade_name          # Nom commercial (optional)
    
    # Address (required for invoices)
    address_line_1
    address_line_2      # Optional
    postal_code
    city
    country_code        # ISO 3166-1 (default: FR)
    
    # French identifiers (nullable - gradual adoption)
    siren               # 9 digits, unique
    siret               # 14 digits, unique
    vat_number          # Numéro TVA intracommunautaire
    
    # Operational
    currency            # ISO 4217 (default: EUR)
    timezone            # IANA (default: Europe/Paris)
    invoice_footer_text # Optional legal text
    
    # Status
    is_active           # Boolean
    created_at / updated_at
```

### Relationship to Sales

```python
class Sale(models.Model):
    legal_entity = models.ForeignKey(
        'legal.LegalEntity',
        on_delete=models.PROTECT,
        related_name='sales',
        help_text='Legal entity issuing this sale'
    )
    # ... other fields
```

### Data Migration

Migration `0002_create_default_entity.py` creates a default French entity:
- Legal Name: "Clinique (À compléter)"
- Address: Placeholder
- Country: FR
- Currency: EUR
- Timezone: Europe/Paris

Assigns this entity to all existing sales.

### Admin Interface

- List view: legal_name, trade_name, SIRET, city, is_active
- Filters: is_active, country_code
- Search: legal_name, trade_name, SIREN, SIRET, VAT, city
- Fieldsets: Identification, Address, French Identifiers, Operational, Status

**NO** invoice generation buttons or fiscal actions.

---

## Compliance & Audit Trail

### Traceability

**Documentation Links**:
- This ADR: `docs/decisions/ADR-002-legal-entity-minimal.md`
- Implementation Guide: `LEGAL_READINESS.md`
- Stability Document: `docs/STABILITY.md` (Legal Layer section)

**Model Documentation**:
- `apps/legal/models.py`: Extensive docstrings with warnings
- `apps/legal/admin.py`: Comments about NO fiscal logic

### Warnings in Code

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

### Review Checklist

- [x] LegalEntity model created with minimal fields
- [x] NO fiscal logic in model or admin
- [x] Sale.legal_entity FK added
- [x] Data migration creates default entity
- [x] Admin interface registered (master data only)
- [x] Extensive documentation in code
- [x] ADR created with full context
- [x] LEGAL_READINESS.md created
- [x] STABILITY.md updated

---

## Future Work

### When Fiscal Logic IS Needed

**Separate Module**: Create `apps.fiscal` or `apps.invoicing`

**New Models** (examples):
- `InvoiceSequence`: Legal numbering with gap detection
- `TaxRate`: TVA rates (20%, 10%, 5.5%, 0%) with date ranges
- `TaxExemption`: Medical service exemptions
- `FiscalPeriod`: Monthly/quarterly periods for reporting
- `Invoice`: Legal invoice (different from Sale)

**Keep LegalEntity Unchanged**: Fiscal logic references LegalEntity, but LegalEntity remains data-only

### Multi-Entity Extension

If clinic opens additional establishments:
- No model changes needed (already supports multiple entities)
- Need UI for selecting legal entity per sale
- Need logic for determining which entity issues invoice (based on patient address, service type, etc.)

### API Exposure

Currently NO public API. When needed:
- Read-only endpoint: `GET /api/v1/legal-entities/` (for POS entity selection)
- Admin-only write operations
- NO create/delete via API (master data management only)

---

## References

### Internal Documentation

- [LEGAL_READINESS.md](../../LEGAL_READINESS.md) - Implementation guide
- [STABILITY.md](../STABILITY.md) - Current system state
- [ADR-001](./ADR-001-remove-legacy-patients-app.md) - Related architectural decision

### French Regulations (for future reference)

- **Code Général des Impôts (CGI)**: French tax code
  - Article 289: Invoice requirements
  - Article 271: TVA deductions
  
- **BOFiP (Bulletin Officiel des Finances Publiques)**: Tax administration guidelines
  - BOI-TVA-DECLA-30-20: Invoice content requirements
  
- **Ordonnance 2021-1189**: Electronic invoicing mandate (2024-2026 rollout)

**Note**: These are NOT implemented yet, just documented for future reference.

---

## Appendix: French Invoicing Quick Reference

### Required Invoice Elements (Future Implementation)

When fiscal logic IS implemented, French invoices must include:

**Issuer (LegalEntity provides these)**:
- ✅ Legal name (raison sociale)
- ✅ Legal address
- ✅ SIREN or SIRET
- ✅ VAT number (if applicable)

**Document**:
- ❌ Sequential invoice number (NOT YET IMPLEMENTED)
- ❌ Issue date (NOT YET IMPLEMENTED)
- ❌ Due date (NOT YET IMPLEMENTED)

**Client**:
- ❌ Client name and address (NOT YET IMPLEMENTED)

**Content**:
- ❌ Detailed line items (NOT YET IMPLEMENTED)
- ❌ Unit prices (NOT YET IMPLEMENTED)
- ❌ TVA rates and amounts (NOT YET IMPLEMENTED)
- ❌ Total HT, TVA, TTC (NOT YET IMPLEMENTED)

**Special Cases**:
- ❌ Medical service exemptions (NOT YET IMPLEMENTED)
- ❌ Reverse charge mechanism (NOT YET IMPLEMENTED)

---

**Last Updated**: 2025-12-22  
**Status**: Accepted and Implemented  
**Next Review**: When invoicing requirements are clarified
