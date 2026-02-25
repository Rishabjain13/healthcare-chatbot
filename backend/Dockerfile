# Dockerfile for FastAPI Healthcare Backend
# Runs on port 3000 (no conflict with your existing services)

FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for Google credentials if needed
RUN mkdir -p /app/credentials

# Expose FastAPI port
EXPOSE 3000

# Environment variables (overridden by docker-compose or .env)
ENV PORT=3000
ENV RASA_URL=http://rasa:5005
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run FastAPI with uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--reload"]
