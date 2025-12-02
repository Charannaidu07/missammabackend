#!/usr/bin/env bash
# build.sh

set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create media directory if it doesn't exist
mkdir -p media

# Apply database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

echo "Build completed successfully!"