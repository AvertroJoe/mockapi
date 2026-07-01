FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/
COPY cli/ ./cli/

# Data directory is expected to be a mounted volume at runtime.
# Run as an unprivileged user rather than the container default (root) —
# this app parses arbitrary uploaded files, so if a parsing dependency
# ever has an exploitable bug, a non-root process limits what an attacker
# who achieves code execution inside the container can do.
# UID/GID are pinned (not auto-assigned) so upgrades of an existing
# deployment can reliably `chown` the pre-existing volume to match — see
# the "Upgrading to a non-root container" note in the README.
RUN mkdir -p /data/artifacts \
    && groupadd --system --gid 999 mockapi \
    && useradd --system --uid 999 --gid mockapi --home-dir /app --no-create-home mockapi \
    && chown -R mockapi:mockapi /app /data

USER mockapi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
