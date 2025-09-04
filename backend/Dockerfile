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

# Stage 5: Define the command to run the application.
# --source specifies the file, which makes the framework map the function to the root path (/).
# --target specifies the function name to run.
# --signature-type=http is used for direct HTTP invocations.
CMD exec functions-framework --source=main.py --target=main --signature-type=http --port=$PORT
