FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# Install Python and system dependencies (ADD zstd HERE)
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    curl \
    wget \
    git \
    build-essential \
    libssl-dev \
    libffi-dev \
    zstd \        # ← ADD THIS LINE
    && rm -rf /var/lib/apt/lists/*

# Install Ollama (NOW IT WILL WORK)
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy bot files
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Create knowledge base directory
RUN mkdir -p /app/knowledge_base

# Run the bot
CMD ["./start.sh"]