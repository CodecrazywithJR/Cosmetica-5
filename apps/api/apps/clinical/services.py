"""
Patient merge service.

Handles merging duplicate patients while maintaining data integrity
and full audit trail.
"""
import logging
from typing import Dict, Any, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.clinical.models import Patient, PatientMergeLog
from apps.clinical.signals import patient_merged

# Prometheus metrics with fallback
try:
    from prometheus_client import Counter
    MERGE_SUCCESS_COUNTER = Counter(
        'patient_merge_total',
        'Total successful patient merges',
        ['strategy']
    )
    MERGE_FAILURE_COUNTER = Counter(
        'patient_merge_failed_total',
        'Total failed patient merge attempts',
        ['reason']
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    MERGE_SUCCESS_COUNTER = None
    MERGE_FAILURE_COUNTER = None

User = get_user_model()
logger = logging.getLogger(__name__)


class PatientMergeError(Exception):
    """Exception raised when patient merge fails validation."""
    pass


def _track_merge_failure(reason: str) -> None:
    """Increment the merge failure metric if Prometheus is available."""
    if METRICS_AVAILABLE:
        MERGE_FAILURE_COUNTER.labels(reason=reason).inc()


def merge_patients(
    source_id: str,
    target_id: str,
    merged_by: User,
    strategy: str = 'manual',
    notes: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None
) -> Patient:
    """
    Merge source patient into target patient.
    
    This operation:
    1. Validates merge is safe (no cycles, no self-merge, etc.)
    2. Moves all relationships from source to target
    3. Marks source as merged
    4. Creates audit log
    
    All operations are atomic - either all succeed or all rollback.
    
    Args:
        source_id: UUID of patient to merge (will be marked inactive)
        target_id: UUID of patient to keep active
        merged_by: User performing the merge
        strategy: How duplicate was detected (phone_exact, email_exact, etc.)
        notes: Free-text explanation
        evidence: Sanitized match evidence (no PHI)
        
    Returns:
        Target patient (with all relationships merged in)
        
    Raises:
        PatientMergeError: If validation fails
        Patient.DoesNotExist: If either patient not found
    """
    with transaction.atomic():
        # Lock both patients for update
        try:
            source = Patient.objects.select_for_update().get(id=source_id)
            target = Patient.objects.select_for_update().get(id=target_id)
        except Patient.DoesNotExist:
            _track_merge_failure('patient_not_found')
            logger.error(
                "Patient merge failed - patient not found",
                extra={'source_id': str(source_id), 'target_id': str(target_id)}
            )
            raise
        
        # Validation 1: Cannot merge into self
        if source.id == target.id:
            _track_merge_failure('self_merge')
            raise PatientMergeError("Cannot merge patient into itself")
        
        # Validation 2: Source must not be already merged
        if source.is_merged:
            _track_merge_failure('source_already_merged')
            raise PatientMergeError(
                f"Source patient {source.id} is already merged into "
                f"{source.merged_into_patient_id}"
            )
        
        # Validation 3: Target must not be merged (or resolve to root)
        if target.is_merged:
            _track_merge_failure('target_already_merged')
            raise PatientMergeError(
                f"Target patient {target.id} is already merged into another patient. "
                f"Cannot merge into a merged patient."
            )
        
        # Validation 4: Prevent cycles (source's merged_patients shouldn't include target)
        # This is implicitly prevented by validation 2 & 3, but double-check
        if target.merged_patients.filter(id=source.id).exists():
            _track_merge_failure('circular_merge')
            raise PatientMergeError("Circular merge detected - cannot proceed")
        
        # Count relationships before merge
        relations_summary = _count_patient_relations(source)
        
        # Move all relationships from source to target
        _move_patient_relations(source, target)
        
        # Mark source as merged
        source.is_merged = True
        source.merged_into_patient = target
        source.merge_reason = notes or f"Merged via {strategy}"
        source.save(update_fields=['is_merged', 'merged_into_patient', 'merge_reason', 'updated_at'])
        
        # Create audit log
        merge_log = PatientMergeLog.objects.create(
            source_patient=source,
            target_patient=target,
            merged_by_user=merged_by,
            strategy=strategy,
            evidence=evidence or {},
            notes=notes
        )
        
        logger.info(
            "Patient merge completed successfully",
            extra={
                'source_patient_id': str(source.id),
                'target_patient_id': str(target.id),
                'merged_by_user_id': str(merged_by.id) if merged_by else None,
                'strategy': strategy,
                'merge_log_id': str(merge_log.id),
                'relations_moved': relations_summary
            }
        )
        
        # Increment success metric
        if METRICS_AVAILABLE:
            MERGE_SUCCESS_COUNTER.labels(strategy=strategy).inc()
        
        # Emit signal (only after transaction succeeds)
        # Note: Signal is emitted inside transaction, but listeners should
        # use on_commit() if they need post-transaction guarantees
        patient_merged.send(
            sender=Patient,
            source_patient_id=str(source.id),
            target_patient_id=str(target.id),
            strategy=strategy,
            merged_by_user_id=str(merged_by.id) if merged_by else None,
            merge_log_id=str(merge_log.id)
        )
        
        return target


def _count_patient_relations(patient: Patient) -> Dict[str, int]:
    """Count all relationships for a patient."""
    return {
        'appointments': patient.appointments.count(),
        'encounters': patient.encounters.count(),
        'sales': patient.sales.count(),
        'photos': patient.clinical_photos.count(),
        'consents': patient.consents.count(),
        'guardians': patient.guardians.count(),
        'audit_logs': patient.audit_logs.count(),
        # Legacy relations if they exist
        'legacy_encounters': patient.legacy_encounters.count() if hasattr(patient, 'legacy_encounters') else 0,
        'legacy_photos': patient.legacy_photos.count() if hasattr(patient, 'legacy_photos') else 0,
    }


def _move_patient_relations(source: Patient, target: Patient) -> None:
    """
    Move all foreign key relationships from source to target.
    
    This updates all models that have FK to Patient.
    """
    # Clinical domain
    source.appointments.update(patient=target)
    source.encounters.update(patient=target)
    source.clinical_photos.update(patient=target)
    source.consents.update(patient=target)
    source.guardians.update(patient=target)
    source.audit_logs.update(patient=target)
    
    # Sales/POS domain
    source.sales.update(patient=target)
    
    # Legacy relations (if they exist)
    if hasattr(source, 'legacy_encounters'):
        source.legacy_encounters.update(patient=target)
    if hasattr(source, 'legacy_photos'):
        source.legacy_photos.update(patient=target)
    
    logger.debug(
        "Moved all patient relationships",
        extra={
            'source_id': str(source.id),
            'target_id': str(target.id)
        }
    )


def get_merge_candidates(
    patient: Patient,
    limit: int = 20
) -> list[Dict[str, Any]]:
    """
    Find potential duplicate patients for merging.
    
    Scoring hierarchy:
    - Phone exact: 1.00
    - Email exact: 0.95
    - Name trigram similarity: 0.30-0.90
    - Birth date match bonus: +0.05 (capped at 1.00)
    
    Args:
        patient: Patient to find duplicates for
        limit: Max number of candidates to return
        
    Returns:
        List of dicts with candidate info (sorted by score DESC)
    """
    from django.contrib.postgres.search import TrigramSimilarity
    from django.db.models import Q, FloatField, Value
    from apps.pos.utils import mask_phone, mask_email, normalize_search_query

    def _build_candidate(p, base_score, reasons):
        score = base_score
        if patient.birth_date and p['birth_date'] == patient.birth_date:
            score = min(score + 0.05, 1.00)
        return {
            'patient_id': p['id'],
            'display_name': p['full_name_normalized'] or f"{p['first_name']} {p['last_name']}",
            'masked_phone': mask_phone(p['phone_e164']),
            'masked_email': mask_email(p['email']),
            'birth_date': p['birth_date'],
            'score': score,
            'match_reasons': reasons,
        }

    candidates = []
    seen_ids = {patient.id}  # Exclude self
    
    # Strategy 1: Exact phone match (score: 1.00)
    if patient.phone_e164:
        phone_matches = Patient.objects.filter(
            phone_e164=patient.phone_e164,
            is_deleted=False,
            is_merged=False
        ).exclude(id__in=seen_ids).values(
            'id', 'first_name', 'last_name', 'full_name_normalized',
            'phone_e164', 'email', 'birth_date'
        )
        
        for p in phone_matches:
            candidates.append(_build_candidate(p, 1.00, ['phone_exact']))
            seen_ids.add(p['id'])
    
    # Strategy 2: Exact email match (score: 0.95)
    if patient.email:
        email_matches = Patient.objects.filter(
            email__iexact=patient.email,
            is_deleted=False,
            is_merged=False
        ).exclude(id__in=seen_ids).values(
            'id', 'first_name', 'last_name', 'full_name_normalized',
            'phone_e164', 'email', 'birth_date'
        )
        
        for p in email_matches:
            candidates.append(_build_candidate(p, 0.95, ['email_exact']))
            seen_ids.add(p['id'])
    
    # Strategy 3: Fuzzy name match (score: 0.30-0.90)
    if patient.full_name_normalized and len(candidates) < limit:
        q_norm = normalize_search_query(patient.full_name_normalized)
        
        fuzzy_matches = Patient.objects.annotate(
            similarity=TrigramSimilarity('full_name_normalized', q_norm)
        ).filter(
            similarity__gte=0.3,  # Threshold for merge candidates
            is_deleted=False,
            is_merged=False
        ).exclude(id__in=seen_ids).values(
            'id', 'first_name', 'last_name', 'full_name_normalized',
            'phone_e164', 'email', 'birth_date', 'similarity'
        ).order_by('-similarity')[:limit * 2]
        
        for p in fuzzy_matches:
            candidates.append(_build_candidate(p, min(float(p['similarity']), 0.90), ['name_trigram']))
            seen_ids.add(p['id'])
    
    # Sort by score DESC and limit
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:limit]


