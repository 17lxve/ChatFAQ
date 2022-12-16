#!/bin/bash
set -e

echo "Apply database migrations"
python manage.py migrate

if [ "DJANGO_SUPERUSER_PASSWORD" ] && [ "DJANGO_SUPERUSER_USERNAME" ] && [ "DJANGO_SUPERUSER_EMAIL" ]
then
    echo "Creating super user"
    {
      python manage.py createsuperuser \
        --noinput \
        --username $DJANGO_SUPERUSER_USERNAME \
        --email $DJANGO_SUPERUSER_EMAIL
    } || {
        echo "Superuser already existed"
    }
fi

echo "Applying fixtures"
make apply_fsm_fixtures

echo "Launching Django..."
daphne -b 0.0.0.0 -p 8000 riddler.config.asgi:application