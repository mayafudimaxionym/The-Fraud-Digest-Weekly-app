# Dockerfile

# Stage 1: Use an official Python runtime as a parent image
# Dockerfile for the frontend Streamlit application
FROM python:3.10-slim

# Stage 2: Set the working directory inside the container
WORKDIR /app

# Stage 3: Copy and install dependencies
# First, upgrade pip to the latest version to ensure compatibility
RUN pip install --upgrade pip

 # Copy requirements from the frontend folder
 COPY frontend/requirements.txt .
 RUN pip install --no-cache-dir -r requirements.txt

# Stage 4: Download the spaCy model separately
# This is a separate layer, so it's only re-run if the model version changes.
# RUN python -m spacy download en_core_web_sm

 # Copy the application source code from the frontend folder
 COPY frontend/ .

# Stage 6: Expose the port the app runs on
EXPOSE 8501

# Stage 7: Add a healthcheck
HEALTHCHECK CMD streamlit hello

# Stage 8: Define the command to run the application
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]