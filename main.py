#!/usr/bin/env python3
import os
import re
import time
import json
import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

from playwright.async_api import async_playwright


# -------------------------------------------------
# CONFIG
# -------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mei-mei")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

OLLAMA_MODEL = "qwen2.5-coder:7b"
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")

KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "/app/knowledge_base")
Path(KNOWLEDGE_BASE_DIR).mkdir(parents=True, exist_ok=True)

MAX_TIMEOUT = 300
MAX_RESPONSE_TOKENS = 1024

# Reduce concurrency for better stability
MAX_CONCURRENT_JOBS = 1
JOB_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# Cache for repeated prompts (TTL: 1 hour)
RESPONSE_CACHE = {}
CACHE_TTL = 3600


# -------------------------------------------------
# BOT
# -------------------------------------------------

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
router = Router()
dp.include_router(router)


# -------------------------------------------------
# INTENT
# -------------------------------------------------

def detect_intent(message: str):
    urls = re.findall(r"https?://[^\s]+", message)

    m = message.lower()

    if urls:
        return {"type": "website_analysis", "url": urls[0]}

    if any(x in m for x in ["who are you", "about you", "your name"]):
        return {"type": "introduction"}

    return {"type": "general"}


# -------------------------------------------------
# OLLAMA API (IMPROVED VERSION)
# -------------------------------------------------

