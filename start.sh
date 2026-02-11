#!/bin/bash

set -e  # Exit on any error

echo "🚀 Starting MEI MEI with 32GB RAM..."

# Function to check Ollama health
check_ollama() {
    for i in {1..10}; do
        if curl -s http://localhost:11434/api/tags > /dev/null; then
            echo "✅ Ollama is ready!"
            return 0
        fi
        sleep 3
    done
    echo "❌ Ollama failed to start"
    return 1
}

# Start Ollama
echo "▶️ Starting Ollama service..."
ollama serve &

# Wait for Ollama
check_ollama || exit 1

# Pull model
echo "📥 Pulling Qwen 2.5 Coder 14B model..."
ollama pull qwen2.5-coder:14b || {
    echo "❌ Failed to pull model, trying smaller model..."
    ollama pull qwen2.5-coder:7b
}

# List models
echo "📋 Available models:"
ollama list || curl -s http://localhost:11434/api/tags

# Start bot with error handling
echo "🚀 Starting MEI MEI bot..."
while true; do
    python3 main.py || {
        echo "⚠️ Bot crashed, restarting in 5 seconds..."
        sleep 5
    }
done