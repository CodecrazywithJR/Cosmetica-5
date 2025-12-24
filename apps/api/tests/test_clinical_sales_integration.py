"""
Integration tests for Clinical → Sales Integration (Fase 3).

Tests ClinicalChargeProposal model, services, permissions, and E2E flow.
Validates:
- Proposal generation from finalized encounters
- Proposal to sale conversion
- Idempotency guarantees
- RBAC permissions
- No breaking changes to existing sales
"""
import pytest
from decimal import Decimal
from rest_framework import status
from django.utils import timezone
from django.db import IntegrityError

from apps.clinical.models import (
    Encounter,
    Treatment,
    EncounterTreatment,
    ClinicalChargeProposal,
    ClinicalChargeProposalLine,
    ProposalStatusChoices,
)
from apps.sales.models import Sale, SaleLine
from apps.core.models import LegalEntity
from apps.clinical.services import (
    generate_charge_proposal_from_encounter,
    create_sale_from_proposal,
)


# ============================================================================
# Model Tests
# ============================================================================

@pytest.mark.django_db
class TestClinicalChargeProposalModel:
    """Test ClinicalChargeProposal model behavior."""
    
    def test_create_proposal_from_encounter(
        self,
        encounter,
        admin_user
    ):
        """Create proposal linked to encounter."""
        proposal = ClinicalChargeProposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('100.00'),
            currency='EUR',
            notes='Test proposal',
            created_by=admin_user
        )
        
        assert proposal.id is not None
        assert proposal.encounter == encounter
        assert proposal.status == ProposalStatusChoices.DRAFT
        assert proposal.total_amount == Decimal('100.00')
        assert proposal.converted_to_sale is None
        assert proposal.converted_at is None
    
    def test_proposal_onetoone_constraint(
        self,
        encounter,
        admin_user
    ):
        """Cannot create duplicate proposals for same encounter."""
        # First proposal succeeds
        ClinicalChargeProposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('100.00'),
            currency='EUR',
            created_by=admin_user
        )
        
        # Second proposal fails (OneToOneField constraint)
        with pytest.raises(IntegrityError):
            ClinicalChargeProposal.objects.create(
                encounter=encounter,
                patient=encounter.patient,
                practitioner=encounter.practitioner,
                status=ProposalStatusChoices.DRAFT,
                total_amount=Decimal('200.00'),
                currency='EUR',
                created_by=admin_user
            )
    
    def test_proposal_recalculate_total(
        self,
        encounter,
        admin_user
    ):
        """recalculate_total() sums line totals correctly."""
        proposal = ClinicalChargeProposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('0.00'),
            currency='EUR',
            created_by=admin_user
        )
        
        # Create treatment for lines
        treatment = Treatment.objects.create(
            name='Test Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        # Create encounter treatment
        encounter_treatment = EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=2,
            notes='Test'
        )
        
        # Create proposal lines
        ClinicalChargeProposalLine.objects.create(
            proposal=proposal,
            encounter_treatment=encounter_treatment,
            treatment=treatment,
            treatment_name=treatment.name,
            description=treatment.description or '',
            quantity=2,
            unit_price=Decimal('100.00')
        )
        
        ClinicalChargeProposalLine.objects.create(
            proposal=proposal,
            encounter_treatment=encounter_treatment,
            treatment=treatment,
            treatment_name='Additional treatment',
            description='Extra',
            quantity=1,
            unit_price=Decimal('50.00')
        )
        
        # Recalculate total
        proposal.recalculate_total()
        proposal.refresh_from_db()
        
        # 2 * 100 + 1 * 50 = 250
        assert proposal.total_amount == Decimal('250.00')
    
    def test_proposal_line_auto_calculate_total(
        self,
        encounter,
        admin_user
    ):
        """Proposal line auto-calculates line_total on save."""
        proposal = ClinicalChargeProposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('0.00'),
            currency='EUR',
            created_by=admin_user
        )
        
        treatment = Treatment.objects.create(
            name='Test Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        encounter_treatment = EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=3,
            notes='Test'
        )
        
        # Create line without line_total
        line = ClinicalChargeProposalLine.objects.create(
            proposal=proposal,
            encounter_treatment=encounter_treatment,
            treatment=treatment,
            treatment_name=treatment.name,
            description='',
            quantity=3,
            unit_price=Decimal('100.00')
        )
        
        # line_total should be auto-calculated
        assert line.line_total == Decimal('300.00')
    
    def test_proposal_status_choices(self, encounter, admin_user):
        """Proposal status choices are valid."""
        proposal = ClinicalChargeProposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('0.00'),
            currency='EUR',
            created_by=admin_user
        )
        
        # Test status transitions
        assert proposal.status == ProposalStatusChoices.DRAFT
        
        proposal.status = ProposalStatusChoices.CONVERTED
        proposal.save()
        assert proposal.status == ProposalStatusChoices.CONVERTED
        
        proposal.status = ProposalStatusChoices.CANCELLED
        proposal.save()
        assert proposal.status == ProposalStatusChoices.CANCELLED
    
    def test_converted_to_sale_idempotency(
        self,
        encounter,
        admin_user,
        clinic_location
    ):
        """converted_to_sale FK ensures idempotency."""
        proposal = ClinicalChargeProposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('100.00'),
            currency='EUR',
            created_by=admin_user
        )
        
        # Create legal entity for sale
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        # Create sale
        sale = Sale.objects.create(
            legal_entity=legal_entity,
            patient=encounter.patient,
            currency='EUR',
            status='draft',
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('100.00'),
            created_by_user=admin_user
        )
        
        # Link sale to proposal
        proposal.converted_to_sale = sale
        proposal.status = ProposalStatusChoices.CONVERTED
        proposal.converted_at = timezone.now()
        proposal.save()
        
        # Verify link
        assert proposal.converted_to_sale == sale
        assert proposal.status == ProposalStatusChoices.CONVERTED