async def run_ollama(prompt: str, timeout: int = 120) -> str:
    """Call Ollama API with caching and error handling"""
    
    # Cache key based on prompt hash
    cache_key = hashlib.md5(prompt.encode()).hexdigest()
    current_time = time.time()
    
    # Check cache
    if cache_key in RESPONSE_CACHE:
        cached_time, cached_response = RESPONSE_CACHE[cache_key]
        if current_time - cached_time < CACHE_TTL:
            logger.info(f"Using cached response for prompt: {prompt[:50]}...")
            return cached_response
    
    system_prompt = """You are MEI MEI created by L1xky.

Expert in:
- API reverse engineering
- checkout flows
- browser automation
- token chaining
"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": MAX_RESPONSE_TOKENS,
            "top_p": 0.9,
            "repeat_penalty": 1.1
        }
    }

    try:
        # Create a single session for this request
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            logger.info(f"Sending request to Ollama API: {prompt[:100]}...")
            start_time = time.time()
            
            async with session.post(OLLAMA_API_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("response", "No response received").strip()
                    
                    # Cache the result
                    RESPONSE_CACHE[cache_key] = (current_time, result)
                    
                    elapsed = time.time() - start_time
                    logger.info(f"Ollama response received in {elapsed:.2f}s")
                    
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Ollama API error {response.status}: {error_text}")
                    return f"API Error: {response.status} - {error_text[:200]}"
                    
    except asyncio.TimeoutError:
        logger.warning(f"Ollama request timeout after {timeout}s")
        return "Model timeout - response took too long."
        
    except aiohttp.ClientError as e:
        logger.error(f"HTTP client error: {str(e)}")
        return f"Connection error: {str(e)}"
        
    except Exception as e:
        logger.error(f"Unexpected error in run_ollama: {str(e)}")
        return f"Error: {str(e)}"


# -------------------------------------------------
# KNOWLEDGE BASE
# -------------------------------------------------

def load_api_summaries():
    out = []
    try:
        for f in os.listdir(KNOWLEDGE_BASE_DIR):
            if f.endswith("_SUMMARY.md"):
                with open(os.path.join(KNOWLEDGE_BASE_DIR, f), "r", errors="ignore") as fd:
                    out.append(fd.read())
    except Exception as e:
        logger.error(f"Error loading knowledge base: {e}")
    return out


def select_relevant_summaries(all_summaries):
    hits = []
    for s in all_summaries:
        sl = s.lower()
        if any(k in sl for k in ["checkout", "cart", "order", "payment", "basket"]):
            hits.append(s)
    return "\n\n".join(hits[:4])


# -------------------------------------------------
# TRAFFIC CAPTURE
# -------------------------------------------------

TRACKING_KEYWORDS = [
    "google", "doubleclick", "facebook", "segment", "sentry",
    "clarity", "hotjar", "datadog", "mixpanel", "gtm"
]

IMPORTANT_METHODS = {"POST", "PUT", "PATCH"}


def is_interesting_request(req):
    url = req["url"].lower()

    if any(x in url for x in TRACKING_KEYWORDS):
        return False

    if req["method"] in IMPORTANT_METHODS:
        return True

    if any(k in url for k in ["cart", "checkout", "order", "basket", "payment", "session"]):
        return True

    return False


async def browser_capture(url: str):
    requests = []
    responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox"
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        async def on_request(req):
            try:
                requests.append({
                    "url": req.url,
                    "method": req.method,
                    "headers": dict(req.headers),
                    "post_data": req.post_data
                })
            except Exception as e:
                logger.warning(f"Error capturing request: {e}")

        async def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "")
                body = None

                if "application/json" in ct:
                    try:
                        body = await resp.text()
                    except:
                        body = None

                responses.append({
                    "url": resp.url,
                    "status": resp.status,
                    "content_type": ct,
                    "body": body[:3000] if body else None
                })
            except Exception as e:
                logger.warning(f"Error capturing response: {e}")

        context.on("request", on_request)
        context.on("response", on_response)

        page = await context.new_page()

        try:
            # Navigate to URL with timeout
            await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Try to interact with product links
            try:
                product_selector = "a[href*='product'], a[href*='shop'], a[href*='item'], a[href*='/p/']"
                product_elements = await page.query_selector_all(product_selector)
                if product_elements and len(product_elements) > 0:
                    await product_elements[0].click()
                    await page.wait_for_timeout(2000)
            except:
                pass

            # Try to add to cart
            try:
                add_buttons = await page.query_selector_all(
                    "button:has-text('Add'), button:has-text('Cart'), button:has-text('Buy'), button:has-text('Add to cart')"
                )
                if add_buttons and len(add_buttons) > 0:
                    await add_buttons[0].click()
                    await page.wait_for_timeout(2000)
            except:
                pass

            # Try checkout
            try:
                checkout_buttons = await page.query_selector_all(
                    "a:has-text('Checkout'), button:has-text('Checkout'), a:has-text('checkout')"
                )
                if checkout_buttons and len(checkout_buttons) > 0:
                    await checkout_buttons[0].click()
                    await page.wait_for_timeout(3000)
            except:
                pass

            # Final wait for any AJAX calls
            await page.wait_for_timeout(3000)

        except Exception as e:
            logger.error(f"Browser navigation error: {e}")
            # Continue with what we captured so far

        finally:
            await browser.close()

    logger.info(f"Captured {len(requests)} requests and {len(responses)} responses")
    return requests, responses


def request_to_curl(r):
    parts = ["curl", "-X", r["method"]]

    for k, v in r["headers"].items():
        # Skip some headers that might cause issues
        if k.lower() in ["content-length", "host", "connection"]:
            continue
        parts.append("-H")
        parts.append(f"{k}: {v}")

    if r.get("post_data"):
        parts.append("--data-raw")
        parts.append(r["post_data"])

    parts.append(r["url"])

    return " ".join("'" + p.replace("'", "'\"'\"'") + "'" if " " in p else p for p in parts)


# -------------------------------------------------
# ANALYSIS PIPELINE (BACKGROUND JOB)
# -------------------------------------------------

async def run_website_analysis(chat_id: int, url: str):
    """Run website analysis with semaphore limiting"""
    
    async with JOB_SEMAPHORE:
        t0 = time.time()
        
        try:
            await bot.send_message(chat_id, "🔎 Starting browser analysis...")
            
            # Capture traffic
            raw_requests, raw_responses = await browser_capture(url)
            
            if not raw_requests:
                await bot.send_message(chat_id, "⚠️ No requests captured. The site may be blocking automation.")
                return
            
            # Filter interesting requests
            filtered = [r for r in raw_requests if is_interesting_request(r)]
            curls = [request_to_curl(r) for r in filtered][:20]  # Limit to 20
            
            # Find important responses
            important_responses = []
            for r in raw_responses:
                if r.get("body"):
                    body_lower = r["body"].lower()
                    if any(k in body_lower for k in ["token", "csrf", "session", "cart", "checkout", "order", "auth"]):
                        important_responses.append(r)
            
            # Load relevant experience
            experience = select_relevant_summaries(load_api_summaries())
            
            # Build prompt
            prompt = f"""
Target site: {url}

TASKS:
1. Analyze checkout flow and identify endpoints
2. Detect authentication mechanisms (tokens, sessions, CSRF)
3. Map API dependencies and call sequences
4. Generate executable curl commands for testing
5. Explain key parameters and payload structure

CAPTURED REQUESTS ({len(curls)} of {len(raw_requests)}):
{chr(10).join(curls[:15])}

IMPORTANT RESPONSES ({len(important_responses)}):
{json.dumps(important_responses[:10], indent=2)}

