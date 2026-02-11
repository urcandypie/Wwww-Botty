#!/usr/bin/env python3
"""
MEI MEI - Smart AI Assistant
Optimized for Ollama 7B
"""

import os
import subprocess
import asyncio
import logging
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ================= CONFIG =================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OLLAMA_MODEL = "qwen2.5:7b"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= OLLAMA FUNCTION =================

async def run_ollama(prompt: str) -> str:
    """
    Run ollama locally using subprocess (old style like you wanted)
    No timeout restriction
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama",
            "run",
            OLLAMA_MODEL,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(prompt.encode())

        if stderr:
            logger.error(stderr.decode())

        return stdout.decode().strip()

    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return f"Error: {str(e)}"

# ================= TELEGRAM HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """
<b>MEI MEI</b> ⚡

Model: Qwen2.5 7B
Running on Railway
32GB RAM Optimized

Just send any message and I'll respond.

Developer: @l1xky
"""
    await update.message.reply_text(
        welcome,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    processing = await update.message.reply_text("Processing...")

    try:
        start_time = time.time()

        prompt = f"""
You are MEI MEI, expert coding assistant.

User:
{user_message}

Respond clearly and give working code if needed.
"""

        response = await run_ollama(prompt)

        end_time = time.time()
        duration = round(end_time - start_time, 2)

        await processing.delete()

        final_text = f"{response}\n\n⏱ {duration}s • Model: {OLLAMA_MODEL}"

        # Telegram 4096 char limit safety
        if len(final_text) > 4000:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(
                    final_text[i:i+4000],
                    disable_web_page_preview=True
                )
        else:
            await update.message.reply_text(
                final_text,
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(e)
        await processing.edit_text(f"Error: {str(e)}")

# ================= MAIN =================

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 MEI MEI 7B Bot Started")
    app.run_polling()

if __name__ == "__main__":
    main()