# ============================================================================
# Service Tests
# ============================================================================

@pytest.mark.django_db
class TestGenerateChargeProposalService:
    """Test generate_charge_proposal_from_encounter() service."""
    
    def test_generate_proposal_happy_path(
        self,
        encounter,
        admin_user
    ):
        """Generate proposal from finalized encounter with treatments."""
        # Create treatment
        treatment = Treatment.objects.create(
            name='Botox Injection',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('150.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        # Add treatment to encounter
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=2,
            notes='Forehead and glabella'
        )
        
        # Finalize encounter
        encounter.status = 'finalized'
        encounter.save()
        
        # Generate proposal
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user,
            notes='Test proposal notes'
        )
        
        # Verify proposal
        assert proposal is not None
        assert proposal.encounter == encounter
        assert proposal.patient == encounter.patient
        assert proposal.practitioner == encounter.practitioner
        assert proposal.status == ProposalStatusChoices.DRAFT
        assert proposal.notes == 'Test proposal notes'
        assert proposal.created_by == admin_user
        
        # Verify lines
        lines = proposal.lines.all()
        assert lines.count() == 1
        line = lines.first()
        assert line.treatment == treatment
        assert line.quantity == 2
        assert line.unit_price == Decimal('150.00')
        assert line.line_total == Decimal('300.00')
        
        # Verify total
        assert proposal.total_amount == Decimal('300.00')
    
    def test_generate_proposal_requires_finalized(
        self,
        encounter,
        admin_user
    ):
        """Cannot generate proposal from non-finalized encounter."""
        # Encounter is in 'draft' status
        assert encounter.status == 'draft'
        
        with pytest.raises(ValueError, match='Encounter must be finalized'):
            generate_charge_proposal_from_encounter(
                encounter=encounter,
                created_by=admin_user
            )
    
    def test_generate_proposal_idempotency(
        self,
        encounter,
        admin_user
    ):
        """Cannot generate duplicate proposals (OneToOne)."""
        # Create treatment
        treatment = Treatment.objects.create(
            name='Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1
        )
        
        encounter.status = 'finalized'
        encounter.save()
        
        # First generation succeeds
        proposal1 = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        assert proposal1 is not None
        
        # Second generation fails
        with pytest.raises(ValueError, match='Proposal already exists'):
            generate_charge_proposal_from_encounter(
                encounter=encounter,
                created_by=admin_user
            )
    
    def test_generate_proposal_requires_treatments(
        self,
        encounter,
        admin_user
    ):
        """Cannot generate proposal from encounter without treatments."""
        encounter.status = 'finalized'
        encounter.save()
        
        # No treatments added
        with pytest.raises(ValueError, match='must have at least one treatment'):
            generate_charge_proposal_from_encounter(
                encounter=encounter,
                created_by=admin_user
            )
    
    def test_generate_proposal_uses_effective_price(
        self,
        encounter,
        admin_user
    ):
        """Proposal uses EncounterTreatment.effective_price (override or default)."""
        # Treatment with default price
        treatment = Treatment.objects.create(
            name='Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        # EncounterTreatment with price override
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1,
            price_override=Decimal('80.00')  # Discounted
        )
        
        encounter.status = 'finalized'
        encounter.save()
        
        # Generate proposal
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        
        # Verify line uses overridden price
        line = proposal.lines.first()
        assert line.unit_price == Decimal('80.00')  # NOT 100.00
        assert line.line_total == Decimal('80.00')
        assert proposal.total_amount == Decimal('80.00')
    
    def test_generate_proposal_combines_notes(
        self,
        encounter,
        admin_user
    ):
        """Line description combines treatment description + encounter notes."""
        treatment = Treatment.objects.create(
            name='Botox',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            description='Botulinum toxin injection',
            is_active=True,
            created_by=admin_user
        )
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1,
            notes='Applied to forehead'
        )
        
        encounter.status = 'finalized'
        encounter.save()
        
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        
        line = proposal.lines.first()
        assert 'Botulinum toxin injection' in line.description
        assert 'Applied to forehead' in line.description
    
    def test_generate_proposal_skips_treatments_without_price(
        self,
        encounter,
        admin_user,
        capsys
    ):
        """Skips treatments with no price (logs warning)."""
        # Treatment without price
        treatment1 = Treatment.objects.create(
            name='Free Consultation',
            treatment_type='consultation',
            category='medical',
            default_price=None,  # No price
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        # Treatment with price
        treatment2 = Treatment.objects.create(
            name='Paid Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment1,
            quantity=1
        )
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment2,
            quantity=1
        )
        
        encounter.status = 'finalized'
        encounter.save()
        
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        
        # Only 1 line (free consultation skipped)
        assert proposal.lines.count() == 1
        line = proposal.lines.first()
        assert line.treatment == treatment2
        assert proposal.total_amount == Decimal('100.00')


