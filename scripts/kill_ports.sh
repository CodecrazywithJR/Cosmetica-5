#!/bin/bash
# Kill processes occupying development ports (macOS/Linux)

set -e

PORTS=(3000 3001 8000 5432 6379 9000 9001)

echo "🔍 Checking for processes on development ports..."

for PORT in "${PORTS[@]}"; do
  PID=$(lsof -ti tcp:$PORT 2>/dev/null || true)
  
  if [ -n "$PID" ]; then
    echo "⚠️  Port $PORT is occupied by PID $PID"
    echo "   Killing process..."
    kill -9 $PID 2>/dev/null || true
    echo "✅ Port $PORT freed"
  else
    echo "✓  Port $PORT is free"
  fi
done

echo ""
echo "✅ All ports checked and cleared"
