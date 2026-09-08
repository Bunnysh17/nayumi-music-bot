FROM python:3.11-slim

# Install system dependencies: OpenJDK 17 (for Lavalink), FFmpeg, libopus, and build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    ffmpeg \
    libopus-dev \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Set environment
ENV PYTHONUNBUFFERED=1

# Start the bot
CMD ["python", "bot.py"]