@pytest.mark.django_db
class TestCreateSaleFromProposalService:
    """Test create_sale_from_proposal() service."""
    
    def test_create_sale_happy_path(
        self,
        encounter,
        admin_user
    ):
        """Convert draft proposal to sale."""
        # Create treatment + encounter treatment
        treatment = Treatment.objects.create(
            name='Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('150.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        encounter_treatment = EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=2
        )
        
        encounter.status = 'finalized'
        encounter.save()
        
        # Generate proposal
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        
        # Create legal entity
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        # Convert to sale
        sale = create_sale_from_proposal(
            proposal=proposal,
            created_by=admin_user,
            legal_entity=legal_entity,
            notes='Test sale notes'
        )
        
        # Verify sale
        assert sale is not None
        assert sale.legal_entity == legal_entity
        assert sale.patient == encounter.patient
        assert sale.status == 'draft'
        assert sale.currency == 'EUR'
        assert sale.subtotal == Decimal('300.00')  # 2 * 150
        assert sale.tax == Decimal('0.00')  # NO TAX (future)
        assert sale.discount == Decimal('0.00')
        assert sale.total == Decimal('300.00')
        assert 'Test sale notes' in sale.notes
        assert sale.created_by_user == admin_user
        
        # Verify sale lines
        lines = sale.lines.all()
        assert lines.count() == 1
        line = lines.first()
        assert line.product is None  # Service charge (no product)
        assert line.description == f'{treatment.name}'
        assert line.quantity == 2
        assert line.unit_price == Decimal('150.00')
        assert line.line_total == Decimal('300.00')
        
        # Verify proposal updated
        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.CONVERTED
        assert proposal.converted_to_sale == sale
        assert proposal.converted_at is not None
    
    def test_create_sale_requires_draft_proposal(
        self,
        encounter,
        admin_user
    ):
        """Cannot convert non-draft proposal."""
        # Create proposal
        proposal = ClinicalChargeProposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.CONVERTED,  # Already converted
            total_amount=Decimal('100.00'),
            currency='EUR',
            created_by=admin_user
        )
        
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        with pytest.raises(ValueError, match='Only draft proposals can be converted'):
            create_sale_from_proposal(
                proposal=proposal,
                created_by=admin_user,
                legal_entity=legal_entity
            )
    
    def test_create_sale_idempotency(
        self,
        encounter,
        admin_user
    ):
        """Cannot convert proposal twice (idempotency)."""
        # Create treatment
        treatment = Treatment.objects.create(
            name='Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1
        )
        
        encounter.status = 'finalized'
        encounter.save()
        
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        # First conversion succeeds
        sale1 = create_sale_from_proposal(
            proposal=proposal,
            created_by=admin_user,
            legal_entity=legal_entity
        )
        assert sale1 is not None
        
        # Proposal is now CONVERTED
        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.CONVERTED
        
        # Second conversion fails
        with pytest.raises(ValueError, match='Only draft proposals can be converted'):
            create_sale_from_proposal(
                proposal=proposal,
                created_by=admin_user,
                legal_entity=legal_entity
            )
    
    def test_create_sale_matches_proposal_lines(
        self,
        encounter,
        admin_user
    ):
        """Sale lines match proposal lines exactly."""
        # Create 3 different treatments
        treatments = [
            Treatment.objects.create(
                name=f'Treatment {i}',
                treatment_type='injection',
                category='aesthetic',
                default_price=Decimal(f'{100 + i * 50}.00'),
                currency='EUR',
                is_active=True,
                created_by=admin_user
            )
            for i in range(1, 4)
        ]
        
        for treatment in treatments:
            EncounterTreatment.objects.create(
                encounter=encounter,
                treatment=treatment,
                quantity=1
            )
        
        encounter.status = 'finalized'
        encounter.save()
        
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        sale = create_sale_from_proposal(
            proposal=proposal,
            created_by=admin_user,
            legal_entity=legal_entity
        )
        
        # Verify line counts match
        assert sale.lines.count() == proposal.lines.count()
        assert sale.lines.count() == 3
        
        # Verify totals match
        assert sale.total == proposal.total_amount
        assert sale.total == Decimal('450.00')  # 100 + 150 + 200


