import os
import base64
import sqlite3
import threading
import queue
import time
import asyncio
import uuid
import io
import logging
from datetime import datetime, timedelta
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
import speech_recognition as sr
from pydub import AudioSegment
import requests
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import hashlib
import json
from functools import lru_cache
import aiohttp
import pytesseract
from typing import Dict, List, Optional
import random

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= CONFIG =================
BOT_TOKEN = "8619731533:AAGOPaGc_CcQaW5_B-HGUCeY3MetJFzoD0U"
GROQ_API_KEY = "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"
BOT_USERNAME = "@STUDYCONTROLLERV2_bot"

OWNER_ID = 6305002830
OWNER_NAME = "꧁⁣༒𓆩A𝔰𝔥𝔦𝔰𝔥𓆪༒꧂"

client = Groq(api_key=GROQ_API_KEY)

# Memory system for Hinglish responses
user_memory = {}

# ================= DATABASE SETUP =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# Create all tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    join_date TEXT,
    last_active TEXT,
    chat_count INTEGER DEFAULT 0,
    is_blocked INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message TEXT,
    response TEXT,
    timestamp TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_preferences(
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'en',
    response_style TEXT DEFAULT 'balanced',
    theme TEXT DEFAULT 'default'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    reminder_text TEXT,
    reminder_time TEXT,
    created_at TEXT,
    status TEXT DEFAULT 'pending'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS groups(
    group_id INTEGER PRIMARY KEY,
    group_name TEXT,
    added_date TEXT,
    is_active INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS broadcast_queue(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    media_type TEXT,
    media_file TEXT,
    created_at TEXT,
    status TEXT DEFAULT 'pending'
)
""")

conn.commit()

# ================= DATABASE FUNCTIONS =================
def add_user(user_id, username, first_name, last_name):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, first_name, last_name, join_date, last_active, chat_count) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, first_name, last_name, current_time, current_time, 0)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding user: {e}")

def update_user_activity(user_id):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("""
            UPDATE users 
            SET last_active = ?, chat_count = chat_count + 1 
            WHERE id = ?
            """,
            (current_time, user_id)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating activity: {e}")

def save_chat_history(user_id, message, response):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("""
            INSERT INTO chat_history (user_id, message, response, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, message, response, timestamp)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving chat: {e}")

def get_user_preferences(user_id):
    try:
        cursor.execute("SELECT language, response_style, theme FROM user_preferences WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return {"language": result[0], "response_style": result[1], "theme": result[2]}
    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
    return {"language": "en", "response_style": "balanced", "theme": "default"}

def set_user_preference(user_id, pref_type, value):
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO user_preferences (user_id, language, response_style, theme)
            VALUES (?, 'en', 'balanced', 'default')
            """, (user_id,))
        
        cursor.execute(f"UPDATE user_preferences SET {pref_type} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error setting preference: {e}")

def total_users():
    try:
        cursor.execute("SELECT id, username, first_name, last_name, join_date, last_active, chat_count FROM users WHERE is_blocked = 0")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

def get_user_stats(user_id):
    try:
        cursor.execute("SELECT chat_count, join_date, last_active FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return None

def get_chat_history(user_id, limit=5):
    try:
        cursor.execute("""
            SELECT message, response, timestamp 
            FROM chat_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            """, (user_id, limit))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return []

def clear_user_history(user_id):
    try:
        cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error clearing history: {e}")

def add_group(group_id, group_name):
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT OR IGNORE INTO groups (group_id, group_name, added_date, is_active)
            VALUES (?, ?, ?, 1)
            """, (group_id, group_name, current_time))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding group: {e}")

def get_all_groups():
    try:
        cursor.execute("SELECT group_id, group_name FROM groups WHERE is_active = 1")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        return []

# ================= AI ENGINE (Hinglish with Memory) =====
async def ask_ai_hinglish(user_id, text, context_type="normal"):
    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": text})
    user_memory[user_id] = user_memory[user_id][-20:]

    # Custom responses for specific questions
    text_lower = text.lower()
    
    # Owner related queries
    if any(word in text_lower for word in ['owner', 'malik', 'banane wala', 'creator', 'banaya', 'kisne banaya', 'tera malik']):
        return f"👑 My owner is {OWNER_NAME}! Unhone mujhe banaya hai. Main sirf unke commands maanta hoon. 🙏"
    
    # GPT related queries
    if any(word in text_lower for word in ['gpt', 'chatgpt', 'kya tum gpt ho']):
        return f"🤖 No bro, main GPT nahi hoon! Mujhe {OWNER_NAME} ne banaya hai. Unhone mujhe sirf study ke liye banaya hai. 📚"
    
    # Study purpose queries
    if any(word in text_lower for word in ['study', 'padhai', 'kyon banaya', 'purpose', 'mak sad', 'kis liye']):
        return f"📚 Haan ji, mujhe sirf study ke liye banaya gaya hai! {OWNER_NAME} ne mujhe students ki help karne ke liye banaya hai. 🎯 Koi bhi question poochho, main Hinglish mein answer dunga!"
    
    # Command related queries
    if any(word in text_lower for word in ['command', 'hukm', 'order', 'kiske kahne mein']):
        return f"⚡ Main sirf {OWNER_NAME} ke commands maanta hoon! Wahi mere owner hain. 👑 Baaki sab ke questions ke answers zaroor deta hoon."
    
    # Who are you
    if any(word in text_lower for word in ['tum kaun ho', 'who are you', 'kya ho tum', 'aap kaun hain']):
        return f"🤖 Main ek study assistant hoon! Mujhe {OWNER_NAME} ne banaya hai. Main Hinglish mein baat karta hoon aur study mein help karta hoon. 📚 Koi question?"
    
    # What can you do
    if any(word in text_lower for word in ['kya kar sakte ho', 'what can you do', 'tumhara kaam', 'features']):
        return f"🎯 Main ye sab kar sakta hoon:\n\n📝 Notes banana /notes\n🔍 Explain karna /explain\n❓ MCQ generate karna /mcq\n📚 PYQ nikalna /pyq\n🤔 Doubt solve karna /doubt\n📄 PDF notes /pdfnotes\n🎨 Image banana /imagine\n⏰ Reminder /remind\n🌍 Group broadcast /groupbroadcast\n\nBas mujhe tag karo @STUDYCONTROLLERV2_bot"
    
    # Thanks
    if any(word in text_lower for word in ['thanks', 'thankyou', 'dhanyavaad', 'shukriya']):
        return f"🙏 Aapka swagat hai! {OWNER_NAME} ne mujhe aapki help karne ke liye hi banaya hai. Kuch aur poochna?"
    
    # Normal AI response
    messages = [
        {"role": "system", "content": f"""Tum ek smart Telegram AI bot ho. Tumhare owner {OWNER_NAME} hain. 
        Tumhe sirf study ke liye banaya gaya hai. Tum sirf {OWNER_NAME} ke commands maante ho.
        Hamesha Hinglish (Hindi + English mix) mein friendly reply do. Agar koi question ho to achhe se samjhao.
        Chhote-chhote answers do, lambe nahi. Tumhara naam 'Study Controller' hai."""
        }
    ] + user_memory[user_id]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )

        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        user_memory[user_id] = user_memory[user_id][-20:]

        return reply
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "❌ Kuch technical problem hai! Thoda der baad try karo."

# ================= ENHANCED IMAGE GENERATION =================
async def generate_image_advanced(prompt, style="normal", amount=1, size="1024x1024"):
    style_prompts = {
        "anime": "anime style, manga art, vibrant colors, detailed illustration",
        "realistic": "ultra realistic, photorealistic, detailed textures, natural lighting",
        "3d": "3d render, cgi, octane render, blender, volumetric lighting",
        "logo": "minimal logo design, vector art, flat design, professional branding",
        "cartoon": "cartoon style, pixar style, colorful, cute",
        "fantasy": "fantasy art, magical, ethereal, dreamlike",
        "cyberpunk": "cyberpunk style, neon lights, futuristic, sci-fi",
        "normal": ""
    }

    final_prompt = f"{prompt} {style_prompts.get(style, '')}"
    final_prompt = final_prompt.replace(" ", "%20")
    
    files = []
    
    # Try multiple image generation sources
    for i in range(amount):
        # Primary: Pollinations.ai
        try:
            url = f"https://image.pollinations.ai/prompt/{final_prompt}"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                filename = f"generated_{i}_{uuid.uuid4().hex[:6]}.png"
                with open(filename, "wb") as f:
                    f.write(response.content)
                files.append(filename)
                continue
        except Exception as e:
            logger.error(f"Pollinations error: {e}")
        
        # Fallback: Placeholder image with text
        try:
            filename = f"generated_{i}_{uuid.uuid4().hex[:6]}.png"
            img = Image.new('RGB', (512, 512), color=(73, 109, 137))
            d = ImageDraw.Draw(img)
            
            # Try to use a font, fallback to default
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            # Wrap text
            text = prompt[:100]
            d.text((10, 250), text, fill=(255, 255, 255), font=font)
            img.save(filename)
            files.append(filename)
        except Exception as e:
            logger.error(f"Fallback image error: {e}")
    
    return files

# ================= ENHANCED VOICE TO TEXT =================
def voice_to_text_enhanced(path):
    try:
        # Convert OGG to WAV
        audio = AudioSegment.from_ogg(path)
        audio.export("voice.wav", format="wav")
        
        r = sr.Recognizer()
        with sr.AudioFile("voice.wav") as source:
            audio_data = r.record(source)
        
        # Try multiple recognizers
        try:
            text = r.recognize_google(audio_data)
            return text
        except:
            try:
                text = r.recognize_google(audio_data, language="hi-IN")
                return text
            except:
                return "Voice samajh nahi aayi. Clear bol kar try karo."
    except Exception as e:
        logger.error(f"Voice recognition error: {e}")
        return "Audio process karne mein error aaya."

# ================= ENHANCED IMAGE ANALYSIS =================
async def analyze_image_advanced(path):
    try:
        with Image.open(path) as img:
            width, height = img.size
            format_type = img.format or "Unknown"
            mode = img.mode
            colors = img.getcolors(maxcolors=10) if img.mode == 'RGB' else None
            
        result = f"""🖼️ **Image Analysis**

📐 **Dimensions:** {width} x {height} pixels
📁 **Format:** {format_type}
🎨 **Color Mode:** {mode}
"""
        
        # Try OCR if it's a text image
        try:
            text = pytesseract.image_to_string(Image.open(path))
            if text and len(text.strip()) > 0:
                result += f"\n📝 **Detected Text:**\n{text[:500]}"
        except:
            pass
        
        result += "\n\n💬 **Aap poochh sakte hain:**\n• Is image mein kya hai?\n• Image describe karo\n• Kya text hai isme?"
        
        return result
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return "❌ Image analyze karne mein error aaya."

# ================= REMINDER SYSTEM =================
reminder_queue = queue.Queue()
reminder_thread_running = True

def reminder_worker():
    while reminder_thread_running:
        try:
            current_time = datetime.now()
            cursor.execute("""
                SELECT id, user_id, reminder_text, reminder_time 
                FROM reminders 
                WHERE status = 'pending' AND datetime(reminder_time) <= datetime(?)
                """, (current_time.strftime("%Y-%m-%d %H:%M:%S"),))
            
            due_reminders = cursor.fetchall()
            
            for reminder in due_reminders:
                reminder_queue.put(reminder)
                cursor.execute("UPDATE reminders SET status = 'sent' WHERE id = ?", (reminder[0],))
                conn.commit()
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"Reminder worker error: {e}")
            time.sleep(60)

