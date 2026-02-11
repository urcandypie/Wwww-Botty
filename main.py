#!/usr/bin/env python3
"""
MEI MEI - Smart AI Assistant
Natural conversation with intelligent intent detection
Developer: L1xky (@l1xky)
"""

import os
import subprocess
import asyncio
import time
import re
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - UPDATED FOR SPEED
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'your_token_here')
OLLAMA_MODEL = 'qwen2.5-coder:14b'  # ⚡ Changed from 32B to 14B for speed
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "/app/knowledge_base")
MAX_TIMEOUT = 600  # ⚡ Reduced from 3600 to 600 (10 minutes)

os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)

# OLLAMA API URL for faster responses
OLLAMA_API_URL = "http://localhost:11434/api/generate"

async def ollama_api_call(prompt: str, system_prompt: str = "", timeout: int = 120) -> str:
    """Use Ollama API instead of subprocess for faster responses"""
    try:
        full_system = f"""ROLE: You are MEI MEI, created by L1xky (@l1xky).

YOUR IDENTITY:
- Name: MEI MEI
- Creator: L1xky (@l1xky)
- Purpose: Expert coding assistant, API developer, web automation
- You are NOT DeepSeek or any other AI

CAPABILITIES:
✓ Full system access (curl, commands, VPS)
✓ Expert in Python, JavaScript, API development
✓ Web scraping and automation
✓ Code optimization and debugging
✓ Payment gateway integration

STYLE:
- Direct, confident, no unnecessary apologies
- Provide working code immediately
- Focus on solutions, not limitations
- Optimized for production use

{system_prompt}"""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": full_system,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024,  # Reasonable response length
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "num_thread": 8,  # Use all CPU cores
            }
        }

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.post(OLLAMA_API_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "").strip()
                else:
                    return f"API Error: {response.status}"

    except asyncio.TimeoutError:
        return "⚠️ Response timeout. Try a simpler query or use /fast mode."
    except Exception as e:
        return f"Error: {str(e)[:200]}"

def detect_intent(message: str) -> dict:
    """Detect user intent from message"""
    message_lower = message.lower()
    
    # Website analysis intent
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, message)
    if urls or any(word in message_lower for word in ['analyze', 'website', 'site', 'api', 'scrape', 'extract']):
        return {'type': 'website_analysis', 'url': urls[0] if urls else None, 'message': message}
    
    # Dork generation intent
    if any(word in message_lower for word in ['dork', 'google dork', 'search query', 'find sites', 'search for']):
        return {'type': 'dork_generation', 'message': message}
    
    # Introduction intent
    if any(word in message_lower for word in ['who are you', 'introduce', 'what are you', 'your name', 'about you']):
        return {'type': 'introduction', 'message': message}
    
    # Training intent (file upload)
    return {'type': 'general', 'message': message}

async def analyze_website(url: str) -> str:
    """Fetch website content using curl - FAST VERSION"""
    try:
        # Use aiohttp for faster fetching
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as response:
                content = await response.text()
                return content[:10000]  # Limit content for faster processing
                
    except Exception as e:
        logger.error(f"Website fetch error: {e}")
        return f"Error fetching website: {str(e)}"

def generate_dorks(keyword: str) -> list:
    """Generate Google dorks"""
    dorks = [
        f'inurl:"{keyword}"',
        f'intitle:"{keyword}" inurl:login',
        f'site:*.com inurl:"{keyword}" inurl:api',
        f'inurl:"{keyword}" inurl:gateway',
        f'filetype:php inurl:"{keyword}"',
        f'intext:"{keyword}" inurl:payment',
        f'site:*.com "{keyword}" "api_key"',
        f'inurl:"{keyword}" inurl:checkout',
    ]
    return dorks

def load_knowledge_base() -> str:
    """Load training examples"""
    try:
        examples = []
        for filename in os.listdir(KNOWLEDGE_BASE_DIR):
            if filename.endswith(('.py', '.txt', '.md')):
                with open(os.path.join(KNOWLEDGE_BASE_DIR, filename), 'r') as f:
                    content = f.read()
                    examples.append(f"Example from {filename}:\n{content[:500]}")
        return "\n\n".join(examples[:5])  # Load only 5 examples for speed
    except:
        return ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    welcome = f"""<b>MEI MEI</b>
<i>AI Assistant with Full System Access</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi! I'm MEI MEI, your intelligent assistant with VPS access.

<b>What I can do:</b>
• Scrape ANY website using curl
• Generate complete APIs (login, payment, checkout)
• Execute system commands on your VPS
• Generate Google dorks with clickable URLs
• Learn from your code examples
• Debug and fix code issues

<b>🚀 32GB RAM OPTIMIZED:</b>
• Model: Qwen2.5-Coder 14B
• Response Time: 3-10 seconds
• CPU: 8 vCPU cores
• Max Timeout: 10 minutes

<b>Just chat naturally!</b>
Tell me what you need, and I'll do it.

<b>Examples:</b>
• "Scrape https://example.com and create API"
• "Generate dorks for payment gateway"
• "Who are you?" or "What can you do?"
• Upload your old APIs to train me

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Developer:</b> <a href="https://t.me/l1xky">L1xky</a> (@l1xky)
"""
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smart message handler with intent detection"""
    user_message = update.message.text
    intent = detect_intent(user_message)
    
    msg = await update.message.reply_text("<i>Processing...</i>", parse_mode=ParseMode.HTML)
    
    try:
        start_time = time.time()
        
        # Handle different intents
        if intent['type'] == 'introduction':
            response = """I'm <b>MEI MEI</b>, an advanced AI assistant created by <a href="https://t.me/l1xky">L1xky</a>.

