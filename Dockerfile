FROM python:3.11

# Install required system packages (zstd fix included)
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

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

EXPOSE 11434

# Start Ollama + Pull 7B + Start Bot
CMD bash -c "\
ollama serve & \
sleep 6 && \
ollama pull qwen2.5:7b && \
python main.py"