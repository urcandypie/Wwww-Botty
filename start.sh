#!/usr/bin/env bash

set -e

echo "🚀 Starting MEI MEI..."

# Start Ollama in background
echo "🧠 Starting Ollama server..."
ollama serve > /tmp/ollama.log 2>&1 &

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to be ready..."
sleep 8

# Pull model only if not exists (important for speed)
if ! ollama list | grep -q "qwen2.5-coder"; then
  echo "📥 Pulling Qwen 2.5 Coder 32B model..."
  ollama pull qwen2.5-coder:32b
else
  echo "✅ Model already present, skipping pull"
fi

echo "🤖 Starting Telegram bot..."
exec python3 main.py
