#!/bin/bash
echo "Starting AI Incident Response Agent..."
python -c "from database import init_db; print('DB initialized')"
exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}