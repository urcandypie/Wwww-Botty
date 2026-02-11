#!/usr/bin/env python3
"""
MEI MEI - Smart AI Assistant
Stable Production Version
"""

import os
import asyncio
import time
import re
import aiohttp
import logging
import html

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================================
# CONFIG
# ==========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OLLAMA_MODEL = "qwen2.5-coder:14b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge_base")

os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)

# ==========================================================
# GLOBAL SESSION (Performance Boost)
# ==========================================================

aiohttp_session = None


async def get_session():
    global aiohttp_session
    if aiohttp_session is None:
        aiohttp_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)
        )
    return aiohttp_session


# ==========================================================
# OLLAMA API CALL (FAST VERSION)
# ==========================================================

async def ollama_api_call(prompt: str, system_prompt: str = "", timeout: int = 180) -> str:
    try:
        session = await get_session()

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "num_thread": os.cpu_count() or 4,
            }
        }

        async with session.post(OLLAMA_API_URL, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("response", "").strip()
            return f"API Error: {response.status}"

    except asyncio.TimeoutError:
        return "⚠️ Model timeout."
    except Exception as e:
        return f"Error: {str(e)}"


# ==========================================================
# INTENT DETECTION
# ==========================================================

def detect_intent(message: str):
    message_lower = message.lower()
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, message)

    if urls:
        return {"type": "website", "url": urls[0]}

    if any(word in message_lower for word in ["who are you", "your name", "about you"]):
        return {"type": "intro"}

    return {"type": "general"}


# ==========================================================
# START COMMAND
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>MEI MEI Online</b>\nSend me anything.",
        parse_mode=ParseMode.HTML
    )


# ==========================================================
# MESSAGE HANDLER
# ==========================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    intent = detect_intent(user_message)

    msg = await update.message.reply_text("Processing...")

    try:
        start_time = time.time()

        if intent["type"] == "intro":
            response = "I am MEI MEI, your AI coding assistant."
        else:
            prompt = f"User: {user_message}\nRespond helpfully."
            response = await ollama_api_call(prompt)

        elapsed = time.time() - start_time
        final_text = f"{response}\n\n⏱ {elapsed:.2f}s"

        await msg.delete()

        if len(final_text) > 4000:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(final_text[i:i+4000])
        else:
            await update.message.reply_text(final_text)

    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"Error: {str(e)}")


# ==========================================================
# DOCUMENT HANDLER (FIXED SAFE VERSION)
# ==========================================================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name

    msg = await update.message.reply_text("Analyzing file...")

    try:
        file = await context.bot.get_file(document.file_id)
        file_path = f"/tmp/{file_name}"
        await file.download_to_drive(file_path)

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # SAFE PROMPT (no triple quote break possible)
        prompt = (
            "Analyze this Python file.\n\n"
            f"File: {file_name}\n\n"
            "Code:\n"
            + content[:8000] +
            "\n\nTasks:\n"
            "1. Explain what it does\n"
            "2. Find bugs\n"
            "3. Optimize\n"
            "4. Provide fully fixed production-ready code\n"
        )

        system_prompt = "You are an expert Python debugger."

        response = await ollama_api_call(prompt, system_prompt)

        await msg.delete()

        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(
                    html.escape(response[i:i+4000]),
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.message.reply_text(
                html.escape(response),
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"Error: {str(e)}")


# ==========================================================
# MAIN
# ==========================================================

async def shutdown():
    global aiohttp_session
    if aiohttp_session:
        await aiohttp_session.close()


if __name__ == "__main__":

    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set.")
        print("Run: export TELEGRAM_BOT_TOKEN=YOUR_TOKEN")
        exit(1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("🚀 MEI MEI starting...")
    app.run_polling()

    asyncio.run(shutdown())