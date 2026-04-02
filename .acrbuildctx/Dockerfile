# --- Build Stage (Optional but recommended for smaller final images) ---
# We use a standard Python 3.10 image as the base
FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
# These are required for compiling dlib, face_recognition, and processing audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    unzip \
    yasm \
    pkg-config \
    libswscale-dev \
    libtbb2 \
    libtbb-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavformat-dev \
    libpq-dev \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    ffmpeg \
    libportaudio2 \
    portaudio19-dev \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create storage directory for temporary processing
RUN mkdir -p storage && chmod 777 storage

# Expose the port the app runs on
EXPOSE 5000

# Set environment variables for production
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Run the application with Gunicorn
# 4 workers is a good start for a production server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--preload", "--timeout", "120", "app:app"]
