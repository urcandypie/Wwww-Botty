#!/usr/bin/env python3
import os
import re
import time
import json
import asyncio
import logging
import aiohttp
from pathlib import Path
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties

# Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mei-mei")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:7b"  # Fast default
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "/app/knowledge_base")

# Bot setup
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# -------------------------------------------------
# OLLAMA FUNCTIONS
# -------------------------------------------------

async def run_ollama(prompt: str, model: str = None, timeout: int = 45) -> str:
    """Call Ollama API with optimized parameters"""
    if model is None:
        model = OLLAMA_MODEL
    
    system_prompt = """You are MEI MEI created by L1xky.
Expert in:
- API reverse engineering
- checkout flows
- browser automation
- token chaining
- web scraping
- security testing
"""
    
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 768,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "num_thread": 8,  # Use more threads with 8 vCPU
        }
    }
    
    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            logger.info(f"Sending to {model}: {prompt[:100]}...")
            start_time = time.time()
            
            async with session.post(OLLAMA_API_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("response", "").strip()
                    
                    elapsed = time.time() - start_time
                    logger.info(f"Response received in {elapsed:.2f}s")
                    
                    return result
                else:
                    return f"API Error: {response.status}"
                    
    except asyncio.TimeoutError:
        return "⚠️ Response timeout. Try a shorter query."
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return f"Error: {str(e)[:200]}"

# -------------------------------------------------
# SIMPLE WEBSITE ANALYSIS (NO BROWSER)
# -------------------------------------------------

async def simple_website_analysis(chat_id: int, url: str):
    """Simple website analysis using HTTP requests"""
    
    await bot.send_message(chat_id, f"🔍 Analyzing: {url}")
    await bot.send_message(chat_id, "📡 Fetching website info...")
    
    try:
        # Simple HTTP request to get basic info
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                html = await response.text()
                
                # Basic analysis
                title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
                title = title_match.group(1) if title_match else "No title"
                
                # Look for common API patterns
                api_patterns = re.findall(r'(?:api|ajax|json|graphql)[^"\']*["\']([^"\']+)["\']', html, re.IGNORECASE)
                api_endpoints = list(set(api_patterns))[:10]
                
                # Look for forms
                forms = re.findall(r'<form[^>]*action=["\']([^"\']*)["\'][^>]*>', html, re.IGNORECASE)
                
                analysis_prompt = f"""
Website: {url}
Title: {title}
Status: {response.status}

Found {len(api_endpoints)} potential API endpoints:
{chr(10).join(f'- {ep}' for ep in api_endpoints)}

Found {len(forms)} forms:
{chr(10).join(f'- {form}' for form in forms[:5])}

Analyze this website for:
1. Potential API endpoints and their purposes
2. Security considerations
3. Checkout/payment flow indicators
4. Recommended testing approach
"""
                
                await bot.send_message(chat_id, "🧠 Analyzing with AI...")
                result = await run_ollama(analysis_prompt)
                
                summary = f"✅ Analysis Complete\n\n"
                summary += f"📊 Title: {title}\n"
                summary += f"🔗 Status: {response.status}\n"
                summary += f"🔍 Found {len(api_endpoints)} API patterns\n"
                summary += f"📝 Found {len(forms)} forms\n\n"
                summary += result
                
                if len(summary) > 3500:
                    await bot.send_message(chat_id, summary[:3500])
                    await bot.send_message(chat_id, summary[3500:])
                else:
                    await bot.send_message(chat_id, summary)
                    
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Analysis failed: {str(e)[:200]}")

# -------------------------------------------------
# KNOWLEDGE BASE
# -------------------------------------------------

def load_knowledge():
    """Load knowledge base for context"""
    try:
        summaries = []
        for file in os.listdir(KNOWLEDGE_BASE_DIR):
            if file.endswith('.md') or file.endswith('.txt'):
                with open(os.path.join(KNOWLEDGE_BASE_DIR, file), 'r') as f:
                    content = f.read()
                    if len(content) > 1000:
                        content = content[:1000] + "..."
                    summaries.append(f"[{file}]: {content}")
        
        return "\n\n".join(summaries[:3]) if summaries else "No knowledge base entries yet."
    except:
        return "Knowledge base not available."

# -------------------------------------------------
# HANDLERS
# -------------------------------------------------

@router.message(CommandStart())
async def start_handler(m: Message):
    await m.answer(
        "🤖 MEI MEI - Advanced AI Assistant\n\n"
        "I can help with:\n"
        "• Website analysis (send a URL)\n"
        "• API reverse engineering\n"
        "• Code review & debugging\n"
        "• Security testing advice\n"
        "• Technical Q&A\n\n"
        "Commands:\n"
        "/mode [fast|quality] - Switch between 7B (fast) and 14B (quality)\n"
        "/knowledge - View knowledge base\n\n"
        "Powered by Qwen2.5 Coder (7B/14B) • 25GB RAM"
    )

@router.message(Command("mode"))
async def mode_handler(m: Message):
    """Switch between models"""
    global OLLAMA_MODEL
    args = m.text.split()
    
    if len(args) > 1:
        mode = args[1].lower()
        if mode in ["fast", "7b"]:
            OLLAMA_MODEL = "qwen2.5-coder:7b"
            await m.answer("✅ Switched to 7B model (fast responses)")
        elif mode in ["quality", "14b"]:
            OLLAMA_MODEL = "qwen2.5-coder:14b"
            await m.answer("✅ Switched to 14B model (better quality)")
        else:
            await m.answer("Usage: /mode [fast|quality]")
    else:
        await m.answer(f"Current model: {OLLAMA_MODEL}\nUse /mode fast or /mode quality")

@router.message(Command("knowledge"))
async def knowledge_handler(m: Message):
    """Show knowledge base"""
    knowledge = load_knowledge()
    await m.answer(f"📚 Knowledge Base:\n\n{knowledge[:3500]}")

@router.message(F.text)
async def message_handler(m: Message):
    """Handle all text messages"""
    
    # Detect URL
    urls = re.findall(r'https?://[^\s]+', m.text)
    
    if urls:
        url = urls[0]
        await m.answer(f"🌐 URL detected: {url}\nStarting analysis...")
        asyncio.create_task(simple_website_analysis(m.chat.id, url))
        return
    
    # Check for special queries
    text_lower = m.text.lower()
    
    if any(x in text_lower for x in ["who are you", "about", "help"]):
        await m.answer(
            "I'm MEI MEI - an AI assistant specialized in:\n"
            "• API Reverse Engineering\n"
            "• Web Security Testing\n"
            "• Browser Automation\n"
            "• Code Analysis\n"
            "• Checkout Flow Analysis\n\n"
            "Send me a URL to analyze a website, or ask me anything technical!"
        )
        return
    
    # General chat
    await bot.send_chat_action(m.chat.id, "typing")
    
    # Add context from knowledge base for technical questions
    if any(word in text_lower for word in ["api", "checkout", "security", "token", "csrf", "xss", "sql"]):
        context = f"Knowledge Context:\n{load_knowledge()}\n\nQuestion: {m.text}"
        response = await run_ollama(context)
    else:
        response = await run_ollama(m.text)
    
    # Send response
    if len(response) > 3500:
        await m.answer(response[:3500])
        if len(response) > 3500:
            await m.answer(response[3500:])
    else:
        await m.answer(response)

# -------------------------------------------------
# MAIN
# -------------------------------------------------

async def main():
    logger.info("🚀 Starting MEI MEI with 25GB RAM configuration")
    logger.info(f"🤖 Model: {OLLAMA_MODEL}")
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())