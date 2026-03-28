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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
import speech_recognition as sr
from pydub import AudioSegment
import requests
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import hashlib
import json
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

# Memory system
user_memory = {}

# ================= DATABASE SETUP =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    join_date TEXT,
    last_active TEXT,
    chat_count INTEGER DEFAULT 0
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
    response_style TEXT DEFAULT 'balanced'
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
    added_date TEXT
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
        cursor.execute("SELECT language, response_style FROM user_preferences WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return {"language": result[0], "response_style": result[1]}
    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
    return {"language": "en", "response_style": "balanced"}

def set_user_preference(user_id, pref_type, value):
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO user_preferences (user_id, language, response_style)
            VALUES (?, 'en', 'balanced')
            """, (user_id,))
        
        cursor.execute(f"UPDATE user_preferences SET {pref_type} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error setting preference: {e}")

def total_users():
    try:
        cursor.execute("SELECT id, username, first_name, last_name, join_date, last_active, chat_count FROM users")
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
            INSERT OR IGNORE INTO groups (group_id, group_name, added_date)
            VALUES (?, ?, ?)
            """, (group_id, group_name, current_time))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding group: {e}")

def get_all_groups():
    try:
        cursor.execute("SELECT group_id, group_name FROM groups")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        return []

# ================= FIXED IMAGE GENERATION =================
async def generate_image_fixed(prompt, style="normal"):
    """Working image generation with multiple fallbacks"""
    
    # Style modifiers
    style_map = {
        "anime": "anime style, manga, vibrant colors",
        "realistic": "photorealistic, detailed, high quality",
        "3d": "3d render, cgi, blender, octane render",
        "logo": "minimal logo, vector art, flat design",
        "cartoon": "cartoon style, pixar style, cute",
        "fantasy": "fantasy art, magical, ethereal",
        "cyberpunk": "cyberpunk, neon lights, futuristic"
    }
    
    style_text = style_map.get(style, "")
    final_prompt = f"{prompt} {style_text}".strip()
    
    # Method 1: Pollinations.ai (new endpoint)
    try:
        encoded_prompt = final_prompt.replace(" ", "%20")
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        
        response = requests.get(url, timeout=15)
        if response.status_code == 200 and len(response.content) > 10000:  # Valid image size
            filename = f"img_{uuid.uuid4().hex[:8]}.png"
            with open(filename, "wb") as f:
                f.write(response.content)
            return filename
    except Exception as e:
        logger.error(f"Pollinations error: {e}")
    
    # Method 2: Lexica API (working alternative)
    try:
        url = "https://lexica.art/api/v1/search"
        params = {"q": prompt}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("images") and len(data["images"]) > 0:
                img_url = data["images"][0]["src"]
                img_response = requests.get(img_url, timeout=15)
                if img_response.status_code == 200:
                    filename = f"img_{uuid.uuid4().hex[:8]}.png"
                    with open(filename, "wb") as f:
                        f.write(img_response.content)
                    return filename
    except Exception as e:
        logger.error(f"Lexica error: {e}")
    
    # Method 3: Placeholder with AI-generated text
    try:
        filename = f"img_{uuid.uuid4().hex[:8]}.png"
        img = Image.new('RGB', (512, 512), color=(50, 50, 80))
        draw = ImageDraw.Draw(img)
        
        # Try to use a font
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        # Draw some random shapes for artistic effect
        for _ in range(50):
            x = random.randint(0, 512)
            y = random.randint(0, 512)
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            draw.point((x, y), fill=(r, g, b))
        
        # Draw text
        text_lines = [prompt[i:i+30] for i in range(0, len(prompt), 30)]
        y_pos = 200
        for line in text_lines[:3]:
            draw.text((50, y_pos), line, fill=(255, 255, 255), font=font)
            y_pos += 30
        
        img.save(filename)
        return filename
    except Exception as e:
        logger.error(f"Placeholder error: {e}")
        return None

