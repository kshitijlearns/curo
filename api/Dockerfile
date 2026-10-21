# One image for the API, the worker and the scheduler (they share the `curo` package).
# Build context: the repo root.  docker build -f api/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /repo
COPY api ./api
COPY worker ./worker
COPY db ./db
COPY fixtures ./fixtures

# Editable installs: in local dev the repo is mounted over /repo, so code changes
# are picked up live without rebuilding.
RUN pip install -c ./api/constraints.txt -e ./api -e ./worker

WORKDIR /repo/api
EXPOSE 8000

# Production default (Railway). docker-compose overrides this for local dev.
CMD ["sh", "-c", "uvicorn curo.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
