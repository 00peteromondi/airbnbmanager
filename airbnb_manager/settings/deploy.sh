#!/bin/bash

# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate --settings=airbnb_manager.settings.production

# Collect static files
python manage.py collectstatic --noinput --settings=airbnb_manager.settings.production

# Restart Gunicorn
sudo systemctl restart gunicorn

# Restart Nginx
sudo systemctl restart nginx

# Clear cache (if needed)
# python manage.py clear_cache --settings=airbnb_manager.settings.production

echo "Deployment complete"
