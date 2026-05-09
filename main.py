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
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
import speech_recognition as sr
from pydub import AudioSegment
import requests
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import pytesseract

# PDF Generation Imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
import tempfile

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= CONFIG =================
BOT_TOKEN = "8619731533:AAGOPaGc_CcQaW5_B-HGUCeY3MetJFzoD0U"

# API KEYS
NOVA_API_KEY = "164deceb-f11e-4a18-9d20-fec20cf954fa"
LUXAND_API_KEY = "0dd78b150b154ab28cad26ee9b999bd9"

BOT_USERNAME = "@STUDYCONTROLLERV2_bot"
OWNER_ID = 6305002830
OWNER_NAME = "꧁⁣༒𓆩A𝔰𝔥𝔦𝔰𝔥𓆪༒꧂"

# ================= NOVA AI FUNCTIONS =================
class NovaAI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.nova.ai/v1/chat/completions"
    
    async def generate_response(self, messages):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {"model": "nova-2", "messages": messages, "temperature": 0.7, "max_tokens": 1000}
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                return await self.get_fallback_response(messages)
        except Exception as e:
            logger.error(f"Nova API Exception: {e}")
            return await self.get_fallback_response(messages)
    
    async def get_fallback_response(self, messages):
        user_message = messages[-1].get("content", "") if messages else ""
        if any(word in user_message.lower() for word in ['hello', 'hi', 'hey']):
            return "Namaste! 🙏 Main aapka AI assistant hoon. Kaise help kar sakta hoon?"
        elif "notes" in user_message.lower():
            return "📚 Main aapke liye detailed notes bana sakta hoon. /notes [topic] use karein!"
        elif "pdf" in user_message.lower():
            return "📄 PDF ke liye /pdf, /pdfnotes, /pdfdiagram commands use karein!"
        elif "game" in user_message.lower():
            return "🎮 Games ke liye: /game, /quizgame, /hangman, /tictactoe, /trivia, /dice"
        else:
            return "Main aapki madad ke liye hoon! /help se saari commands dekhein."

