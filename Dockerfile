# Use a slim Python image to keep the build light and fast [cite: 1]
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies required for psycopg2 and general building
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache [cite: 2]
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code (Fixed syntax)
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=debug

# Expose the port (Ensure this matches fly.toml internal_port)
EXPOSE 8000

# Start command using Gunicorn
# Using 0.0.0.0 is critical for Fly.io to route traffic to the container
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--log-level", "debug"]