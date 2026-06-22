#!/bin/bash
# Build SQLite DB from price.csv if not present
if [ ! -f "mst.db" ]; then
    echo "Building product database..."
    python3 build_db.py
fi
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
