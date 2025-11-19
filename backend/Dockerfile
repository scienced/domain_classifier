FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium browser
RUN playwright install --with-deps chromium

# Copy application code
COPY backend/app/ ./app/

# Copy config directory from project root
COPY config/ ./config/

# Create volume mount point for database
VOLUME ["/app/data"]

# Expose API port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
