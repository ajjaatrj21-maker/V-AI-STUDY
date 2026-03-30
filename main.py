import os
import base64
import sqlite3
import threading
import queue
import time as time_module
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
import re

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= CONFIG =================
BOT_TOKEN = "8619731533:AAGOPaGc_CcQaW5_B-HGUCeY3MetJFzoD0U"
GROQ_API_KEY = "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"
BOT_USERNAME = "@STUDYCONTROLLERV2_bot"

OWNER_ID = 6305002830
OWNER_NAME = "꧁⁣༒𓆩A𝔰𝔥𝔦𝔰𝔥𓆪༒꧂"

# Database connection with thread-local storage
import threading
thread_local = threading.local()

def get_db():
    """Get database connection for current thread"""
    if not hasattr(thread_local, "conn"):
        thread_local.conn = sqlite3.connect("users.db", check_same_thread=False)
        thread_local.cursor = thread_local.conn.cursor()
    return thread_local.conn, thread_local.cursor

# Initialize database
conn, cursor = get_db()

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
    is_blocked INTEGER DEFAULT 0,
    is_premium INTEGER DEFAULT 0,
    premium_until TEXT,
    daily_usage_count INTEGER DEFAULT 0,
    last_daily_reset TEXT,
    is_winner INTEGER DEFAULT 0,
    winner_date TEXT
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
    theme TEXT DEFAULT 'default',
    ai_model TEXT DEFAULT 'llama-3.3-70b-versatile'
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS feedback(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    user_name TEXT,
    group_id INTEGER,
    group_name TEXT,
    feedback_text TEXT,
    feedback_type TEXT,
    rating INTEGER,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS complaints(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    user_name TEXT,
    group_id INTEGER,
    group_name TEXT,
    complaint_text TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    resolved_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_activity(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    user_name TEXT,
    group_id INTEGER,
    group_name TEXT,
    action_type TEXT,
    action_details TEXT,
    timestamp TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_usage(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    usage_date TEXT,
    chat_count INTEGER DEFAULT 0,
    commands_used TEXT,
    last_activity TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS quiz_results(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    topic TEXT,
    score INTEGER,
    total_questions INTEGER,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS flashcards(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    question TEXT,
    answer TEXT,
    category TEXT,
    created_at TEXT,
    review_count INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    content TEXT,
    category TEXT,
    created_at TEXT,
    updated_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS winners(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    user_name TEXT,
    winner_date TEXT,
    month TEXT,
    daily_usage_count INTEGER,
    prize TEXT DEFAULT 'Premium Account'
)
""")

conn.commit()

# ================= DATABASE FUNCTIONS =================
def ensure_connection():
    """Ensure database connection is alive"""
    try:
        conn, cursor = get_db()
        cursor.execute("SELECT 1")
        return conn, cursor
    except:
        thread_local.conn = sqlite3.connect("users.db", check_same_thread=False)
        thread_local.cursor = thread_local.conn.cursor()
        return thread_local.conn, thread_local.cursor

def add_user(user_id, username, first_name, last_name):
    conn, cursor = ensure_connection()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, first_name, last_name, join_date, last_active, chat_count, last_daily_reset) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, first_name, last_name, current_time, current_time, 0, current_time)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding user: {e}")

def update_user_activity(user_id, chat_type="private", group_id=None, group_name=None):
    conn, cursor = ensure_connection()
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
        
        cursor.execute("SELECT username, first_name FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        if user_data:
            username = user_data[0]
            user_name = user_data[1]
            
            cursor.execute("""
                INSERT INTO user_activity (user_id, username, user_name, group_id, group_name, action_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, username, user_name, group_id, group_name, "message", current_time))
            conn.commit()
            
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO daily_usage (user_id, usage_date, chat_count, last_activity)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, usage_date) DO UPDATE SET
                chat_count = chat_count + 1,
                last_activity = ?
                """, (user_id, today, current_time, current_time))
            conn.commit()
            
            cursor.execute("SELECT last_daily_reset FROM users WHERE id = ?", (user_id,))
            last_reset = cursor.fetchone()
            if last_reset and last_reset[0]:
                last_reset_date = datetime.strptime(last_reset[0], "%Y-%m-%d %H:%M:%S").date()
                today_date = datetime.now().date()
                if last_reset_date != today_date:
                    cursor.execute("UPDATE users SET daily_usage_count = 0, last_daily_reset = ? WHERE id = ?", 
                                 (current_time, user_id))
                    conn.commit()
            
            cursor.execute("""
                UPDATE users SET daily_usage_count = daily_usage_count + 1 
                WHERE id = ?
                """, (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating activity: {e}")

def save_chat_history(user_id, message, response):
    conn, cursor = ensure_connection()
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
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT language, response_style, theme, ai_model FROM user_preferences WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return {"language": result[0], "response_style": result[1], "theme": result[2], "ai_model": result[3]}
    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
    return {"language": "en", "response_style": "balanced", "theme": "default", "ai_model": "llama-3.3-70b-versatile"}

def set_user_preference(user_id, pref_type, value):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO user_preferences (user_id, language, response_style, theme, ai_model)
            VALUES (?, 'en', 'balanced', 'default', 'llama-3.3-70b-versatile')
            """, (user_id,))
        cursor.execute(f"UPDATE user_preferences SET {pref_type} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting preference: {e}")
        return False

def save_feedback(user_id, username, user_name, group_id, group_name, feedback_text, feedback_type="feedback", rating=5):
    conn, cursor = ensure_connection()
    try:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO feedback (user_id, username, user_name, group_id, group_name, feedback_text, feedback_type, rating, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, user_name, group_id, group_name, feedback_text, feedback_type, rating, created_at))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return False

def save_complaint(user_id, username, user_name, group_id, group_name, complaint_text):
    conn, cursor = ensure_connection()
    try:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO complaints (user_id, username, user_name, group_id, group_name, complaint_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, user_name, group_id, group_name, complaint_text, created_at))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving complaint: {e}")
        return None

def get_daily_top_users(limit=10):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("""
            SELECT user_id, username, first_name, daily_usage_count 
            FROM users 
            WHERE daily_usage_count > 0 
            ORDER BY daily_usage_count DESC 
            LIMIT ?
            """, (limit,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting top users: {e}")
        return []

def get_monthly_top_users(limit=10):
    conn, cursor = ensure_connection()
    current_month = datetime.now().strftime("%Y-%m")
    try:
        cursor.execute("""
            SELECT u.id, u.username, u.first_name, SUM(du.chat_count) as total_usage
            FROM users u
            JOIN daily_usage du ON u.id = du.user_id
            WHERE du.usage_date LIKE ?
            GROUP BY u.id
            ORDER BY total_usage DESC
            LIMIT ?
            """, (f"{current_month}%", limit))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting monthly top users: {e}")
        return []

def check_and_declare_winner():
    conn, cursor = ensure_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("SELECT COUNT(*) FROM winners WHERE winner_date = ?", (today,))
    winner_exists = cursor.fetchone()[0]
    
    if winner_exists == 0:
        top_users = get_daily_top_users(1)
        if top_users:
            winner = top_users[0]
            user_id, username, first_name, usage_count = winner
            current_month = datetime.now().strftime("%Y-%m")
            cursor.execute("""
                INSERT INTO winners (user_id, username, user_name, winner_date, month, daily_usage_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, today, current_month, usage_count))
            conn.commit()
            cursor.execute("UPDATE users SET is_winner = 1, winner_date = ? WHERE id = ?", (today, user_id))
            conn.commit()
            return winner
    return None

def get_premium_until(user_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT premium_until FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        if result and result[0]:
            return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
    except:
        pass
    return None

def is_premium_user(user_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT is_premium, premium_until FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        if result and result[0] == 1:
            if result[1]:
                premium_until = datetime.strptime(result[1], "%Y-%m-%d %H:%M:%S")
                if premium_until > datetime.now():
                    return True
                else:
                    cursor.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE id = ?", (user_id,))
                    conn.commit()
        return False
    except:
        return False

def set_premium(user_id, days=30):
    conn, cursor = ensure_connection()
    try:
        premium_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE id = ?", (premium_until, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting premium: {e}")
        return False

def total_users():
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT id, username, first_name, last_name, join_date, last_active, chat_count, is_premium FROM users WHERE is_blocked = 0")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

def get_user_stats(user_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT chat_count, join_date, last_active, daily_usage_count FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return None

def get_chat_history(user_id, limit=5):
    conn, cursor = ensure_connection()
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
    conn, cursor = ensure_connection()
    try:
        cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return False

def add_group(group_id, group_name):
    conn, cursor = ensure_connection()
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT OR IGNORE INTO groups (group_id, group_name, added_date, is_active) VALUES (?, ?, ?, 1)", 
                      (group_id, group_name, current_time))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding group: {e}")

def get_all_groups():
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT group_id, group_name FROM groups WHERE is_active = 1")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        return []

def save_quiz_result(user_id, topic, score, total):
    conn, cursor = ensure_connection()
    try:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO quiz_results (user_id, topic, score, total_questions, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (user_id, topic, score, total, created_at))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving quiz result: {e}")

def add_flashcard(user_id, question, answer, category="General"):
    conn, cursor = ensure_connection()
    try:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO flashcards (user_id, question, answer, category, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (user_id, question, answer, category, created_at))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error adding flashcard: {e}")
        return None

def get_flashcards(user_id, category=None, limit=10):
    conn, cursor = ensure_connection()
    try:
        if category:
            cursor.execute("""
                SELECT id, question, answer, category FROM flashcards 
                WHERE user_id = ? AND category = ? 
                ORDER BY review_count ASC LIMIT ?
                """, (user_id, category, limit))
        else:
            cursor.execute("""
                SELECT id, question, answer, category FROM flashcards 
                WHERE user_id = ? 
                ORDER BY review_count ASC LIMIT ?
                """, (user_id, limit))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting flashcards: {e}")
        return []

def update_flashcard_review(card_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("UPDATE flashcards SET review_count = review_count + 1 WHERE id = ?", (card_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating flashcard: {e}")

def add_note(user_id, title, content, category="General"):
    conn, cursor = ensure_connection()
    try:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO notes (user_id, title, content, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, title, content, category, created_at, created_at))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error adding note: {e}")
        return None

def get_notes(user_id, category=None):
    conn, cursor = ensure_connection()
    try:
        if category:
            cursor.execute("""
                SELECT id, title, content, category, created_at FROM notes 
                WHERE user_id = ? AND category = ? 
                ORDER BY updated_at DESC
                """, (user_id, category))
        else:
            cursor.execute("""
                SELECT id, title, content, category, created_at FROM notes 
                WHERE user_id = ? 
                ORDER BY updated_at DESC
                """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting notes: {e}")
        return []

def update_note(note_id, content):
    conn, cursor = ensure_connection()
    try:
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE notes SET content = ?, updated_at = ? WHERE id = ?", (content, updated_at, note_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating note: {e}")
        return False

def delete_note(note_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        return False

# ================= AI ENGINE =================
client = Groq(api_key=GROQ_API_KEY)
user_memory = {}

async def ask_ai_hinglish(user_id, text):
    if user_id not in user_memory:
        user_memory[user_id] = []
    
    prefs = get_user_preferences(user_id)
    language = prefs['language']
    style = prefs['response_style']
    
    user_memory[user_id].append({"role": "user", "content": text})
    user_memory[user_id] = user_memory[user_id][-20:]
    
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['owner', 'malik', 'banane wala', 'creator']):
        return f"👑 My owner is {OWNER_NAME}! Unhone mujhe banaya hai. Main sirf unke commands maanta hoon. 🙏"
    
    system_prompt = f"""Tum ek smart Telegram AI bot ho. Tumhare owner {OWNER_NAME} hain.
    Language: {language}
    Response Style: {style}
    Be friendly and helpful. Focus on study-related topics.
    Answer in Hinglish (Hindi + English mix)."""
    
    messages = [{"role": "system", "content": system_prompt}] + user_memory[user_id]
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )
        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "❌ Kuch technical problem hai! Thoda der baad try karo."

# ================= IMAGE GENERATION =================
async def generate_image(prompt, style="normal"):
    try:
        style_prompts = {
            "anime": "anime style, manga art, vibrant colors",
            "realistic": "ultra realistic, photorealistic",
            "3d": "3d render, cgi, octane render",
            "logo": "minimal logo design, vector art",
            "cartoon": "cartoon style, colorful, cute",
            "fantasy": "fantasy art, magical, ethereal",
            "cyberpunk": "cyberpunk style, neon lights",
            "normal": ""
        }
        
        final_prompt = f"{prompt} {style_prompts.get(style, '')}".strip()
        url = f"https://image.pollinations.ai/prompt/{final_prompt.replace(' ', '+')}"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            filename = f"image_{uuid.uuid4().hex[:6]}.png"
            with open(filename, "wb") as f:
                f.write(response.content)
            return filename
    except Exception as e:
        logger.error(f"Image error: {e}")
    return None

# ================= VOICE TO TEXT =================
def voice_to_text(path):
    try:
        audio = AudioSegment.from_ogg(path)
        audio.export("voice.wav", format="wav")
        r = sr.Recognizer()
        with sr.AudioFile("voice.wav") as source:
            audio_data = r.record(source)
        try:
            text = r.recognize_google(audio_data)
            return text
        except:
            try:
                text = r.recognize_google(audio_data, language="hi-IN")
                return text
            except:
                return "Voice samajh nahi aayi."
    except Exception as e:
        logger.error(f"Voice error: {e}")
        return "Audio process error."

# ================= IMAGE ANALYSIS =================
async def analyze_image(path):
    try:
        with Image.open(path) as img:
            width, height = img.size
            format_type = img.format or "Unknown"
            mode = img.mode
            
        result = f"🖼️ **Image Analysis**\n\n📐 Size: {width}x{height}\n📁 Format: {format_type}\n🎨 Mode: {mode}"
        
        try:
            text = pytesseract.image_to_string(Image.open(path))
            if text.strip():
                result += f"\n\n📝 **Text Found:**\n{text[:500]}"
        except:
            pass
        
        return result
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ================= REMINDER SYSTEM =================
reminder_queue = queue.Queue()

def reminder_worker():
    while True:
        try:
            conn, cursor = ensure_connection()
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
            time_module.sleep(30)
        except Exception as e:
            logger.error(f"Reminder error: {e}")
            time_module.sleep(60)

reminder_thread = threading.Thread(target=reminder_worker, daemon=True)
reminder_thread.start()

def parse_reminder_time(time_str):
    now = datetime.now()
    try:
        if time_str.endswith('m'):
            return now + timedelta(minutes=int(time_str[:-1]))
        elif time_str.endswith('h'):
            return now + timedelta(hours=int(time_str[:-1]))
        elif time_str.endswith('d'):
            return now + timedelta(days=int(time_str[:-1]))
        else:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except:
        return None

# ================= COMMAND HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = f"""
🌟 **Namaste {user.first_name}!** 🌟

Main aapka advanced AI assistant **Study Controller** hoon.

📚 **STUDY FEATURES**
• /notes [topic] - Notes banayein
• /explain [topic] - Samjhao koi bhi topic
• /mcq [topic] - MCQ generate karein
• /pyq [subject] - Previous year questions
• /doubt [question] - Doubt solve karein
• /quiz [topic] [q] - Interactive quiz

🎨 **CREATIVE FEATURES**
• /imagine [prompt] - AI image generate
• /draw [prompt] - Enhanced prompt
• .gen [style] [prompt] - Quick image
• /voice [text] - Text to voice
• /analyze - Image analyze

📝 **NOTE TAKING**
• /addnote [title] [content] - Note save
• /mynotes - Notes list
• /editnote [id] [content] - Note edit
• /deletenote [id] - Note delete

🃏 **FLASHCARDS**
• /addcard [q] [a] - Flashcard add
• /mycards - All flashcards
• /study [category] - Study flashcards

⏰ **REMINDER COMMANDS**
• /remind [time] [message] - Set reminder
• /myreminders - View reminders
• /cancel [id] - Cancel reminder
• /clearreminders - Clear all

📝 **FEEDBACK & SUPPORT**
• /feedback [message] - Give feedback
• /complaint [message] - File complaint
• /complaintstatus [id] - Check complaint status

🏆 **DAILY REWARDS**
• /daily - Check daily usage
• /leaderboard - Monthly leaderboard
• /premium - Premium features

⚙️ **SETTINGS**
• /settings - Customize bot
• /stats - Your statistics
• /help - All commands

**🎁 WIN FREE TG ACCOUNT !** Most active user daily gets 30 days !

**Bas mujhe tag karo ya reply karo!** 🚀
"""
    
    keyboard = [
        [InlineKeyboardButton("📚 Study", callback_data="study_help"),
         InlineKeyboardButton("🎨 Creative", callback_data="creative")],
        [InlineKeyboardButton("📝 Notes", callback_data="notes_menu"),
         InlineKeyboardButton("🃏 Flashcards", callback_data="flashcards_menu")],
        [InlineKeyboardButton("⏰ Reminders", callback_data="reminders"),
         InlineKeyboardButton("📝 Feedback", callback_data="feedback_menu")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
         InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
         InlineKeyboardButton("📊 Stats", callback_data="stats")]
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
/quiz [topic] [q] - Interactive quiz

**🎨 CREATIVE COMMANDS**
/imagine [prompt] - AI image generation
/draw [prompt] - Enhanced prompt
/voice [text] - Text to speech
.gen [style] [prompt] - Quick generate
/analyze - Analyze replied image

**📝 NOTE COMMANDS**
/addnote [title] [content] - Add note
/mynotes - View all notes
/editnote [id] [content] - Edit note
/deletenote [id] - Delete note

**🃏 FLASHCARD COMMANDS**
/addcard [q] [a] - Add flashcard
/mycards - View flashcards
/study [category] - Study flashcards

**⏰ REMINDER COMMANDS**
/remind [time] [message] - Set reminder
/myreminders - View reminders
/cancel [id] - Cancel reminder
/clearreminders - Clear all

**📝 FEEDBACK & COMPLAINTS**
/feedback [message] - Give feedback
/complaint [message] - File complaint
/complaintstatus [id] - Check status

**🏆 REWARDS & PREMIUM**
/daily - Check daily usage
/leaderboard - Monthly leaderboard
/premium - Premium features info

**👑 OWNER COMMANDS**
/users - All users list
/broadcast [message] - Broadcast to all
/groupbroadcast [message] - Broadcast to groups
/addgroup - Add current group
/removegroup [id] - Remove group
/statsall - Overall bot stats
/feedbacklist - View all feedback
/complaintslist - View all complaints
/resolve [id] - Resolve complaint
/addpremium [id] [days] - Add premium
/block [user_id] - Block user
/unblock [user_id] - Unblock user

**⚙️ USER COMMANDS**
/settings - Customize bot
/stats - Your statistics
/help - This menu

**🎁 WIN FREE TG ACCOUNT!** Most active user daily wins 30 days !
"""
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= FEEDBACK & COMPLAINT HANDLERS =================
async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📝 **Send Feedback**\n\n"
            "**Usage:** `/feedback [message]`\n"
            "**Example:** `/feedback Bot is very helpful!`",
            parse_mode='Markdown'
        )
        return
    
    user = update.message.from_user
    feedback_text = " ".join(context.args)
    group_id = update.message.chat_id if update.message.chat.type in ['group', 'supergroup'] else None
    group_name = update.message.chat.title if group_id else None
    
    save_feedback(user.id, user.username, user.first_name, group_id, group_name, feedback_text, "feedback", 5)
    
    await update.message.reply_text(
        f"✅ **Thank you for your feedback!** 🙏\n\n"
        f"Your feedback has been recorded.\n\n"
        f"📝 **Your Feedback:** {feedback_text}",
        parse_mode='Markdown'
    )
    
    # Send to owner
    try:
        owner_text = f"""
📝 **NEW FEEDBACK**

👤 **User:** {user.first_name} (@{user.username})
🆔 **ID:** `{user.id}`
📍 **From:** {group_name if group_name else 'Private Chat'}
📝 **Feedback:** {feedback_text}
⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        await context.bot.send_message(chat_id=OWNER_ID, text=owner_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to send to owner: {e}")

async def complaint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ **File a Complaint**\n\n"
            "**Usage:** `/complaint [message]`\n"
            "**Example:** `/complaint Bot is not responding`",
            parse_mode='Markdown'
        )
        return
    
    user = update.message.from_user
    complaint_text = " ".join(context.args)
    group_id = update.message.chat_id if update.message.chat.type in ['group', 'supergroup'] else None
    group_name = update.message.chat.title if group_id else None
    
    complaint_id = save_complaint(user.id, user.username, user.first_name, group_id, group_name, complaint_text)
    
    if complaint_id:
        await update.message.reply_text(
            f"⚠️ **Complaint Registered**\n\n"
            f"🆔 **ID:** `{complaint_id}`\n"
            f"📝 **Issue:** {complaint_text}\n\n"
            f"✅ Complaint submitted. Owner will review it soon.\n"
            f"Use `/complaintstatus {complaint_id}` to check status.",
            parse_mode='Markdown'
        )
        
        # Send to owner
        try:
            owner_text = f"""
⚠️ **NEW COMPLAINT**

👤 **User:** {user.first_name} (@{user.username})
🆔 **ID:** `{user.id}`
📍 **From:** {group_name if group_name else 'Private Chat'}
🆔 **Complaint ID:** `{complaint_id}`
📝 **Complaint:** {complaint_text}
⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            await context.bot.send_message(chat_id=OWNER_ID, text=owner_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send to owner: {e}")
    else:
        await update.message.reply_text("❌ Failed to register complaint.")

async def complaint_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/complaintstatus [id]`", parse_mode='Markdown')
        return
    
    try:
        complaint_id = int(context.args[0])
        conn, cursor = ensure_connection()
        cursor.execute("SELECT complaint_text, status, created_at, resolved_at FROM complaints WHERE id = ?", (complaint_id,))
        result = cursor.fetchone()
        
        if result:
            text = f"""
⚠️ **Complaint Status**

🆔 **ID:** {complaint_id}
📝 **Issue:** {result[0]}
📊 **Status:** {result[1].upper()}
📅 **Filed:** {result[2]}
            """
            if result[3]:
                text += f"✅ **Resolved:** {result[3]}"
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Complaint not found!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

# ================= STUDY COMMANDS =================
async def notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/notes [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📝 Generating notes for **{topic}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Create detailed study notes for {topic} in Hinglish")
    await msg.edit_text(reply)

async def explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/explain [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Explaining **{topic}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Explain {topic} in simple Hinglish with examples")
    await msg.edit_text(reply)

async def mcq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/mcq [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📝 Generating MCQs for **{topic}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Create 10 multiple choice questions for {topic} in Hinglish with 4 options and answers")
    await msg.edit_text(reply)

async def pyq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/pyq [subject]`", parse_mode='Markdown')
        return
    subject = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 Finding PYQs for **{subject}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Generate important previous year exam questions for {subject} with answers in Hinglish")
    await msg.edit_text(reply)

async def doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/doubt [question]`", parse_mode='Markdown')
        return
    question = " ".join(context.args)
    msg = await update.message.reply_text(f"❓ Solving your doubt...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Solve this doubt step by step: {question}")
    await msg.edit_text(reply)

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ **Usage:** `/quiz [topic] [questions]`\nExample: `/quiz photosynthesis 5`", parse_mode='Markdown')
        return
    topic = context.args[0]
    try:
        num = min(int(context.args[1]), 20)
    except:
        num = 5
    msg = await update.message.reply_text(f"📝 Generating {num} MCQs...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Generate {num} multiple choice questions for {topic} in Hinglish with 4 options each")
    await msg.edit_text(reply)

# ================= CREATIVE COMMANDS =================
async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/imagine [prompt]`\nExample: `/imagine beautiful landscape`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🎨 Generating image...")
    filename = await generate_image(prompt)
    if filename:
        with open(filename, "rb") as f:
            await update.message.reply_photo(photo=f, caption=f"🖼️ **Generated:** {prompt}")
        os.remove(filename)
        await msg.delete()
    else:
        await msg.edit_text("❌ Failed to generate image.")

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/draw [prompt]`\nExample: `/draw dragon`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    enhanced = f"Ultra detailed {prompt}, cinematic lighting, 8k resolution, hyper realistic, sharp focus"
    await update.message.reply_text(f"✨ **Enhanced Prompt:**\n\n`{enhanced}`", parse_mode='Markdown')

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/generate [prompt]`\nExample: `/generate cyberpunk city`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🎨 Generating image...")
    filename = await generate_image(prompt)
    if filename:
        with open(filename, "rb") as f:
            await update.message.reply_photo(photo=f, caption=f"🖼️ {prompt}")
        os.remove(filename)
        await msg.delete()
    else:
        await msg.edit_text("❌ Generation failed.")

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

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Reply to an image with `/analyze` to analyze it!", parse_mode='Markdown')
        return
    
    msg = await update.message.reply_text("🔍 Analyzing image...")
    photo = await update.message.reply_to_message.photo[-1].get_file()
    path = f"temp_{uuid.uuid4().hex[:6]}.jpg"
    await photo.download_to_drive(path)
    reply = await analyze_image(path)
    await msg.edit_text(reply, parse_mode='Markdown')
    if os.path.exists(path):
        os.remove(path)

# ================= NOTE COMMANDS =================
async def add_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ **Usage:** `/addnote [title] [content]`\nExample: `/addnote Physics Newton's laws`", parse_mode='Markdown')
        return
    
    title = context.args[0]
    content = " ".join(context.args[1:])
    user_id = update.message.from_user.id
    
    note_id = add_note(user_id, title, content)
    if note_id:
        await update.message.reply_text(f"✅ **Note saved!**\n\n📝 **Title:** {title}\n🆔 **ID:** `{note_id}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed to save note.")

async def my_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    notes = get_notes(user_id)
    
    if not notes:
        await update.message.reply_text("📭 No notes found. Use `/addnote` to create notes!", parse_mode='Markdown')
        return
    
    text = "📝 **Your Notes:**\n\n"
    for note in notes[:10]:
        text += f"🆔 `{note[0]}` • **{note[1]}**\n"
        text += f"📂 {note[3]} | 📅 {note[4][:10]}\n"
        text += f"📄 {note[2][:100]}...\n\n"
    
    if len(notes) > 10:
        text += f"\n... and {len(notes) - 10} more notes"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def edit_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ **Usage:** `/editnote [note_id] [new_content]`", parse_mode='Markdown')
        return
    
    try:
        note_id = int(context.args[0])
        content = " ".join(context.args[1:])
        
        if update_note(note_id, content):
            await update.message.reply_text(f"✅ Note `{note_id}` updated!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Note not found!", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Invalid note ID!", parse_mode='Markdown')

async def delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/deletenote [note_id]`", parse_mode='Markdown')
        return
    
    try:
        note_id = int(context.args[0])
        if delete_note(note_id):
            await update.message.reply_text(f"✅ Note `{note_id}` deleted!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Note not found!", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Invalid note ID!", parse_mode='Markdown')

# ================= FLASHCARD COMMANDS =================
async def add_flashcard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ **Usage:** `/addcard [question] [answer]`\nExample: `/addcard What is photosynthesis? Process of making food`", parse_mode='Markdown')
        return
    
    question = context.args[0]
    answer = " ".join(context.args[1:])
    user_id = update.message.from_user.id
    
    card_id = add_flashcard(user_id, question, answer)
    if card_id:
        await update.message.reply_text(f"✅ **Flashcard added!**\n\n❓ {question}\n💡 {answer}\n\nUse `/study` to practice!", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed to add flashcard.")

async def my_flashcards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    cards = get_flashcards(user_id, limit=20)
    
    if not cards:
        await update.message.reply_text("📭 No flashcards found. Use `/addcard` to create cards!", parse_mode='Markdown')
        return
    
    text = "🃏 **Your Flashcards:**\n\n"
    for card in cards:
        text += f"🆔 `{card[0]}` • **{card[1][:50]}**\n"
        text += f"💡 {card[2][:50]}...\n"
        text += f"📂 {card[3]}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def study_flashcards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    category = " ".join(context.args) if context.args else None
    
    cards = get_flashcards(user_id, category, limit=10)
    
    if not cards:
        await update.message.reply_text("📭 No flashcards found. Use `/addcard` to create cards!", parse_mode='Markdown')
        return
    
    context.user_data['flashcards'] = cards
    context.user_data['current_card'] = 0
    
    card = cards[0]
    text = f"🃏 **Flashcard 1/{len(cards)}**\n\n❓ **Question:** {card[1]}\n\n📂 Category: {card[3]}"
    
    keyboard = [
        [InlineKeyboardButton("💡 Show Answer", callback_data=f"show_answer_{card[0]}")],
        [InlineKeyboardButton("✅ Got it", callback_data=f"card_correct_{card[0]}"),
         InlineKeyboardButton("🔄 Repeat", callback_data=f"card_wrong_{card[0]}")],
        [InlineKeyboardButton("➡️ Next", callback_data="next_card")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

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
    time_str = context.args[0].lower()
    message = " ".join(context.args[1:])
    reminder_time = parse_reminder_time(time_str)
    
    if not reminder_time:
        await update.message.reply_text("❌ Invalid time format! Use: 10m, 2h, 1d, or YYYY-MM-DD HH:MM")
        return
    
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reminder_time_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")
    
    conn, cursor = ensure_connection()
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
        f"🆔 **ID:** `{reminder_id}`",
        parse_mode='Markdown'
    )

async def myreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    conn, cursor = ensure_connection()
    cursor.execute("""
        SELECT id, reminder_text, reminder_time FROM reminders 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY reminder_time ASC
        """, (user.id,))
    reminders = cursor.fetchall()
    
    if not reminders:
        await update.message.reply_text("📭 No pending reminders.", parse_mode='Markdown')
        return
    
    text = "📋 **Your Reminders:**\n\n"
    for r in reminders:
        text += f"🆔 `{r[0]}` • **{r[1]}**\n   ⏰ {r[2]}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/cancel [reminder_id]`", parse_mode='Markdown')
        return
    
    user = update.message.from_user
    reminder_id = context.args[0]
    
    conn, cursor = ensure_connection()
    cursor.execute("""
        UPDATE reminders SET status = 'cancelled' 
        WHERE id = ? AND user_id = ? AND status = 'pending'
        """, (reminder_id, user.id))
    conn.commit()
    
    if cursor.rowcount > 0:
        await update.message.reply_text(f"✅ Reminder `{reminder_id}` cancelled!", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Reminder not found!")

async def clearreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    conn, cursor = ensure_connection()
    cursor.execute("""
        UPDATE reminders SET status = 'cancelled' 
        WHERE user_id = ? AND status = 'pending'
        """, (user.id,))
    conn.commit()
    await update.message.reply_text("✅ All reminders cleared!", parse_mode='Markdown')

# ================= USER COMMANDS =================
async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    stats = get_user_stats(user.id)
    is_premium = is_premium_user(user.id)
    
    if stats:
        chat_count, join_date, last_active, daily_usage = stats
        text = f"""
📊 **Your Statistics**

👤 **User:** {user.first_name} {user.last_name or ''}
🆔 **ID:** `{user.id}`
💬 **Total Chats:** {chat_count}
📊 **Today's Usage:** {daily_usage}
💎 **Premium:** {'✅ Active' if is_premium else '❌ Inactive'}
📅 **Joined:** {join_date}
⏰ **Last Active:** {last_active}
        """
    else:
        text = "No data yet. Start chatting!"
    await update.message.reply_text(text, parse_mode='Markdown')

async def daily_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    conn, cursor = ensure_connection()
    cursor.execute("SELECT daily_usage_count FROM users WHERE id = ?", (user.id,))
    result = cursor.fetchone()
    
    if result:
        usage = result[0]
        top = get_daily_top_users(5)
        text = f"📊 **Your Daily Usage:** {usage} messages\n\n🏆 **Today's Top Users:**\n"
        for i, (uid, un, name, count) in enumerate(top, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
            text += f"{medal} {name} - {count} msgs\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text("No usage data found.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monthly = get_monthly_top_users(10)
    text = "🏆 **Monthly Leaderboard** 🏆\n\n"
    for i, (uid, un, name, total) in enumerate(monthly, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name} - {total} msgs\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium = is_premium_user(user_id)
    
    conn, cursor = ensure_connection()
    cursor.execute("SELECT daily_usage_count FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    daily = result[0] if result else 0
    
    if is_premium:
        premium_until = get_premium_until(user_id)
        days_left = (premium_until - datetime.now()).days if premium_until else 0
        text = f"""
💎 **PREMIUM MEMBER** 💎

**Your Benefits:**
• 🚀 Priority response
• 🎨 Advanced AI models
• 📚 Unlimited notes storage
• 🃏 Unlimited flashcards
• 🖼️ HD image generation

**Premium Until:** {premium_until.strftime('%Y-%m-%d') if premium_until else 'N/A'}
**Days Left:** {days_left} days

Thank you for supporting the bot! 🙏
"""
    else:
        text = f"""
💎 **PREMIUM FEATURES** 💎

**Benefits:**
• 🚀 Priority response
• 🎨 Advanced AI models
• 📚 Unlimited notes storage
• 🃏 Unlimited flashcards
• 🖼️ HD image generation

**🎁 WIN TG ACCOUNT  FOR FREE!**
Use the bot daily to win!
• **Daily Winner:** Most active user gets 30 days !

**Your Today's Activity:** {daily} messages
**Goal:** Be #1 daily to win!
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefs = get_user_preferences(update.message.from_user.id)
    keyboard = [
        [InlineKeyboardButton("🌐 Language", callback_data="set_lang"),
         InlineKeyboardButton("📝 Style", callback_data="set_style")],
        [InlineKeyboardButton("🎨 Theme", callback_data="set_theme"),
         InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    text = f"""
⚙️ **Settings**

**Current Preferences:**
• Language: {prefs['language']}
• Response Style: {prefs['response_style']}
• Theme: {prefs['theme']}
    """
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ================= OWNER COMMANDS =================
async def users_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    users = total_users()
    text = f"📊 **Total Users:** {len(users)}\n\n"
    for u in users[:20]:
        premium = "💎" if u[7] else ""
        text += f"{premium} {u[1] or u[2] or 'Unknown'} (ID: `{u[0]}`)\n"
        text += f"  💬 Chats: {u[6]} | 📅 Joined: {u[4][:10]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

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
    status = await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=message, parse_mode='Markdown')
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await status.edit_text(f"✅ Broadcast sent to {sent} users!")

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
    status = await update.message.reply_text(f"📢 Broadcasting to {len(groups)} groups...")
    for gid, name in groups:
        try:
            await context.bot.send_message(chat_id=gid, text=message, parse_mode='Markdown')
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await status.edit_text(f"✅ Broadcast sent to {sent} groups!")

async def stats_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    users = total_users()
    groups = get_all_groups()
    conn, cursor = ensure_connection()
    cursor.execute("SELECT COUNT(*) FROM chat_history")
    chats = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM feedback")
    feedbacks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints")
    complaints = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM notes")
    notes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM flashcards")
    cards = cursor.fetchone()[0]
    
    text = f"""
📊 **BOT STATISTICS**

👥 **Total Users:** {len(users)}
💎 **Premium Users:** {premium}
👥 **Active Groups:** {len(groups)}
💬 **Total Chats:** {chats}
📝 **Total Feedback:** {feedbacks}
⚠️ **Total Complaints:** {complaints}
📚 **Total Notes:** {notes}
🃏 **Total Flashcards:** {cards}

**Status:** 🟢 Active
**System:** AI Model: Llama 3.3 70B
**Daily Winner:** ✅ Enabled
    """
    await update.message.reply_text(text, parse_mode='Markdown')

async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    add_group(update.message.chat_id, update.message.chat.title)
    await update.message.reply_text("✅ Group added to broadcast list!")

async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if not context.args:
        await update.message.reply_text("**Usage:** `/removegroup [group_id]`", parse_mode='Markdown')
        return
    conn, cursor = ensure_connection()
    cursor.execute("UPDATE groups SET is_active = 0 WHERE group_id = ?", (int(context.args[0]),))
    conn.commit()
    await update.message.reply_text("✅ Group removed from broadcast list!")

async def add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ **Usage:** `/addpremium [user_id] [days]`", parse_mode='Markdown')
        return
    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        if set_premium(user_id, days):
            await update.message.reply_text(f"✅ Premium added to user `{user_id}` for {days} days!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Failed to add premium.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def get_all_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    conn, cursor = ensure_connection()
    cursor.execute("SELECT id, username, user_name, feedback_text, rating, created_at FROM feedback ORDER BY created_at DESC LIMIT 30")
    fb = cursor.fetchall()
    if not fb:
        await update.message.reply_text("📭 No feedback yet!")
        return
    text = "📝 **Recent Feedback:**\n\n"
    for f in fb:
        text += f"🆔 `{f[0]}` | {f[2]} (@{f[1]}) | ⭐ {f[4]}\n📝 {f[3][:100]}\n📅 {f[5]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def get_all_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    conn, cursor = ensure_connection()
    cursor.execute("SELECT id, username, user_name, complaint_text, status, created_at FROM complaints ORDER BY created_at DESC LIMIT 30")
    comp = cursor.fetchall()
    if not comp:
        await update.message.reply_text("📭 No complaints yet!")
        return
    text = "⚠️ **Recent Complaints:**\n\n"
    for c in comp:
        text += f"🆔 `{c[0]}` | {c[2]} (@{c[1]}) | Status: {c[4].upper()}\n📝 {c[3][:100]}\n📅 {c[5]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def resolve_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ **Usage:** `/resolve [complaint_id]`", parse_mode='Markdown')
        return
    try:
        cid = int(context.args[0])
        resolved = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn, cursor = ensure_connection()
        cursor.execute("SELECT user_id, complaint_text FROM complaints WHERE id = ?", (cid,))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE complaints SET status = 'resolved', resolved_at = ? WHERE id = ?", (resolved, cid))
            conn.commit()
            try:
                await context.bot.send_message(chat_id=result[0], text=f"✅ Your complaint #{cid} has been resolved!")
            except:
                pass
            await update.message.reply_text(f"✅ Complaint `{cid}` resolved!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Complaint not found!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/block [user_id]`", parse_mode='Markdown')
        return
    try:
        uid = int(context.args[0])
        conn, cursor = ensure_connection()
        cursor.execute("UPDATE users SET is_blocked = 1 WHERE id = ?", (uid,))
        conn.commit()
        await update.message.reply_text(f"✅ User `{uid}` blocked!", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Error!")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/unblock [user_id]`", parse_mode='Markdown')
        return
    try:
        uid = int(context.args[0])
        conn, cursor = ensure_connection()
        cursor.execute("UPDATE users SET is_blocked = 0 WHERE id = ?", (uid,))
        conn.commit()
        await update.message.reply_text(f"✅ User `{uid}` unblocked!", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Error!")

# ================= MAIN MESSAGE HANDLER =================
async def handle_gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.reply_text(
            "✨ **Quick Image Generator**\n\n"
            "**Usage:**\n"
            "• `.gen dragon` - Normal image\n"
            "• `.gen anime girl` - Anime style\n"
            "• `.gen 3d car` - 3D style\n"
            "• `.gen logo gaming` - Logo design\n"
            "• `.gen cartoon cat` - Cartoon style",
            parse_mode='Markdown'
        )
        return
    
    style = "normal"
    prompt_start = 1
    if len(parts) > 1 and parts[1].lower() in ["anime", "3d", "logo", "cartoon", "realistic", "fantasy", "cyberpunk"]:
        style = parts[1].lower()
        prompt_start = 2
    
    prompt = " ".join(parts[prompt_start:]) if prompt_start < len(parts) else "beautiful landscape"
    msg = await message.reply_text(f"🎨 Generating {style} image...")
    filename = await generate_image(prompt, style)
    if filename:
        with open(filename, "rb") as f:
            await message.reply_photo(photo=f, caption=f"🎨 **{style.upper()}** | {prompt[:100]}")
        os.remove(filename)
        await msg.delete()
    else:
        await msg.edit_text("❌ Failed to generate image.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or update.message.from_user.is_bot:
        return
    
    # Check if blocked
    conn, cursor = ensure_connection()
    cursor.execute("SELECT is_blocked FROM users WHERE id = ?", (update.message.from_user.id,))
    result = cursor.fetchone()
    if result and result[0] == 1:
        return
    
    # Handle .gen command
    if update.message.text and update.message.text.startswith(".gen"):
        await handle_gen_command(update, context)
        return
    
    # Check if bot should respond
    def should_respond(msg):
        if msg.chat.type == "private":
            return True
        if msg.text and BOT_USERNAME.lower() in msg.text.lower():
            return True
        if msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.username == BOT_USERNAME.replace("@", ""):
            return True
        return False
    
    if not should_respond(update.message):
        return
    
    user_id = update.message.from_user.id
    group_id = update.message.chat_id if update.message.chat.type in ['group', 'supergroup'] else None
    group_name = update.message.chat.title if group_id else None
    
    update_user_activity(user_id, update.message.chat.type, group_id, group_name)
    
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    
    if update.message.text:
        text = update.message.text.replace(BOT_USERNAME, "").strip()
        if not text:
            text = "Hello"
        reply = await ask_ai_hinglish(user_id, text)
        save_chat_history(user_id, text, reply)
        await update.message.reply_text(reply, parse_mode='Markdown')
        
    elif update.message.voice:
        file = await update.message.voice.get_file()
        path = f"voice_{uuid.uuid4().hex[:6]}.ogg"
        await file.download_to_drive(path)
        text = voice_to_text(path)
        await update.message.reply_text(f"📝 **You said:** {text}", parse_mode='Markdown')
        reply = await ask_ai_hinglish(user_id, text)
        await update.message.reply_text(reply, parse_mode='Markdown')
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists("voice.wav"):
            os.remove("voice.wav")
            
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
        path = f"img_{uuid.uuid4().hex[:6]}.jpg"
        await file.download_to_drive(path)
        reply = await analyze_image(path)
        await update.message.reply_text(reply, parse_mode='Markdown')
        if os.path.exists(path):
            os.remove(path)

# ================= BUTTON CALLBACK =================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()
    
    if data == "study_help":
        text = "📚 **Study Commands**\n\n/notes [topic]\n/explain [topic]\n/mcq [topic]\n/pyq [subject]\n/doubt [q]\n/quiz [topic] [q]"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "creative":
        text = "🎨 **Creative Commands**\n\n/imagine [prompt]\n/draw [prompt]\n/voice [text]\n.gen [style] [prompt]\n/analyze"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "notes_menu":
        text = "📝 **Note Commands**\n\n/addnote [title] [content]\n/mynotes\n/editnote [id] [content]\n/deletenote [id]"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "flashcards_menu":
        text = "🃏 **Flashcard Commands**\n\n/addcard [q] [a]\n/mycards\n/study [category]"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "reminders":
        text = "⏰ **Reminder Commands**\n\n/remind [time] [msg]\n/myreminders\n/cancel [id]\n/clearreminders"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "feedback_menu":
        text = "📝 **Feedback & Complaints**\n\n/feedback [msg]\n/complaint [msg]\n/complaintstatus [id]"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "leaderboard":
        monthly = get_monthly_top_users(10)
        text = "🏆 **Monthly Leaderboard** 🏆\n\n"
        for i, (uid, un, name, total) in enumerate(monthly, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {name} - {total} msgs\n"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "premium_info":
        is_premium = is_premium_user(user_id)
        if is_premium:
            text = "💎 You are a Premium Member! 🎉"
        else:
            text = "💎 Use /daily to track usage!\nTop daily user wins FREE TG ACCOUNT !"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "stats":
        stats = get_user_stats(user_id)
        if stats:
            text = f"📊 **Your Stats**\n\n💬 Total: {stats[0]}\n📊 Today: {stats[3]}\n📅 Joined: {stats[1]}"
        else:
            text = "No stats found"
        await query.edit_message_text(text, parse_mode='Markdown')
        
    elif data == "settings":
        prefs = get_user_preferences(user_id)
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_lang"),
             InlineKeyboardButton("📝 Style", callback_data="set_style")],
            [InlineKeyboardButton("🎨 Theme", callback_data="set_theme"),
             InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ]
        text = f"⚙️ **Settings**\n\nLanguage: {prefs['language']}\nStyle: {prefs['response_style']}\nTheme: {prefs['theme']}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "set_lang":
        keyboard = [
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
             InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi")],
            [InlineKeyboardButton("🇪🇸 Spanish", callback_data="lang_es"),
             InlineKeyboardButton("🇫🇷 French", callback_data="lang_fr")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ]
        await query.edit_message_text("🌐 **Select Language**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data.startswith("lang_"):
        lang = data.replace("lang_", "")
        set_user_preference(user_id, "language", lang)
        await query.edit_message_text(f"✅ Language set to {lang}")
        
    elif data == "set_style":
        keyboard = [
            [InlineKeyboardButton("📌 Concise", callback_data="style_concise"),
             InlineKeyboardButton("⚖️ Balanced", callback_data="style_balanced")],
            [InlineKeyboardButton("📚 Detailed", callback_data="style_detailed"),
             InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ]
        await query.edit_message_text("📝 **Response Style**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
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
        await query.edit_message_text("🎨 **Select Theme**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
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
            [InlineKeyboardButton("📝 Notes", callback_data="notes_menu"),
             InlineKeyboardButton("🃏 Flashcards", callback_data="flashcards_menu")],
            [InlineKeyboardButton("⏰ Reminders", callback_data="reminders"),
             InlineKeyboardButton("📝 Feedback", callback_data="feedback_menu")],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
             InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")]
        ]
        await query.edit_message_text("🌟 **Welcome back!** Choose an option:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data.startswith("show_answer_"):
        card_id = int(data.split("_")[2])
        conn, cursor = ensure_connection()
        cursor.execute("SELECT question, answer FROM flashcards WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        if result:
            text = f"❓ **Question:** {result[0]}\n\n💡 **Answer:** {result[1]}"
            await query.edit_message_text(text, parse_mode='Markdown')
            
    elif data.startswith("card_correct_"):
        card_id = int(data.split("_")[2])
        update_flashcard_review(card_id)
        
        flashcards = context.user_data.get('flashcards', [])
        current = context.user_data.get('current_card', 0)
        
        if current + 1 < len(flashcards):
            context.user_data['current_card'] = current + 1
            card = flashcards[current + 1]
            text = f"🃏 **Flashcard {current+2}/{len(flashcards)}**\n\n❓ **Question:** {card[1]}"
            keyboard = [
                [InlineKeyboardButton("💡 Show Answer", callback_data=f"show_answer_{card[0]}")],
                [InlineKeyboardButton("✅ Got it", callback_data=f"card_correct_{card[0]}"),
                 InlineKeyboardButton("🔄 Repeat", callback_data=f"card_wrong_{card[0]}")],
                [InlineKeyboardButton("➡️ Next", callback_data="next_card")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await query.edit_message_text("🎉 **Congratulations!** You've completed all flashcards!", parse_mode='Markdown')
            
    elif data == "next_card":
        flashcards = context.user_data.get('flashcards', [])
        current = context.user_data.get('current_card', 0)
        
        if current + 1 < len(flashcards):
            context.user_data['current_card'] = current + 1
            card = flashcards[current + 1]
            text = f"🃏 **Flashcard {current+2}/{len(flashcards)}**\n\n❓ **Question:** {card[1]}"
            keyboard = [
                [InlineKeyboardButton("💡 Show Answer", callback_data=f"show_answer_{card[0]}")],
                [InlineKeyboardButton("✅ Got it", callback_data=f"card_correct_{card[0]}"),
                 InlineKeyboardButton("🔄 Repeat", callback_data=f"card_wrong_{card[0]}")],
                [InlineKeyboardButton("➡️ Next", callback_data="next_card")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await query.edit_message_text("🎉 You've completed all flashcards!", parse_mode='Markdown')

# ================= CHECK REMINDERS =================
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        while not reminder_queue.empty():
            reminder = reminder_queue.get_nowait()
            rid, uid, msg, rt = reminder
            try:
                await context.bot.send_message(chat_id=uid, text=f"⏰ **REMINDER!** ⏰\n\n{msg}", parse_mode='Markdown')
            except:
                pass
    except:
        pass

async def check_winner_auto(context: ContextTypes.DEFAULT_TYPE):
    winner = check_and_declare_winner()
    if winner:
        uid, un, name, count = winner
        set_premium(uid, 30)
        try:
            await context.bot.send_message(chat_id=uid, text=f"🎉 **CONGRATULATIONS!** 🎉\n\n🏆 You are the Daily Winner!\n🎁 Prize: 30 Days !\n\n📊 Your Activity: {count} messages today!", parse_mode='Markdown')
            await context.bot.send_message(chat_id=OWNER_ID, text=f"🏆 **Daily Winner**\n\n👤 {name} (@{un})\n📊 {count} messages\n🎁 Premium awarded!", parse_mode='Markdown')
        except:
            pass

# ================= POST INIT =================
async def post_init(application):
    logger.info(f"🚀 Ultimate Study Controller Bot Started!")
    logger.info(f"Bot Username: @{application.bot.username}")
    logger.info(f"Owner ID: {OWNER_ID}")
    logger.info("All features loaded successfully!")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", user_stats))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("daily", daily_usage))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("premium", premium_info))
    
    # Feedback commands
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("complaint", complaint_command))
    app.add_handler(CommandHandler("complaintstatus", complaint_status))
    
    # Study commands
    app.add_handler(CommandHandler("notes", notes))
    app.add_handler(CommandHandler("explain", explain))
    app.add_handler(CommandHandler("mcq", mcq))
    app.add_handler(CommandHandler("pyq", pyq))
    app.add_handler(CommandHandler("doubt", doubt))
    app.add_handler(CommandHandler("quiz", quiz_command))
    
    # Note commands
    app.add_handler(CommandHandler("addnote", add_note_command))
    app.add_handler(CommandHandler("mynotes", my_notes))
    app.add_handler(CommandHandler("editnote", edit_note))
    app.add_handler(CommandHandler("deletenote", delete_note))
    
    # Flashcard commands
    app.add_handler(CommandHandler("addcard", add_flashcard_command))
    app.add_handler(CommandHandler("mycards", my_flashcards))
    app.add_handler(CommandHandler("study", study_flashcards))
    
    # Creative commands
    app.add_handler(CommandHandler("imagine", imagine))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("enhance", enhance))
    app.add_handler(CommandHandler("analyze", analyze_command))
    
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
    app.add_handler(CommandHandler("addpremium", add_premium))
    app.add_handler(CommandHandler("feedbacklist", get_all_feedback))
    app.add_handler(CommandHandler("complaintslist", get_all_complaints))
    app.add_handler(CommandHandler("resolve", resolve_complaint))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("unblock", unblock_user))
    
    # Callback handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Main message handler
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, handle_message))
    
    # Job queue for reminders and winner check
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_reminders, interval=30, first=10)
        from datetime import time
        job_queue.run_daily(check_winner_auto, time=time(hour=0, minute=0))
    
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
