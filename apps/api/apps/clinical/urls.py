"""
Clinical URLs - Patients, Appointments, Encounters, etc.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PatientViewSet,
    AppointmentViewSet,
    PatientMergeCandidatesView,
    PatientMergeView,
    EncounterViewSet,
    TreatmentViewSet,
    ClinicalChargeProposalViewSet,
)

router = DefaultRouter()
router.register(r'patients', PatientViewSet, basename='patient')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'encounters', EncounterViewSet, basename='encounter')
router.register(r'treatments', TreatmentViewSet, basename='treatment')
router.register(r'proposals', ClinicalChargeProposalViewSet, basename='clinical-charge-proposal')

urlpatterns = [
    # Patient merge operations
    path('patients/<uuid:pk>/merge-candidates', PatientMergeCandidatesView.as_view(), name='patient-merge-candidates'),
    path('patients/merge', PatientMergeView.as_view(), name='patient-merge'),
    
    # Standard CRUD via router
    path('', include(router.urls)),
]
