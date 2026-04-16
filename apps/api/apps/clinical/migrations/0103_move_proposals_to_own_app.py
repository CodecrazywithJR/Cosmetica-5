"""
State-only migration: remove ClinicalChargeProposal and ClinicalChargeProposalLine
from the clinical app's Django state.

These models now live in the proposals app (proposals.Proposal, proposals.ProposalLine).
The DB tables are untouched — this only changes Django's internal state tracking.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0102_clinicalmedia"),
        ("proposals", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # Delete ProposalLine first (has FK to Proposal)
                migrations.DeleteModel(name="ClinicalChargeProposalLine"),
                # Then delete Proposal
                migrations.DeleteModel(name="ClinicalChargeProposal"),
            ],
            database_operations=[],
        ),
    ]
