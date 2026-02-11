#!/bin/bash

set -e

echo "🚀 Starting MEI MEI (7B Mode)"

MODEL="qwen2.5:7b"

# =========================
# Wait for Ollama
# =========================
check_ollama() {
    echo "⏳ Waiting for Ollama..."
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

check_ollama

# =========================
# Pull Model if Missing
# =========================
if ! ollama list | grep -q "$MODEL"; then
    echo "📥 Pulling $MODEL..."
    ollama pull $MODEL
else
    echo "✅ $MODEL already installed."
fi

echo "📋 Available models:"
ollama list

# =========================
# Start Bot (Auto Restart Loop)
# =========================
echo "🚀 Starting MEI MEI bot..."

while true; do
    python3 main.py
    echo "⚠️ Bot crashed. Restarting in 5 seconds..."
    sleep 5
done