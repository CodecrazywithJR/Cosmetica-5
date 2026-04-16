"""
Legal Entity ViewSet — System Plane.

Access: is_superuser=True only.
No X-Active-Legal-Entity required.
No multi-tenant filtering.
No physical DELETE.
"""
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.legal.models import LegalEntity
from apps.legal.serializers import (
    LegalEntityListSerializer,
    LegalEntityDetailSerializer,
    LegalEntityCreateSerializer,
    LegalEntityUpdateSerializer,
)


class IsSuperUser(permissions.BasePermission):
    """Only is_superuser=True may access."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class LegalEntityViewSet(viewsets.ModelViewSet):
    """
    System Plane — Legal Entity CRUD.

    Endpoints:
        GET    /api/v1/system/legal-entities/          → list
        POST   /api/v1/system/legal-entities/          → create (+ admin user)
        GET    /api/v1/system/legal-entities/{id}/      → retrieve
        PATCH  /api/v1/system/legal-entities/{id}/      → update
        POST   /api/v1/system/legal-entities/{id}/activate/   → activate
        POST   /api/v1/system/legal-entities/{id}/deactivate/ → deactivate

    DELETE is disabled (no physical deletion allowed).
    """

    permission_classes = [IsSuperUser]
    lookup_field = 'pk'
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = LegalEntity.objects.all().order_by('-created_at')

        # Optional filters
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')

        q = self.request.query_params.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(legal_name__icontains=q)
                | Q(trade_name__icontains=q)
                | Q(legal_email__icontains=q)
                | Q(city__icontains=q)
            )

        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return LegalEntityListSerializer
        if self.action == 'retrieve':
            return LegalEntityDetailSerializer
        if self.action == 'create':
            return LegalEntityCreateSerializer
        if self.action in ('update', 'partial_update'):
            return LegalEntityUpdateSerializer
        return LegalEntityDetailSerializer

    # ── CREATE ────────────────────────────────────────────────────────
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        legal_entity = serializer.save()

        return Response(
            {
                'legal_entity_id': str(legal_entity.id),
                'legal_entity': LegalEntityDetailSerializer(legal_entity).data,
                'admin_user_id': str(legal_entity._admin_user.id),
                'admin_email': legal_entity._admin_user.email,
                'temporary_password': legal_entity._temporary_password,
            },
            status=status.HTTP_201_CREATED,
        )

    # ── UPDATE ────────────────────────────────────────────────────────
    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True  # always PATCH semantics
        return super().update(request, *args, **kwargs)

    # ── DELETE disabled ───────────────────────────────────────────────
    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Physical deletion of legal entities is not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # ── ACTIVATE ──────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        le = self.get_object()
        if le.is_active:
            return Response(
                {'detail': 'Legal entity is already active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        le.is_active = True
        le.save(update_fields=['is_active', 'updated_at'])
        return Response(LegalEntityDetailSerializer(le).data)

    # ── DEACTIVATE ────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        le = self.get_object()
        if not le.is_active:
            return Response(
                {'detail': 'Legal entity is already inactive.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        le.is_active = False
        le.save(update_fields=['is_active', 'updated_at'])
        return Response(LegalEntityDetailSerializer(le).data)
