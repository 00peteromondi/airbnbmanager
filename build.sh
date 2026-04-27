#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies (including extras for ASGI/Channels)
if [ -f requirements-extra.txt ]; then
	pip install -r requirements.txt -r requirements-extra.txt
else
	pip install -r requirements.txt
fi

# Collect static files
python manage.py collectstatic --no-input

# Apply any outstanding database migrations
python manage.py migrate