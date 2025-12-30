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
    PractitionerCalendarView,
    PractitionerAvailabilityView,
    PractitionerBookingView,
    PractitionerAvailabilityView,
)
from .views_photos import ClinicalPhotoViewSet
from .views_documents import DocumentViewSet

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
    
    # Calendar view (Sprint 1: Agenda Read-Only)
    path('practitioners/<uuid:practitioner_id>/calendar/', PractitionerCalendarView.as_view(), name='practitioner-calendar'),
    
    # Availability calculation (Sprint 2: Free Slots)
    path('practitioners/<uuid:practitioner_id>/availability/', PractitionerAvailabilityView.as_view(), name='practitioner-availability'),
    
    # Appointment booking (Sprint 3: Book from Available Slots)
    path('practitioners/<uuid:practitioner_id>/book/', PractitionerBookingView.as_view(), name='practitioner-booking'),
    
    # Encounter attachments (v1)
    path('encounters/<uuid:encounter_id>/photos/', ClinicalPhotoViewSet.as_view({'get': 'list', 'post': 'create'}), name='encounter-photos'),
    path('photos/<uuid:pk>/', ClinicalPhotoViewSet.as_view({'delete': 'destroy'}), name='photo-detail'),
    path('photos/<uuid:pk>/download/', ClinicalPhotoViewSet.as_view({'get': 'download'}), name='photo-download'),
    
    path('encounters/<uuid:encounter_id>/documents/', DocumentViewSet.as_view({'get': 'list', 'post': 'create'}), name='encounter-documents'),
    path('documents/<uuid:pk>/', DocumentViewSet.as_view({'delete': 'destroy'}), name='document-detail'),
    path('documents/<uuid:pk>/download/', DocumentViewSet.as_view({'get': 'download'}), name='document-download'),
    
    # Standard CRUD via router
    path('', include(router.urls)),
]
