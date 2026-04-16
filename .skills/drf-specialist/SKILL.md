---
name: drf-specialist
description: Use when building or maintaining Django REST Framework APIs. Covers ViewSets, serializers, permissions, throttling, pagination, filtering, nested serializers, custom actions, error handling, and OpenAPI schema generation with drf-spectacular.
license: MIT
metadata:
  author: Cosmetica-5 Team
  version: "1.0.0"
  domain: backend
  triggers: DRF, ViewSet, serializer, permission class, throttling, pagination, filtering, APIView, ModelSerializer, drf-spectacular, OpenAPI, REST API endpoints
  role: specialist
  scope: implementation
  output-format: code
  related-skills: django-expert, api-designer, test-master
---

# DRF Specialist

Django REST Framework specialist for production-grade API development.

## When to Use This Skill

- Designing ViewSets, serializers, or permission classes
- Implementing custom API actions (`@action` decorator)
- Nested serializer relationships (read vs write)
- Pagination, filtering, and ordering
- Custom error responses (RFC 7807)
- OpenAPI schema customization with drf-spectacular
- JWT authentication flows
- Rate limiting / throttling

## Core Workflow

1. **Design the resource** — URL structure, HTTP methods, expected payloads
2. **Define serializers** — Separate read (nested) from write (flat IDs)
3. **Implement ViewSet** — Permission classes, queryset optimization, actions
4. **Configure routing** — Router registration, nested routes if needed
5. **Document** — drf-spectacular `@extend_schema` decorations
6. **Test** — `APIClient`, status code assertions, permission edge cases

## Constraints

### MUST DO
- Separate read serializers (nested, display) from write serializers (flat, IDs)
- Use `get_queryset()` to apply tenant filtering and RBAC
- Always define `permission_classes` explicitly on ViewSets
- Use `@extend_schema` for accurate OpenAPI documentation
- Return consistent error format (detail, code, field-level errors)
- Use `serializer.is_valid(raise_exception=True)` — let DRF handle 400s
- Use `select_related`/`prefetch_related` in `get_queryset()` to avoid N+1
- Use `pagination_class` on list endpoints (never return unbounded lists)
- Use `source` parameter for field renaming instead of SerializerMethodField
- Set `read_only_fields` in Meta for computed/system fields

### MUST NOT DO
- Put business logic in serializers — use model methods or service layer
- Use `ModelSerializer` with `fields = '__all__'` (security risk — mass assignment)
- Return raw model instances from views — always serialize
- Use `request.data` directly without validation
- Mix authentication schemes without explicit configuration
- Ignore `perform_create` / `perform_update` hooks for side effects
- Use global throttling without per-view overrides for public endpoints
- Return 200 for creation (use 201), updates (use 200), deletes (use 204)

## Serializer Patterns

```python
# READ serializer — nested, display-friendly
class PatientReadSerializer(serializers.ModelSerializer):
    legal_entity_name = serializers.CharField(source='legal_entity.trade_name', read_only=True)
    practitioner = PractitionerMinimalSerializer(read_only=True)

    class Meta:
        model = Patient
        fields = ['id', 'first_name', 'last_name', 'email', 'legal_entity_name', 'practitioner']
        read_only_fields = fields


# WRITE serializer — flat IDs, validation
class PatientWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['first_name', 'last_name', 'email', 'phone', 'practitioner']

    def validate_email(self, value):
        if Patient.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value
```

## ViewSet Pattern

```python
class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinicRole]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'practitioner']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['created_at', 'last_name']
    ordering = ['-created_at']

    def get_queryset(self):
        return Patient.objects.filter(
            legal_entity=self.request.user.legal_entity
        ).select_related('legal_entity', 'practitioner')

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return PatientReadSerializer
        return PatientWriteSerializer

    def perform_create(self, serializer):
        serializer.save(legal_entity=self.request.user.legal_entity)

    @action(detail=True, methods=['post'], url_path='merge')
    @extend_schema(request=PatientMergeSerializer, responses={200: PatientReadSerializer})
    def merge(self, request, pk=None):
        """Merge another patient into this one."""
        patient = self.get_object()
        serializer = PatientMergeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merged = patient_merge_service(patient, serializer.validated_data['source_id'])
        return Response(PatientReadSerializer(merged).data)
```

## Permission Class Pattern

```python
class HasRole(BasePermission):
    """Check user has required role for the action."""
    role_map = {
        'list': [RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION],
        'retrieve': [RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION],
        'create': [RoleChoices.ADMIN, RoleChoices.RECEPTION],
        'update': [RoleChoices.ADMIN],
        'destroy': [RoleChoices.ADMIN],
    }

    def has_permission(self, request, view):
        required_roles = self.role_map.get(view.action, [])
        if not required_roles:
            return False
        return request.user.roles.filter(role__in=required_roles).exists()
```

## Error Response Pattern

```python
# Consistent error format
{
    "type": "validation_error",
    "errors": [
        {
            "code": "invalid",
            "detail": "Email already registered.",
            "attr": "email"
        }
    ]
}
```

## Project-Specific Notes (Cosmetica 5)

- **API prefix**: `/api/v1/` (private), `/public/` (public)
- **Auth**: JWT via `djangorestframework-simplejwt` (Bearer token)
- **Schema**: drf-spectacular at `/api/schema/swagger-ui/`
- **Roles**: admin, practitioner, reception, accounting, marketing
- **Tenant header**: `X-Legal-Entity-ID` for superuser tenant resolution
- **State machines**: Sale (draft→paid→refunded), Proposal (draft→sent→accepted), Appointment status transitions
- **Pagination**: Always paginate list endpoints
