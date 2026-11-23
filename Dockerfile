# Container image for Google Cloud Run.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Production settings refuse to load without a secret and a PostgreSQL URL.
# collectstatic never touches the database, so build-only placeholders are
# enough here; the real values are supplied by Cloud Run at runtime.
RUN DJANGO_DEBUG=False \
    DJANGO_SECRET_KEY=build-only-placeholder \
    DATABASE_URL=postgresql://build@localhost/build \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

# Cloud Run sends traffic to $PORT and terminates HTTPS in front of the app.
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 0 \
    --access-logfile - --error-logfile - tayota_crm.wsgi:application
