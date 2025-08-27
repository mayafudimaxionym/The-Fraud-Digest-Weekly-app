# Dockerfile

# Stage 1: Use a modern, lightweight Python image
FROM python:3.11-slim

# Set best practices for Python environment in containers for logging and clean directories
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Stage 2: Set the working directory inside the container
WORKDIR /app

# Stage 3: Copy and install dependencies
# First, upgrade pip to the latest version to ensure compatibility
RUN pip install --upgrade pip

# Copy requirements from the frontend folder and install them.
# This leverages Docker's layer caching.
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 4: Copy the application source code from the frontend folder
COPY frontend/ .

# Stage 5: Expose the port that Cloud Run expects
EXPOSE 8080

# Stage 6: Define the command to run the application
# Use CMD for the main running process.
# --server.port=8080 is CRITICAL for Cloud Run compatibility.
# --server.headless=true is a best practice for containerized environments.
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.headless=true"]
