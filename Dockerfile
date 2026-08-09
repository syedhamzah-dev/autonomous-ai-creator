# Use an official lightweight Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV APP_ENV=prod

# Set work directory inside the container
WORKDIR /app

# Copy dependency definition files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY app/ ./app/
COPY docs/ ./docs/
COPY README.md .

# Create persistent storage folder for memory logs
RUN mkdir -p data/memory

# Expose target port
EXPOSE 8000

# Production startup command using uvicorn binding to PORT env
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
