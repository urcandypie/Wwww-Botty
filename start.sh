#!/bin/bash

# MEI MEI - Railway Start Script

echo "🚀 Starting MEI MEI on Railway..."

# Start Ollama service in background
ollama serve &

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
sleep 10

# Pull the model
echo "📥 Pulling Qwen 2.5 Coder 32B model..."
ollama pull qwen2.5-coder:7b

echo "✅ Model ready!"

# Start the bot
echo "🤖 Starting MEI MEI bot..."
python3 main.py
