#!/bin/bash
# Test del endpoint de calendario

# Obtener token de admin
echo "=== 1. Login como admin ==="
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}')

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access', ''))")

if [ -z "$TOKEN" ]; then
  echo "ERROR: No se pudo obtener el token"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Token obtenido"

# Obtener lista de practitioners
echo ""
echo "=== 2. Obtener lista de practitioners ==="
PRACTITIONERS=$(curl -s -X GET http://localhost:8000/api/v1/practitioners/ \
  -H "Authorization: Bearer $TOKEN")

echo "$PRACTITIONERS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Practitioners: {len(data) if isinstance(data, list) else len(data.get(\"results\", []))}')"

PRACTITIONER_ID=$(echo "$PRACTITIONERS" | python3 -c "import sys, json; data=json.load(sys.stdin); items=data if isinstance(data, list) else data.get('results', []); print(items[0]['id'] if items else '')")

if [ -z "$PRACTITIONER_ID" ]; then
  echo "⚠️  No hay practitioners en el sistema"
  exit 0
fi

echo "✅ Practitioner ID: $PRACTITIONER_ID"

# Probar el endpoint de calendario
echo ""
echo "=== 3. Obtener calendario (próxima semana) ==="
DATE_FROM=$(date -v+1d '+%Y-%m-%d' 2>/dev/null || date -d '+1 day' '+%Y-%m-%d')
DATE_TO=$(date -v+7d '+%Y-%m-%d' 2>/dev/null || date -d '+7 days' '+%Y-%m-%d')

echo "Fechas: $DATE_FROM a $DATE_TO"

CALENDAR=$(curl -s -X GET "http://localhost:8000/api/v1/clinical/practitioners/${PRACTITIONER_ID}/calendar/?date_from=${DATE_FROM}&date_to=${DATE_TO}" \
  -H "Authorization: Bearer $TOKEN")

echo "$CALENDAR" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data, indent=2))"

echo ""
echo "✅ Test completado"