# ============================================================================
# Appointment → Encounter Integration (Fase 2.2)
# ============================================================================

def create_encounter_from_appointment(
    appointment,
    encounter_type: str,
    created_by: User,
    occurred_at=None,
    mark_completed: bool = False,
    **encounter_kwargs
):
    """
    Create an Encounter from a completed Appointment.
    
    BUSINESS RULE: Explicit creation - NOT automatic.
    This is called intentionally by the practitioner/clinician after appointment completion.
    
    Args:
        appointment: Appointment instance (should be in COMPLETED status)
        encounter_type: str - EncounterTypeChoices value
        created_by: User - The user creating the encounter
        occurred_at: datetime (optional) - When encounter occurred (defaults to appointment.scheduled_start)
        **encounter_kwargs: Additional Encounter fields (chief_complaint, assessment, plan, etc.)
    
    Returns:
        Encounter instance
    
    Raises:
        ValidationError: If appointment is not in a valid state
    
    Usage:
        # After appointment is marked COMPLETED
        appointment.status = 'completed'
        appointment.save()
        
        # Practitioner explicitly creates encounter
        encounter = create_encounter_from_appointment(
            appointment=appointment,
            encounter_type='medical_consult',
            created_by=request.user,
            chief_complaint='Patient reports acne',
            assessment='Mild inflammatory acne',
            plan='Topical treatment'
        )
    """
    from apps.clinical.models import Encounter, EncounterTypeChoices
    
    # Validation: Appointment should be completed
    if appointment.status != 'completed':
        raise ValidationError(
            f"Cannot create encounter from appointment with status '{appointment.status}'. "
            "Appointment must be 'completed' first."
        )
    
    # Validation: Appointment should not already have an encounter
    if appointment.encounter:
        raise ValidationError(
            f"Appointment {appointment.id} already has an encounter ({appointment.encounter.id})"
        )
    
    # Default occurred_at to appointment scheduled_start
    if occurred_at is None:
        occurred_at = appointment.scheduled_start
    
    # Create encounter
    with transaction.atomic():
        encounter = Encounter.objects.create(
            patient=appointment.patient,
            practitioner=appointment.practitioner,
            clinic=appointment.clinic,
            type=encounter_type,
            status='draft',  # Always start as draft
            occurred_at=occurred_at,
            created_by_user=created_by,
            **encounter_kwargs
        )
        
        # Link appointment to encounter and mark as completed if requested
        appointment.encounter = encounter
        if mark_completed:
            appointment.status = 'completed'
            appointment.save(update_fields=['encounter', 'status', 'updated_at'])
        else:
            appointment.save(update_fields=['encounter', 'updated_at'])
        
        logger.info(
            f"Created encounter {encounter.id} from appointment {appointment.id}",
            extra={
                'encounter_id': str(encounter.id),
                'appointment_id': str(appointment.id),
                'patient_id': str(appointment.patient.id),
                'practitioner_id': str(appointment.practitioner.id) if appointment.practitioner else None,
                'created_by': str(created_by.id)
            }
        )
    
    return encounter


