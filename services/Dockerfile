# FlowDesk backend image — runs BOTH the FastAPI service and the per-minute
# worker from one image (pick the process via the compose `command`).
#
#   build context MUST be the repo `services/` dir (it needs engine + api):
#     docker build -f services/Dockerfile -t flowdesk-backend services/
#
# Python is pinned to 3.11 to match `flowdesk-api` (requires-python ==3.11.*)
# and the engine's <3.13 cap. numpy/scipy resolve to manylinux wheels here.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl is used by the compose healthcheck against /healthz.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the engine first (the api depends on it as `flowdesk-engine`), then the
# api. Editable installs keep the `db` top-level package (alongside api/src)
# importable exactly as the test/pythonpath config expects.
# NOTE: the live feed needs the [ingest] extra (databento>=0.80). It is NOT
# installed here — the beta image runs historical-only and arming live is an
# operator procedure (docs/ops/deploy-runbook.md §5). Build with
# `--build-arg WITH_INGEST=1` only for an environment that will arm live.
ARG WITH_INGEST=0

COPY engine /app/engine
RUN if [ "$WITH_INGEST" = "1" ]; then \
        pip install -e "/app/engine[ingest]"; \
    else \
        pip install -e "/app/engine"; \
    fi

COPY api /app/api
RUN pip install -e /app/api

# Run as a non-root user.
RUN useradd --create-home --uid 10001 flowdesk \
    && chown -R flowdesk:flowdesk /app
USER flowdesk

# Default to the API; compose overrides `command` for the worker service.
# The api package layout puts `db` next to `src`, so both are on the path.
WORKDIR /app/api
ENV PYTHONPATH=/app/api/src:/app/api

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
