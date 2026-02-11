FROM python:3.11

# Install system packages (including zstd support)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    zstd \
    xz-utils \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama safely
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# Copy requirements first
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

EXPOSE 11434

# Start Ollama + wait + pull model + start bot
CMD bash -c "\
ollama serve & \
sleep 8 && \
ollama pull qwen2.5:7b && \
python main.py"