# ============================================================================
# Clinical → Sales Integration Services (Fase 3)
# ============================================================================

def generate_charge_proposal_from_encounter(
    encounter,
    created_by: User,
    notes: Optional[str] = None
):
    """
    Generate a ClinicalChargeProposal from a finalized Encounter.
    
    This is the EXPLICIT step before creating a Sale, allowing:
    - Audit trail of what clinical acts are being charged
    - Review/approval workflow (future)
    - Separation of clinical documentation from billing
    
    Business Rules:
    - Encounter must be FINALIZED (not draft, not cancelled)
    - One proposal per encounter (idempotency via OneToOneField)
    - Proposal lines derived from EncounterTreatment
    - Pricing snapshot: Uses EncounterTreatment.effective_price
    - NO TAX calculation (deferred to future fiscal module)
    - NO automatic Sale creation (explicit conversion required)
    
    Args:
        encounter: Encounter instance (must be FINALIZED)
        created_by: User creating the proposal
        notes: Optional internal notes
    
    Returns:
        ClinicalChargeProposal instance with lines
    
    Raises:
        ValidationError: If encounter is not finalized or already has proposal
    
    Example:
        encounter = Encounter.objects.get(id=encounter_id)
        proposal = generate_charge_proposal_from_encounter(
            encounter=encounter,
            created_by=request.user,
            notes='Standard consultation charge'
        )
        # proposal.lines.all() → ClinicalChargeProposalLine queryset
        # proposal.total_amount → Decimal sum of line totals
    """
    from apps.clinical.models import (
        Encounter,
        EncounterStatusChoices,
    )
    from apps.proposals.models import (
        Proposal,
        ProposalLine,
        ProposalStatusChoices,
    )
    from decimal import Decimal
    
    # Validation: Encounter must be FINALIZED
    if encounter.status != EncounterStatusChoices.FINALIZED:
        raise ValidationError({
            'encounter': f"Cannot generate proposal from encounter with status '{encounter.status}'. "
                        "Encounter must be FINALIZED."
        })
    
    # Validation: Encounter must not already have a proposal (idempotency)
    if hasattr(encounter, 'charge_proposal') and encounter.charge_proposal:
        raise ValidationError({
            'encounter': f"Encounter {encounter.id} already has a charge proposal "
                        f"(ID: {encounter.charge_proposal.id})"
        })
    
    # Validation: Encounter must have treatments
    encounter_treatments = encounter.encounter_treatments.all()
    if not encounter_treatments.exists():
        raise ValidationError({
            'encounter': f"Cannot generate proposal from encounter {encounter.id} with no treatments. "
                        "Add at least one treatment to the encounter first."
        })
    
    # Create proposal with lines atomically
    with transaction.atomic():
        # Create proposal header
        proposal = Proposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            currency='EUR',  # FUTURE: derive from LegalEntity.currency
            notes=notes or '',
            created_by=created_by
        )
        
        # Create proposal lines from encounter treatments
        total_amount = Decimal('0.00')
        for enc_treatment in encounter_treatments:
            # Get effective price (override or default)
            effective_price = enc_treatment.effective_price
            if effective_price is None:
                logger.warning(
                    f"EncounterTreatment {enc_treatment.id} has no price - skipping",
                    extra={
                        'encounter_treatment_id': str(enc_treatment.id),
                        'treatment_id': str(enc_treatment.treatment.id),
                        'encounter_id': str(encounter.id)
                    }
                )
                continue
            
            # Build description (treatment + notes)
            description_parts = []
            if enc_treatment.treatment.description:
                description_parts.append(enc_treatment.treatment.description)
            if enc_treatment.notes:
                description_parts.append(f"Notes: {enc_treatment.notes}")
            description = "\n".join(description_parts) if description_parts else None
            
            # Calculate line total
            line_total = enc_treatment.quantity * effective_price
            total_amount += line_total
            
            # Create proposal line
            ProposalLine.objects.create(
                proposal=proposal,
                encounter_treatment=enc_treatment,
                treatment=enc_treatment.treatment,
                treatment_name=enc_treatment.treatment.name,
                description=description,
                quantity=enc_treatment.quantity,
                unit_price=effective_price,
                line_total=line_total
            )
        
        # Update proposal total
        proposal.total_amount = total_amount
        proposal.save(update_fields=['total_amount', 'updated_at'])
        
        logger.info(
            f"Generated charge proposal {proposal.id} from encounter {encounter.id}",
            extra={
                'proposal_id': str(proposal.id),
                'encounter_id': str(encounter.id),
                'patient_id': str(encounter.patient.id),
                'practitioner_id': str(encounter.practitioner.id) if encounter.practitioner else None,
                'line_count': proposal.lines.count(),
                'total_amount': str(proposal.total_amount),
                'created_by': str(created_by.id)
            }
        )
    
    return proposal