reminder_thread = threading.Thread(target=reminder_worker, daemon=True)
reminder_thread.start()

def parse_reminder_time(time_str):
    now = datetime.now()
    try:
        if time_str.endswith('m'):
            minutes = int(time_str[:-1])
            return now + timedelta(minutes=minutes)
        elif time_str.endswith('h'):
            hours = int(time_str[:-1])
            return now + timedelta(hours=hours)
        elif time_str.endswith('d'):
            days = int(time_str[:-1])
            return now + timedelta(days=days)
        else:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except:
        return None

# ================= COMMAND HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = (
        f"🌟 **Namaste {user.first_name}!** 🌟\n\n"
        "Main aapka advanced AI assistant **Study Controller** hoon.\n\n"
        
        "📚 **Study Features**\n"
        "• `/notes [topic]` - Notes banayein\n"
        "• `/explain [topic]` - Samjhao koi bhi topic\n"
        "• `/mcq [topic]` - MCQ generate karein\n"
        "• `/pyq [subject]` - Previous year questions\n"
        "• `/doubt [question]` - Doubt solve karein\n"
        "• `/pdfnotes [topic]` - PDF notes\n"
        "• `/quiz [topic] [class] [subject] [q]` - Custom quiz\n\n"
        
        "🎨 **Creative Features**\n"
        "• `/imagine [prompt]` - AI image\n"
        "• `/draw [prompt]` - Prompt banayein\n"
        "• `/generate [prompt]` - Image generate\n"
        "• `/voice [text]` - Text to voice\n"
        "• `/enhance [prompt]` - Prompt enhance\n"
        "• `.gen [prompt]` - Quick image (anime/3d/logo)\n\n"
        
        "⏰ **Reminder Features**\n"
        "• `/remind [time] [message]` - Reminder set\n"
        "• `/myreminders` - Reminders dekhein\n"
        "• `/cancel [id]` - Reminder cancel\n"
        "• `/clearreminders` - Saare reminders hataein\n\n"
        
        "🖼️ **Image Features**\n"
        "• Image send karo - Main analyze karunga\n"
        "• `/analyze` - Kisi image ka reply karo\n\n"
        
        "⚙️ **Settings**\n"
        "• `/settings` - Customize karein\n"
        "• `/stats` - Aapke statistics\n"
        "• `/help` - Saari commands\n\n"
        
        "**Bas mujhe tag karo ya reply karo!** 🚀"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📚 Study", callback_data="study_help"),
            InlineKeyboardButton("🎨 Creative", callback_data="creative")
        ],
        [
            InlineKeyboardButton("⏰ Reminders", callback_data="reminders"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
            InlineKeyboardButton("❓ Examples", callback_data="examples")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🌟 **ALL COMMANDS** 🌟

**📚 STUDY COMMANDS**
/notes [topic] - Detailed notes
/explain [topic] - Simple explanation
/mcq [topic] - Multiple choice questions
/pyq [subject] - Previous year questions
/doubt [question] - Solve doubts
/pdfnotes [topic] - PDF format notes
/quiz [topic] [class] [subject] [q] - Custom quiz

**🎨 CREATIVE COMMANDS**
/imagine [prompt] - AI image generation
/draw [prompt] - Enhanced prompt
/generate [prompt] - Quick image
/voice [text] - Text to speech
/enhance [prompt] - Better prompt
.gen [prompt] - Quick generate
.gen anime [prompt] - Anime style
.gen 3d [prompt] - 3D style
.gen logo [prompt] - Logo design
.gen cartoon [prompt] - Cartoon style

**⏰ REMINDER COMMANDS**
/remind [time] [message] - Set reminder
/myreminders - View reminders
/cancel [id] - Cancel reminder
/clearreminders - Clear all

**🖼️ IMAGE ANALYSIS**
/analyze - Analyze replied image
Send image directly - Auto analyze

**👑 OWNER COMMANDS**
/users - All users list
/broadcast [message] - Broadcast to all
/groupbroadcast [message] - Broadcast to groups
/addgroup - Add current group
/removegroup [id] - Remove group
/statsall - Overall bot stats

**⚙️ USER COMMANDS**
/settings - Customize bot
/stats - Your statistics
/help - This menu

**💬 Just tag me or reply to chat!**
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👑 **Owner Information**\n\n"
        f"**Name:** {OWNER_NAME}\n"
        f"**ID:** `{OWNER_ID}`\n\n"
        f"Unhone mujhe students ki help ke liye banaya hai!\n"
        f"Main sirf unke commands maanta hoon. 🙏",
        parse_mode='Markdown'
    )

async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    stats = get_user_stats(user.id)
    
    if stats:
        chat_count, join_date, last_active = stats
        text = f"""
📊 **Your Statistics**

👤 **User:** {user.first_name} {user.last_name or ''}
🆔 **ID:** `{user.id}`
💬 **Total Chats:** {chat_count}
📅 **Joined:** {join_date}
⏰ **Last Active:** {last_active}
        """
    else:
        text = "No chat history yet. Start chatting with me!"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= STUDY COMMANDS =================
async def notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/notes [topic]`\nExample: `/notes photosynthesis`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"📝 Generating notes for **{topic}**...", parse_mode='Markdown')
    
    user_id = update.message.from_user.id
    prompt = f"Create detailed study notes for {topic} in Hinglish language with clear headings and bullet points"
    reply = await ask_ai_hinglish(user_id, prompt)
    await msg.edit_text(reply)

async def explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/explain [topic]`\nExample: `/explain quantum physics`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"🔍 Explaining **{topic}**...", parse_mode='Markdown')
    
    user_id = update.message.from_user.id
    prompt = f"Explain {topic} in simple Hinglish language with examples for students"
    reply = await ask_ai_hinglish(user_id, prompt)
    await msg.edit_text(reply)

