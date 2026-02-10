#!/usr/bin/env python3
import os
import re
import time
import asyncio
import subprocess
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OLLAMA_MODEL = "qwen2.5-coder:32b"
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "/app/knowledge_base")
MAX_TIMEOUT = 3600

os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================= HELPERS =================
def detect_intent(message: str) -> dict:
    msg = message.lower()
    urls = re.findall(r'https?://[^\s]+', message)

    if urls or any(w in msg for w in ["analyze", "website", "site", "scrape", "api"]):
        return {"type": "website_analysis", "url": urls[0] if urls else None}

    if any(w in msg for w in ["dork", "google dork"]):
        return {"type": "dork"}

    if any(w in msg for w in ["who are you", "about you", "introduce"]):
        return {"type": "intro"}

    return {"type": "general"}

def run_ollama(prompt: str, timeout=300) -> str:
    try:
        cmd = ["ollama", "run", OLLAMA_MODEL, prompt]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else r.stderr
    except Exception as e:
        return str(e)

def analyze_website(url: str) -> str:
    cmd = f"curl -s -L -A 'Mozilla/5.0' '{url}' | head -c 12000"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout or r.stderr

# ================= UI =================
WELCOME_TEXT = """
<b>MEI MEI</b>
<i>AI Assistant with Full System Access</i>

━━━━━━━━━━━━━━━━━━━━━━━

Hi! I'm MEI MEI, your intelligent assistant.

<b>What I can do:</b>
• Scrape websites using curl
• Generate APIs (login / payment / checkout)
• Generate Google dorks
• Analyze & fix code

<b>Examples:</b>
• Scrape https://example.com
• Generate dorks for payment gateway
• Who are you?

━━━━━━━━━━━━━━━━━━━━━━━
<b>Developer:</b> <a href="https://t.me/l1xky">L1xky</a>
"""

INTRO_TEXT = """
I'm <b>MEI MEI</b>, an advanced AI assistant created by <b>L1xky</b>.

<b>Capabilities:</b>
• Web scraping
• API generation
• Code debugging
• Research & dorks

<i>Fast. Direct. No excuses.</i>
"""

# ================= HANDLERS =================
@router.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(WELCOME_TEXT, disable_web_page_preview=True)

@router.message()
async def chat_handler(message: Message):
    intent = detect_intent(message.text)
    processing = await message.answer("<i>Processing...</i>")

    start_time = time.time()

    try:
        if intent["type"] == "intro":
            reply = INTRO_TEXT

        elif intent["type"] == "website_analysis":
            if not intent["url"]:
                reply = "❌ Please provide a website URL."
            else:
                html = analyze_website(intent["url"])
                prompt = f"""
Analyze this website and generate Python API code.

URL: {intent["url"]}
HTML:
{html[:4000]}
"""
                reply = run_ollama(prompt, MAX_TIMEOUT)

        elif intent["type"] == "dork":
            kw = message.text.replace("dork", "").strip()
            dorks = [
                f'inurl:"{kw}"',
                f'intitle:"{kw}" inurl:login',
                f'inurl:"{kw}" api',
                f'inurl:"{kw}" checkout'
            ]
            reply = "<b>Generated Dorks</b>\n\n" + "\n".join(f"• <code>{d}</code>" for d in dorks)

        else:
            reply = run_ollama(message.text, 300)

        elapsed = time.time() - start_time
        await processing.delete()

        final = f"{reply}\n\n<i>Response time: {elapsed:.2f}s</i>"
        await message.answer(final[:4000], disable_web_page_preview=True)

    except Exception as e:
        await processing.edit_text(f"❌ Error: {e}")

# ================= MAIN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