def create_sale_from_proposal(
    proposal,
    created_by: User,
    legal_entity,
    notes: Optional[str] = None
):
    """
    Convert a Proposal to a Sale (draft status).
    
    Delegates to Proposal.accept() state-machine method, which atomically:
    - Sets status → ACCEPTED
    - Creates Sale + SaleLines
    - Links converted_to_sale

    If the proposal is still in DRAFT, auto-sends it first.
    
    Business Rules:
    - Proposal must be in DRAFT or SENT status
    - Proposal must not already have a sale (idempotency)
    - Proposal must not be expired (valid_until check inside accept())
    - Proposal status → ACCEPTED (terminal state)
    
    Args:
        proposal: Proposal instance
        created_by: User creating the sale
        legal_entity: LegalEntity for the sale
        notes: Optional notes for the sale (currently unused — kept for API compat)
    
    Returns:
        Sale instance (status=DRAFT) with lines
    
    Raises:
        ValidationError: If proposal not in draft/sent or already converted
    """
    from apps.proposals.models import ProposalStatusChoices
    from django.utils import timezone as tz

    # Validation: Proposal must be in DRAFT or SENT status
    if proposal.status not in (ProposalStatusChoices.DRAFT, ProposalStatusChoices.SENT):
        raise ValidationError({
            'proposal': f"Cannot convert proposal with status '{proposal.status}'. "
                       "Only DRAFT or SENT proposals can be converted to sales."
        })

    # Validation: Proposal must not already have a sale (idempotency)
    if proposal.converted_to_sale is not None:
        raise ValidationError({
            'proposal': f"Proposal {proposal.id} already converted to sale "
                       f"(Sale ID: {proposal.converted_to_sale.id})"
        })

    # Validation: Proposal must have lines
    proposal_lines = proposal.lines.all()
    if not proposal_lines.exists():
        raise ValidationError({
            'proposal': f"Cannot convert proposal {proposal.id} with no lines."
        })

    # If still in draft, auto-send first so accept() works
    if proposal.status == ProposalStatusChoices.DRAFT:
        proposal.send(user=created_by)

    # Delegate to model state machine (atomic inside accept())
    sale = proposal.accept(user=created_by, legal_entity=legal_entity)

    logger.info(
        f"Converted proposal {proposal.id} to sale {sale.id}",
        extra={
            'proposal_id': str(proposal.id),
            'sale_id': str(sale.id),
            'encounter_id': str(proposal.encounter.id),
            'patient_id': str(proposal.patient.id),
            'legal_entity_id': str(legal_entity.id),
            'line_count': sale.lines.count(),
            'total_amount': str(sale.total),
            'created_by': str(created_by.id)
        }
    )

    return sale


