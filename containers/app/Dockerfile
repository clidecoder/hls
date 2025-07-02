# Multi-stage build for efficiency
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy requirements first for better caching
WORKDIR /app
COPY requirements.txt .

# Install Python dependencies with UV
RUN uv pip install --system -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    gnupg \
    lsb-release \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install webhook service (adnanh/webhook)
RUN wget https://github.com/adnanh/webhook/releases/download/2.8.0/webhook-linux-amd64.tar.gz \
    && tar -xzf webhook-linux-amd64.tar.gz \
    && mv webhook-linux-amd64/webhook /usr/local/bin/ \
    && rm -rf webhook-linux-amd64*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user
RUN useradd -m -s /bin/bash app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy application code
COPY hls/ ./hls/
COPY webhook_dispatch.py .
COPY prompts/ ./prompts/

# Create necessary directories
RUN mkdir -p /app/logs /app/outputs /app/config /app/data && \
    chown -R app:app /app

# Copy and set permissions for entrypoint
COPY containers/app/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Switch to non-root user
USER app

# Set environment variables
ENV PYTHONPATH=/app
ENV PATH="/home/app/.local/bin:${PATH}"

# Configure Claude
RUN mkdir -p /home/app/.claude

# Expose ports
EXPOSE 8000 9000

# Use entrypoint script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
