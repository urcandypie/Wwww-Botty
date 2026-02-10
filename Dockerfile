# MEI MEI - Railway Deployment (advanced browser analysis)
FROM python:3.11-slim

# -------------------------------------------------
# System dependencies (Chromium + Playwright deps)
# -------------------------------------------------
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    zstd \
    libnss3 \
    libatk1.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*


# -------------------------------------------------
# Install Ollama
# -------------------------------------------------
RUN curl -fsSL https://ollama.com/install.sh | sh

# -------------------------------------------------
# App
# -------------------------------------------------
WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------
# Install Playwright browser
# -------------------------------------------------
RUN playwright install chromium

# -------------------------------------------------
# Bot files
# -------------------------------------------------
COPY main.py .
COPY start.sh .

RUN chmod +x start.sh

# -------------------------------------------------
# Knowledge base
# -------------------------------------------------
RUN mkdir -p /app/knowledge_base

EXPOSE 8080

CMD ["./start.sh"]