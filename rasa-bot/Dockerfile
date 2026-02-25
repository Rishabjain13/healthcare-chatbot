# Dockerfile for Rasa Healthcare Bot - Production Linux Build
# Optimized for GCP/Cloud deployment
# Platform: linux/amd64

FROM --platform=linux/amd64 rasa/rasa:3.6.21-full

# Set working directory
WORKDIR /app

# Switch to root to copy files
USER root

# Copy all Rasa project files including pre-trained models
COPY --chown=1001:1001 . /app

# Ensure models directory exists and has correct permissions
RUN mkdir -p /app/models && chown -R 1001:1001 /app/models

# Expose Rasa API port
EXPOSE 5005

# Switch back to non-root user for security
USER 1001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5005', timeout=5)"

# Start Rasa server with API enabled, bind to all interfaces
CMD ["run", "--enable-api", "--cors", "*", "-p", "5005", "-i", "0.0.0.0"]