# ============================================================================
# AVAILABILITY SERVICE (Sprint 2)
# ============================================================================

class AvailabilityService:
    """
    Service for calculating practitioner availability slots.
    
    Calculates free time slots based on PractitionerSchedule working hours,
    subtracts existing appointments and practitioner blocks,
    supports treatment-aware slot duration and practitioner capability
    validation.
    
    Phase 4 upgrade:
    - Working hours sourced from PractitionerSchedule (per practitioner/clinic/weekday)
    - Treatment.duration_minutes overrides slot_duration when treatment_id provided
    - PractitionerTreatment capability validated before generating slots
    - Appointments filtered by clinic
    - Multi-day PractitionerBlock correctly spans across days
    """
    
    DEFAULT_SLOT_DURATION = 30  # minutes — fallback when no treatment_id
    
    @staticmethod
    def calculate_availability(
        practitioner_id: str,
        clinic_id: str,
        date_from: str,
        date_to: str,
        treatment_id: str = None,
        slot_duration: int = DEFAULT_SLOT_DURATION,
        timezone_str: str = "UTC"
    ) -> dict:
        """
        Calculate available time slots for a practitioner at a specific clinic.
        
        Args:
            practitioner_id: UUID of practitioner
            clinic_id: UUID of clinic (required)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            treatment_id: Optional UUID of treatment — overrides slot_duration
            slot_duration: Duration of each slot in minutes (fallback)
            timezone_str: Timezone for calculations (default UTC)
            
        Returns:
            Dict with availability data including clinic_id and optional
            treatment_id in the response envelope.
        """
        from datetime import datetime, timedelta, date as date_class, time
        from django.utils import timezone
        import pytz
        from apps.clinical.models import (
            Appointment, PractitionerBlock, PractitionerSchedule,
            PractitionerTreatment, Treatment,
        )
        
        # Parse dates
        date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
        date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
        
        # Get timezone
        tz = pytz.timezone(timezone_str)
        now = timezone.now()
        
        # ------------------------------------------------------------------
        # Treatment-aware slot duration (Step 2)
        # ------------------------------------------------------------------
        resolved_treatment_id = None
        if treatment_id:
            try:
                treatment_obj = Treatment.objects.get(id=treatment_id, is_active=True)
                slot_duration = treatment_obj.duration_minutes
                resolved_treatment_id = str(treatment_obj.id)
            except Treatment.DoesNotExist:
                # Inactive or missing treatment → empty availability
                return AvailabilityService._empty_response(
                    practitioner_id, clinic_id, date_from, date_to,
                    slot_duration, timezone_str, treatment_id,
                )
        
        # ------------------------------------------------------------------
        # Practitioner capability check (Step 3)
        # ------------------------------------------------------------------
        if resolved_treatment_id:
            has_capability = PractitionerTreatment.objects.filter(
                practitioner_id=practitioner_id,
                treatment_id=resolved_treatment_id,
                is_active=True,
                treatment__is_active=True,
            ).exists()
            if not has_capability:
                return AvailabilityService._empty_response(
                    practitioner_id, clinic_id, date_from, date_to,
                    slot_duration, timezone_str, resolved_treatment_id,
                )
        
        # ------------------------------------------------------------------
        # Fetch PractitionerSchedule rows for practitioner+clinic (Step 4)
        # ------------------------------------------------------------------
        schedule_qs = PractitionerSchedule.objects.filter(
            practitioner_id=practitioner_id,
            clinic_id=clinic_id,
            is_active=True,
        )
        # Build lookup: weekday → list of (start_time, end_time)
        schedule_by_weekday: dict[int, list] = {}
        for sched in schedule_qs:
            schedule_by_weekday.setdefault(sched.weekday, []).append(
                (sched.start_time, sched.end_time)
            )
        
        # ------------------------------------------------------------------
        # Clinic-scoped appointment query (Step 5)
        # ------------------------------------------------------------------
        appointments = Appointment.objects.filter(
            practitioner_id=practitioner_id,
            clinic_id=clinic_id,
            is_deleted=False,
            scheduled_start__date__gte=date_from_obj,
            scheduled_start__date__lte=date_to_obj,
            status__in=['scheduled', 'confirmed', 'checked_in'],
        ).order_by('scheduled_start')
        
        # ------------------------------------------------------------------
        # Multi-day block fix (Step 6)
        # Blocks whose time-span overlaps the requested date range:
        #   block.start <= range_end  AND  block.end >= range_start
        # ------------------------------------------------------------------
        range_start_dt = tz.localize(datetime.combine(date_from_obj, time.min))
        range_end_dt = tz.localize(datetime.combine(date_to_obj, time.max))
        blocks = PractitionerBlock.objects.filter(
            practitioner_id=practitioner_id,
            is_deleted=False,
            start__lte=range_end_dt,
            end__gte=range_start_dt,
        ).order_by('start')
        
        # ------------------------------------------------------------------
        # Day-by-day slot generation
        # ------------------------------------------------------------------
        availability = []
        current_date = date_from_obj
        
        while current_date <= date_to_obj:
            # Skip past dates (except today)
            if current_date < now.date():
                current_date += timedelta(days=1)
                continue
            
            # Look up schedule windows for this weekday
            windows = schedule_by_weekday.get(current_date.weekday())
            if not windows:
                # No schedule for this day → skip entirely
                current_date += timedelta(days=1)
                continue
            
            day_result = AvailabilityService._process_day(
                current_date, windows, appointments, blocks,
                slot_duration, now, tz,
            )
            availability.append(day_result)
            
            current_date += timedelta(days=1)
        
        result = {
            'practitioner_id': practitioner_id,
            'clinic_id': clinic_id,
            'date_from': date_from,
            'date_to': date_to,
            'slot_duration': slot_duration,
            'timezone': timezone_str,
            'availability': availability,
        }
        if resolved_treatment_id:
            result['treatment_id'] = resolved_treatment_id
        return result
    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _process_day(current_date, windows, appointments, blocks, slot_duration, now, tz):
        """Build availability slots for a single date."""
        from datetime import datetime, time

        day_appointments = [
            appt for appt in appointments
            if appt.scheduled_start.astimezone(tz).date() == current_date
        ]

        day_start_dt = tz.localize(datetime.combine(current_date, time.min))
        day_end_dt = tz.localize(datetime.combine(current_date, time.max))
        day_blocks = [
            block for block in blocks
            if block.start.astimezone(tz) < day_end_dt and block.end.astimezone(tz) > day_start_dt
        ]

        busy_periods = []
        for appt in day_appointments:
            busy_periods.append({
                'start': appt.scheduled_start.astimezone(tz),
                'end': appt.scheduled_end.astimezone(tz),
            })
        for block in day_blocks:
            busy_periods.append({
                'start': block.start.astimezone(tz),
                'end': block.end.astimezone(tz),
            })
        busy_periods.sort(key=lambda x: x['start'])

        day_slots = []
        for win_start, win_end in sorted(windows):
            work_start_dt = tz.localize(datetime.combine(current_date, win_start))
            work_end_dt = tz.localize(datetime.combine(current_date, win_end))
            free_slots = AvailabilityService._calculate_free_slots(
                work_start_dt, work_end_dt, busy_periods,
                slot_duration, now, tz,
            )
            day_slots.extend(free_slots)

        return {'date': current_date.isoformat(), 'slots': day_slots}

    @staticmethod
    def _empty_response(
        practitioner_id, clinic_id, date_from, date_to,
        slot_duration, timezone_str, treatment_id=None,
    ) -> dict:
        """Return a valid response envelope with zero availability days."""
        result = {
            'practitioner_id': practitioner_id,
            'clinic_id': clinic_id,
            'date_from': date_from,
            'date_to': date_to,
            'slot_duration': slot_duration,
            'timezone': timezone_str,
            'availability': [],
        }
        if treatment_id:
            result['treatment_id'] = str(treatment_id)
        return result
    
    @staticmethod
    def _align_to_slot_boundary(current_time, work_start_dt, slot_duration):
        """
        Re-align *current_time* forward to the next slot boundary relative
        to *work_start_dt*.  If already aligned, return unchanged.
        """
        from datetime import timedelta
        elapsed = (current_time - work_start_dt).total_seconds()
        slot_secs = slot_duration * 60
        remainder = elapsed % slot_secs
        if remainder == 0:
            return current_time
        return current_time + timedelta(seconds=slot_secs - remainder)
    
    @staticmethod
    def _calculate_free_slots(
        work_start_dt,
        work_end_dt,
        busy_periods,
        slot_duration,
        now,
        tz
    ):
        """
        Calculate free time slots within working hours, excluding busy periods.
        
        Args:
            work_start_dt: Working day start datetime
            work_end_dt: Working day end datetime
            busy_periods: List of dicts with 'start' and 'end' datetime
            slot_duration: Duration of each slot in minutes
            now: Current datetime (to skip past slots)
            tz: Timezone object
            
        Returns:
            List of dicts with 'start' and 'end' time strings (HH:MM)
        """
        from datetime import timedelta
        
        free_slots = []
        slot_delta = timedelta(minutes=slot_duration)
        
        # Start from beginning of work day
        current_time = work_start_dt
        
        while current_time + slot_delta <= work_end_dt:
            slot_end = current_time + slot_delta
            
            # Skip if slot is in the past
            if slot_end <= now:
                current_time += slot_delta
                continue
            
            # Check if this slot overlaps with any busy period
            is_busy = False
            for busy in busy_periods:
                # Check overlap: slot_start < busy_end AND busy_start < slot_end
                if current_time < busy['end'] and busy['start'] < slot_end:
                    is_busy = True
                    # Jump to end of busy period and re-align to slot boundary
                    current_time = AvailabilityService._align_to_slot_boundary(
                        busy['end'], work_start_dt, slot_duration
                    )
                    break
            
            if not is_busy:
                # This slot is free
                free_slots.append({
                    'start': current_time.strftime("%H:%M"),
                    'end': slot_end.strftime("%H:%M")
                })
                current_time += slot_delta
        
        return free_slots
