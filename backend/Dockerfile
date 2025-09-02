# backend/Dockerfile

# Stage 1: Use a modern, lightweight Python image
FROM python:3.11-slim

# Set best practices for Python environment
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Stage 2: Set the working directory
WORKDIR /app

# Stage 3: Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 4: Copy the backend application code
COPY . .

# Stage 5: Define the command to run the application using the Functions Framework.
# This is the standard way to run a function designed with this framework.
# Cloud Run provides the $PORT environment variable.
CMD exec functions-framework --target=main --signature-type=cloudevent --port=$PORT
