# Use slim Python image for smaller size
FROM python:3.11-slim

# Cache buster - add this line
ARG CACHEBUST=1

# Install system dependencies for nsjail
RUN apt-get update && apt-get install -y \
    autoconf \
    bison \
    flex \
    gcc \
    g++ \
    git \
    libnl-route-3-dev \
    libtool \
    make \
    pkg-config \
    protobuf-compiler \
    libprotobuf-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Build and install nsjail
WORKDIR /tmp
RUN git clone --depth 1 https://github.com/google/nsjail.git && \
    cd nsjail && \
    make && \
    cp nsjail /usr/local/bin/ && \
    cd .. && \
    rm -rf nsjail

# Install Python dependencies
RUN pip install --no-cache-dir flask gunicorn pandas numpy

# Set working directory
WORKDIR /app

# Copy application code
COPY app.py .

# Create non-root user for running the app
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "60", "app:app"]