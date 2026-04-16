"""
Backward-compatible re-exports — serializers moved to apps.proposals.serializers.

This module will be removed in a future cleanup.
"""
from apps.proposals.serializers import (  # noqa: F401
    ProposalLineSerializer as ClinicalChargeProposalLineSerializer,
    ProposalListSerializer as ClinicalChargeProposalListSerializer,
    ProposalDetailSerializer as ClinicalChargeProposalDetailSerializer,
    CreateSaleFromProposalSerializer,
)

