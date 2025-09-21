FROM --platform=linux/amd64 ubuntu:22.04 AS base

SHELL ["/bin/bash", "-c"]

ENV project=voice-meeting-bot
ENV cwd=/app

WORKDIR $cwd

ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies for both projects
RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    gdb \
    git \
    gfortran \
    libopencv-dev \
    libdbus-1-3 \
    libgbm1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libglib2.0-dev \
    libssl-dev \
    libx11-dev \
    libx11-xcb1 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-xfixes0 \
    libxcb-xtest0 \
    libgl1-mesa-dri \
    libxfixes3 \
    linux-libc-dev \
    pkgconf \
    python3-pip \
    tar \
    unzip \
    zip \
    vim \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Audio dependencies
RUN apt-get update && apt-get install -y \
    libasound2 \
    libasound2-plugins \
    alsa \
    alsa-utils \
    alsa-oss \
    pulseaudio \
    pulseaudio-utils \
    portaudio19-dev \
    python3-pyaudio \
    && rm -rf /var/lib/apt/lists/*

# Alias python3 to python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install Python dependencies for Zoom SDK
RUN pip install pyjwt cython gdown deepgram-sdk python-dotenv opencv-python numpy

# Copy and install voice bot requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install optional API dependencies (comment out if not needed)
RUN pip install fastapi uvicorn

# Copy voice bot source code
COPY src/ ./src/
COPY data/ ./data/
COPY zoom_integration_bridge.py .
COPY test_assemblyai_bot.py .
COPY test_voice_bot.py .

# Copy Zoom SDK
COPY py-zoom-meeting-sdk/ ./py-zoom-meeting-sdk/

# Install Zoom SDK
WORKDIR /app/py-zoom-meeting-sdk
RUN pip install zoom-meeting-sdk

# Return to app directory
WORKDIR /app

# Create temp directory for notes files
RUN mkdir -p temp

# Copy environment file
COPY .env .

# Expose ports
EXPOSE 3000

# Default command runs the integration bridge
CMD ["python", "zoom_integration_bridge.py"]