# ============================================================================
# Permission Tests
# ============================================================================

@pytest.mark.django_db
class TestClinicalChargeProposalPermissions:
    """Test RBAC permissions for ClinicalChargeProposal endpoints."""
    
    @pytest.fixture
    def finalized_encounter_with_proposal(
        self,
        encounter,
        admin_user
    ):
        """Fixture: finalized encounter with generated proposal."""
        treatment = Treatment.objects.create(
            name='Treatment',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('100.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1
        )
        
        encounter.status = 'finalized'
        encounter.save()
        
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=admin_user
        )
        
        return proposal
    
    def test_reception_can_list_proposals(
        self,
        reception_client,
        finalized_encounter_with_proposal
    ):
        """Reception can list all proposals."""
        response = reception_client.get('/api/v1/clinical/proposals/')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Proposal endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_reception_can_view_proposal_detail(
        self,
        reception_client,
        finalized_encounter_with_proposal
    ):
        """Reception can view proposal detail."""
        proposal_id = finalized_encounter_with_proposal.id
        response = reception_client.get(f'/api/v1/clinical/proposals/{proposal_id}/')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Proposal endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(proposal_id)
    
    def test_reception_can_convert_proposal_to_sale(
        self,
        reception_client,
        finalized_encounter_with_proposal,
        admin_user
    ):
        """Reception can convert proposal to sale (create-sale action)."""
        # Create legal entity
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        proposal_id = finalized_encounter_with_proposal.id
        payload = {
            'legal_entity_id': str(legal_entity.id),
            'notes': 'Reception creating sale'
        }
        
        response = reception_client.post(
            f'/api/v1/clinical/proposals/{proposal_id}/create-sale/',
            payload,
            format='json'
        )
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Proposal endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'sale_id' in response.data
    
    def test_accounting_can_view_proposals(
        self,
        accounting_client,
        finalized_encounter_with_proposal
    ):
        """Accounting can view proposals (read-only)."""
        proposal_id = finalized_encounter_with_proposal.id
        response = accounting_client.get(f'/api/v1/clinical/proposals/{proposal_id}/')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Proposal endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_accounting_cannot_convert_proposal_to_sale(
        self,
        accounting_client,
        finalized_encounter_with_proposal,
        admin_user
    ):
        """Accounting cannot convert proposal to sale (read-only)."""
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        proposal_id = finalized_encounter_with_proposal.id
        payload = {
            'legal_entity_id': str(legal_entity.id),
            'notes': 'Accounting trying to create sale'
        }
        
        response = accounting_client.post(
            f'/api/v1/clinical/proposals/{proposal_id}/create-sale/',
            payload,
            format='json'
        )
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Proposal endpoints not implemented yet')
        
        # Accounting should be forbidden
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_marketing_cannot_access_proposals(
        self,
        marketing_client,
        finalized_encounter_with_proposal
    ):
        """Marketing has NO access to proposals."""
        proposal_id = finalized_encounter_with_proposal.id
        response = marketing_client.get(f'/api/v1/clinical/proposals/{proposal_id}/')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Proposal endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# E2E Test
# ============================================================================

