FROM python:3.11-slim

WORKDIR /app

# Install ALL required system dependencies for Playwright Chromium
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    unzip \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libx11-xcb1 \
    libxshmfence1 \
    libglib2.0-0 \
    libnspr4 \
    libexpat1 \
    libxcb1 \
    libxext6 \
    libxfixes3 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libcairo2 \
    libfontconfig1 \
    libfreetype6 \
    libharfbuzz0b \
    libpixman-1-0 \
    libxrender1 \
    libxcb-render0 \
    libxcb-shm0 \
    # Additional dependencies found to be necessary
    libwayland-client0 \
    libwayland-server0 \
    libx11-6 \
    libxcb1 \
    libxcb-dri3-0 \
    libxcb-present0 \
    libxss1 \
    libxtst6 \
    libnss3-tools \
    libevent-2.1-7 \
    libappindicator3-1 \
    libsecret-1-0 \
    libdbus-1-3 \
    libdrm2 \
    libegl1 \
    libopus0 \
    libwoff1 \
    libxslt1.1 \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright WITHOUT browser (we'll use system Chromium)
RUN pip install playwright==1.45.0

# Copy the rest of the application
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Create knowledge base directory
RUN mkdir -p /app/knowledge_base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1  # Skip Playwright browser download
ENV DISPLAY=:99

# Run the start script
CMD ["./start.sh"]