async def mcq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/mcq [topic]`\nExample: `/mcq world war 2`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"📝 Generating MCQs for **{topic}**...", parse_mode='Markdown')
    
    user_id = update.message.from_user.id
    prompt = f"Create 10 multiple choice questions with 4 options and answers for {topic} in Hinglish"
    reply = await ask_ai_hinglish(user_id, prompt)
    await msg.edit_text(reply)

async def pyq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/pyq [subject]`\nExample: `/pyq physics`", parse_mode='Markdown')
        return
    subject = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"📚 Finding PYQs for **{subject}**...", parse_mode='Markdown')
    
    user_id = update.message.from_user.id
    prompt = f"Generate important previous year exam questions for {subject} with answers in Hinglish"
    reply = await ask_ai_hinglish(user_id, prompt)
    await msg.edit_text(reply)

async def doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/doubt [question]`\nExample: `/doubt what is photosynthesis`", parse_mode='Markdown')
        return
    question = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"❓ Solving your doubt...", parse_mode='Markdown')
    
    user_id = update.message.from_user.id
    prompt = f"Solve this question step by step in Hinglish with clear explanation: {question}"
    reply = await ask_ai_hinglish(user_id, prompt)
    await msg.edit_text(reply)

async def pdfnotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/pdfnotes [topic]`\nExample: `/pdfnotes biology`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 Generating PDF notes for **{topic}**...", parse_mode='Markdown')
    
    user_id = update.message.from_user.id
    notes_text = await ask_ai_hinglish(user_id, f"Create detailed study notes for {topic} in Hinglish")
    
    filename = f"{topic.replace(' ', '_')}_notes.txt"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(notes_text)
    
    await msg.edit_text("✅ Notes ready! Sending PDF...")
    await update.message.reply_document(document=open(filename, "rb"), filename=filename)
    os.remove(filename)

