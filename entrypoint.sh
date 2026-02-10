#!/bin/bash
set -e

# Fix permissions for mounted volumes
chown -R botuser:botuser /app/data /app/logs 2>/dev/null || true
chmod -R 775 /app/data /app/logs 2>/dev/null || true

# Run as botuser
exec gosu botuser python main.py
