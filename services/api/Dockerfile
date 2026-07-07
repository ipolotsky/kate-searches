# syntax=docker/dockerfile:1.7
# API + Celery worker/beat (role is set via `command:` in compose).
# Default image is lightweight — no Playwright (crawl4ai lives behind the [scraper] extra).

# builder: venv + dependencies, cached by pyproject.toml (editing app code never re-runs pip)
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
# Insurance only: lxml/psycopg[binary]/uvicorn[standard] ship manylinux wheels, so normally
# nothing compiles here. Build tooling stays in this stage and never reaches the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
WORKDIR /app
# deps layer: only the manifest is present -> installs [project.dependencies] (the empty app
# package builds fine). Cached until pyproject.toml changes.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .
# source in a later layer so code edits do not invalidate the deps layer
COPY . .

# runtime: slim image, no build tooling; app imported via PYTHONPATH (no editable .pth)
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app
RUN useradd -r -u 1001 -m appuser
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --from=builder /app /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
