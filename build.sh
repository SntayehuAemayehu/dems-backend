#!/bin/bash

echo "🚀 Building DEMS for Render..."

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate

echo "✅ Build complete!"