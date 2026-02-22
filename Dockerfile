# Use the official Playwright image which includes all system dependencies
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Set work directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port your app runs on
EXPOSE 8000

# Start command (update 'main:app' to match your entry point)
# Add --access-logfile - and --error-logfile - to see all traffic in Render logs
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]