# ================= AI ENGINE =================
async def ask_ai_hinglish(user_id, text):
    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": text})
    user_memory[user_id] = user_memory[user_id][-20:]

    text_lower = text.lower()
    
    if any(word in text_lower for word in ['owner', 'malik', 'banane wala', 'creator']):
        return f"👑 My owner is {OWNER_NAME}! Unhone mujhe banaya hai. Main sirf unke commands maanta hoon. 🙏"
    
    if any(word in text_lower for word in ['gpt', 'chatgpt', 'kya tum gpt ho']):
        return f"🤖 No bro, main GPT nahi hoon! Mujhe {OWNER_NAME} ne banaya hai. 📚"
    
    if any(word in text_lower for word in ['study', 'padhai', 'kyon banaya']):
        return f"📚 Haan ji, mujhe sirf study ke liye banaya gaya hai! {OWNER_NAME} ne mujhe students ki help karne ke liye banaya hai. 🎯"
    
    if any(word in text_lower for word in ['tum kaun ho', 'who are you']):
        return f"🤖 Main Study Controller hoon! {OWNER_NAME} ne banaya hai. Main Hinglish mein baat karta hoon. 📚"
    
    if any(word in text_lower for word in ['kya kar sakte ho', 'what can you do']):
        return f"🎯 Main ye sab kar sakta hoon:\n\n📝 Notes /notes\n🔍 Explain /explain\n❓ MCQ /mcq\n📚 PYQ /pyq\n🤔 Doubt /doubt\n🎨 Image /imagine\n⏰ Reminder /remind\n\nMujhe tag karo @STUDYCONTROLLERV2_bot"
    
    if any(word in text_lower for word in ['thanks', 'thankyou', 'shukriya']):
        return f"🙏 Aapka swagat hai! Kuch aur poochna?"

    messages = [
        {"role": "system", "content": f"""Tum Study Controller bot ho. Tumhare owner {OWNER_NAME} hain. 
        Hamesha Hinglish (Hindi + English mix) mein friendly reply do. Chhote answers do."""}
    ] + user_memory[user_id]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "❌ Technical problem hai! Thoda der baad try karo."

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
            logger.error(f"Reminder error: {e}")
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

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        while not reminder_queue.empty():
            reminder = reminder_queue.get_nowait()
            reminder_id, user_id, message, reminder_time = reminder
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ **REMINDER!** ⏰\n\n📝 {message}\n\n🆔 ID: `{reminder_id}`",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send reminder: {e}")
    except queue.Empty:
        pass

