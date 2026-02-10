#!/bin/bash

set -e

echo "🚀 Starting MEI MEI..."

OLLAMA_MODEL = "qwen2.5-coder:7b"

if [ ! -f "$OLLAMA_BIN" ]; then
  echo "❌ Ollama not found at $OLLAMA_BIN"
  exit 1
fi

echo "✅ Ollama found"

# Start Ollama
$OLLAMA_BIN serve &
sleep 10

echo "📥 Pulling model..."
OLLAMA_MODEL = "qwen2.5-coder:7b"

echo "🤖 Starting Telegram bot..."
python3 /app/main.py
