# backend/Dockerfile

# Stage 1: Use a modern, lightweight Python image
FROM python:3.11-slim

# Set best practices for Python environment
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Stage 2: Set the working directory
WORKDIR /app

# Stage 3: Install dependencies
# Copy only the requirements file first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 4: Copy the backend application code
COPY . .

# Stage 5: Define the command to run the application with Gunicorn
# Gunicorn is a production-ready web server for Python.
# Cloud Run provides the $PORT environment variable.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:main
