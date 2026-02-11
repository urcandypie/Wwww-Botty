#!/bin/bash

# MEI MEI - Railway Start Script

echo "🚀 Starting MEI MEI on Railway..."

# Install Playwright with system Chromium
echo "🌐 Setting up Playwright with system Chromium..."
python -m playwright install --with-deps chromium

# Start Ollama service in background
echo "▶️ Starting Ollama service..."
ollama serve &

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        echo "✅ Ollama is ready!"
        break
    fi
    echo "Waiting for Ollama... ($i/30)"
    sleep 2
done

# Pull the model (using 7B, not 32B)
echo "📥 Pulling Qwen 2.5 Coder 7B model..."
ollama pull qwen2.5-coder:7b

# Test Playwright
echo "🧪 Testing Playwright..."
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    page.goto('https://example.com')
    print('✅ Playwright test passed')
    browser.close()
"

echo "✅ Setup complete!"

# Start the bot
echo "🤖 Starting MEI MEI bot..."
python3 main.py