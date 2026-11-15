# ==============================================================================
# All-in-One Production Dockerfile for AGV Network Telemetry Dashboard
# Base Image: python:3.11-slim
# Default Port: 9921 (.env DASHBOARD_PORT / PORT)
# ==============================================================================

FROM python:3.11-slim

LABEL org.opencontainers.image.title="AGV/AMR-ACS Wireless Network Telemetry Dashboard" \
      org.opencontainers.image.description="AGV/AMR & ACS 18-metric wireless network pre-detection & post-mortem RCA mock-up dashboard" \
      org.opencontainers.image.source="https://github.com/planner77/network_dashboard" \
      org.opencontainers.image.url="https://github.com/planner77/network_dashboard" \
      org.opencontainers.image.version="1.1.2"

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9921 \
    DASHBOARD_PORT=9921 \
    DEFAULT_THEME=light \
    TSDB_PATH=/app/tsdb_data/network_telemetry.db

WORKDIR /app

# Install curl for container HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and documentation
COPY app/ ./app/
COPY docs/ ./docs/
COPY AGENTS.md DESIGN.md README.md ./

# Create tsdb storage directory and pre-seed initial mock-up data into the image
RUN mkdir -p /app/tsdb_data && \
    python -c "from app.tsdb import TSDB; db = TSDB('/app/tsdb_data/network_telemetry.db'); db.seed_initial_data(force=True); db.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)'); db.conn.close()" && \
    chmod -R 777 /app/tsdb_data

# Expose web service port (default: 9921)
EXPOSE 9921

# Health check against FastAPI /api/health endpoint on port 9921
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:9921/api/health || exit 1

# Start FastAPI application using uvicorn on port 9921
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9921"]