async def enhanced_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 4:
        await update.message.reply_text(
            "❌ **Format:** `/quiz [topic] [class] [subject] [questions]`\n\n"
            "**Examples:**\n"
            "• `/quiz photosynthesis 10 science 5`\n"
            "• `/quiz world war 2 12 history 10`\n"
            "• `/quiz algebra 9 mathematics 8`",
            parse_mode='Markdown'
        )
        return
    
    try:
        num_questions = int(context.args[-1])
        subject = context.args[-2]
        class_level = context.args[-3]
        topic = " ".join(context.args[:-3])
        
        if num_questions < 1 or num_questions > 20:
            await update.message.reply_text("❌ Questions must be between 1-20")
            return
        
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
        msg = await update.message.reply_text(f"📝 Generating quiz for Class {class_level} on {topic}...", parse_mode='Markdown')
        
        user_id = update.message.from_user.id
        quiz_prompt = f"""
        Create a detailed quiz for Class {class_level} students on {topic} for {subject} in Hinglish language.
        - {num_questions} multiple choice questions
        - 4 options per question (A, B, C, D)
        - Include answer key with explanations
        """
        
        reply = await ask_ai_hinglish(user_id, quiz_prompt)
        
        if len(reply) > 4000:
            parts = [reply[i:i+4000] for i in range(0, len(reply), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await msg.edit_text(reply)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ================= CREATIVE COMMANDS =================
async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ **Usage:** `/imagine [prompt]`\n\n"
            "**Styles:** normal, anime, realistic, 3d, logo, cartoon, fantasy, cyberpunk\n"
            "**Example:** `/imagine anime girl`\n"
            "**Quick:** `.gen [style] [prompt]`",
            parse_mode='Markdown'
        )
        return
    
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🎨 Generating AI image...")
    
    try:
        images = await generate_image_advanced(prompt, "normal", 1)
        
        if images:
            with open(images[0], "rb") as img:
                await update.message.reply_photo(photo=img, caption=f"🖼️ **Generated:** {prompt[:100]}\n\nPrompt: `{prompt}`", parse_mode='Markdown')
            os.remove(images[0])
            await msg.delete()
        else:
            await msg.edit_text("❌ Image generation failed. Try again with different prompt.")
    except Exception as e:
        logger.error(f"Imagine error: {e}")
        await msg.edit_text("❌ Error generating image. Please try again.")

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/draw [prompt]`\nExample: `/draw dragon`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🎨 Creating enhanced prompt...", parse_mode='Markdown')
    
    user_id = update.message.from_user.id
    reply = await ask_ai_hinglish(user_id, f"Create a detailed, professional AI image generation prompt for: {prompt}")
    await msg.edit_text(f"✨ **Enhanced Prompt:**\n\n`{reply}`", parse_mode='Markdown')

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/generate [prompt]`\nExample: `/generate cyberpunk city`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🎨 Generating image...", parse_mode='Markdown')
    
    try:
        images = await generate_image_advanced(prompt, "normal", 1)
        
        if images:
            with open(images[0], "rb") as img:
                await update.message.reply_photo(photo=img, caption=f"🖼️ {prompt}")
            os.remove(images[0])
            await msg.delete()
        else:
            await msg.edit_text("❌ Generation failed.")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/voice [text]`\nExample: `/voice Hello World`", parse_mode='Markdown')
        return
    text = " ".join(context.args)
    try:
        msg = await update.message.reply_text("🔊 Converting to voice...")
        tts = gTTS(text, lang='hi' if any(c in text for c in 'अआइईउऊ') else 'en')
        filename = f"voice_{uuid.uuid4().hex[:6]}.mp3"
        tts.save(filename)
        await update.message.reply_voice(open(filename, "rb"))
        os.remove(filename)
        await msg.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def enhance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/enhance [prompt]`\nExample: `/enhance dragon`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    enhanced = f"Ultra detailed {prompt}, cinematic lighting, 8k resolution, hyper realistic, sharp focus, professional photography"
    await update.message.reply_text(f"✨ **Enhanced Prompt:**\n\n`{enhanced}`", parse_mode='Markdown')

# ================= REMINDER COMMANDS =================
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "⏰ **Set Reminder**\n\n"
            "**Format:** `/remind [time] [message]`\n\n"
            "**Examples:**\n"
            "• `/remind 10m Study math`\n"
            "• `/remind 2h Submit assignment`\n"
            "• `/remind 1d Water plants`\n"
            "• `/remind 2024-12-25 10:30 Party`",
            parse_mode='Markdown'
        )
        return
    
    user = update.message.from_user
    
    try:
        time_str = context.args[0].lower()
        message = " ".join(context.args[1:])
        reminder_time = parse_reminder_time(time_str)
        
        if not reminder_time:
            await update.message.reply_text("❌ Invalid time format! Use: 10m, 2h, 1d, or YYYY-MM-DD HH:MM")
            return
        
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reminder_time_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO reminders (user_id, reminder_text, reminder_time, created_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """, (user.id, message, reminder_time_str, created_at))
        conn.commit()
        
        reminder_id = cursor.lastrowid
        
        await update.message.reply_text(
            f"✅ **Reminder Set!**\n\n"
            f"📝 **Message:** {message}\n"
            f"⏰ **Time:** {reminder_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"🆔 **ID:** `{reminder_id}`\n\n"
            f"Use `/myreminders` to view all",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def myreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    cursor.execute("""
        SELECT id, reminder_text, reminder_time FROM reminders 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY reminder_time ASC
        """, (user.id,))
    
    reminders = cursor.fetchall()
    
    if not reminders:
        await update.message.reply_text("📭 No pending reminders. Use `/remind` to set one!", parse_mode='Markdown')
        return
    
    text = "📋 **Your Pending Reminders:**\n\n"
    for reminder in reminders:
        text += f"🆔 `{reminder[0]}` • **{reminder[1]}**\n"
        text += f"   ⏰ {reminder[2]}\n\n"
    
    text += "Use `/cancel [id]` to cancel a reminder"
    await update.message.reply_text(text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/cancel [reminder_id]`\nExample: `/cancel 5`", parse_mode='Markdown')
        return
    
    user = update.message.from_user
    reminder_id = context.args[0]
    
    cursor.execute("""
        UPDATE reminders SET status = 'cancelled' 
        WHERE id = ? AND user_id = ? AND status = 'pending'
        """, (reminder_id, user.id))
    conn.commit()
    
    if cursor.rowcount > 0:
        await update.message.reply_text(f"✅ Reminder `{reminder_id}` cancelled!", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Reminder not found!", parse_mode='Markdown')

async def clearreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    cursor.execute("""
        UPDATE reminders SET status = 'cancelled' 
        WHERE user_id = ? AND status = 'pending'
        """, (user.id,))
    conn.commit()
    await update.message.reply_text("✅ All your reminders cleared!", parse_mode='Markdown')

# ================= OWNER COMMANDS =================
async def users_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized! Only owner can use this.")
        return
    
    users = total_users()
    text = f"📊 **Total Users:** {len(users)}\n\n"
    
    for user in users[:20]:
        text += f"• {user[1] or user[2] or 'Unknown'} (ID: `{user[0]}`)\n"
        text += f"  💬 Chats: {user[6]} | Joined: {user[4][:10]}\n\n"
    
    if len(users) > 20:
        text += f"\n... and {len(users) - 20} more users"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized! Only owner can use this.")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("**Usage:** `/broadcast [message]`\nExample: `/broadcast Hello everyone!`", parse_mode='Markdown')
        return

    users = total_users()
    sent = 0
    failed = 0
    
    status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message, parse_mode='Markdown')
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast failed to {user[0]}: {e}")

    await status_msg.edit_text(f"✅ **Broadcast Complete!**\n\n📤 Sent: {sent}\n❌ Failed: {failed}")

async def group_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized! Only owner can use this.")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("**Usage:** `/groupbroadcast [message]`\nExample: `/groupbroadcast Hello everyone!`", parse_mode='Markdown')
        return

    groups = get_all_groups()
    sent = 0
    failed = 0
    
    status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(groups)} groups...")
    
    for group_id, group_name in groups:
        try:
            await context.bot.send_message(chat_id=group_id, text=message, parse_mode='Markdown')
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"Group broadcast failed to {group_id}: {e}")

    await status_msg.edit_text(f"✅ **Group Broadcast Complete!**\n\n📤 Sent: {sent}\n❌ Failed: {failed}")

async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not update.message.chat.type in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    group_id = update.message.chat_id
    group_name = update.message.chat.title
    
    add_group(group_id, group_name)
    await update.message.reply_text(f"✅ Group added to broadcast list!\n\n📝 **Name:** {group_name}\n🆔 **ID:** `{group_id}`", parse_mode='Markdown')

async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not context.args:
        await update.message.reply_text("**Usage:** `/removegroup [group_id]`\nExample: `/removegroup -1001234567890`", parse_mode='Markdown')
        return
    
    group_id = int(context.args[0])
    
    try:
        cursor.execute("UPDATE groups SET is_active = 0 WHERE group_id = ?", (group_id,))
        conn.commit()
        await update.message.reply_text(f"✅ Group `{group_id}` removed from broadcast list!", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def stats_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    users = total_users()
    groups = get_all_groups()
    
    cursor.execute("SELECT COUNT(*) FROM chat_history")
    total_chats = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE status = 'pending'")
    pending_reminders = cursor.fetchone()[0]
    
    text = f"""
📊 **Bot Statistics**

👥 **Total Users:** {len(users)}
👥 **Active Groups:** {len(groups)}
💬 **Total Chats:** {total_chats}
⏰ **Pending Reminders:** {pending_reminders}

**System Info:**
• AI Model: Llama 3.3 70B
• Memory Limit: 20 messages per user
• Image Generation: Pollinations.ai
    """
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= SETTINGS =================
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    prefs = get_user_preferences(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("🌐 Language", callback_data="set_lang"),
            InlineKeyboardButton("📝 Style", callback_data="set_style")
        ],
        [
            InlineKeyboardButton("🎨 Theme", callback_data="set_theme"),
            InlineKeyboardButton("📊 Stats", callback_data="stats")
        ],
        [
            InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history"),
            InlineKeyboardButton("🔙 Back", callback_data="back_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
⚙️ **Settings**

**Current Preferences:**
• Language: {prefs['language']}
• Response Style: {prefs['response_style']}
• Theme: {prefs['theme']}

Choose an option to customize:
    """
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Reply to an image with `/analyze` to analyze it!", parse_mode='Markdown')
        return
    
    msg = await update.message.reply_text("🔍 Analyzing image...")
    
    photo = await update.message.reply_to_message.photo[-1].get_file()
    path = f"temp_analyze_{uuid.uuid4().hex[:6]}.jpg"
    await photo.download_to_drive(path)
    
    reply = await analyze_image_advanced(path)
    await msg.edit_text(reply, parse_mode='Markdown')
    
    if os.path.exists(path):
        os.remove(path)

# ================= CALLBACK HANDLER =================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if data == "study_help":
        text = "📚 **Study Features**\n\n• `/notes [topic]` - Detailed notes\n• `/explain [topic]` - Simple explanation\n• `/mcq [topic]` - Multiple choice questions\n• `/pyq [subject]` - Previous year questions\n• `/doubt [question]` - Solve doubts\n• `/pdfnotes [topic]` - PDF format notes\n• `/quiz [topic] [class] [subject] [q]` - Custom quiz"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "creative":
        text = "🎨 **Creative Features**\n\n• `/imagine [prompt]` - AI image\n• `/draw [prompt]` - Create prompt\n• `/generate [prompt]` - Quick image\n• `/voice [text]` - Text to speech\n• `/enhance [prompt]` - Enhance prompt\n• `.gen [prompt]` - Quick generate\n• `.gen anime [prompt]` - Anime style\n• `.gen 3d [prompt]` - 3D style\n• `.gen logo [prompt]` - Logo design"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "reminders":
        text = "⏰ **Reminder Commands**\n\n• `/remind [time] [message]` - Set reminder\n• `/myreminders` - View reminders\n• `/cancel [id]` - Cancel reminder\n• `/clearreminders` - Clear all\n\n**Time formats:** 10m, 2h, 1d, YYYY-MM-DD HH:MM"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "settings":
        prefs = get_user_preferences(user_id)
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_lang"),
             InlineKeyboardButton("📝 Style", callback_data="set_style")],
            [InlineKeyboardButton("🎨 Theme", callback_data="set_theme"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")],
            [InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history"),
             InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"⚙️ **Settings**\n\nCurrent: {prefs['language']} | {prefs['response_style']} | {prefs['theme']}", 
                                    reply_markup=reply_markup, parse_mode='Markdown')
        
    elif data == "stats":
        stats = get_user_stats(user_id)
        if stats:
            text = f"📊 **Your Stats**\n\n💬 Chats: {stats[0]}\n📅 Joined: {stats[1]}\n⏰ Last: {stats[2]}"
        else:
            text = "No stats found"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "examples":
        text = "❓ **Example Questions**\n\n• 'Photosynthesis kya hai?'\n• 'x² + 5x + 6 = 0 solve karo'\n• 'Quantum physics samjhao'\n• '5 math problems do'\n• 'Water cycle explain karo'\n• 'C programming basics'\n• 'Essay on global warming'"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "set_lang":
        keyboard = [
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
             InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi")],
            [InlineKeyboardButton("🇪🇸 Spanish", callback_data="lang_es"),
             InlineKeyboardButton("🇫🇷 French", callback_data="lang_fr")],
            [InlineKeyboardButton("🇩🇪 German", callback_data="lang_de"),
             InlineKeyboardButton("🇨🇳 Chinese", callback_data="lang_zh")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🌐 **Select Language**", reply_markup=reply_markup, parse_mode='Markdown')
        
    elif data.startswith("lang_"):
        lang = data.replace("lang_", "")
        set_user_preference(user_id, "language", lang)
        await query.edit_message_text(f"✅ Language set to {lang}")
        
    elif data == "set_style":
        keyboard = [
            [InlineKeyboardButton("📌 Concise", callback_data="style_concise"),
             InlineKeyboardButton("⚖️ Balanced", callback_data="style_balanced")],
            [InlineKeyboardButton("📚 Detailed", callback_data="style_detailed"),
             InlineKeyboardButton("🎓 Academic", callback_data="style_academic")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📝 **Response Style**", reply_markup=reply_markup, parse_mode='Markdown')
        
    elif data.startswith("style_"):
        style = data.replace("style_", "")
        set_user_preference(user_id, "response_style", style)
        await query.edit_message_text(f"✅ Style set to {style}")
        
    elif data == "set_theme":
        keyboard = [
            [InlineKeyboardButton("🌞 Light", callback_data="theme_light"),
             InlineKeyboardButton("🌙 Dark", callback_data="theme_dark")],
            [InlineKeyboardButton("💜 Purple", callback_data="theme_purple"),
             InlineKeyboardButton("💚 Green", callback_data="theme_green")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎨 **Select Theme**", reply_markup=reply_markup, parse_mode='Markdown')
        
    elif data.startswith("theme_"):
        theme = data.replace("theme_", "")
        set_user_preference(user_id, "theme", theme)
        await query.edit_message_text(f"✅ Theme set to {theme}")
        
    elif data == "clear_history":
        clear_user_history(user_id)
        await query.edit_message_text("✅ Chat history cleared!")
        
    elif data == "back_main":
        keyboard = [
            [InlineKeyboardButton("📚 Study", callback_data="study_help"),
             InlineKeyboardButton("🎨 Creative", callback_data="creative")],
            [InlineKeyboardButton("⏰ Reminders", callback_data="reminders"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats"),
             InlineKeyboardButton("❓ Examples", callback_data="examples")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🌟 **Welcome back!** Choose an option:", reply_markup=reply_markup, parse_mode='Markdown')

# ================= MAIN MESSAGE HANDLER =================
def is_tag_or_reply(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.username == BOT_USERNAME.replace("@", ""):
            return True
    
    if message.text and BOT_USERNAME.lower() in message.text.lower():
        return True
    
    if message.chat.type == "private":
        return True
    
    return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    message = update.message
    if not message.from_user:
        return
    
    # Check if group and add to database
    if message.chat.type in ['group', 'supergroup']:
        add_group(message.chat_id, message.chat.title)

    user_id = message.from_user.id
    update_user_activity(user_id)

    # Handle .gen command
    if message.text and message.text.startswith(".gen"):
        parts = message.text.split(" ")

        if len(parts) < 2:
            await message.reply_text(
                "✨ **Quick Image Generator**\n\n"
                "**Usage:**\n"
                "• `.gen dragon` - Normal\n"
                "• `.gen anime girl` - Anime style\n"
                "• `.gen 3d car` - 3D style\n"
                "• `.gen logo gaming` - Logo design\n"
                "• `.gen cartoon cat` - Cartoon style\n"
                "• `.gen 4 cyberpunk` - 4 images",
                parse_mode='Markdown'
            )
            return

        style = "normal"
        amount = 1
        
        if len(parts) > 1:
            if parts[1] in ["anime", "realistic", "3d", "logo", "cartoon", "fantasy", "cyberpunk"]:
                style = parts[1]
                prompt = " ".join(parts[2:])
            elif parts[1] == "4":
                amount = 4
                style = "normal"
                prompt = " ".join(parts[2:]) if len(parts) > 2 else ""
            else:
                prompt = " ".join(parts[1:])
        
        if not prompt:
            prompt = "beautiful landscape"
        
        msg = await message.reply_text("🎨 Generating image...")
        
        try:
            images = await generate_image_advanced(prompt, style, amount)
            
            if images:
                for img in images:
                    with open(img, "rb") as f:
                        await message.reply_photo(photo=f, caption=f"🎨 **{style.upper()}** | {prompt[:50]}")
                    os.remove(img)
                await msg.delete()
            else:
                await msg.edit_text("❌ Image generation failed. Try again!")
        except Exception as e:
            logger.error(f".gen error: {e}")
            await msg.edit_text("❌ Error generating image. Please try again.")
        
        return

    # Don't respond to bot messages
    if message.from_user.is_bot:
        return
    
    # Check if bot should respond
    if not is_tag_or_reply(message):
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")

    # Handle different message types
    if message.text:
        text = message.text.replace(BOT_USERNAME, "").strip()
        if not text:
            text = "Hello"
        
        # Check if it's a reply to bot's message
        if message.reply_to_message and message.reply_to_message.from_user.username == BOT_USERNAME.replace("@", ""):
            text = f"[Reply to bot's message] {text}"
        
        reply = await ask_ai_hinglish(user_id, text)
        save_chat_history(user_id, text, reply)
        await message.reply_text(reply, parse_mode='Markdown')

    elif message.photo:
        file = await message.photo[-1].get_file()
        path = f"temp_{user_id}_{uuid.uuid4().hex[:6]}.jpg"
        await file.download_to_drive(path)

        reply = await analyze_image_advanced(path)
        await message.reply_text(reply, parse_mode='Markdown')
        
        if os.path.exists(path):
            os.remove(path)

    elif message.voice:
        file = await message.voice.get_file()
        path = f"temp_voice_{uuid.uuid4().hex[:6]}.ogg"
        await file.download_to_drive(path)

        text = voice_to_text_enhanced(path)
        await message.reply_text(f"📝 **You said:** {text}", parse_mode='Markdown')
        
        reply = await ask_ai_hinglish(user_id, text)
        await message.reply_text(reply, parse_mode='Markdown')
        
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists("voice.wav"):
            os.remove("voice.wav")

# ================= CHECK REMINDERS =================
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        while not reminder_queue.empty():
            reminder = reminder_queue.get_nowait()
            reminder_id, user_id, message, reminder_time = reminder
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ **REMINDER!** ⏰\n\n📝 {message}\n\n🆔 ID: `{reminder_id}`\n⏰ Time: {reminder_time}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send reminder to {user_id}: {e}")
    except queue.Empty:
        pass

# ================= POST INIT =================
async def post_init(application):
    bot_username = application.bot.username
    logger.info(f"🚀 Ultimate AI Bot Started!")
    logger.info(f"Bot Username: @{bot_username}")
    logger.info(f"Owner ID: {OWNER_ID}")
    logger.info("Features: Hinglish Chat, Study, Creative, Reminders, Voice, Images, Group Broadcast")
    logger.info("Database connected successfully!")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("owner", owner_command))
    app.add_handler(CommandHandler("stats", user_stats))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("analyze", analyze_command))
    
    # Study commands
    app.add_handler(CommandHandler("notes", notes))
    app.add_handler(CommandHandler("explain", explain))
    app.add_handler(CommandHandler("mcq", mcq))
    app.add_handler(CommandHandler("pyq", pyq))
    app.add_handler(CommandHandler("doubt", doubt))
    app.add_handler(CommandHandler("pdfnotes", pdfnotes))
    app.add_handler(CommandHandler("quiz", enhanced_quiz))
    
    # Creative commands
    app.add_handler(CommandHandler("imagine", imagine))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("enhance", enhance))
    
    # Reminder commands
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("myreminders", myreminders))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("clearreminders", clearreminders))
    
    # Owner commands
    app.add_handler(CommandHandler("users", users_count))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("groupbroadcast", group_broadcast))
    app.add_handler(CommandHandler("addgroup", add_group_command))
    app.add_handler(CommandHandler("removegroup", remove_group_command))
    app.add_handler(CommandHandler("statsall", stats_all))
    
    # Callback handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Main message handler
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, handle_message))
    
    # Job queue for reminders
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_reminders, interval=30, first=10)
    
    logger.info("Starting Ultimate AI Bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
