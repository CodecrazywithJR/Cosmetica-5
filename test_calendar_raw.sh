#!/bin/bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('access', ''))")

PRACTITIONER_ID="1d30db31-c033-4e12-9f39-917a90a8746f"
DATE_FROM="2025-12-29"
DATE_TO="2026-01-04"

curl -v "http://localhost:8000/api/v1/clinical/practitioners/${PRACTITIONER_ID}/calendar/?date_from=${DATE_FROM}&date_to=${DATE_TO}" \
  -H "Authorization: Bearer $TOKEN"