# ================= COMMAND HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = (
        f"🌟 **Namaste {user.first_name}!** 🌟\n\n"
        "Main **Study Controller** AI assistant hoon!\n\n"
        
        "📚 **Study Features**\n"
        "• `/notes [topic]` - Notes\n"
        "• `/explain [topic]` - Samjhao\n"
        "• `/mcq [topic]` - MCQ\n"
        "• `/pyq [subject]` - PYQ\n"
        "• `/doubt [question]` - Doubt solve\n\n"
        
        "🎨 **Image Features**\n"
        "• `/imagine [prompt]` - AI image\n"
        "• `/imagine anime [prompt]` - Anime style\n"
        "• `/imagine realistic [prompt]` - Realistic\n"
        "• `/imagine 3d [prompt]` - 3D style\n"
        "• `/imagine logo [prompt]` - Logo design\n\n"
        
        "⏰ **Reminders**\n"
        "• `/remind 10m [message]` - Set reminder\n"
        "• `/myreminders` - View reminders\n\n"
        
        "**Bas mujhe tag karo!** 🚀"
    )
    
    keyboard = [
        [InlineKeyboardButton("📚 Study", callback_data="study"),
         InlineKeyboardButton("🎨 Image", callback_data="image")],
        [InlineKeyboardButton("⏰ Reminder", callback_data="reminder"),
         InlineKeyboardButton("⚙️ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🌟 **ALL COMMANDS** 🌟

**📚 STUDY**
/notes [topic] - Detailed notes
/explain [topic] - Simple explanation
/mcq [topic] - Multiple choice questions
/pyq [subject] - Previous year questions
/doubt [question] - Solve doubts

**🎨 IMAGE GENERATION**
/imagine [prompt] - Normal style
/imagine anime [prompt] - Anime style
/imagine realistic [prompt] - Realistic
/imagine 3d [prompt] - 3D render
/imagine logo [prompt] - Logo design

**⏰ REMINDERS**
/remind 10m [message] - 10 min reminder
/remind 2h [message] - 2 hour reminder
/remind 1d [message] - 1 day reminder
/myreminders - View reminders
/cancel [id] - Cancel reminder

**⚙️ OTHER**
/stats - Your statistics
/owner - Bot owner info

**💬 Just tag me or reply!**
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🎨 **Image Generation**\n\n"
            "**Usage:**\n"
            "• `/imagine cat` - Normal\n"
            "• `/imagine anime girl` - Anime\n"
            "• `/imagine realistic mountain` - Realistic\n"
            "• `/imagine 3d car` - 3D style\n"
            "• `/imagine logo gaming` - Logo\n\n"
            "Try: `/imagine beautiful landscape`",
            parse_mode='Markdown'
        )
        return
    
    # Parse style and prompt
    style = "normal"
    args = context.args
    
    if args[0] in ["anime", "realistic", "3d", "logo", "cartoon", "fantasy", "cyberpunk"]:
        style = args[0]
        prompt = " ".join(args[1:])
    else:
        prompt = " ".join(args)
    
    if not prompt:
        prompt = "beautiful scenery"
    
    msg = await update.message.reply_text(f"🎨 Generating {style} image: **{prompt[:50]}**...", parse_mode='Markdown')
    
    try:
        filename = await generate_image_fixed(prompt, style)
        
        if filename and os.path.exists(filename):
            with open(filename, "rb") as img:
                await update.message.reply_photo(
                    photo=img, 
                    caption=f"🎨 **{style.upper()}**\n📝 {prompt[:100]}"
                )
            os.remove(filename)
            await msg.delete()
        else:
            await msg.edit_text("❌ Image generate nahi ho payi. Dobara try karo!")
    except Exception as e:
        logger.error(f"Imagine error: {e}")
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/notes [topic]`\nExample: `/notes photosynthesis`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"📝 Generating notes for **{topic}**...", parse_mode='Markdown')
    
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Create detailed study notes for {topic} in Hinglish")
    await msg.edit_text(reply)

async def explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/explain [topic]`\nExample: `/explain quantum physics`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"🔍 Explaining **{topic}**...", parse_mode='Markdown')
    
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Explain {topic} in simple Hinglish language")
    await msg.edit_text(reply)

async def mcq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/mcq [topic]`\nExample: `/mcq world war 2`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"📝 Generating MCQs for **{topic}**...", parse_mode='Markdown')
    
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Create 10 MCQs with answers for {topic} in Hinglish")
    await msg.edit_text(reply)

async def pyq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/pyq [subject]`\nExample: `/pyq physics`", parse_mode='Markdown')
        return
    subject = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"📚 Finding PYQs for **{subject}**...", parse_mode='Markdown')
    
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Generate important previous year questions for {subject} in Hinglish")
    await msg.edit_text(reply)

async def doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/doubt [question]`\nExample: `/doubt what is photosynthesis`", parse_mode='Markdown')
        return
    question = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    msg = await update.message.reply_text(f"❓ Solving your doubt...", parse_mode='Markdown')
    
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Solve step by step: {question}")
    await msg.edit_text(reply)

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "⏰ **Set Reminder**\n\n"
            "**Examples:**\n"
            "• `/remind 10m Study math`\n"
            "• `/remind 2h Submit assignment`\n"
            "• `/remind 1d Water plants`",
            parse_mode='Markdown'
        )
        return
    
    user = update.message.from_user
    
    try:
        time_str = context.args[0].lower()
        message = " ".join(context.args[1:])
        reminder_time = parse_reminder_time(time_str)
        
        if not reminder_time:
            await update.message.reply_text("❌ Invalid time! Use: 10m, 2h, 1d")
            return
        
        reminder_time_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO reminders (user_id, reminder_text, reminder_time, created_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """, (user.id, message, reminder_time_str, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        await update.message.reply_text(
            f"✅ **Reminder Set!**\n\n"
            f"📝 {message}\n"
            f"⏰ {reminder_time.strftime('%Y-%m-%d %H:%M')}",
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
        await update.message.reply_text("📭 No pending reminders!")
        return
    
    text = "📋 **Your Reminders:**\n\n"
    for r in reminders:
        text += f"🆔 `{r[0]}` • {r[1]}\n   ⏰ {r[2]}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/cancel [id]`", parse_mode='Markdown')
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
        await update.message.reply_text("❌ Reminder not found!")

