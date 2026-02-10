#!/usr/bin/env python3
import os
import re
import time
import json
import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, Update
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

from aiohttp import web
from playwright.async_api import async_playwright


# -------------------------------------------------
# CONFIG
# -------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mei-mei")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", 8080))

OLLAMA_MODEL = "qwen2.5-coder:7b"

KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "/app/knowledge_base")
Path(KNOWLEDGE_BASE_DIR).mkdir(parents=True, exist_ok=True)

MAX_TIMEOUT = 300

# how many heavy jobs at same time (important for Railway)
MAX_CONCURRENT_JOBS = 2
JOB_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


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
# OLLAMA
# -------------------------------------------------

async def run_ollama(prompt: str, timeout: int = 180) -> str:
    system = """You are MEI MEI created by L1xky.

Expert in:
- API reverse engineering
- checkout flows
- browser automation
- token chaining
"""

    final_prompt = system + "\n\n" + prompt

    proc = await asyncio.create_subprocess_exec(
        "ollama", "run", OLLAMA_MODEL, final_prompt,
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
    except:
        pass
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

        try:
            p1 = await page.query_selector("a[href*='product'],a[href*='shop'],a[href*='item']")
            if p1:
                await p1.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        try:
            btn = await page.query_selector(
                "button:has-text('Add'),button:has-text('Cart'),button:has-text('Buy')"
            )
            if btn:
                await btn.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        try:
            chk = await page.query_selector(
                "a:has-text('Checkout'),button:has-text('Checkout')"
            )
            if chk:
                await chk.click()
                await page.wait_for_timeout(4000)
        except:
            pass

        await page.wait_for_timeout(5000)
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


# -------------------------------------------------
# ANALYSIS PIPELINE (BACKGROUND JOB)
# -------------------------------------------------

async def run_website_analysis(chat_id: int, url: str):

    async with JOB_SEMAPHORE:

        t0 = time.time()

        await bot.send_message(chat_id, "🔎 Browser analysis started...")

        raw_requests, raw_responses = await browser_capture(url)

        filtered = [r for r in raw_requests if is_interesting_request(r)]
        curls = [request_to_curl(r) for r in filtered][:25]

        important_responses = []
        for r in raw_responses:
            if r.get("body") and any(
                k in r["body"].lower()
                for k in ["token", "csrf", "session", "cart", "checkout", "order"]
            ):
                important_responses.append(r)

        experience = select_relevant_summaries(load_api_summaries())

        prompt = f"""
Target site:
{url}

TASKS:

1. Build checkout flow chart.
2. Detect token / session / cart creation responses.
3. Detect dependency chain.
4. Generate ordered curl sequence.
5. Explain payload fields.

REQUESTS:
{chr(10).join(curls)}

RESPONSES:
{json.dumps(important_responses[:15], indent=2)}

PAST EXPERIENCE:
{experience}
"""

        await bot.send_message(chat_id, "🧠 Reasoning on captured traffic...")

        result = await run_ollama(prompt, MAX_TIMEOUT)

        elapsed = time.time() - t0
        final = result + f"\n\nTime: {elapsed:.1f}s"

        if len(final) > 3800:
            for i in range(0, len(final), 3800):
                await bot.send_message(chat_id, final[i:i + 3800])
        else:
            await bot.send_message(chat_id, final)


# -------------------------------------------------
# HANDLERS
# -------------------------------------------------

@router.message(CommandStart())
async def start(m: Message):
    await m.answer("MEI MEI – async automation & API analyzer.")


@router.message(F.text)
async def handle_message(m: Message):

    intent = detect_intent(m.text)

    if intent["type"] == "introduction":
        await m.answer("MEI MEI by L1xky – API & automation assistant.")
        return

    if intent["type"] == "website_analysis":

        url = intent["url"]

        await m.answer(
            "✅ Job accepted.\n\nI'll analyze the site in background and send you the result."
        )

        # fire & forget background job
        asyncio.create_task(
            run_website_analysis(m.chat.id, url)
        )

        return

    # normal chat (fast path)
    out = await run_ollama(m.text, 120)
    await m.answer(out[:3800])


# -------------------------------------------------
# WEBHOOK
# -------------------------------------------------

async def on_startup(app):
    path = f"/webhook/{TELEGRAM_BOT_TOKEN}"
    await bot.set_webhook(f"{WEBHOOK_URL}{path}")
    logger.info("Webhook set")


async def handle_webhook(request: web.Request):
    data = await request.json()
    update = Update.model_validate(data)
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
