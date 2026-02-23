# Use the official Playwright image which includes all system dependencies
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Set work directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# Copy your application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=debug
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Expose the port your app runs on
EXPOSE 8000

# Start command
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app",
     "--bind", "0.0.0.0:8000",
     "--access-logfile", "-",
     "--error-logfile", "-",
     "--capture-output",
     "--log-level", "debug"]