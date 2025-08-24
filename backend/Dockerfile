# backend/Dockerfile

# 1. Use the same base image for consistency
FROM python:3.10-slim

# 2. Set the working directory
WORKDIR /app

# 3. Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of the backend source code
COPY . .

# 5. Set the entrypoint. functions-framework will automatically
# listen on the PORT environment variable provided by Cloud Run.
CMD ["functions-framework", "--target=main", "--signature-type=cloudevent"]
