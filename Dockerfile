FROM python:3.11-slim

WORKDIR /app

# System dependencies for chromadb / sentence-transformers
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Persistent data volume mount point
RUN mkdir -p /root/.omnicontext/data/chromadb

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/stats || exit 1

CMD ["python", "cli.py", "serve"]
