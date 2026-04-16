"""
State-only migration: register Proposal and ProposalLine in the proposals app state.

The actual DB tables (clinical_charge_proposal, clinical_charge_proposal_line)
already exist, created by clinical.0012_add_clinical_charge_proposal.
This migration uses SeparateDatabaseAndState to add models to Django state
WITHOUT creating any tables or running any SQL.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("sales", "0007_sale_legal_entity"),
        ("authz", "0003_practitioner_role_type_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clinical", "0012_add_clinical_charge_proposal"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Proposal",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("draft", "Draft"),
                                    ("converted", "Converted to Sale"),
                                    ("cancelled", "Cancelled"),
                                ],
                                default="draft",
                                help_text="Proposal status (draft/converted/cancelled)",
                                max_length=20,
                            ),
                        ),
                        (
                            "converted_at",
                            models.DateTimeField(
                                blank=True,
                                help_text="Timestamp when converted to sale",
                                null=True,
                            ),
                        ),
                        (
                            "total_amount",
                            models.DecimalField(
                                decimal_places=2,
                                default=0,
                                help_text="Total charge amount (sum of line totals, NO TAX)",
                                max_digits=10,
                            ),
                        ),
                        (
                            "currency",
                            models.CharField(
                                default="EUR",
                                help_text="Currency code (ISO 4217)",
                                max_length=3,
                            ),
                        ),
                        (
                            "notes",
                            models.TextField(
                                blank=True,
                                help_text="Internal notes about this proposal",
                                null=True,
                            ),
                        ),
                        (
                            "cancellation_reason",
                            models.TextField(
                                blank=True,
                                help_text="Reason for cancellation (if status=cancelled)",
                                null=True,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "converted_to_sale",
                            models.ForeignKey(
                                blank=True,
                                help_text="Sale created from this proposal (null if not yet converted)",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="source_proposal",
                                to="sales.sale",
                            ),
                        ),
                        (
                            "created_by",
                            models.ForeignKey(
                                help_text="User who generated this proposal",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="created_proposals",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            "encounter",
                            models.OneToOneField(
                                help_text="Source encounter (must be FINALIZED)",
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="charge_proposal",
                                to="clinical.encounter",
                            ),
                        ),
                        (
                            "patient",
                            models.ForeignKey(
                                help_text="Patient from encounter (denormalized for querying)",
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="charge_proposals",
                                to="clinical.patient",
                            ),
                        ),
                        (
                            "practitioner",
                            models.ForeignKey(
                                help_text="Practitioner from encounter (denormalized)",
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="charge_proposals",
                                to="authz.practitioner",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Proposal",
                        "verbose_name_plural": "Proposals",
                        "db_table": "clinical_charge_proposal",
                        "ordering": ["-created_at"],
                    },
                ),
                migrations.CreateModel(
                    name="ProposalLine",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "treatment_name",
                            models.CharField(
                                help_text="Treatment name at proposal creation time",
                                max_length=255,
                            ),
                        ),
                        (
                            "description",
                            models.TextField(
                                blank=True,
                                help_text="Combined: treatment description + encounter treatment notes",
                                null=True,
                            ),
                        ),
                        (
                            "quantity",
                            models.PositiveIntegerField(
                                default=1,
                                help_text="Quantity of treatment performed",
                            ),
                        ),
                        (
                            "unit_price",
                            models.DecimalField(
                                decimal_places=2,
                                help_text="Price per unit (snapshot from EncounterTreatment.effective_price)",
                                max_digits=10,
                            ),
                        ),
                        (
                            "line_total",
                            models.DecimalField(
                                decimal_places=2,
                                help_text="Line total: quantity * unit_price (NO discounts, NO tax)",
                                max_digits=10,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "encounter_treatment",
                            models.ForeignKey(
                                help_text="Source encounter treatment",
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="proposal_lines",
                                to="clinical.encountertreatment",
                            ),
                        ),
                        (
                            "proposal",
                            models.ForeignKey(
                                help_text="Parent proposal",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="lines",
                                to="proposals.proposal",
                            ),
                        ),
                        (
                            "treatment",
                            models.ForeignKey(
                                help_text="Treatment reference (denormalized for reporting)",
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="proposal_lines",
                                to="clinical.treatment",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Proposal Line",
                        "verbose_name_plural": "Proposal Lines",
                        "db_table": "clinical_charge_proposal_line",
                        "ordering": ["created_at"],
                    },
                ),
                migrations.AddIndex(
                    model_name="proposalline",
                    index=models.Index(
                        fields=["proposal"], name="idx_proposal_line_proposal"
                    ),
                ),
                migrations.AddIndex(
                    model_name="proposalline",
                    index=models.Index(
                        fields=["encounter_treatment"],
                        name="idx_proposal_line_enc_trt",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="proposalline",
                    constraint=models.CheckConstraint(
                        check=models.Q(("quantity__gt", 0)),
                        name="proposal_line_quantity_positive",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="proposalline",
                    constraint=models.CheckConstraint(
                        check=models.Q(("unit_price__gte", 0)),
                        name="proposal_line_unit_price_non_negative",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="proposalline",
                    constraint=models.CheckConstraint(
                        check=models.Q(("line_total__gte", 0)),
                        name="proposal_line_total_non_negative",
                    ),
                ),
                migrations.AddIndex(
                    model_name="proposal",
                    index=models.Index(
                        fields=["-created_at"], name="idx_proposal_created"
                    ),
                ),
                migrations.AddIndex(
                    model_name="proposal",
                    index=models.Index(
                        fields=["status", "-created_at"],
                        name="idx_proposal_status_created",
                    ),
                ),
                migrations.AddIndex(
                    model_name="proposal",
                    index=models.Index(
                        fields=["patient", "-created_at"],
                        name="idx_proposal_patient_created",
                    ),
                ),
                migrations.AddIndex(
                    model_name="proposal",
                    index=models.Index(
                        fields=["encounter"], name="idx_proposal_encounter"
                    ),
                ),
                migrations.AddConstraint(
                    model_name="proposal",
                    constraint=models.CheckConstraint(
                        check=models.Q(("total_amount__gte", 0)),
                        name="proposal_total_non_negative",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
