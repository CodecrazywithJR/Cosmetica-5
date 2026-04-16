"""
URL routing for Public Booking API.

Mounted at /public/booking/ in config/urls.py.
"""
from django.urls import path

from .views_public_booking import PublicAvailabilityView, PublicCreateBookingView

urlpatterns = [
    path('availability/', PublicAvailabilityView.as_view(), name='public-availability'),
    path('create/', PublicCreateBookingView.as_view(), name='public-create-booking'),
]
