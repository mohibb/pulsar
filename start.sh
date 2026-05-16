#!/bin/bash
set -e
cd "$(dirname "$0")"

# Activate virtual environment if present
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

echo "Starting PULSAR on http://localhost:8001"
caffeinate -i uvicorn server.main:app --host 127.0.0.1 --port 8001
