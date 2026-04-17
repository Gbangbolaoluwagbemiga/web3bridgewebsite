FROM python:3.12-slim

WORKDIR /app

# Install psycopg2 dependencies for alembic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Build context must be the monorepo root (how Koyeb builds by default):
#   docker build -f portal_backend/Dockerfile .
# If you instead set Koyeb "Root directory" / context to portal_backend only,
# use: docker build -f Dockerfile .   (paths below would need reverting to requirements.txt + COPY . .)
COPY portal_backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

COPY portal_backend/ .

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8100}"]
