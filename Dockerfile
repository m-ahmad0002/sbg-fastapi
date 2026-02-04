# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /code

# Ensure project root is on PYTHONPATH
ENV PYTHONPATH=/code

# Install system dependencies (only if needed by any wheels)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy ALL project files (app/, db/, etc.)
COPY . /code

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