async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    stats = get_user_stats(user.id)
    
    if stats:
        text = f"📊 **Your Stats**\n\n💬 Chats: {stats[0]}\n📅 Joined: {stats[1][:10]}\n⏰ Last: {stats[2][:16]}"
    else:
        text = "No stats yet! Start chatting!"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👑 **Owner:** {OWNER_NAME}\n🆔 `{OWNER_ID}`\n\nUnhone mujhe banaya hai!",
        parse_mode='Markdown'
    )

# ================= GROUP BROADCAST =================
async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command works only in groups!")
        return
    
    add_group(update.message.chat_id, update.message.chat.title)
    await update.message.reply_text(f"✅ Group added to broadcast list!")

async def group_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("**Usage:** `/groupbroadcast [message]`", parse_mode='Markdown')
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
            logger.error(f"Failed to {group_id}: {e}")
    
    await status_msg.edit_text(f"✅ **Broadcast Done!**\n\n📤 Sent: {sent}\n❌ Failed: {failed}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("**Usage:** `/broadcast [message]`", parse_mode='Markdown')
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
    
    await status_msg.edit_text(f"✅ **Done!**\n\n📤 Sent: {sent}\n❌ Failed: {failed}")

async def users_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    users = total_users()
    text = f"📊 **Total Users:** {len(users)}\n\n"
    for user in users[:15]:
        text += f"• {user[1] or user[2] or 'Unknown'} (ID: `{user[0]}`)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= CALLBACK HANDLER =================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if data == "study":
        text = "📚 **Study Commands**\n\n/notes [topic]\n/explain [topic]\n/mcq [topic]\n/pyq [subject]\n/doubt [question]"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "image":
        text = "🎨 **Image Commands**\n\n/imagine [prompt]\n/imagine anime [prompt]\n/imagine realistic [prompt]\n/imagine 3d [prompt]\n/imagine logo [prompt]"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "reminder":
        text = "⏰ **Reminder Commands**\n\n/remind 10m [message]\n/remind 2h [message]\n/myreminders\n/cancel [id]"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "help":
        text = await help_command(update, context)
        await query.edit_message_text(text, parse_mode='Markdown')

# ================= MESSAGE HANDLER =================
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
    if not message.from_user or message.from_user.is_bot:
        return
    
    # Add group if in group
    if message.chat.type in ['group', 'supergroup']:
        add_group(message.chat_id, message.chat.title)
    
    user_id = message.from_user.id
    update_user_activity(user_id)
    
    if not is_tag_or_reply(message):
        return
    
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    
    if message.text:
        text = message.text.replace(BOT_USERNAME, "").strip()
        if not text:
            text = "Hello"
        
        reply = await ask_ai_hinglish(user_id, text)
        save_chat_history(user_id, text, reply)
        await message.reply_text(reply, parse_mode='Markdown')
    
    elif message.photo:
        await message.reply_text("🖼️ Image mil gaya! Main sirf text aur voice samajh sakta hoon. Koi question poochho!")

# ================= POST INIT =================
async def post_init(application):
    logger.info("🚀 Study Controller Bot Started!")
    logger.info(f"Bot: @{application.bot.username}")
    logger.info(f"Owner: {OWNER_NAME}")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("owner", owner_command))
    app.add_handler(CommandHandler("stats", user_stats))
    
    # Study
    app.add_handler(CommandHandler("notes", notes))
    app.add_handler(CommandHandler("explain", explain))
    app.add_handler(CommandHandler("mcq", mcq))
    app.add_handler(CommandHandler("pyq", pyq))
    app.add_handler(CommandHandler("doubt", doubt))
    
    # Image
    app.add_handler(CommandHandler("imagine", imagine))
    
    # Reminder
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("myreminders", myreminders))
    app.add_handler(CommandHandler("cancel", cancel))
    
    # Owner
    app.add_handler(CommandHandler("users", users_count))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("groupbroadcast", group_broadcast))
    app.add_handler(CommandHandler("addgroup", add_group_command))
    
    # Callback
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
    
    # Reminder job
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_reminders, interval=30, first=10)
    
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
