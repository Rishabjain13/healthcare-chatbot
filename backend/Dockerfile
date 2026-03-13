# Dockerfile for FastAPI Healthcare Backend
# Runs on port 3000 (no conflict with your existing services)

FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first (layer caching)
COPY requirements.txt .

# Upgrade pip + install dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Create runtime directories (mounted as volumes)
RUN mkdir -p /app/logs /app/credentials

# Expose API port
EXPOSE 3000

# Environment safety
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Start FastAPI (PRODUCTION MODE)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]