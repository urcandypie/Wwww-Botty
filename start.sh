#!/bin/bash
set -e

echo "🚀 Starting MEI MEI..."

# Ollama binary path
OLLAMA_BIN="/usr/local/bin/ollama"

# Model name
OLLAMA_MODEL="qwen2.5-coder:7b"

# Check Ollama exists
if [ ! -x "$OLLAMA_BIN" ]; then
  echo "❌ Ollama not found at $OLLAMA_BIN"
  exit 1
fi

echo "✅ Ollama found at $OLLAMA_BIN"

# Start Ollama service
echo "⚙️ Starting Ollama server..."
$OLLAMA_BIN serve &
sleep 10

# Pull model
echo "📥 Pulling model: $OLLAMA_MODEL"
$OLLAMA_BIN pull "$OLLAMA_MODEL"

echo "✅ Model ready"

# Start Telegram bot
echo "🤖 Starting Telegram bot..."
python3 /app/main.py
