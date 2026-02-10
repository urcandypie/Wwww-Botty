#!/usr/bin/env python3
import os
import re
import time
import json
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart

from aiohttp import web
from playwright.async_api import async_playwright


# -------------------- CONFIG --------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mei-mei")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", 8080))

OLLAMA_MODEL = "qwen2.5-coder:7b"

KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "/app/knowledge_base")
Path(KNOWLEDGE_BASE_DIR).mkdir(parents=True, exist_ok=True)

MAX_TIMEOUT = 300


# -------------------- BOT --------------------

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# -------------------- UTIL --------------------

def detect_intent(message: str) -> dict:
    urls = re.findall(r"https?://[^\s]+", message)

    m = message.lower()

    if urls:
        return {"type": "website_analysis", "url": urls[0], "message": message}

    if any(w in m for w in ["who are you", "about you", "your name"]):
        return {"type": "introduction"}

    return {"type": "general"}


# -------------------- OLLAMA --------------------

async def run_ollama(prompt: str, system_prompt: str = "", timeout: int = 180) -> str:
    base_system = """You are MEI MEI created by L1xky.
You are an expert in:
- API reverse engineering
- checkout flows
- browser automation
- scraping and request chaining.
"""

    full_prompt = f"{base_system}\n{system_prompt}\n\n{prompt}"

    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "run", OLLAMA_MODEL, full_prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return "Model timeout"

        if proc.returncode == 0:
            return out.decode(errors="ignore")
        return err.decode(errors="ignore")

    except Exception as e:
        return str(e)


# -------------------- KNOWLEDGE BASE --------------------

def load_api_summaries() -> list:
    out = []
    try:
        for f in os.listdir(KNOWLEDGE_BASE_DIR):
            if f.endswith("_SUMMARY.md"):
                with open(os.path.join(KNOWLEDGE_BASE_DIR, f), "r", errors="ignore") as fd:
                    out.append(fd.read())
    except:
        pass
    return out


def select_relevant_summaries(all_summaries: list) -> str:
    hits = []
    for s in all_summaries:
        sl = s.lower()
        if any(k in sl for k in ["checkout", "cart", "order", "payment", "basket"]):
            hits.append(s)
    return "\n\n".join(hits[:4])


# -------------------- TRAFFIC CAPTURE --------------------

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


async def browser_capture(url: str, max_wait: int = 15000):
    requests = []
    responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        context = await browser.new_context()

        async def on_request(req):
            requests.append({
                "url": req.url,
                "method": req.method,
                "headers": dict(req.headers),
                "post_data": req.post_data
            })

        async def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "")
                body = None

                if "application/json" in ct:
                    body = await resp.text()

                responses.append({
                    "url": resp.url,
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "content_type": ct,
                    "body": body[:3000] if body else None
                })
            except:
                pass

        context.on("request", on_request)
        context.on("response", on_response)

        page = await context.new_page()

        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(4000)

        # very generic interaction attempt
        try:
            product = await page.query_selector(
                "a[href*='product'],a[href*='shop'],a[href*='item']"
            )
            if product:
                await product.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        try:
            add_btn = await page.query_selector(
                "button:has-text('Add'),button:has-text('Cart'),button:has-text('Buy')"
            )
            if add_btn:
                await add_btn.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        try:
            checkout = await page.query_selector(
                "a:has-text('Checkout'),button:has-text('Checkout')"
            )
            if checkout:
                await checkout.click()
                await page.wait_for_timeout(4000)
        except:
            pass

        await page.wait_for_timeout(max_wait)
        await browser.close()

    return requests, responses


def request_to_curl(r):
    parts = ["curl", "-X", r["method"]]

    for k, v in r["headers"].items():
        parts.append("-H")
        parts.append(f"{k}: {v}")

    if r.get("post_data"):
        parts.append("--data-raw")
        parts.append(r["post_data"])

    parts.append(r["url"])

    return " ".join("'" + p.replace("'", "\\'") + "'" if " " in p else p for p in parts)


# -------------------- PROMPT BUILDER --------------------

def build_analysis_prompt(url, reqs, resps, experience):

    return f"""
You analyzed a real website using browser automation.

TARGET:
{url}

You are given HTTP requests and responses.

Your tasks:

1. Build a CHECKOUT / PURCHASE FLOW CHART
   (product → cart → checkout → order / payment).

2. Detect responses that CREATE:
   - cart_id
   - checkout_id
   - session id
   - csrf / auth tokens

3. Detect which later requests DEPEND on those values.

4. Build a dependency chain.

5. Produce a final ordered curl sequence.

6. Explain main payload fields.

=== FILTERED REQUESTS (as curl) ===
{chr(10).join(reqs)}

=== IMPORTANT JSON RESPONSES ===
{json.dumps(resps, indent=2)[:12000]}

=== PAST EXPERIENCE FROM OTHER SITES ===
{experience}
"""


# -------------------- HANDLERS --------------------

@router.message(CommandStart())
async def start(m: Message):
    await m.answer("MEI MEI – advanced API / checkout analyzer.")


@router.message(F.text)
async def handle_message(m: Message):

    intent = detect_intent(m.text)

    msg = await m.answer("<i>Working… this may take a few minutes.</i>")

    try:

        if intent["type"] == "introduction":
            await msg.edit_text("MEI MEI by L1xky – API & automation assistant.")
            return

        if intent["type"] != "website_analysis":
            out = await run_ollama(m.text, "", 120)
            await msg.edit_text(out[:3800])
            return

        url = intent["url"]

        await msg.edit_text("Launching browser & capturing traffic…")

        raw_requests, raw_responses = await browser_capture(url)

        filtered_requests = [r for r in raw_requests if is_interesting_request(r)]

        curls = [request_to_curl(r) for r in filtered_requests][:25]

        important_responses = []
        for r in raw_responses:
            if r.get("body") and any(
                k in (r.get("body") or "").lower()
                for k in ["token", "csrf", "session", "cart", "checkout", "order"]
            ):
                important_responses.append(r)

        all_summaries = load_api_summaries()
        experience = select_relevant_summaries(all_summaries)

        prompt = build_analysis_prompt(
            url,
            curls,
            important_responses[:15],
            experience
        )

        await msg.edit_text("Running deep analysis…")

        start = time.time()
        result = await run_ollama(prompt, "", MAX_TIMEOUT)
        elapsed = time.time() - start

        final = result + f"\n\nTime: {elapsed:.1f}s"

        if len(final) > 3800:
            await msg.delete()
            for i in range(0, len(final), 3800):
                await m.answer(final[i:i + 3800])
        else:
            await msg.edit_text(final)

    except Exception as e:
        logger.exception("analysis error")
        await msg.edit_text(str(e))


# -------------------- WEBHOOK SERVER --------------------

async def on_startup(app):
    path = f"/webhook/{TELEGRAM_BOT_TOKEN}"
    await bot.set_webhook(f"{WEBHOOK_URL}{path}")
    logger.info("Webhook set")


async def handle_webhook(request: web.Request):
    data = await request.json()
    update = dp.update_class(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


def main():
    app = web.Application()
    path = f"/webhook/{TELEGRAM_BOT_TOKEN}"

    app.router.add_post(path, handle_webhook)
    app.on_startup.append(on_startup)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
