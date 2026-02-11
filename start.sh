#!/bin/bash

set -e

echo "🚀 Starting MEI MEI (32GB Mode)"

# =========================
# Check Ollama Health
# =========================
check_ollama() {
    echo "⏳ Waiting for Ollama to become ready..."
    until curl -s http://localhost:11434/api/tags > /dev/null; do
        sleep 2
    done
    echo "✅ Ollama is ready!"
}

# =========================
# Start Ollama
# =========================
echo "▶️ Starting Ollama..."
ollama serve > /dev/null 2>&1 &

# Wait until Ollama is fully up
check_ollama

# =========================
# Pull Model (Only if missing)
# =========================
MODEL="qwen2.5-coder:14b"

if ! ollama list | grep -q "$MODEL"; then
    echo "📥 Pulling $MODEL..."
    ollama pull $MODEL
else
    echo "✅ Model already exists."
fi

echo "📋 Available models:"
ollama list

# =========================
# Start Bot (Auto Restart)
# =========================
echo "🚀 Starting MEI MEI bot..."

while true; do
    python3 main.py
    echo "⚠️ Bot crashed. Restarting in 5 seconds..."
    sleep 5
done