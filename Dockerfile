FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# 🔥 Ensure PATH
ENV PATH="/usr/local/bin:${PATH}"

ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_MODELS=/app/.ollama

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY start.sh .

RUN chmod +x start.sh
RUN mkdir -p /app/.ollama

EXPOSE 11434

CMD ["./start.sh"]
