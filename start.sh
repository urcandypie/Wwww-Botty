#!/bin/bash

# MEI MEI - Railway Start Script (OPTIMIZED)

echo "🚀 Starting MEI MEI with 32GB RAM..."

# Start Ollama service in background
echo "▶️ Starting Ollama service..."
ollama serve &

# Wait for Ollama to be ready (with health check)
echo "⏳ Waiting for Ollama to start..."
for i in {1..20}; do
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        echo "✅ Ollama is ready!"
        break
    fi
    echo "Waiting for Ollama... ($i/20)"
    sleep 2
done

# Pull the model (Qwen 2.5 Coder 14B - BEST BALANCE)
echo "📥 Pulling Qwen 2.5 Coder 14B model (Optimal for 32GB)..."
ollama pull qwen2.5-coder:14b

# Optional: Pull a faster model for simple queries
echo "📥 Pulling Phi-3 Mini (3.8B) for ultra-fast responses..."
ollama pull phi3:mini &

echo "✅ Models ready!"
echo "🤖 RAM: 32GB • CPU: 8 vCPU"
echo "🚀 Starting MEI MEI bot..."
python3 main.py