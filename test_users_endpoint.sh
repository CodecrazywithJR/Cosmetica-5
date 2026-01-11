#!/bin/bash
# Test script for /api/v1/users/ endpoint

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY3NzM5MTE0LCJpYXQiOjE3Njc3MzU1MTQsImp0aSI6ImRkZGI5NGM2ZGJlZjQ3YzFiMzhhNTU0MjVkYjdkZDc1IiwidXNlcl9pZCI6IjQ1ZmY5ZWJlLTUyNmQtNDBkYS04YmJjLTIwZGY3OGY0YTU0ZSJ9.v3pyPz-wNey-iPRNzxrcEoN4N58xVxlHsDMTcHoa9d4"

echo "Testing GET /api/v1/users/ endpoint..."
echo ""

curl -i -X GET http://localhost:8000/api/v1/users/ \
  -H "Authorization: Bearer $TOKEN" \
  2>&1 | head -50
