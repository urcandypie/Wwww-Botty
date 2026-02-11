FROM python:3.11

# Install system packages
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    zstd \
    xz-utils \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# 🔥 ADD THIS LINE (VERY IMPORTANT)
RUN chmod +x start.sh

EXPOSE 11434

CMD ["./start.sh"]