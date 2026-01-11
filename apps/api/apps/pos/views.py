"""POS patient views with fuzzy search."""
import logging
from typing import List, Dict, Any
from decimal import Decimal

from django.db.models import Q, Value, FloatField
from django.contrib.postgres.search import TrigramSimilarity
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.clinical.models import Patient
from .serializers import (
    POSPatientSearchResultSerializer,
    POSPatientUpsertSerializer,
    POSPatientUpsertResponseSerializer
)
from .permissions import IsPOSUser
from .utils import (
    normalize_phone_to_e164,
    mask_phone,
    mask_email,
    normalize_search_query,
    is_email_like,
    is_phone_like
)

logger = logging.getLogger(__name__)


class PatientSearchView(APIView):
    """
    GET /api/v1/pos/patients/search
    
    Fuzzy patient search for POS with intelligent scoring.
    
    Query params:
        - q: Search query (phone, email, or name)
        - limit: Max results (default: 10)
    
    Scoring hierarchy:
        1. Phone exact match: 1.00
        2. Email exact match: 0.95
        3. Name fuzzy match (trigram): 0.30-0.90
        4. Name contains fallback: 0.20
    """
    permission_classes = [IsPOSUser]
    
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 10))
        
        if not query:
            return Response(
                {'error': 'Query parameter "q" is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if limit < 1 or limit > 100:
            limit = 10
        
        # Find candidates with scoring
        candidates = self._search_patients(query, limit)
        
        # Serialize results
        serializer = POSPatientSearchResultSerializer(candidates, many=True)
        
        # Log search (no PHI/PII)
        logger.info(
            "POS patient search",
            extra={
                'user_id': str(request.user.id) if request.user.is_authenticated else None,
                'query_type': self._detect_query_type(query),
                'results_count': len(candidates),
                'limit': limit
            }
        )
        
        return Response(serializer.data)
    
    def _detect_query_type(self, query: str) -> str:
        """Detect query type for logging."""
        if is_phone_like(query):
            return 'phone'
        elif is_email_like(query):
            return 'email'
        else:
            return 'name'
    
    def _search_patients(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Search patients using multiple strategies with scoring.
        
        Returns list of dicts with patient data + match_reason + score.
        """
        results = []
        seen_ids = set()
        
        # Strategy 1: Exact phone match (score: 1.00)
        if is_phone_like(query):
            phone_e164 = normalize_phone_to_e164(query)
            if phone_e164:
                phone_matches = Patient.objects.filter(
                    phone_e164=phone_e164,
                    is_deleted=False
                ).values('id', 'full_name_normalized', 'identity_confidence', 'phone_e164', 'email')
                
                for patient in phone_matches:
                    if patient['id'] not in seen_ids:
                        results.append({
                            'id': patient['id'],
                            'full_name_normalized': patient['full_name_normalized'] or '',
                            'identity_confidence': patient['identity_confidence'],
                            'phone_masked': mask_phone(patient['phone_e164']),
                            'email_masked': mask_email(patient['email']),
                            'match_reason': 'phone_exact',
                            'score': 1.00
                        })
                        seen_ids.add(patient['id'])
        
        # Strategy 2: Exact email match (score: 0.95)
        if is_email_like(query):
            email_normalized = query.lower().strip()
            email_matches = Patient.objects.filter(
                email__iexact=email_normalized,
                is_deleted=False
            ).values('id', 'full_name_normalized', 'identity_confidence', 'phone_e164', 'email')
            
            for patient in email_matches:
                if patient['id'] not in seen_ids:
                    results.append({
                        'id': patient['id'],
                        'full_name_normalized': patient['full_name_normalized'] or '',
                        'identity_confidence': patient['identity_confidence'],
                        'phone_masked': mask_phone(patient['phone_e164']),
                        'email_masked': mask_email(patient['email']),
                        'match_reason': 'email_exact',
                        'score': 0.95
                    })
                    seen_ids.add(patient['id'])
        
        # Strategy 3: Fuzzy name match using trigram similarity (score: similarity value, capped at 0.90)
        if not is_phone_like(query) and not is_email_like(query):
            q_norm = normalize_search_query(query)
            
            # Use TrigramSimilarity for fuzzy matching
            fuzzy_matches = Patient.objects.annotate(
                similarity=TrigramSimilarity('full_name_normalized', q_norm)
            ).filter(
                similarity__gte=0.2,  # Minimum threshold
                is_deleted=False
            ).values(
                'id', 'full_name_normalized', 'identity_confidence', 
                'phone_e164', 'email', 'similarity'
            ).order_by('-similarity')[:limit * 2]  # Get extra for deduping
            
            for patient in fuzzy_matches:
                if patient['id'] not in seen_ids:
                    # Cap similarity score at 0.90 to keep below exact matches
                    score = min(float(patient['similarity']), 0.90)
                    
                    results.append({
                        'id': patient['id'],
                        'full_name_normalized': patient['full_name_normalized'] or '',
                        'identity_confidence': patient['identity_confidence'],
                        'phone_masked': mask_phone(patient['phone_e164']),
                        'email_masked': mask_email(patient['email']),
                        'match_reason': 'name_fuzzy',
                        'score': score
                    })
                    seen_ids.add(patient['id'])
            
            # Strategy 4: Fallback to icontains if no fuzzy results (score: 0.20)
            if len([r for r in results if r['match_reason'] == 'name_fuzzy']) == 0:
                contains_matches = Patient.objects.filter(
                    Q(first_name__icontains=q_norm) | 
                    Q(last_name__icontains=q_norm) |
                    Q(full_name_normalized__icontains=q_norm),
                    is_deleted=False
                ).values(
                    'id', 'full_name_normalized', 'identity_confidence',
                    'phone_e164', 'email'
                )[:limit]
                
                for patient in contains_matches:
                    if patient['id'] not in seen_ids:
                        results.append({
                            'id': patient['id'],
                            'full_name_normalized': patient['full_name_normalized'] or '',
                            'identity_confidence': patient['identity_confidence'],
                            'phone_masked': mask_phone(patient['phone_e164']),
                            'email_masked': mask_email(patient['email']),
                            'match_reason': 'name_contains_fallback',
                            'score': 0.20
                        })
                        seen_ids.add(patient['id'])
        
        # Sort by score DESC and limit
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]


class PatientUpsertView(APIView):
    """
    POST /api/v1/pos/patients/upsert
    
    Create or retrieve patient with deduplication by phone/email.
    
    Business rules:
        1. If phone_e164 matches existing patient -> return existing (no duplicate)
        2. Else if email matches existing patient -> return existing (no duplicate)
        3. Else create new patient with identity_confidence='low'
    
    Does NOT do fuzzy name matching for upsert (too risky for auto-merge).
    """
    permission_classes = [IsPOSUser]
    
    def post(self, request):
        serializer = POSPatientUpsertSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Normalize phone and email
        phone_e164 = normalize_phone_to_e164(data.get('phone')) if data.get('phone') else None
        email_normalized = data.get('email').lower().strip() if data.get('email') else None
        
        # Try to find existing patient by phone (highest priority)
        if phone_e164:
            existing = Patient.objects.filter(
                phone_e164=phone_e164,
                is_deleted=False
            ).first()
            
            if existing:
                patient_data = self._patient_to_response(existing, 'phone_exact', created=False)
                
                logger.info(
                    "POS patient upsert - found by phone",
                    extra={
                        'patient_id': str(existing.id),
                        'user_id': str(request.user.id) if request.user.is_authenticated else None
                    }
                )
                
                return Response(patient_data, status=status.HTTP_200_OK)
        
        # Try to find existing patient by email
        if email_normalized:
            existing = Patient.objects.filter(
                email__iexact=email_normalized,
                is_deleted=False
            ).first()
            
            if existing:
                patient_data = self._patient_to_response(existing, 'email_exact', created=False)
                
                logger.info(
                    "POS patient upsert - found by email",
                    extra={
                        'patient_id': str(existing.id),
                        'user_id': str(request.user.id) if request.user.is_authenticated else None
                    }
                )
                
                return Response(patient_data, status=status.HTTP_200_OK)
        
        # No match found -> create new patient
        full_name = f"{data['first_name']} {data['last_name']}".strip()
        full_name_normalized = full_name.lower()
        
        new_patient = Patient.objects.create(
            first_name=data['first_name'],
            last_name=data['last_name'],
            full_name_normalized=full_name_normalized,
            phone=data.get('phone', ''),
            phone_e164=phone_e164 or '',
            email=email_normalized or '',
            birth_date=data.get('birth_date'),
            sex=data.get('sex', 'U'),
            identity_confidence='low',  # POS-created patients start with low confidence
        )
        
        patient_data = self._patient_to_response(new_patient, 'created', created=True)
        
        logger.info(
            "POS patient upsert - created new",
            extra={
                'patient_id': str(new_patient.id),
                'user_id': str(request.user.id) if request.user.is_authenticated else None,
                'identity_confidence': 'low'
            }
        )
        
        return Response(patient_data, status=status.HTTP_201_CREATED)
    
    def _patient_to_response(self, patient: Patient, match_reason: str, created: bool) -> dict:
        """Convert patient to response format."""
        return {
            'patient': {
                'id': patient.id,
                'full_name_normalized': patient.full_name_normalized or '',
                'identity_confidence': patient.identity_confidence,
                'phone_masked': mask_phone(patient.phone_e164),
                'email_masked': mask_email(patient.email),
                'match_reason': match_reason,
                'score': 1.00 if not created else 0.00
            },
            'created': created,
            'match_reason': match_reason
        }