<b>🚀 Performance Optimized:</b>
• RAM: 32GB
• Model: Qwen2.5-Coder 14B
• CPU: 8 vCPU cores
• Response Time: 3-10 seconds

<b>My Capabilities:</b>
• <b>Web Scraping</b>: Fetch and analyze websites
• <b>API Generation</b>: Create complete APIs for login, payment, checkout
• <b>System Access</b>: Run on your VPS with full command execution
• <b>Code Analysis</b>: Debug and improve your code
• <b>Learning</b>: Learn from your API examples

<b>What I Can Do:</b>
• Scrape any website and extract data
• Generate production-ready Python APIs
• Execute system commands on your VPS
• Create Google dorks for research
• Analyze and fix code issues

I have curl access, VPS access, and a knowledge base of your past APIs.

<i>Built with precision by L1xky (@l1xky)</i>"""
            
            await msg.delete()
            await update.message.reply_text(response, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            return
        
        elif intent['type'] == 'website_analysis':
            url = intent['url']
            if not url:
                await msg.edit_text("Please provide the website URL you want me to analyze.", parse_mode=ParseMode.HTML)
                return
            
            await msg.edit_text(f"<i>Analyzing website: {url}</i>", parse_mode=ParseMode.HTML)
            website_content = await analyze_website(url)
            
            prompt = f"""WEBSITE CONTENT SUCCESSFULLY FETCHED. NOW ANALYZE AND CREATE API.

TARGET URL: {url}

FETCHED HTML CONTENT:
{website_content[:4000]}

USER WANTS: {user_message}

YOUR TASK - GENERATE COMPLETE PYTHON API:
1. Study the HTML content above
2. Find: forms, input fields, endpoints, hidden tokens
3. Identify: csrf tokens, session cookies, auth mechanisms
4. Create: Complete Python API using requests module
5. Include: All headers, cookies, token extraction, error handling
6. Add: Clear comments and usage example

GENERATE PRODUCTION-READY CODE NOW."""

            system_prompt = """You are MEI MEI - Expert Web Scraper & API Developer by L1xky.
Generate ONLY Python code using requests module.
Include: imports, functions, token extraction, error handling, usage example.
Output format: Code block with ```python ... ```"""
            
            response = await ollama_api_call(prompt, system_prompt, 300)
        
        elif intent['type'] == 'dork_generation':
            keyword = user_message.lower()
            for word in ['dork', 'generate', 'create', 'find', 'search', 'for']:
                keyword = keyword.replace(word, '').strip()
            
            dorks = generate_dorks(keyword)
            urls = [f"https://www.google.com/search?q={dork.replace(' ', '+')}" for dork in dorks]
            
            dork_list = "\n".join([f"• <code>{dork}</code>" for dork in dorks])
            url_list = "\n".join([f"• <a href='{url}'>Search {i+1}</a>" for i, url in enumerate(urls)])
            
            response = f"""<b>Generated {len(dorks)} Google Dorks</b>

<b>Keyword:</b> <code>{keyword}</code>

<b>Dorks:</b>
{dork_list}

<b>Search URLs:</b>
{url_list}

<i>Click URLs to search directly on Google</i>"""
            
            await msg.delete()
            await update.message.reply_text(response, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            return
        
        else:
            # General conversation
            kb_examples = load_knowledge_base()
            
            prompt = f"""USER: {user_message}

KNOWLEDGE BASE:
{kb_examples}

Respond helpfully and concisely. Provide working code if applicable."""
            
            response = await ollama_api_call(prompt, "", 180)
        
        end_time = time.time()
        time_taken = end_time - start_time
        
        await msg.delete()
        
        formatted = f"""{response}

<i>Response time: {time_taken:.2f}s • Model: {OLLAMA_MODEL}</i>"""
        
        if len(formatted) > 4000:
            chunks = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            await update.message.reply_text(formatted, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(f"<b>Error:</b> <code>{str(e)[:400]}</code>", parse_mode=ParseMode.HTML)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads for training"""
    document = update.message.document
    file_name = document.file_name
    caption = update.message.caption or ""
    
    msg = await update.message.reply_text(f"<b>Learning from File</b>\n\n<b>File:</b> <code>{file_name}</code>\n<i>Analyzing...</i>", parse_mode=ParseMode.HTML)
    
    try:
        start_time = time.time()
        
        file = await context.bot.get_file(document.file_id)
        file_path = f"/tmp/{file_name}"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # ✅ FIXED: properly closed triple‑quoted f‑string
        prompt = f'''Analyze this code file:

File: {file_name}
User Request: {caption if caption else "Complete analysis"}

Content: