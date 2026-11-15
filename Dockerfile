# ==============================================================================
# All-in-One Production Dockerfile for AGV Network Telemetry Dashboard
# Base Image: python:3.11-slim
# Default Port: 9921 (.env DASHBOARD_PORT / PORT)
# ==============================================================================

FROM python:3.11-slim

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

# Create tsdb storage directory with proper read/write permissions
RUN mkdir -p /app/tsdb_data && chmod 777 /app/tsdb_data

# Expose web service port (default: 9921)
EXPOSE 9921

# Health check against FastAPI /api/health endpoint on port 9921
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:9921/api/health || exit 1

# Start FastAPI application using uvicorn on port 9921
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9921"]
