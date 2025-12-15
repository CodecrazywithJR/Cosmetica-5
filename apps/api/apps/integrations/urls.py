"""Integration URLs."""
from django.urls import path
from .views import calendly_webhook

urlpatterns = [
    path('calendly/webhook/', calendly_webhook, name='calendly-webhook'),
]