# ================= LUXAND API FUNCTIONS =================
class LuxandAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.face_api_url = "https://api.luxand.cloud/photo/detect"
        self.emotion_api_url = "https://api.luxand.cloud/photo/emotions"
        self.age_api_url = "https://api.luxand.cloud/photo/age"
    
    async def detect_faces(self, image_path):
        try:
            with open(image_path, 'rb') as img_file:
                files = {'photo': img_file}
                headers = {'token': self.api_key}
                response = requests.post(self.face_api_url, files=files, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Luxand detection error: {e}")
            return None
    
    async def analyze_emotions(self, image_path):
        try:
            with open(image_path, 'rb') as img_file:
                files = {'photo': img_file}
                headers = {'token': self.api_key}
                response = requests.post(self.emotion_api_url, files=files, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Emotion analysis error: {e}")
            return None
    
    async def estimate_age(self, image_path):
        try:
            with open(image_path, 'rb') as img_file:
                files = {'photo': img_file}
                headers = {'token': self.api_key}
                response = requests.post(self.age_api_url, files=files, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Age estimation error: {e}")
            return None

nova_ai = NovaAI(NOVA_API_KEY)
luxand_api = LuxandAPI(LUXAND_API_KEY)

# ================= DATABASE =================
thread_local = threading.local()

def get_db():
    if not hasattr(thread_local, "conn"):
        thread_local.conn = sqlite3.connect("users.db", check_same_thread=False)
        thread_local.cursor = thread_local.conn.cursor()
    return thread_local.conn, thread_local.cursor

conn, cursor = get_db()

# Create all tables
cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
    join_date TEXT, last_active TEXT, chat_count INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0,
    daily_usage_count INTEGER DEFAULT 0, last_daily_reset TEXT, points INTEGER DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS chat_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT, response TEXT, timestamp TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS user_preferences(
    user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'en', response_style TEXT DEFAULT 'balanced', theme TEXT DEFAULT 'default'
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS reminders(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, reminder_text TEXT, reminder_time TEXT, created_at TEXT, status TEXT DEFAULT 'pending'
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS groups(
    group_id INTEGER PRIMARY KEY, group_name TEXT, added_date TEXT, is_active INTEGER DEFAULT 1
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS feedback(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, user_name TEXT,
    group_id INTEGER, group_name TEXT, feedback_text TEXT, rating INTEGER DEFAULT 5, created_at TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS complaints(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, user_name TEXT,
    group_id INTEGER, group_name TEXT, complaint_text TEXT, status TEXT DEFAULT 'pending',
    created_at TEXT, resolved_at TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS daily_usage(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, usage_date TEXT, chat_count INTEGER DEFAULT 0, last_activity TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS flashcards(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, question TEXT, answer TEXT,
    category TEXT, created_at TEXT, review_count INTEGER DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, content TEXT,
    category TEXT, created_at TEXT, updated_at TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS user_scores(
    user_id INTEGER PRIMARY KEY, total_points INTEGER DEFAULT 0, games_won INTEGER DEFAULT 0,
    quizzes_passed INTEGER DEFAULT 0, daily_streak INTEGER DEFAULT 0, last_daily_claim TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS game_stats(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, game_name TEXT, score INTEGER, played_at TEXT
)""")

conn.commit()

# ================= FONT REGISTRATION =================
def register_fonts():
    fonts_registered = []
    font_paths = [('DejaVuSans', 'DejaVuSans.ttf'), ('Arial', 'arial.ttf'), ('FreeSans', 'FreeSans.ttf')]
    for font_name, font_file in font_paths:
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_file))
            fonts_registered.append(font_name)
        except:
            continue
    return fonts_registered[0] if fonts_registered else 'Helvetica'

MAIN_FONT = register_fonts()

# ================= AI ENGINE =================
user_memory = {}

async def ask_ai_hinglish(user_id, text):
    if user_id not in user_memory:
        user_memory[user_id] = []
    
    prefs = get_user_preferences(user_id)
    language = prefs['language']
    style = prefs['response_style']
    
    user_memory[user_id].append({"role": "user", "content": text})
    user_memory[user_id] = user_memory[user_id][-20:]
    
    if any(word in text.lower() for word in ['owner', 'malik', 'banane wala', 'creator']):
        return f"👑 My owner is {OWNER_NAME}! Unhone mujhe banaya hai. 🙏"
    
    system_prompt = f"""Tum ek smart Telegram AI bot ho. Tumhare owner {OWNER_NAME} hain.
    Language: {language}, Style: {style}. Be friendly and helpful. Format responses with **bold** for headings, • for bullets."""
    
    messages = [{"role": "system", "content": system_prompt}] + user_memory[user_id]
    reply = await nova_ai.generate_response(messages)
    
    if reply:
        user_memory[user_id].append({"role": "assistant", "content": reply})
        return reply
    return "❌ Technical problem! Try again."

# ================= DATABASE FUNCTIONS =================
def ensure_connection():
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
        cursor.execute("""INSERT OR IGNORE INTO users (id, username, first_name, last_name, join_date, last_active, chat_count, last_daily_reset) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (user_id, username, first_name, last_name, current_time, current_time, 0, current_time))
        cursor.execute("INSERT OR IGNORE INTO user_scores (user_id, total_points, games_won, quizzes_passed, daily_streak) VALUES (?, 0, 0, 0, 0)", (user_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding user: {e}")

def update_user_activity(user_id, chat_type="private", group_id=None, group_name=None):
    conn, cursor = ensure_connection()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("UPDATE users SET last_active = ?, chat_count = chat_count + 1 WHERE id = ?", (current_time, user_id))
        conn.commit()
        
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""INSERT INTO daily_usage (user_id, usage_date, chat_count, last_activity)
            VALUES (?, ?, 1, ?) ON CONFLICT(user_id, usage_date) DO UPDATE SET chat_count = chat_count + 1, last_activity = ?""",
            (user_id, today, current_time, current_time))
        conn.commit()
        
        cursor.execute("SELECT last_daily_reset FROM users WHERE id = ?", (user_id,))
        last_reset = cursor.fetchone()
        if last_reset and last_reset[0] and datetime.strptime(last_reset[0], "%Y-%m-%d %H:%M:%S").date() != datetime.now().date():
            cursor.execute("UPDATE users SET daily_usage_count = 0, last_daily_reset = ? WHERE id = ?", (current_time, user_id))
            conn.commit()
        
        cursor.execute("UPDATE users SET daily_usage_count = daily_usage_count + 1 WHERE id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating activity: {e}")

def save_chat_history(user_id, message, response):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("INSERT INTO chat_history (user_id, message, response, timestamp) VALUES (?, ?, ?, ?)",
                      (user_id, message, response, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving chat: {e}")

def get_user_preferences(user_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT language, response_style, theme FROM user_preferences WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return {"language": result[0], "response_style": result[1], "theme": result[2]}
    except:
        pass
    return {"language": "en", "response_style": "balanced", "theme": "default"}

def set_user_preference(user_id, pref_type, value):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("INSERT OR IGNORE INTO user_preferences (user_id, language, response_style, theme) VALUES (?, 'en', 'balanced', 'default')", (user_id,))
        cursor.execute(f"UPDATE user_preferences SET {pref_type} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting preference: {e}")
        return False

def save_feedback(user_id, username, user_name, group_id, group_name, feedback_text):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("""INSERT INTO feedback (user_id, username, user_name, group_id, group_name, feedback_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (user_id, username, user_name, group_id, group_name, feedback_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return False

def save_complaint(user_id, username, user_name, group_id, group_name, complaint_text):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("""INSERT INTO complaints (user_id, username, user_name, group_id, group_name, complaint_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (user_id, username, user_name, group_id, group_name, complaint_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving complaint: {e}")
        return None

def get_daily_top_users(limit=10):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT user_id, username, first_name, daily_usage_count FROM users WHERE daily_usage_count > 0 ORDER BY daily_usage_count DESC LIMIT ?", (limit,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting top users: {e}")
        return []

def total_users():
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT id, username, first_name, join_date, chat_count FROM users WHERE is_blocked = 0")
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

def clear_user_history(user_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False

def add_group(group_id, group_name):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("INSERT OR IGNORE INTO groups (group_id, group_name, added_date, is_active) VALUES (?, ?, ?, 1)",
                      (group_id, group_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding group: {e}")

def get_all_groups():
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT group_id, group_name FROM groups WHERE is_active = 1")
        return cursor.fetchall()
    except:
        return []

def add_flashcard(user_id, question, answer):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("INSERT INTO flashcards (user_id, question, answer, category, created_at) VALUES (?, ?, ?, 'General', ?)",
                      (user_id, question, answer, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return cursor.lastrowid
    except:
        return None

def get_flashcards(user_id, limit=10):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT id, question, answer FROM flashcards WHERE user_id = ? ORDER BY review_count ASC LIMIT ?", (user_id, limit))
        return cursor.fetchall()
    except:
        return []

def update_flashcard_review(card_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("UPDATE flashcards SET review_count = review_count + 1 WHERE id = ?", (card_id,))
        conn.commit()
    except:
        pass

def add_note(user_id, title, content):
    conn, cursor = ensure_connection()
    try:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO notes (user_id, title, content, category, created_at, updated_at) VALUES (?, ?, ?, 'General', ?, ?)",
                      (user_id, title, content, created_at, created_at))
        conn.commit()
        return cursor.lastrowid
    except:
        return None

def get_notes(user_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT id, title, content, created_at FROM notes WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
        return cursor.fetchall()
    except:
        return []

def update_note(note_id, content):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("UPDATE notes SET content = ?, updated_at = ? WHERE id = ?",
                      (content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), note_id))
        conn.commit()
        return True
    except:
        return False

def delete_note(note_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return True
    except:
        return False

def add_points(user_id, points):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("UPDATE user_scores SET total_points = total_points + ? WHERE user_id = ?", (points, user_id))
        conn.commit()
        return True
    except:
        return False

def get_user_points(user_id):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("SELECT total_points, games_won, quizzes_passed, daily_streak FROM user_scores WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    except:
        return (0, 0, 0, 0)

def update_game_stats(user_id, game_name, score):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("INSERT INTO game_stats (user_id, game_name, score, played_at) VALUES (?, ?, ?, ?)",
                      (user_id, game_name, score, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        if game_name in ['Quiz', 'Trivia'] and score > 0:
            cursor.execute("UPDATE user_scores SET quizzes_passed = quizzes_passed + 1 WHERE user_id = ?", (user_id,))
        if score > 0:
            cursor.execute("UPDATE user_scores SET games_won = games_won + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    except:
        pass

# ================= PDF STYLES =================
def get_pdf_styles():
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontName=MAIN_FONT, fontSize=28,
        textColor=colors.HexColor('#1E3C72'), alignment=TA_CENTER, spaceAfter=30, leading=32, spaceBefore=20)
    heading1_style = ParagraphStyle('CustomHeading1', parent=styles['Heading1'], fontName=MAIN_FONT, fontSize=20,
        textColor=colors.HexColor('#2A5298'), alignment=TA_LEFT, spaceAfter=12, spaceBefore=18, leading=24)
    heading2_style = ParagraphStyle('CustomHeading2', parent=styles['Heading2'], fontName=MAIN_FONT, fontSize=16,
        textColor=colors.HexColor('#4A90E2'), alignment=TA_LEFT, spaceAfter=10, spaceBefore=12, leading=20)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontName=MAIN_FONT, fontSize=11,
        alignment=TA_JUSTIFY, spaceAfter=6, leading=16, textColor=colors.HexColor('#2C3E50'))
    bullet_style = ParagraphStyle('BulletStyle', parent=styles['Normal'], fontName=MAIN_FONT, fontSize=11,
        leftIndent=25, alignment=TA_LEFT, spaceAfter=4, leading=16, bulletText='•')
    
    return {'title': title_style, 'heading1': heading1_style, 'heading2': heading2_style, 'normal': normal_style, 'bullet': bullet_style}

def clean_text_for_pdf(text):
    replacements = {'∈': 'element of', '∑': 'sum', '∫': 'integral', '√': 'square root', 'π': 'pi',
        '→': '->', '•': '•', '–': '-', '&': '&amp;', '<': '&lt;', '>': '&gt;'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def parse_content_to_elements(content, styles):
    story = []
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith('##') or (line.startswith('**') and line.endswith('**')):
            heading = line.strip('#').strip('*').strip()
            story.append(Paragraph(clean_text_for_pdf(heading), styles['heading1']))
        elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
            bullet_text = line.lstrip('•-* ').strip()
            story.append(Paragraph(f'• {clean_text_for_pdf(bullet_text)}', styles['bullet']))
        else:
            story.append(Paragraph(clean_text_for_pdf(line), styles['normal']))
        story.append(Spacer(1, 2))
    return story

def generate_complete_pdf(title, content, include_diagram=False, diagram_type=None, diagram_data=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = get_pdf_styles()
    story = []
    story.append(Spacer(1, 10))
    story.append(Paragraph(clean_text_for_pdf(title), styles['title']))
    story.append(Spacer(1, 20))
    content_elements = parse_content_to_elements(content, styles)
    story.extend(content_elements)
    
    if include_diagram and diagram_data:
        story.append(PageBreak())
        story.append(Paragraph("📊 Visual Diagram", styles['heading1']))
        story.append(Spacer(1, 10))
        # Create simple diagram representation
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        ax.text(0.5, 0.9, title, fontsize=14, ha='center', weight='bold')
        y_pos = 0.8
        for i, item in enumerate(diagram_data[:8]):
            ax.text(0.5, y_pos - i*0.08, f"{i+1}. {item}", fontsize=10, ha='center')
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
        plt.close()
        img_buffer.seek(0)
        img = RLImage(img_buffer, width=6*inch, height=4*inch)
        story.append(KeepTogether([img, Spacer(1, 10)]))
    
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont(MAIN_FONT, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(doc.width / 2 + doc.leftMargin, doc.bottomMargin - 20, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()

# ================= IMAGE GENERATION =================
async def generate_image(prompt):
    try:
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '+')}"
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
            return r.recognize_google(audio_data)
        except:
            try:
                return r.recognize_google(audio_data, language="hi-IN")
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
            result = f"🖼️ **Image Analysis**\n\n📐 Size: {width}x{height}"
            try:
                text = pytesseract.image_to_string(Image.open(path))
                if text.strip():
                    result += f"\n\n📝 **Text Found:**\n{text[:500]}"
            except:
                pass
            try:
                faces = await luxand_api.detect_faces(path)
                if faces and len(faces) > 0:
                    result += f"\n\n👤 **Faces Detected:** {len(faces)}"
            except:
                pass
            return result
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ================= GAMES SECTION =================

# Game states
active_games: Dict[int, Dict] = {}

# Hangman words and stages
hangman_words = ["PYTHON", "PROGRAMMING", "COMPUTER", "TELEGRAM", "BOT", "DEVELOPER",
    "ARTIFICIAL", "INTELLIGENCE", "MACHINE", "LEARNING", "DATABASE", "ALGORITHM", "CODING", "SOFTWARE"]

hangman_stages = [
    "       --------\n       |      |\n       |      \n       |    \n       |      \n       |     \n       -",
    "       --------\n       |      |\n       |      O\n       |    \n       |      \n       |     \n       -",
    "       --------\n       |      |\n       |      O\n       |      |\n       |      \n       |     \n       -",
    "       --------\n       |      |\n       |      O\n       |     /|\n       |      \n       |     \n       -",
    "       --------\n       |      |\n       |      O\n       |     /|\\\n       |      \n       |     \n       -",
    "       --------\n       |      |\n       |      O\n       |     /|\\\n       |     /\n       |     \n       -",
    "       --------\n       |      |\n       |      O\n       |     /|\\\n       |     / \\\n       |     \n       -"
]

# Quiz questions
quiz_questions = {
    'general': [
        {'q': "What is the capital of France?", 'a': "Paris", 'options': ["London", "Berlin", "Paris", "Madrid"]},
        {'q': "Which planet is known as the Red Planet?", 'a': "Mars", 'options': ["Venus", "Mars", "Jupiter", "Saturn"]},
        {'q': "Who wrote 'Romeo and Juliet'?", 'a': "William Shakespeare", 'options': ["Charles Dickens", "Jane Austen", "William Shakespeare", "Mark Twain"]},
        {'q': "What is the largest ocean on Earth?", 'a': "Pacific Ocean", 'options': ["Atlantic Ocean", "Indian Ocean", "Arctic Ocean", "Pacific Ocean"]},
        {'q': "Which is the longest river in the world?", 'a': "Nile", 'options': ["Amazon", "Nile", "Yangtze", "Mississippi"]},
    ],
    'science': [
        {'q': "What is H2O commonly known as?", 'a': "Water", 'options': ["Oxygen", "Hydrogen", "Water", "Salt"]},
        {'q': "What is the hardest natural substance?", 'a': "Diamond", 'options': ["Gold", "Iron", "Diamond", "Platinum"]},
        {'q': "Which organ pumps blood in the human body?", 'a': "Heart", 'options': ["Brain", "Liver", "Heart", "Kidney"]},
    ],
    'math': [
        {'q': "What is 15 × 8?", 'a': "120", 'options': ["100", "110", "120", "130"]},
        {'q': "What is the square root of 144?", 'a': "12", 'options': ["10", "11", "12", "13"]},
        {'q': "What is 25% of 200?", 'a': "50", 'options': ["25", "50", "75", "100"]},
    ]
}

# Trivia questions
trivia_questions = [
    {"question": "What is the fastest animal on land?", "answer": "Cheetah", "options": ["Lion", "Cheetah", "Leopard", "Tiger"]},
    {"question": "Which country gifted the Statue of Liberty to the USA?", "answer": "France", "options": ["England", "Spain", "France", "Germany"]},
    {"question": "Who painted the Mona Lisa?", "answer": "Leonardo da Vinci", "options": ["Van Gogh", "Picasso", "Leonardo da Vinci", "Rembrandt"]},
    {"question": "What is the smallest country in the world?", "answer": "Vatican City", "options": ["Monaco", "San Marino", "Vatican City", "Malta"]},
    {"question": "Which year did World War II end?", "answer": "1945", "options": ["1944", "1945", "1946", "1943"]},
]

# Fun facts
fun_facts = [
    "🐘 Elephants are the only mammals that can't jump!",
    "🍌 Bananas are berries, but strawberries aren't!",
    "🦒 A giraffe's tongue is 21 inches long!",
    "🐙 Octopuses have three hearts!",
    "🐧 Penguins can drink salt water!",
    "🐌 Snails can sleep for 3 years!",
    "🦩 Flamingos are born gray!",
]

# Jokes
jokes = [
    "Why don't scientists trust atoms?\nBecause they make up everything! 🤓",
    "What do you call a fake noodle?\nAn impasta! 🍝",
    "Why did the scarecrow win an award?\nHe was outstanding in his field! 🌾",
    "What do you call a bear with no teeth?\nA gummy bear! 🐻",
]

# Quotes
quotes = [
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Success is not final, failure is not fatal: it is the courage to continue that counts.", "Winston Churchill"),
    ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
]

# ================= GAME HANDLERS =================

async def guess_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    secret = random.randint(1, 100)
    active_games[user_id] = {'type': 'guess', 'secret': secret, 'attempts': 0, 'max_attempts': 7}
    await update.message.reply_text(
        f"🎮 **Number Guessing Game!**\n\nI've selected a number between 1 and 100.\nYou have 7 attempts.\n\nType `/guess [number]` to play!",
        parse_mode='Markdown')

async def guess_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in active_games or active_games[user_id].get('type') != 'guess':
        await update.message.reply_text("❌ No active game! Start with `/game`", parse_mode='Markdown')
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/guess [number]`", parse_mode='Markdown')
        return
    try:
        guess = int(context.args[0])
    except:
        await update.message.reply_text("❌ Please enter a valid number!", parse_mode='Markdown')
        return
    
    game = active_games[user_id]
    game['attempts'] += 1
    
    if guess == game['secret']:
        points = 50 - (game['attempts'] * 2)
        points = max(points, 10)
        add_points(user_id, points)
        update_game_stats(user_id, "Number Guessing", points)
        await update.message.reply_text(f"🎉 **CORRECT!** The number was {game['secret']}\nAttempts: {game['attempts']}\n💰 Points earned: {points}", parse_mode='Markdown')
        del active_games[user_id]
    elif guess < game['secret']:
        remaining = game['max_attempts'] - game['attempts']
        msg = f"📈 **Too Low!**\nAttempts left: {remaining}"
        if game['attempts'] >= game['max_attempts']:
            msg += f"\n❌ **GAME OVER!** The number was {game['secret']}"
            del active_games[user_id]
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        remaining = game['max_attempts'] - game['attempts']
        msg = f"📉 **Too High!**\nAttempts left: {remaining}"
        if game['attempts'] >= game['max_attempts']:
            msg += f"\n❌ **GAME OVER!** The number was {game['secret']}"
            del active_games[user_id]
        await update.message.reply_text(msg, parse_mode='Markdown')

async def quiz_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = context.args[0] if context.args and context.args[0] in quiz_questions else 'general'
    questions = quiz_questions[category][:5]
    user_id = update.message.from_user.id
    active_games[user_id] = {'type': 'quiz', 'questions': questions, 'current': 0, 'score': 0, 'category': category}
    await send_quiz_question(update, user_id)

async def send_quiz_question(update: Update, user_id: int):
    game = active_games.get(user_id)
    if not game or game['current'] >= len(game['questions']):
        total = len(game['questions']) if game else 0
        score = game['score'] if game else 0
        points = score * 10
        add_points(user_id, points)
        update_game_stats(user_id, "Quiz", score)
        await update.message.reply_text(
            f"🎉 **Quiz Completed!**\nScore: {score}/{total}\n💰 Points earned: {points}\n"
            f"{'🏆 PERFECT SCORE!' if score == total else '👍 Good attempt!'}",
            parse_mode='Markdown')
        if user_id in active_games:
            del active_games[user_id]
        return
    
    q = game['questions'][game['current']]
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz_{opt}_{user_id}")] for opt in q['options']]
    await update.message.reply_text(
        f"🎯 **Quiz Q{game['current']+1}/{len(game['questions'])}**\nCategory: {game['category'].upper()}\nScore: {game['score']}\n\n{q['q']}",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if not data.startswith("quiz_"):
        return
    answer = data.split("_")[1]
    user_id = int(data.split("_")[2])
    if query.from_user.id != user_id:
        await query.answer("❌ Not your game!", show_alert=True)
        return
    
    game = active_games.get(user_id)
    if not game or game['type'] != 'quiz':
        await query.answer("❌ Game expired!", show_alert=True)
        return
    
    current_q = game['questions'][game['current']]
    if answer == current_q['a']:
        game['score'] += 1
        await query.answer("✅ Correct! +1 point", show_alert=True)
    else:
        await query.answer(f"❌ Wrong! Answer: {current_q['a']}", show_alert=True)
    
    game['current'] += 1
    await query.message.delete()
    await send_quiz_question(update, user_id)

async def hangman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = random.choice(hangman_words)
    user_id = update.message.from_user.id
    active_games[user_id] = {'type': 'hangman', 'word': word, 'guessed': set(), 'wrong': 0, 'max_wrong': 6}
    await display_hangman(update, user_id)

async def display_hangman(update: Update, user_id: int):
    game = active_games[user_id]
    display = " ".join([l if l in game['guessed'] else "_" for l in game['word']])
    
    keyboard = []
    row = []
    for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        row.append(InlineKeyboardButton(letter, callback_data=f"hang_{letter}_{user_id}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔄 New Game", callback_data="hang_new")])
    
    await update.message.reply_text(
        f"🎮 **HANGMAN**\n{hangman_stages[game['wrong']]}\n\n📖 Word: {display}\n❌ Wrong: {game['wrong']}/{game['max_wrong']}\n🔤 Guessed: {', '.join(sorted(game['guessed']))}",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Monospace')

async def hangman_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data == "hang_new":
        word = random.choice(hangman_words)
        active_games[user_id] = {'type': 'hangman', 'word': word, 'guessed': set(), 'wrong': 0, 'max_wrong': 6}
        await query.message.delete()
        await display_hangman(update, user_id)
        await query.answer()
        return
    
    if data.startswith("hang_"):
        letter = data.split("_")[1]
        game_user_id = int(data.split("_")[2])
        if user_id != game_user_id:
            await query.answer("❌ Not your game!", show_alert=True)
            return
        if user_id not in active_games:
            await query.answer("❌ No active game!", show_alert=True)
            return
        
        game = active_games[user_id]
        if letter in game['guessed']:
            await query.answer("Already guessed!", show_alert=True)
            return
        
        game['guessed'].add(letter)
        if letter not in game['word']:
            game['wrong'] += 1
        
        if all(l in game['guessed'] for l in game['word']):
            points = 100 - (game['wrong'] * 5)
            add_points(user_id, points)
            update_game_stats(user_id, "Hangman", points)
            await query.message.delete()
            await query.message.reply_text(f"🎉 **YOU WIN!** Word: {game['word']}\n💰 Points: {points}\nPlay again: `/hangman`", parse_mode='Markdown')
            del active_games[user_id]
        elif game['wrong'] >= game['max_wrong']:
            await query.message.delete()
            await query.message.reply_text(f"💀 **GAME OVER!** Word was: {game['word']}\nPlay again: `/hangman`", parse_mode='Markdown')
            del active_games[user_id]
        else:
            await query.message.delete()
            await display_hangman(update, user_id)
        await query.answer()

async def trivia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    question = random.choice(trivia_questions)
    active_games[user_id] = {'type': 'trivia', 'question': question, 'answered': False}
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"triv_{opt}_{user_id}")] for opt in question['options']]
    await update.message.reply_text(f"🧠 **TRIVIA**\n\n{question['question']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def trivia_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if not data.startswith("triv_"):
        return
    answer = data.split("_")[1]
    user_id = int(data.split("_")[2])
    if query.from_user.id != user_id:
        await query.answer("❌ Not your game!", show_alert=True)
        return
    
    game = active_games.get(user_id)
    if not game or game.get('answered'):
        await query.answer("❌ Game expired!", show_alert=True)
        return
    
    game['answered'] = True
    if answer == game['question']['answer']:
        add_points(user_id, 20)
        update_game_stats(user_id, "Trivia", 20)
        await query.edit_message_text(f"✅ **CORRECT!**\nAnswer: {answer}\n💰 +20 points!", parse_mode='Markdown')
    else:
        await query.edit_message_text(f"❌ **WRONG!**\nAnswer: {game['question']['answer']}\nTry again: `/trivia`", parse_mode='Markdown')
    del active_games[user_id]
    await query.answer()

async def tictactoe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    active_games[user_id] = {'type': 'ttt', 'board': [' ']*9, 'current': 'X', 'winner': None}
    await display_ttt(update, user_id)

async def display_ttt(update: Update, user_id: int):
    game = active_games[user_id]
    keyboard = []
    for i in range(0, 9, 3):
        row = [InlineKeyboardButton(game['board'][i+j] if game['board'][i+j] != ' ' else '⬜', callback_data=f"ttt_{i+j}_{user_id}") for j in range(3)]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔄 New Game", callback_data="ttt_new")])
    
    status = "🎉 YOU WIN!" if game['winner'] == 'X' else "🤖 AI WINS!" if game['winner'] == 'O' else "🤝 DRAW!" if game['winner'] == 'DRAW' else f"Your turn ({game['current']})"
    await update.message.reply_text(f"🎯 **TIC TAC TOE**\n\n{status}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def ttt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data == "ttt_new":
        active_games[user_id] = {'type': 'ttt', 'board': [' ']*9, 'current': 'X', 'winner': None}
        await query.message.delete()
        await display_ttt(update, user_id)
        await query.answer()
        return
    
    if data.startswith("ttt_"):
        pos = int(data.split("_")[1])
        game_user_id = int(data.split("_")[2])
        if user_id != game_user_id:
            await query.answer("❌ Not your game!", show_alert=True)
            return
        if user_id not in active_games:
            await query.answer("❌ No active game!", show_alert=True)
            return
        
        game = active_games[user_id]
        if game['winner'] or game['board'][pos] != ' ':
            await query.answer("❌ Invalid move!", show_alert=True)
            return
        
        game['board'][pos] = 'X'
        
        win_patterns = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]
        def check_win(b):
            for p in win_patterns:
                if b[p[0]] == b[p[1]] == b[p[2]] != ' ':
                    return b[p[0]]
            return None
        
        winner = check_win(game['board'])
        if winner:
            game['winner'] = winner
            if winner == 'X':
                add_points(user_id, 50)
                update_game_stats(user_id, "TicTacToe", 50)
        elif ' ' not in game['board']:
            game['winner'] = 'DRAW'
        else:
            empty = [i for i, cell in enumerate(game['board']) if cell == ' ']
            if empty:
                ai_move = random.choice(empty)
                game['board'][ai_move] = 'O'
                winner = check_win(game['board'])
                if winner:
                    game['winner'] = winner
                elif ' ' not in game['board']:
                    game['winner'] = 'DRAW'
        
        await query.message.delete()
        await display_ttt(update, user_id)
        await query.answer()

async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    dice = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    
    if user_roll > bot_roll:
        points = 20
        add_points(update.message.from_user.id, points)
        update_game_stats(update.message.from_user.id, "Dice", points)
        result = f"🎉 YOU WIN! +{points} points"
    elif bot_roll > user_roll:
        result = "🤖 BOT WINS!"
    else:
        result = "🤝 DRAW!"
    
    await update.message.reply_text(
        f"🎲 **DICE GAME**\n\nYou: {dice[user_roll-1]} {user_roll}\nBot: {dice[bot_roll-1]} {bot_roll}\n\n{result}",
        parse_mode='Markdown')

# ================= ENTERTAINMENT HANDLERS =================

async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get("https://meme-api.com/gimme")
        if response.status_code == 200:
            data = response.json()
            meme_response = requests.get(data['url'])
            if meme_response.status_code == 200:
                await update.message.reply_photo(photo=io.BytesIO(meme_response.content), caption=f"😂 **{data['title']}**\n👍 {data.get('ups', 'N/A')}")
            else:
                await update.message.reply_text("❌ Couldn't fetch meme!")
        else:
            await update.message.reply_text("❌ Meme API error!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"😂 **Joke**\n\n{random.choice(jokes)}", parse_mode='Markdown')

async def funfact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📚 **Fun Fact**\n\n{random.choice(fun_facts)}", parse_mode='Markdown')

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q, a = random.choice(quotes)
    await update.message.reply_text(f"💭 **Quote**\n\n\"{q}\"\n\n— {a}", parse_mode='Markdown')

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🌤️ Usage: `/weather [city]`\nExample: `/weather Mumbai`", parse_mode='Markdown')
        return
    city = " ".join(context.args)
    msg = await update.message.reply_text(f"🌤️ Fetching weather for {city}...")
    try:
        response = requests.get(f"https://wttr.in/{city}?format=%C|%t|%w|%h")
        if response.status_code == 200:
            data = response.text.strip().split('|')
            await msg.edit_text(f"🌍 **Weather: {city.upper()}**\n\n☁️ {data[0]}\n🌡️ {data[1]}\n💨 {data[2]}\n💧 {data[3]}", parse_mode='Markdown')
        else:
            await msg.edit_text(f"❌ City '{city}' not found!")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def daily_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    conn, cursor = ensure_connection()
    cursor.execute("SELECT last_daily_claim, daily_streak FROM user_scores WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0] == today:
        await update.message.reply_text("⏰ Already claimed today! Come back tomorrow!", parse_mode='Markdown')
        return
    
    points = random.randint(50, 200)
    streak = (result[1] + 1) if result else 1
    if result and result[0] and (datetime.now() - datetime.strptime(result[0], "%Y-%m-%d")).days > 1:
        streak = 1
    
    cursor.execute("UPDATE user_scores SET total_points = total_points + ?, daily_streak = ?, last_daily_claim = ? WHERE user_id = ?",
                  (points, streak, today, user_id))
    conn.commit()
    
    await update.message.reply_text(
        f"🎁 **Daily Reward!**\n\n💰 +{points} points\n🔥 Streak: {streak} day(s)\n\nCome back tomorrow!",
        parse_mode='Markdown')

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn, cursor = ensure_connection()
    cursor.execute("SELECT u.first_name, s.total_points, s.games_won, s.quizzes_passed FROM user_scores s JOIN users u ON s.user_id = u.id WHERE s.total_points > 0 ORDER BY s.total_points DESC LIMIT 10")
    top = cursor.fetchall()
    if not top:
        await update.message.reply_text("📊 No points yet! Play games to earn points!", parse_mode='Markdown')
        return
    
    text = "🏆 **LEADERBOARD** 🏆\n\n"
    for i, (name, points, games, quizzes) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} {name} - {points} pts (🎮{games} | 📚{quizzes})\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= REMINDER SYSTEM =================
reminder_queue = queue.Queue()

def reminder_worker():
    while True:
        try:
            conn, cursor = get_db()
            current_time = datetime.now()
            cursor.execute("SELECT id, user_id, reminder_text FROM reminders WHERE status = 'pending' AND datetime(reminder_time) <= datetime(?)", 
                          (current_time.strftime("%Y-%m-%d %H:%M:%S"),))
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

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        while not reminder_queue.empty():
            reminder = reminder_queue.get_nowait()
            rid, uid, msg = reminder
            try:
                await context.bot.send_message(chat_id=uid, text=f"⏰ **REMINDER!**\n\n{msg}", parse_mode='Markdown')
            except:
                pass
    except:
        pass

# ================= COMMAND HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = f"""
🌟 **Namaste {user.first_name}!** 🌟

Main aapka advanced AI assistant **Study Controller** hoon.

📚 **STUDY COMMANDS**
/notes [topic] - Detailed notes
/explain [topic] - Simple explanation
/mcq [topic] - Multiple choice questions
/pyq [subject] - Previous year questions
/doubt [question] - Solve doubts
/quiz [topic] [q] - Interactive quiz

📄 **PDF COMMANDS**
/pdf [topic] - Complete PDF with diagram
/pdfnotes [topic] - Simple PDF notes
/pdfdiagram [topic] - PDF with visual diagram

🎮 **GAMES & ENTERTAINMENT**
/game - Number guessing game
/quizgame - Quiz competition
/hangman - Word guessing game
/trivia - Random trivia
/tictactoe - Play Tic Tac Toe
/dice - Roll dice game
/meme - Random memes
/joke - Funny jokes
/fact - Interesting facts
/quote - Inspirational quotes

🎨 **CREATIVE COMMANDS**
/imagine [prompt] - AI image generate
/voice [text] - Text to voice
/analyze - Image analyze

📝 **NOTE & FLASHCARD**
/addnote [title] [content] - Save note
/mynotes - View notes
/addcard [q] [a] - Add flashcard
/study - Study flashcards

⏰ **REMINDERS**
/remind [time] [msg] - Set reminder
/myreminders - View reminders

💰 **REWARDS**
/daily - Claim daily reward
/leaderboard - Top players
/points - Your points

🌤️ **UTILITIES**
/weather [city] - Weather forecast

📝 **FEEDBACK**
/feedback [msg] - Give feedback
/complaint [msg] - File complaint

**Bas mujhe tag karo ya reply karo!** 🚀
"""
    
    keyboard = [
        [InlineKeyboardButton("📚 Study", callback_data="study"), InlineKeyboardButton("🎮 Games", callback_data="games")],
        [InlineKeyboardButton("📄 PDF", callback_data="pdf"), InlineKeyboardButton("💰 Rewards", callback_data="rewards")],
        [InlineKeyboardButton("🎨 Creative", callback_data="creative"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🌟 **COMPLETE COMMANDS LIST** 🌟

📚 **STUDY**
/notes [topic] - Notes
/explain [topic] - Explanation
/mcq [topic] - MCQs
/pyq [subject] - PYQs
/doubt [q] - Doubt solve
/quiz [topic] [q] - Quiz

📄 **PDF**
/pdf [topic] - Complete PDF
/pdfnotes [topic] - Simple PDF
/pdfdiagram [topic] - PDF with diagram

🎮 **GAMES**
/game - Guess number
/quizgame - Quiz game
/hangman - Hangman
/trivia - Trivia
/tictactoe - Tic Tac Toe
/dice - Dice game

🎨 **CREATIVE**
/imagine [prompt] - AI image
/voice [text] - Text to speech
/analyze - Image analysis

💰 **REWARDS**
/daily - Daily reward
/leaderboard - Top players
/points - Your points

🌤️ **UTILITIES**
/weather [city] - Weather
/remind [time] [msg] - Reminder
/myreminders - View reminders

📝 **NOTES & CARDS**
/addnote [title] [content]
/mynotes
/addcard [q] [a]
/study

🎉 **ENTERTAINMENT**
/meme - Random meme
/joke - Funny joke
/fact - Fun fact
/quote - Quote

📝 **FEEDBACK**
/feedback [msg]
/complaint [msg]
/complaintstatus [id]
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    points, games, quizzes, streak = get_user_points(update.message.from_user.id)
    await update.message.reply_text(
        f"💰 **Your Points**\n\n⭐ Total: {points}\n🎮 Games Won: {games}\n📚 Quizzes: {quizzes}\n🔥 Streak: {streak} days\n\nPlay games to earn more points!",
        parse_mode='Markdown')

# ================= PDF COMMANDS =================

async def pdf_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📚 Usage: `/pdf [topic]`\nExample: `/pdf photosynthesis`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 Generating PDF for **{topic}**...", parse_mode='Markdown')
    try:
        user_id = update.message.from_user.id
        content = await ask_ai_hinglish(user_id, f"Create detailed study notes for {topic} in Hinglish with headings and bullet points")
        diagram_data = [f"Main concept {i+1}" for i in range(6)]
        pdf_bytes = generate_complete_pdf(f"Study Notes: {topic.title()}", content, True, 'mindmap', diagram_data)
        await update.message.reply_document(document=io.BytesIO(pdf_bytes), filename=f"{topic.replace(' ', '_')}_notes.pdf", caption=f"✅ PDF for {topic} generated!")
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def pdf_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📚 Usage: `/pdfnotes [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 Generating PDF notes...", parse_mode='Markdown')
    try:
        user_id = update.message.from_user.id
        content = await ask_ai_hinglish(user_id, f"Create detailed study notes for {topic}")
        pdf_bytes = generate_complete_pdf(f"Notes: {topic.title()}", content, False, None, None)
        await update.message.reply_document(document=io.BytesIO(pdf_bytes), filename=f"{topic.replace(' ', '_')}_notes.pdf")
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def pdf_diagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📊 Usage: `/pdfdiagram [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"🎨 Generating PDF with diagram...", parse_mode='Markdown')
    try:
        user_id = update.message.from_user.id
        content = await ask_ai_hinglish(user_id, f"Create study notes for {topic}")
        pdf_bytes = generate_complete_pdf(f"Diagram: {topic.title()}", content, True, 'mindmap', [f"Point {i+1}" for i in range(6)])
        await update.message.reply_document(document=io.BytesIO(pdf_bytes), filename=f"{topic.replace(' ', '_')}_diagram.pdf")
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

# ================= STUDY COMMANDS =================

async def notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/notes [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📝 Generating notes for **{topic}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Create detailed study notes for {topic} in Hinglish")
    await msg.edit_text(reply)

async def explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/explain [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Explaining **{topic}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Explain {topic} in simple Hinglish with examples")
    await msg.edit_text(reply)

async def mcq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/mcq [topic]`", parse_mode='Markdown')
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📝 Generating MCQs...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Create 10 multiple choice questions for {topic} with answers")
    await msg.edit_text(reply)

async def doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/doubt [question]`", parse_mode='Markdown')
        return
    question = " ".join(context.args)
    msg = await update.message.reply_text(f"❓ Solving your doubt...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Solve this doubt: {question}")
    await msg.edit_text(reply)

# ================= CREATIVE COMMANDS =================

async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/imagine [prompt]`", parse_mode='Markdown')
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
        await msg.edit_text("❌ Failed to generate image.")

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/voice [text]`", parse_mode='Markdown')
        return
    text = " ".join(context.args)
    try:
        msg = await update.message.reply_text("🔊 Converting...")
        tts = gTTS(text, lang='hi' if any(c in text for c in 'अआइईउऊ') else 'en')
        filename = f"voice_{uuid.uuid4().hex[:6]}.mp3"
        tts.save(filename)
        await update.message.reply_voice(open(filename, "rb"))
        os.remove(filename)
        await msg.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Reply to an image with `/analyze`", parse_mode='Markdown')
        return
    msg = await update.message.reply_text("🔍 Analyzing...")
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
        await update.message.reply_text("❌ Usage: `/addnote [title] [content]`", parse_mode='Markdown')
        return
    title = context.args[0]
    content = " ".join(context.args[1:])
    note_id = add_note(update.message.from_user.id, title, content)
    if note_id:
        await update.message.reply_text(f"✅ Note saved! ID: `{note_id}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed to save note.")

async def my_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes_list = get_notes(update.message.from_user.id)
    if not notes_list:
        await update.message.reply_text("📭 No notes found.", parse_mode='Markdown')
        return
    text = "📝 **Your Notes:**\n\n"
    for note in notes_list[:10]:
        text += f"🆔 `{note[0]}` • **{note[1]}**\n📄 {note[2][:100]}...\n📅 {note[3]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/deletenote [id]`", parse_mode='Markdown')
        return
    try:
        note_id = int(context.args[0])
        if delete_note(note_id):
            await update.message.reply_text(f"✅ Note `{note_id}` deleted!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Note not found!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

# ================= FLASHCARD COMMANDS =================

async def add_flashcard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/addcard [question] [answer]`", parse_mode='Markdown')
        return
    question = context.args[0]
    answer = " ".join(context.args[1:])
    card_id = add_flashcard(update.message.from_user.id, question, answer)
    if card_id:
        await update.message.reply_text(f"✅ Flashcard added! ID: `{card_id}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed to add flashcard.")

async def my_flashcards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cards = get_flashcards(update.message.from_user.id, 20)
    if not cards:
        await update.message.reply_text("📭 No flashcards found.", parse_mode='Markdown')
        return
    text = "🃏 **Your Flashcards:**\n\n"
    for card in cards:
        text += f"🆔 `{card[0]}` • {card[1][:50]}\n💡 {card[2][:50]}...\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def study_flashcards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cards = get_flashcards(update.message.from_user.id, 10)
    if not cards:
        await update.message.reply_text("📭 No flashcards to study.", parse_mode='Markdown')
        return
    context.user_data['flashcards'] = cards
    context.user_data['current_card'] = 0
    card = cards[0]
    keyboard = [[InlineKeyboardButton("💡 Show Answer", callback_data=f"show_{card[0]}")]]
    await update.message.reply_text(f"🃏 **Flashcard 1/{len(cards)}**\n\n❓ {card[1]}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ================= REMINDER COMMANDS =================

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⏰ **Set Reminder**\nExamples:\n• `/remind 10m Study`\n• `/remind 2h Submit`\n• `/remind 1d Water plants`", parse_mode='Markdown')
        return
    time_str = context.args[0].lower()
    message = " ".join(context.args[1:])
    reminder_time = parse_reminder_time(time_str)
    if not reminder_time:
        await update.message.reply_text("❌ Invalid time! Use: 10m, 2h, 1d")
        return
    conn, cursor = ensure_connection()
    cursor.execute("INSERT INTO reminders (user_id, reminder_text, reminder_time, created_at) VALUES (?, ?, ?, ?)",
                  (update.message.from_user.id, message, reminder_time.strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    await update.message.reply_text(f"✅ Reminder set!\n\n📝 {message}\n⏰ {reminder_time.strftime('%Y-%m-%d %H:%M')}", parse_mode='Markdown')

async def myreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn, cursor = ensure_connection()
    cursor.execute("SELECT id, reminder_text, reminder_time FROM reminders WHERE user_id = ? AND status = 'pending' ORDER BY reminder_time", (update.message.from_user.id,))
    reminders_list = cursor.fetchall()
    if not reminders_list:
        await update.message.reply_text("📭 No pending reminders.", parse_mode='Markdown')
        return
    text = "📋 **Your Reminders:**\n\n"
    for r in reminders_list:
        text += f"🆔 `{r[0]}` • {r[1]}\n   ⏰ {r[2]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= FEEDBACK COMMANDS =================

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📝 Usage: `/feedback [message]`", parse_mode='Markdown')
        return
    user = update.message.from_user
    feedback_text = " ".join(context.args)
    save_feedback(user.id, user.username, user.first_name, update.message.chat_id, None, feedback_text)
    await update.message.reply_text("✅ **Thank you for your feedback!** 🙏", parse_mode='Markdown')
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=f"📝 Feedback from {user.first_name}: {feedback_text}")
    except:
        pass

async def complaint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/complaint [message]`", parse_mode='Markdown')
        return
    user = update.message.from_user
    complaint_text = " ".join(context.args)
    complaint_id = save_complaint(user.id, user.username, user.first_name, update.message.chat_id, None, complaint_text)
    if complaint_id:
        await update.message.reply_text(f"⚠️ **Complaint Registered**\n\n🆔 ID: `{complaint_id}`", parse_mode='Markdown')
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=f"⚠️ Complaint #{complaint_id} from {user.first_name}: {complaint_text}")
        except:
            pass
    else:
        await update.message.reply_text("❌ Failed to register complaint.")

# ================= USER STATS COMMANDS =================

async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_user_stats(update.message.from_user.id)
    if stats:
        await update.message.reply_text(f"📊 **Your Stats**\n\n💬 Total: {stats[0]}\n📊 Today: {stats[3]}\n📅 Joined: {stats[1]}", parse_mode='Markdown')
    else:
        await update.message.reply_text("No data yet. Start chatting!")

async def daily_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn, cursor = ensure_connection()
    cursor.execute("SELECT daily_usage_count FROM users WHERE id = ?", (update.message.from_user.id,))
    result = cursor.fetchone()
    usage = result[0] if result else 0
    top = get_daily_top_users(5)
    text = f"📊 **Your Daily Usage:** {usage} messages\n\n🏆 **Today's Top Users:**\n"
    for i, (uid, un, name, count) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} {name} - {count} msgs\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefs = get_user_preferences(update.message.from_user.id)
    keyboard = [
        [InlineKeyboardButton("🌐 Language", callback_data="lang"), InlineKeyboardButton("📝 Style", callback_data="style")],
        [InlineKeyboardButton("🗑️ Clear History", callback_data="clear")]
    ]
    await update.message.reply_text(f"⚙️ **Settings**\n\nLanguage: {prefs['language']}\nStyle: {prefs['response_style']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ================= CALLBACK HANDLER =================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()
    
    if data == "study":
        await query.edit_message_text("📚 **Study Commands**\n\n/notes [topic]\n/explain [topic]\n/mcq [topic]\n/pyq [subject]\n/doubt [q]\n/quiz [topic] [q]", parse_mode='Markdown')
    elif data == "games":
        await query.edit_message_text("🎮 **Games**\n\n/game - Guess number\n/quizgame - Quiz\n/hangman - Hangman\n/trivia - Trivia\n/tictactoe - Tic Tac Toe\n/dice - Dice game\n/meme - Memes\n/joke - Jokes\n/fact - Facts\n/quote - Quotes", parse_mode='Markdown')
    elif data == "pdf":
        await query.edit_message_text("📄 **PDF Commands**\n\n/pdf [topic]\n/pdfnotes [topic]\n/pdfdiagram [topic]", parse_mode='Markdown')
    elif data == "rewards":
        await query.edit_message_text("💰 **Rewards**\n\n/daily - Daily reward\n/leaderboard - Top players\n/points - Your points", parse_mode='Markdown')
    elif data == "creative":
        await query.edit_message_text("🎨 **Creative**\n\n/imagine [prompt]\n/voice [text]\n/analyze", parse_mode='Markdown')
    elif data == "stats":
        stats = get_user_stats(user_id)
        pts, games, quizzes, streak = get_user_points(user_id)
        if stats:
            await query.edit_message_text(f"📊 **Your Stats**\n\n💬 Messages: {stats[0]}\n📊 Today: {stats[3]}\n💰 Points: {pts}\n🎮 Games Won: {games}\n🔥 Streak: {streak}", parse_mode='Markdown')
    elif data == "settings":
        prefs = get_user_preferences(user_id)
        keyboard = [[InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"), InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi")],
                    [InlineKeyboardButton("📌 Concise", callback_data="style_concise"), InlineKeyboardButton("⚖️ Balanced", callback_data="style_balanced")],
                    [InlineKeyboardButton("🗑️ Clear History", callback_data="clear")]]
        await query.edit_message_text(f"⚙️ **Settings**\n\nLanguage: {prefs['language']}\nStyle: {prefs['response_style']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("lang_"):
        set_user_preference(user_id, "language", data.replace("lang_", ""))
        await query.edit_message_text("✅ Language set!")
    elif data.startswith("style_"):
        set_user_preference(user_id, "response_style", data.replace("style_", ""))
        await query.edit_message_text("✅ Style set!")
    elif data == "clear":
        clear_user_history(user_id)
        await query.edit_message_text("✅ Chat history cleared!")
    elif data.startswith("show_"):
        card_id = int(data.split("_")[1])
        conn, cursor = ensure_connection()
        cursor.execute("SELECT question, answer FROM flashcards WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        if result:
            await query.edit_message_text(f"❓ {result[0]}\n\n💡 {result[1]}", parse_mode='Markdown')

# ================= MESSAGE HANDLER =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or update.message.from_user.is_bot:
        return
    
    conn, cursor = ensure_connection()
    cursor.execute("SELECT is_blocked FROM users WHERE id = ?", (update.message.from_user.id,))
    result = cursor.fetchone()
    if result and result[0] == 1:
        return
    
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
    
    update_user_activity(update.message.from_user.id, update.message.chat.type, update.message.chat_id, update.message.chat.title if update.message.chat.type in ['group', 'supergroup'] else None)
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    
    if update.message.text:
        text = update.message.text.replace(BOT_USERNAME, "").strip()
        if not text:
            text = "Hello"
        reply = await ask_ai_hinglish(update.message.from_user.id, text)
        save_chat_history(update.message.from_user.id, text, reply)
        await update.message.reply_text(reply, parse_mode='Markdown')
    elif update.message.voice:
        file = await update.message.voice.get_file()
        path = f"voice_{uuid.uuid4().hex[:6]}.ogg"
        await file.download_to_drive(path)
        text = voice_to_text(path)
        await update.message.reply_text(f"📝 **You said:** {text}", parse_mode='Markdown')
        reply = await ask_ai_hinglish(update.message.from_user.id, text)
        await update.message.reply_text(reply, parse_mode='Markdown')
        for f in [path, "voice.wav"]:
            if os.path.exists(f):
                os.remove(f)
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
        path = f"img_{uuid.uuid4().hex[:6]}.jpg"
        await file.download_to_drive(path)
        reply = await analyze_image(path)
        await update.message.reply_text(reply, parse_mode='Markdown')
        if os.path.exists(path):
            os.remove(path)

# ================= OWNER COMMANDS =================

async def users_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    users = total_users()
    text = f"📊 **Total Users:** {len(users)}\n\n"
    for u in users[:20]:
        text += f"• {u[1] or u[2] or 'Unknown'} (ID: `{u[0]}`)\n  💬 {u[4]} | 📅 {u[3][:10]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage: `/broadcast [message]`", parse_mode='Markdown')
        return
    users = total_users()
    sent = 0
    status = await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=message)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await status.edit_text(f"✅ Sent to {sent} users!")

async def stats_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    users = total_users()
    groups = get_all_groups()
    conn, cursor = ensure_connection()
    cursor.execute("SELECT COUNT(*) FROM chat_history")
    chats = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM game_stats")
    games_played = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(total_points) FROM user_scores")
    total_points = cursor.fetchone()[0] or 0
    
    text = f"""
📊 **BOT STATISTICS**

👥 Users: {len(users)}
👥 Groups: {len(groups)}
💬 Chats: {chats}
🎮 Games Played: {games_played}
💰 Total Points: {total_points}
📝 Feedback: {cursor.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]}
⚠️ Complaints: {cursor.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]}

Status: 🟢 Active
    """
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= MAIN =================

async def post_init(application):
    logger.info(f"🚀 Study Controller Bot Started!")
    logger.info(f"Bot: @{application.bot.username}")
    logger.info("All features active: Games, PDF, Face Recognition, Notes, Flashcards, Reminders!")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", user_stats))
    app.add_handler(CommandHandler("daily", daily_usage))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("points", points))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    
    # Study commands
    app.add_handler(CommandHandler("notes", notes))
    app.add_handler(CommandHandler("explain", explain))
    app.add_handler(CommandHandler("mcq", mcq))
    app.add_handler(CommandHandler("doubt", doubt))
    
    # PDF commands
    app.add_handler(CommandHandler("pdf", pdf_full))
    app.add_handler(CommandHandler("pdfnotes", pdf_notes))
    app.add_handler(CommandHandler("pdfdiagram", pdf_diagram))
    
    # Game commands
    app.add_handler(CommandHandler("game", guess_game))
    app.add_handler(CommandHandler("guess", guess_number))
    app.add_handler(CommandHandler("quizgame", quiz_game))
    app.add_handler(CommandHandler("hangman", hangman))
    app.add_handler(CommandHandler("trivia", trivia))
    app.add_handler(CommandHandler("tictactoe", tictactoe))
    app.add_handler(CommandHandler("dice", dice_game))
    
    # Entertainment commands
    app.add_handler(CommandHandler("meme", meme))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("fact", funfact))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("daily", daily_reward))
    
    # Creative commands
    app.add_handler(CommandHandler("imagine", imagine))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    
    # Note commands
    app.add_handler(CommandHandler("addnote", add_note_command))
    app.add_handler(CommandHandler("mynotes", my_notes))
    app.add_handler(CommandHandler("deletenote", delete_note))
    
    # Flashcard commands
    app.add_handler(CommandHandler("addcard", add_flashcard_command))
    app.add_handler(CommandHandler("mycards", my_flashcards))
    app.add_handler(CommandHandler("study", study_flashcards))
    
    # Reminder commands
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("myreminders", myreminders))
    
    # Feedback commands
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("complaint", complaint_command))
    
    # Owner commands
    app.add_handler(CommandHandler("users", users_count))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("statsall", stats_all))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(quiz_callback, pattern="quiz_"))
    app.add_handler(CallbackQueryHandler(hangman_callback, pattern="hang"))
    app.add_handler(CallbackQueryHandler(trivia_callback, pattern="triv_"))
    app.add_handler(CallbackQueryHandler(ttt_callback, pattern="ttt"))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, handle_message))
    
    # Job queue
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_reminders, interval=30, first=10)
    
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