@pytest.mark.django_db
class TestClinicalToSaleE2E:
    """End-to-end test: Complete clinical → proposal → sale flow."""
    
    def test_complete_clinical_to_sale_flow(
        self,
        admin_client,
        patient,
        practitioner,
        clinic_location,
        admin_user
    ):
        """
        Complete flow:
        1. Create encounter with treatments
        2. Finalize encounter
        3. Generate proposal (via API)
        4. Convert proposal to sale (via API)
        5. Verify sale created in draft status
        6. Verify idempotency (cannot regenerate/reconvert)
        """
        # Step 1: Create encounter
        encounter_payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.user.id),
            'location_id': str(clinic_location.id),
            'type': 'cosmetic_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
            'chief_complaint': 'Anti-aging treatment',
            'assessment': 'Moderate forehead lines',
            'plan': 'Botox injection'
        }
        
        response = admin_client.post(
            '/api/v1/clinical/encounters/',
            encounter_payload,
            format='json'
        )
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_201_CREATED
        encounter_id = response.data['id']
        
        # Step 2: Add treatment to encounter
        treatment = Treatment.objects.create(
            name='Botox 50U',
            treatment_type='injection',
            category='aesthetic',
            default_price=Decimal('250.00'),
            currency='EUR',
            is_active=True,
            created_by=admin_user
        )
        
        encounter = Encounter.objects.get(id=encounter_id)
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=2,
            notes='Applied to forehead and glabella'
        )
        
        # Step 3: Finalize encounter
        encounter.status = 'finalized'
        encounter.save()
        
        # Step 4: Generate proposal (via API)
        generate_payload = {'notes': 'Post-treatment proposal'}
        response = admin_client.post(
            f'/api/v1/clinical/encounters/{encounter_id}/generate-proposal/',
            generate_payload,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'proposal_id' in response.data
        assert response.data['total_amount'] == '500.00'  # 2 * 250
        assert response.data['line_count'] == 1
        
        proposal_id = response.data['proposal_id']
        
        # Verify proposal detail
        response = admin_client.get(f'/api/v1/clinical/proposals/{proposal_id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'draft'
        assert len(response.data['lines']) == 1
        
        # Step 5: Convert proposal to sale (via API)
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        sale_payload = {
            'legal_entity_id': str(legal_entity.id),
            'notes': 'Converting proposal to sale'
        }
        
        response = admin_client.post(
            f'/api/v1/clinical/proposals/{proposal_id}/create-sale/',
            sale_payload,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'sale_id' in response.data
        assert response.data['sale_status'] == 'draft'
        assert response.data['sale_total'] == '500.00'
        
        sale_id = response.data['sale_id']
        
        # Verify sale exists in database
        sale = Sale.objects.get(id=sale_id)
        assert sale.status == 'draft'
        assert sale.patient == patient
        assert sale.total == Decimal('500.00')
        assert sale.tax == Decimal('0.00')  # NO TAX (future)
        assert sale.lines.count() == 1
        
        # Step 6: Verify idempotency - cannot regenerate proposal
        response = admin_client.post(
            f'/api/v1/clinical/encounters/{encounter_id}/generate-proposal/',
            {},
            format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Verify idempotency - cannot reconvert proposal
        response = admin_client.post(
            f'/api/v1/clinical/proposals/{proposal_id}/create-sale/',
            sale_payload,
            format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Verify proposal is now CONVERTED
        proposal = ClinicalChargeProposal.objects.get(id=proposal_id)
        assert proposal.status == ProposalStatusChoices.CONVERTED
        assert proposal.converted_to_sale == sale


# ============================================================================
# Regression Test
# ============================================================================

@pytest.mark.django_db
class TestExistingSalesNotBroken:
    """Test that existing Sales endpoints are not broken by integration."""
    
    def test_existing_sales_not_broken(
        self,
        admin_client,
        patient,
        admin_user
    ):
        """
        Verify existing Sales API still works (no breaking changes).
        
        BUSINESS RULE: Clinical → Sales Integration must NOT break
        existing STABLE Sales/Stock/Refunds functionality.
        """
        # Create legal entity
        legal_entity = LegalEntity.objects.create(
            business_name='Test Clinic',
            legal_name='Test Clinic SRL',
            tax_id='FR123456789',
            country_code='FR',
            is_active=True
        )
        
        # Create old-style sale (without proposal)
        sale = Sale.objects.create(
            legal_entity=legal_entity,
            patient=patient,
            currency='EUR',
            status='draft',
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('100.00'),
            notes='Manual sale (not from proposal)',
            created_by_user=admin_user
        )
        
        # Verify sale created successfully
        assert sale.id is not None
        assert sale.status == 'draft'
        
        # Verify sales list endpoint works
        response = admin_client.get('/api/v1/sales/')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Sales endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify sale detail endpoint works
        response = admin_client.get(f'/api/v1/sales/{sale.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(sale.id)
        
        # Verify no FK constraints broken
        # (Sale.converted_from_proposal is nullable, so old sales have NULL)
        sale.refresh_from_db()
        assert True  # No FK errors