PAST EXPERIENCE:
{experience}

Provide concise, actionable analysis. Focus on security testing vectors and automation potential.
"""
            
            await bot.send_message(chat_id, "🧠 Analyzing captured data with AI...")
            
            # Get AI analysis
            result = await run_ollama(prompt, min(MAX_TIMEOUT, 240))  # Max 4 minutes
            
            elapsed = time.time() - t0
            
            # Format final message
            summary = f"✅ Analysis complete in {elapsed:.1f}s\n"
            summary += f"📊 Captured {len(raw_requests)} requests, {len(raw_responses)} responses\n"
            summary += f"🔍 Found {len(filtered)} interesting endpoints\n\n"
            summary += result
            
            # Split long messages
            if len(summary) > 3500:
                await bot.send_message(chat_id, summary[:3500])
                if len(summary) > 3500:
                    await bot.send_message(chat_id, summary[3500:7000] if len(summary) > 7000 else summary[3500:])
            else:
                await bot.send_message(chat_id, summary)
                
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            await bot.send_message(chat_id, f"❌ Analysis failed: {str(e)[:200]}")


# -------------------------------------------------
# HANDLERS
# -------------------------------------------------

@router.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "🤖 MEI MEI – API & Automation Assistant\n\n"
        "Commands:\n"
        "• Send a URL to analyze checkout flows\n"
        "• Ask technical questions about APIs\n"
        "• Request browser automation insights\n\n"
        "Created by L1xky"
    )


@router.message(F.text)
async def handle_message(m: Message):
    """Handle incoming messages with intent detection"""
    
    if not m.text or m.text.strip() == "":
        return
    
    intent = detect_intent(m.text)
    
    # Introduction
    if intent["type"] == "introduction":
        await m.answer(
            "I'm MEI MEI – an AI assistant specialized in:\n"
            "• API reverse engineering\n"
            "• Checkout flow analysis\n"
            "• Browser automation\n"
            "• Security testing\n\n"
            "Send me a website URL to analyze its APIs!"
        )
        return
    
    # Website analysis
    if intent["type"] == "website_analysis":
        url = intent["url"]
        
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        await m.answer(
            f"🌐 Analyzing: {url}\n\n"
            "This will take 2-4 minutes. I'll:\n"
            "1. Browse the site and capture API calls\n"
            "2. Identify checkout/payment flows\n"
            "3. Generate curl commands for testing\n"
            "4. Provide security insights\n\n"
            "Standby..."
        )
        
        # Start analysis in background
        asyncio.create_task(run_website_analysis(m.chat.id, url))
        return
    
    # General chat (fast path)
    try:
        # Show typing indicator
        await bot.send_chat_action(m.chat.id, "typing")
        
        # Get AI response with shorter timeout
        response = await run_ollama(m.text, 60)
        
        # Send response
        if len(response) > 3500:
            await m.answer(response[:3500])
            if len(response) > 3500:
                await m.answer(response[3500:7000] if len(response) > 7000 else response[3500:])
        else:
            await m.answer(response)
            
    except Exception as e:
        logger.error(f"Error in general chat: {e}")
        await m.answer(f"Sorry, I encountered an error: {str(e)[:100]}")


# -------------------------------------------------
# HEALTH CHECK AND CLEANUP
# -------------------------------------------------

async def cleanup_cache():
    """Periodically clean old cache entries"""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        current_time = time.time()
        to_delete = []
        
        for key, (cached_time, _) in RESPONSE_CACHE.items():
            if current_time - cached_time > CACHE_TTL:
                to_delete.append(key)
        
        for key in to_delete:
            del RESPONSE_CACHE[key]
        
        if to_delete:
            logger.info(f"Cleaned {len(to_delete)} expired cache entries")


# -------------------------------------------------
# POLLING MAIN
# -------------------------------------------------

async def main():
    """Main entry point with cleanup tasks"""
    logger.info("🚀 Starting MEI MEI bot in polling mode...")
    logger.info(f"📚 Knowledge base: {KNOWLEDGE_BASE_DIR}")
    logger.info(f"🤖 Model: {OLLAMA_MODEL}")
    logger.info(f"🔒 Max concurrent jobs: {MAX_CONCURRENT_JOBS}")
    
    # Start cache cleanup task
    cleanup_task = asyncio.create_task(cleanup_cache())
    
    try:
        # Start polling
        await dp.start_polling(bot, allowed_updates=["message"])
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        # Cancel cleanup task
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())