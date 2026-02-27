# Use a slim Python image to keep the build light and fast
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies required for psycopg2 and general building
# libpq-dev is the fix for the "pg_config executable not found" error
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install and upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Environment variables
# PYTHONUNBUFFERED ensures logs are sent straight to Render's dashboard
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=debug

# Expose the port Render expects
EXPOSE 8000

# Start command using Gunicorn and Uvicorn workers
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--log-level", "debug"]