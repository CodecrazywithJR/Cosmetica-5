"""URL configuration for POS app."""
from django.urls import path
from .views import PatientSearchView, PatientUpsertView

app_name = 'pos'

urlpatterns = [
    path('patients/search', PatientSearchView.as_view(), name='patient-search'),
    path('patients/upsert', PatientUpsertView.as_view(), name='patient-upsert'),
]
