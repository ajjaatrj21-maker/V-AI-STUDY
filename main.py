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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
import speech_recognition as sr
from pydub import AudioSegment
import requests
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import pytesseract
from typing import Dict, List, Optional
import random
import re

# ================= PDF GENERATION IMPORTS =================
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics import renderPDF
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
GROQ_API_KEY = "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"
BOT_USERNAME = "@STUDYCONTROLLERV2_bot"

OWNER_ID = 6305002830
OWNER_NAME = "꧁⁣༒𓆩A𝔰𝔥𝔦𝔰𝔥𓆪༒꧂"

# ================= FONT REGISTRATION =================
def register_fonts():
    """Register fonts for better PDF rendering"""
    fonts_registered = []
    font_paths = [
        ('DejaVuSans', 'DejaVuSans.ttf'),
        ('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'),
        ('DejaVuSans-Oblique', 'DejaVuSans-Oblique.ttf'),
        ('Arial', 'arial.ttf'),
        ('ArialUnicode', 'arialuni.ttf'),
        ('NotoSans', 'NotoSans-Regular.ttf'),
        ('FreeSans', 'FreeSans.ttf')
    ]
    
    for font_name, font_file in font_paths:
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_file))
            fonts_registered.append(font_name)
        except:
            continue
    
    if fonts_registered:
        return fonts_registered[0]
    return 'Helvetica'

MAIN_FONT = register_fonts()

# ================= DATABASE =================
thread_local = threading.local()

def get_db():
    if not hasattr(thread_local, "conn"):
        thread_local.conn = sqlite3.connect("users.db", check_same_thread=False)
        thread_local.cursor = thread_local.conn.cursor()
    return thread_local.conn, thread_local.cursor

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
    daily_usage_count INTEGER DEFAULT 0,
    last_daily_reset TEXT
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
CREATE TABLE IF NOT EXISTS feedback(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    user_name TEXT,
    group_id INTEGER,
    group_name TEXT,
    feedback_text TEXT,
    rating INTEGER DEFAULT 5,
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
CREATE TABLE IF NOT EXISTS daily_usage(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    usage_date TEXT,
    chat_count INTEGER DEFAULT 0,
    last_activity TEXT
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

conn.commit()

# ================= PDF STYLES =================
def get_pdf_styles():
    """Create professional PDF styles"""
    styles = getSampleStyleSheet()
    
    # Title Style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontName=MAIN_FONT,
        fontSize=28,
        textColor=colors.HexColor('#1E3C72'),
        alignment=TA_CENTER,
        spaceAfter=30,
        leading=32,
        spaceBefore=20
    )
    
    # Heading 1 Style
    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontName=MAIN_FONT,
        fontSize=20,
        textColor=colors.HexColor('#2A5298'),
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=18,
        leading=24,
        borderPadding=5,
        backColor=colors.HexColor('#E8F0FF')
    )
    
    # Heading 2 Style
    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontName=MAIN_FONT,
        fontSize=16,
        textColor=colors.HexColor('#4A90E2'),
        alignment=TA_LEFT,
        spaceAfter=10,
        spaceBefore=12,
        leading=20
    )
    
    # Heading 3 Style
    heading3_style = ParagraphStyle(
        'CustomHeading3',
        parent=styles['Heading3'],
        fontName=MAIN_FONT,
        fontSize=14,
        textColor=colors.HexColor('#6C63FF'),
        alignment=TA_LEFT,
        spaceAfter=8,
        spaceBefore=10,
        leading=18
    )
    
    # Normal Text Style
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=MAIN_FONT,
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leading=16,
        textColor=colors.HexColor('#2C3E50')
    )
    
    # Bullet Point Style
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontName=MAIN_FONT,
        fontSize=11,
        leftIndent=25,
        alignment=TA_LEFT,
        spaceAfter=4,
        leading=16,
        bulletText='•'
    )
    
    # Numbered List Style
    numbered_style = ParagraphStyle(
        'NumberedStyle',
        parent=styles['Normal'],
        fontName=MAIN_FONT,
        fontSize=11,
        leftIndent=25,
        alignment=TA_LEFT,
        spaceAfter=4,
        leading=16
    )
    
    # Code/Quote Style
    quote_style = ParagraphStyle(
        'QuoteStyle',
        parent=styles['Normal'],
        fontName=MAIN_FONT,
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=8,
        leading=14,
        backColor=colors.HexColor('#F5F5F5'),
        leftIndent=20,
        rightIndent=20,
        borderPadding=8,
        textColor=colors.HexColor('#555555')
    )
    
    return {
        'title': title_style,
        'heading1': heading1_style,
        'heading2': heading2_style,
        'heading3': heading3_style,
        'normal': normal_style,
        'bullet': bullet_style,
        'numbered': numbered_style,
        'quote': quote_style
    }

def clean_text_for_pdf(text):
    """Clean and prepare text for PDF rendering"""
    # Replace special mathematical symbols
    replacements = {
        '∈': 'element of',
        '∑': 'sum',
        '∫': 'integral',
        '√': 'square root',
        'π': 'pi',
        'θ': 'theta',
        'Δ': 'delta',
        'α': 'alpha',
        'β': 'beta',
        'γ': 'gamma',
        '→': '->',
        '←': '<-',
        '↑': 'up',
        '↓': 'down',
        '★': '*',
        '☆': '*',
        '✓': '[✓]',
        '✗': '[✗]',
        '•': '•',
        '–': '-',
        '—': '-',
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '≈': 'approximately',
        '≠': 'not equal to',
        '≤': 'less than or equal to',
        '≥': 'greater than or equal to',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Escape HTML entities
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    return text

def parse_content_to_elements(content, styles):
    """Parse content into PDF elements with proper formatting"""
    story = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            story.append(Spacer(1, 6))
            i += 1
            continue
        
        # Check for main headings (## or **Title**)
        if line.startswith('##') or (line.startswith('**') and line.endswith('**')):
            heading = line.strip('#').strip('*').strip()
            story.append(Paragraph(clean_text_for_pdf(heading), styles['heading1']))
            story.append(Spacer(1, 6))
            
        # Check for subheadings (### or ***)
        elif line.startswith('###') or line.startswith('***'):
            heading = line.strip('#').strip('*').strip()
            story.append(Paragraph(clean_text_for_pdf(heading), styles['heading2']))
            story.append(Spacer(1, 6))
            
        # Check for bullet points
        elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
            bullet_text = line.lstrip('•-* ').strip()
            story.append(Paragraph(f'• {clean_text_for_pdf(bullet_text)}', styles['bullet']))
            
        # Check for numbered lists
        elif re.match(r'^\d+\.', line):
            story.append(Paragraph(clean_text_for_pdf(line), styles['numbered']))
            
        # Check for quotes (lines starting with >)
        elif line.startswith('>'):
            quote_text = line.lstrip('> ').strip()
            story.append(Paragraph(clean_text_for_pdf(quote_text), styles['quote']))
            
        # Normal text with paragraph formatting
        else:
            # Split long paragraphs into lines
            if len(line) > 100:
                words = line.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) < 100:
                        current_line += word + " "
                    else:
                        if current_line:
                            story.append(Paragraph(clean_text_for_pdf(current_line.strip()), styles['normal']))
                        current_line = word + " "
                if current_line:
                    story.append(Paragraph(clean_text_for_pdf(current_line.strip()), styles['normal']))
            else:
                story.append(Paragraph(clean_text_for_pdf(line), styles['normal']))
        
        story.append(Spacer(1, 2))
        i += 1
    
    return story

# ================= DIAGRAM GENERATION =================
def create_flowchart_diagram(title, steps):
    """Create a flowchart diagram"""
    plt.figure(figsize=(12, 8))
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    
    # Create flowchart using matplotlib
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Add title
    ax.text(5, 9.5, title, fontsize=16, ha='center', va='center', weight='bold')
    
    # Create boxes for each step
    y_positions = np.linspace(8, 2, len(steps))
    colors_list = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7D794']
    
    for i, (step, y) in enumerate(zip(steps, y_positions)):
        # Draw box
        rect = plt.Rectangle((3, y-0.4), 4, 0.8, facecolor=colors_list[i % len(colors_list)], edgecolor='black', linewidth=2)
        ax.add_patch(rect)
        
        # Add text
        step_text = f"{i+1}. {step[:50]}"
        ax.text(5, y, step_text, fontsize=10, ha='center', va='center', wrap=True)
        
        # Draw arrow
        if i < len(steps) - 1:
            ax.annotate('', xy=(5, y-0.5), xytext=(5, y-0.4), 
                       arrowprops=dict(arrowstyle='->', lw=2, color='gray'))
    
    plt.tight_layout()
    
    # Save to bytes
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    img_buffer.seek(0)
    return img_buffer

def create_mindmap_diagram(title, concepts):
    """Create a mindmap diagram"""
    plt.figure(figsize=(12, 10))
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS']
    
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Center circle
    center = (5, 5)
    circle = plt.Circle(center, 0.8, facecolor='#FF6B6B', edgecolor='black', linewidth=2)
    ax.add_patch(circle)
    ax.text(center[0], center[1], title[:30], fontsize=12, ha='center', va='center', weight='bold', color='white')
    
    # Surrounding concepts
    angles = np.linspace(0, 2*np.pi, len(concepts), endpoint=False)
    radius = 2.5
    
    colors_list = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7D794', '#FFB6C1']
    
    for i, (concept, angle) in enumerate(zip(concepts[:12], angles)):
        x = center[0] + radius * np.cos(angle)
        y = center[1] + radius * np.sin(angle)
        
        # Draw circle for concept
        concept_circle = plt.Circle((x, y), 0.6, facecolor=colors_list[i % len(colors_list)], edgecolor='black', linewidth=1.5)
        ax.add_patch(concept_circle)
        
        # Add text
        concept_text = concept[:40]
        ax.text(x, y, concept_text, fontsize=8, ha='center', va='center', wrap=True)
        
        # Draw connecting line
        ax.plot([center[0], x], [center[1], y], 'k-', linewidth=1, alpha=0.5)
    
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    img_buffer.seek(0)
    return img_buffer

def create_timeline_diagram(title, events):
    """Create a timeline diagram"""
    plt.figure(figsize=(14, 6))
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS']
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    # Create timeline
    y = 0
    ax.set_ylim(-1, 1)
    ax.set_xlim(-0.5, len(events) - 0.5)
    ax.axis('off')
    
    # Draw horizontal line
    ax.hlines(y, -0.5, len(events) - 0.5, colors='black', linewidth=2)
    
    colors_list = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
    
    for i, event in enumerate(events[:10]):
        x = i
        
        # Draw point
        ax.plot(x, y, 'o', markersize=10, color=colors_list[i % len(colors_list)], markeredgecolor='black')
        
        # Add text above
        event_text = event[:50]
        ax.text(x, 0.2, event_text, fontsize=9, ha='center', va='bottom', wrap=True, rotation=45)
        
        # Add number
        ax.text(x, -0.2, str(i+1), fontsize=10, ha='center', va='top', weight='bold')
    
    ax.set_title(title, fontsize=14, weight='bold', pad=20)
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    img_buffer.seek(0)
    return img_buffer

def create_table_diagram(title, headers, data):
    """Create a table diagram"""
    plt.figure(figsize=(12, max(4, len(data) * 0.5)))
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS']
    
    fig, ax = plt.subplots(figsize=(10, max(4, len(data) * 0.5)))
    ax.axis('off')
    
    # Create table
    table_data = [headers] + data[:15]
    table = ax.table(cellText=table_data, loc='center', cellLoc='center', colWidths=[0.3] * len(headers))
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    
    # Style the table
    for i in range(len(table_data)):
        for j in range(len(headers)):
            cell = table[(i, j)]
            if i == 0:
                cell.set_facecolor('#4ECDC4')
                cell.set_text_props(weight='bold', color='white')
            else:
                cell.set_facecolor('#F5F5F5' if i % 2 == 0 else 'white')
    
    ax.set_title(title, fontsize=14, weight='bold', pad=20)
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    img_buffer.seek(0)
    return img_buffer

# ================= MAIN PDF GENERATION =================
def generate_complete_pdf(title, content, include_diagram=False, diagram_type=None, diagram_data=None):
    """Generate complete PDF with professional formatting and diagrams"""
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
        title=title,
        author="Study Controller Bot"
    )
    
    styles = get_pdf_styles()
    story = []
    
    # Add decorative line
    story.append(Spacer(1, 10))
    
    # Add title
    story.append(Paragraph(clean_text_for_pdf(title), styles['title']))
    
    # Add date and info
    date_style = ParagraphStyle('DateStyle', parent=styles['normal'], fontSize=9, textColor=colors.grey, alignment=TA_RIGHT)
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %H:%M')}", date_style))
    story.append(Paragraph(f"Generated by: Study Controller Bot", date_style))
    story.append(Spacer(1, 20))
    
    # Add content
    content_elements = parse_content_to_elements(content, styles)
    story.extend(content_elements)
    
    # Add diagram if requested
    if include_diagram and diagram_data:
        story.append(PageBreak())
        
        # Diagram title
        story.append(Paragraph("📊 Visual Diagram", styles['heading1']))
        story.append(Spacer(1, 10))
        
        # Create diagram based on type
        if diagram_type == 'flowchart':
            diagram_img = create_flowchart_diagram(title, diagram_data[:10])
        elif diagram_type == 'mindmap':
            diagram_img = create_mindmap_diagram(title, diagram_data[:12])
        elif diagram_type == 'timeline':
            diagram_img = create_timeline_diagram(title, diagram_data[:10])
        elif diagram_type == 'table':
            if isinstance(diagram_data, dict):
                diagram_img = create_table_diagram(title, diagram_data.get('headers', ['Item', 'Description']), diagram_data.get('data', []))
            else:
                diagram_img = create_table_diagram(title, ['Step', 'Description'], [[i+1, item] for i, item in enumerate(diagram_data[:10])])
        else:
            diagram_img = create_mindmap_diagram(title, diagram_data[:12])
        
        # Add diagram to PDF
        img = RLImage(diagram_img, width=6*inch, height=4*inch)
        story.append(KeepTogether([img, Spacer(1, 10)]))
        
        # Add diagram description
        desc_style = ParagraphStyle('DescStyle', parent=styles['normal'], fontSize=9, textColor=colors.grey, alignment=TA_CENTER)
        story.append(Paragraph(f"Figure: {title} - Visual Representation", desc_style))
    
    # Add footer with page numbers
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        canvas.saveState()
        canvas.setFont(MAIN_FONT, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(doc.width / 2 + doc.leftMargin, doc.bottomMargin - 20, f"Page {page_num}")
        canvas.drawRightString(doc.width + doc.leftMargin - 20, doc.bottomMargin - 20, "Study Controller Bot")
        canvas.restoreState()
    
    # Build PDF
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()

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
    
    if any(word in text.lower() for word in ['owner', 'malik', 'banane wala', 'creator']):
        return f"👑 My owner is {OWNER_NAME}! Unhone mujhe banaya hai. 🙏"
    
    system_prompt = f"""Tum ek smart Telegram AI bot ho. Tumhare owner {OWNER_NAME} hain.
    Language: {language}
    Response Style: {style}
    Be friendly and helpful. Focus on study-related topics.
    Answer in Hinglish (Hindi + English mix).
    Format your responses with:
    - **bold** for main headings
    - • for bullet points
    - Numbers for steps
    - Clear sections"""
    
    messages = [{"role": "system", "content": system_prompt}] + user_memory[user_id]
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "❌ Kuch technical problem hai! Thoda der baad try karo."

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
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, first_name, last_name, join_date, last_active, chat_count, last_daily_reset) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, current_time, current_time, 0, current_time))
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
            if datetime.strptime(last_reset[0], "%Y-%m-%d %H:%M:%S").date() != datetime.now().date():
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
        cursor.execute("""
            INSERT INTO feedback (user_id, username, user_name, group_id, group_name, feedback_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, user_name, group_id, group_name, feedback_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return False

def save_complaint(user_id, username, user_name, group_id, group_name, complaint_text):
    conn, cursor = ensure_connection()
    try:
        cursor.execute("""
            INSERT INTO complaints (user_id, username, user_name, group_id, group_name, complaint_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, user_name, group_id, group_name, complaint_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
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
            return result
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ================= REMINDER SYSTEM =================
reminder_queue = queue.Queue()

def reminder_worker():
    while True:
        try:
            conn, cursor = get_db()
            current_time = datetime.now()
            cursor.execute("SELECT id, user_id, reminder_text, reminder_time FROM reminders WHERE status = 'pending' AND datetime(reminder_time) <= datetime(?)", 
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

📄 **PDF & DIAGRAM FEATURES**
• /pdf [topic] - High-quality PDF with diagram
• /pdfnotes [topic] - Simple PDF notes
• /pdfdiagram [topic] - PDF with visual diagram

🎨 **CREATIVE FEATURES**
• /imagine [prompt] - AI image generate
• /draw [prompt] - Enhanced prompt
• .gen [prompt] - Quick image
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
• /study - Study flashcards

⏰ **REMINDER COMMANDS**
• /remind [time] [message] - Set reminder
• /myreminders - View reminders
• /cancel [id] - Cancel reminder
• /clearreminders - Clear all

📝 **FEEDBACK & SUPPORT**
• /feedback [message] - Give feedback
• /complaint [message] - File complaint
• /complaintstatus [id] - Check complaint status

📊 **STATS**
• /daily - Check daily usage
• /stats - Your statistics
• /help - All commands

**Bas mujhe tag karo ya reply karo!** 🚀
"""
    
    keyboard = [
        [InlineKeyboardButton("📚 Study", callback_data="study_help"),
         InlineKeyboardButton("📄 PDF", callback_data="pdf_help")],
        [InlineKeyboardButton("🎨 Creative", callback_data="creative"),
         InlineKeyboardButton("📝 Notes", callback_data="notes_menu")],
        [InlineKeyboardButton("🃏 Flashcards", callback_data="flashcards_menu"),
         InlineKeyboardButton("⏰ Reminders", callback_data="reminders")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
         InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

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

**📄 PDF COMMANDS**
/pdf [topic] - Complete PDF with professional formatting and diagram
/pdfnotes [topic] - Simple PDF notes
/pdfdiagram [topic] - PDF with visual diagram

**🎨 CREATIVE COMMANDS**
/imagine [prompt] - AI image generation
/draw [prompt] - Enhanced prompt
/voice [text] - Text to speech
.gen [prompt] - Quick generate
/analyze - Analyze replied image

**📝 NOTE COMMANDS**
/addnote [title] [content] - Add note
/mynotes - View all notes
/editnote [id] [content] - Edit note
/deletenote [id] - Delete note

**🃏 FLASHCARD COMMANDS**
/addcard [q] [a] - Add flashcard
/mycards - View flashcards
/study - Study flashcards

**⏰ REMINDER COMMANDS**
/remind [time] [message] - Set reminder
/myreminders - View reminders
/cancel [id] - Cancel reminder
/clearreminders - Clear all

**📝 FEEDBACK & COMPLAINTS**
/feedback [message] - Give feedback
/complaint [message] - File complaint
/complaintstatus [id] - Check status

**📊 STATS**
/daily - Check daily usage
/stats - Your statistics
/help - This menu

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
/block [user_id] - Block user
/unblock [user_id] - Unblock user
"""
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= PDF COMMANDS =================
async def pdf_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate complete PDF with professional formatting and diagram"""
    if not context.args:
        await update.message.reply_text(
            "📚 **Complete PDF with Diagram**\n\n"
            "**Usage:** `/pdf [topic]`\n"
            "**Example:** `/pdf photosynthesis`\n\n"
            "✨ **Features:**\n"
            "• Professional formatting with headings\n"
            "• Bullet points and numbered lists\n"
            "• Automatic diagram generation\n"
            "• Page numbers and metadata\n"
            "• High-quality text rendering\n"
            "• Visual representation of concepts",
            parse_mode='Markdown'
        )
        return
    
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 Generating professional PDF for **{topic}**...\n⏳ Creating content and diagram...", parse_mode='Markdown')
    
    try:
        user_id = update.message.from_user.id
        
        # Generate content
        content_prompt = f"""Create detailed study notes for {topic} in Hinglish.
        
Format the notes with:
- **Main Title** as heading
- ## Subheadings for sections
- • Bullet points for key points
- Numbered steps for processes
- Clear explanations and examples

Make it comprehensive and well-structured."""
        
        content = await ask_ai_hinglish(user_id, content_prompt)
        
        # Generate diagram data
        diagram_prompt = f"List the main steps, parts, or concepts of {topic} in simple bullet points (max 12 items)"
        diagram_response = await ask_ai_hinglish(user_id, diagram_prompt)
        
        diagram_data = []
        for line in diagram_response.split('\n'):
            line = line.strip()
            if line and (line.startswith('•') or line.startswith('-') or line.startswith('*') or line[0].isdigit()):
                clean_line = line.lstrip('•-*0123456789. ').strip()
                if clean_line:
                    diagram_data.append(clean_line)
        
        if not diagram_data:
            diagram_data = [f"Main concept {i+1}" for i in range(6)]
        
        # Determine diagram type based on topic
        if any(word in topic.lower() for word in ['process', 'steps', 'procedure', 'method']):
            diagram_type = 'flowchart'
        elif any(word in topic.lower() for word in ['history', 'timeline', 'events']):
            diagram_type = 'timeline'
        elif any(word in topic.lower() for word in ['table', 'comparison', 'list']):
            diagram_type = 'table'
        else:
            diagram_type = 'mindmap'
        
        # Generate PDF
        pdf_bytes = generate_complete_pdf(f"Study Notes: {topic.title()}", content, True, diagram_type, diagram_data)
        
        # Send PDF
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"{topic.replace(' ', '_')}_complete_notes.pdf",
            caption=f"📚 **{topic.upper()}**\n\n✅ Professional PDF generated!\n📊 Includes: {diagram_type.upper()} diagram\n✨ High-quality formatting with headings, bullet points, and visual elements"
        )
        
        await msg.delete()
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        await msg.edit_text(f"❌ Error: {str(e)[:200]}\n\nPlease try again with a simpler topic.")

async def pdf_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate simple PDF notes without diagram"""
    if not context.args:
        await update.message.reply_text("📚 **PDF Notes**\n\nUsage: `/pdfnotes [topic]`", parse_mode='Markdown')
        return
    
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 Generating PDF notes for **{topic}**...", parse_mode='Markdown')
    
    try:
        user_id = update.message.from_user.id
        content = await ask_ai_hinglish(user_id, f"Create detailed study notes for {topic} in Hinglish with headings and bullet points")
        
        pdf_bytes = generate_complete_pdf(f"Study Notes: {topic.title()}", content, False, None, None)
        
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"{topic.replace(' ', '_')}_notes.pdf",
            caption=f"📚 **{topic.upper()}**\n\n✅ PDF notes generated!"
        )
        await msg.delete()
        
    except Exception as e:
        logger.error(f"PDF error: {e}")
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def pdf_diagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate PDF with diagram"""
    if not context.args:
        await update.message.reply_text("📊 **PDF with Diagram**\n\nUsage: `/pdfdiagram [topic]`", parse_mode='Markdown')
        return
    
    topic = " ".join(context.args)
    msg = await update.message.reply_text(f"🎨 Creating PDF with diagram for **{topic}**...", parse_mode='Markdown')
    
    try:
        user_id = update.message.from_user.id
        content = await ask_ai_hinglish(user_id, f"Create detailed study notes for {topic} in Hinglish")
        
        # Generate diagram data
        diagram_prompt = f"List the main steps or parts of {topic} in simple bullet points (max 10 items)"
        diagram_response = await ask_ai_hinglish(user_id, diagram_prompt)
        
        diagram_data = []
        for line in diagram_response.split('\n'):
            line = line.strip()
            if line and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                diagram_data.append(line.lstrip('•-* ').strip())
        
        if not diagram_data:
            diagram_data = [f"Concept {i+1}" for i in range(6)]
        
        pdf_bytes = generate_complete_pdf(f"Study Notes: {topic.title()}", content, True, 'mindmap', diagram_data)
        
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"{topic.replace(' ', '_')}_diagram.pdf",
            caption=f"📊 **{topic.upper()}**\n\n✅ PDF with diagram included!"
        )
        await msg.delete()
        
    except Exception as e:
        logger.error(f"Diagram PDF error: {e}")
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
    msg = await update.message.reply_text(f"📝 Generating MCQs for **{topic}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Create 10 multiple choice questions for {topic} with answers")
    await msg.edit_text(reply)

async def pyq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/pyq [subject]`", parse_mode='Markdown')
        return
    subject = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 Finding PYQs for **{subject}**...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Generate important previous year questions for {subject}")
    await msg.edit_text(reply)

async def doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/doubt [question]`", parse_mode='Markdown')
        return
    question = " ".join(context.args)
    msg = await update.message.reply_text(f"❓ Solving your doubt...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Solve this doubt: {question}")
    await msg.edit_text(reply)

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/quiz [topic] [questions]`", parse_mode='Markdown')
        return
    topic = context.args[0]
    try:
        num = min(int(context.args[1]), 20)
    except:
        num = 5
    msg = await update.message.reply_text(f"📝 Generating {num} MCQs...", parse_mode='Markdown')
    reply = await ask_ai_hinglish(update.message.from_user.id, f"Generate {num} multiple choice questions for {topic}")
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

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/draw [prompt]`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    enhanced = f"Ultra detailed {prompt}, cinematic lighting, 8k resolution"
    await update.message.reply_text(f"✨ **Enhanced Prompt:**\n\n`{enhanced}`", parse_mode='Markdown')

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/generate [prompt]`", parse_mode='Markdown')
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

async def enhance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/enhance [prompt]`", parse_mode='Markdown')
        return
    prompt = " ".join(context.args)
    enhanced = f"Ultra detailed {prompt}, cinematic lighting, 8k resolution"
    await update.message.reply_text(f"✨ **Enhanced Prompt:**\n\n`{enhanced}`", parse_mode='Markdown')

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
    notes = get_notes(update.message.from_user.id)
    if not notes:
        await update.message.reply_text("📭 No notes found.", parse_mode='Markdown')
        return
    
    text = "📝 **Your Notes:**\n\n"
    for note in notes[:10]:
        text += f"🆔 `{note[0]}` • **{note[1]}**\n📄 {note[2][:100]}...\n📅 {note[3]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def edit_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/editnote [id] [content]`", parse_mode='Markdown')
        return
    try:
        note_id = int(context.args[0])
        content = " ".join(context.args[1:])
        if update_note(note_id, content):
            await update.message.reply_text(f"✅ Note `{note_id}` updated!", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Note not found!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

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
    keyboard = [[InlineKeyboardButton("💡 Show Answer", callback_data=f"show_answer_{card[0]}")]]
    await update.message.reply_text(f"🃏 **Flashcard 1/{len(cards)}**\n\n❓ {card[1]}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ================= REMINDER COMMANDS =================
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⏰ **Set Reminder**\n\nExamples:\n• `/remind 10m Study`\n• `/remind 2h Submit`\n• `/remind 1d Water plants`", parse_mode='Markdown')
        return
    
    time_str = context.args[0].lower()
    message = " ".join(context.args[1:])
    reminder_time = parse_reminder_time(time_str)
    
    if not reminder_time:
        await update.message.reply_text("❌ Invalid time! Use: 10m, 2h, 1d")
        return
    
    conn, cursor = ensure_connection()
    cursor.execute("INSERT INTO reminders (user_id, reminder_text, reminder_time, created_at, status) VALUES (?, ?, ?, ?, 'pending')",
                  (update.message.from_user.id, message, reminder_time.strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    reminder_id = cursor.lastrowid
    
    await update.message.reply_text(f"✅ Reminder set!\n\n📝 {message}\n⏰ {reminder_time.strftime('%Y-%m-%d %H:%M')}\n🆔 ID: `{reminder_id}`", parse_mode='Markdown')

async def myreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn, cursor = ensure_connection()
    cursor.execute("SELECT id, reminder_text, reminder_time FROM reminders WHERE user_id = ? AND status = 'pending' ORDER BY reminder_time", (update.message.from_user.id,))
    reminders = cursor.fetchall()
    
    if not reminders:
        await update.message.reply_text("📭 No pending reminders.", parse_mode='Markdown')
        return
    
    text = "📋 **Your Reminders:**\n\n"
    for r in reminders:
        text += f"🆔 `{r[0]}` • {r[1]}\n   ⏰ {r[2]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/cancel [id]`", parse_mode='Markdown')
        return
    
    conn, cursor = ensure_connection()
    cursor.execute("UPDATE reminders SET status = 'cancelled' WHERE id = ? AND user_id = ?", (context.args[0], update.message.from_user.id))
    conn.commit()
    await update.message.reply_text(f"✅ Reminder cancelled!" if cursor.rowcount > 0 else "❌ Reminder not found!", parse_mode='Markdown')

async def clearreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn, cursor = ensure_connection()
    cursor.execute("UPDATE reminders SET status = 'cancelled' WHERE user_id = ? AND status = 'pending'", (update.message.from_user.id,))
    conn.commit()
    await update.message.reply_text("✅ All reminders cleared!", parse_mode='Markdown')

# ================= FEEDBACK COMMANDS =================
async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📝 **Send Feedback**\n\nUsage: `/feedback [message]`", parse_mode='Markdown')
        return
    
    user = update.message.from_user
    feedback_text = " ".join(context.args)
    group_name = update.message.chat.title if update.message.chat.type in ['group', 'supergroup'] else None
    
    save_feedback(user.id, user.username, user.first_name, update.message.chat_id if group_name else None, group_name, feedback_text)
    await update.message.reply_text(f"✅ **Thank you for your feedback!** 🙏", parse_mode='Markdown')
    
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=f"📝 Feedback from {user.first_name}: {feedback_text}")
    except:
        pass

async def complaint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ **File a Complaint**\n\nUsage: `/complaint [message]`", parse_mode='Markdown')
        return
    
    user = update.message.from_user
    complaint_text = " ".join(context.args)
    group_name = update.message.chat.title if update.message.chat.type in ['group', 'supergroup'] else None
    
    complaint_id = save_complaint(user.id, user.username, user.first_name, update.message.chat_id if group_name else None, group_name, complaint_text)
    
    if complaint_id:
        await update.message.reply_text(f"⚠️ **Complaint Registered**\n\n🆔 ID: `{complaint_id}`\n✅ Owner will review it soon.", parse_mode='Markdown')
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=f"⚠️ Complaint #{complaint_id} from {user.first_name}: {complaint_text}")
        except:
            pass
    else:
        await update.message.reply_text("❌ Failed to register complaint.")

async def complaint_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/complaintstatus [id]`", parse_mode='Markdown')
        return
    
    try:
        cid = int(context.args[0])
        conn, cursor = ensure_connection()
        cursor.execute("SELECT complaint_text, status, created_at FROM complaints WHERE id = ?", (cid,))
        result = cursor.fetchone()
        if result:
            await update.message.reply_text(f"⚠️ **Complaint #{cid}**\n\nIssue: {result[0]}\nStatus: {result[1].upper()}\nFiled: {result[2]}", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Complaint not found!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

# ================= USER STATS COMMANDS =================
async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_user_stats(update.message.from_user.id)
    if stats:
        await update.message.reply_text(f"📊 **Your Stats**\n\n💬 Total: {stats[0]}\n📊 Today: {stats[3]}\n📅 Joined: {stats[1]}\n⏰ Last: {stats[2]}", parse_mode='Markdown')
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
        [InlineKeyboardButton("🌐 Language", callback_data="set_lang"),
         InlineKeyboardButton("📝 Style", callback_data="set_style")],
        [InlineKeyboardButton("🎨 Theme", callback_data="set_theme"),
         InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    await update.message.reply_text(f"⚙️ **Settings**\n\nLanguage: {prefs['language']}\nStyle: {prefs['response_style']}\nTheme: {prefs['theme']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

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

async def group_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage: `/groupbroadcast [message]`", parse_mode='Markdown')
        return
    groups = get_all_groups()
    sent = 0
    status = await update.message.reply_text(f"📢 Broadcasting to {len(groups)} groups...")
    for gid, name in groups:
        try:
            await context.bot.send_message(chat_id=gid, text=message)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await status.edit_text(f"✅ Sent to {sent} groups!")

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
    cursor.execute("SELECT COUNT(*) FROM notes")
    notes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM flashcards")
    cards = cursor.fetchone()[0]
    
    text = f"""
📊 **BOT STATISTICS**

👥 **Users:** {len(users)}
👥 **Groups:** {len(groups)}
💬 **Chats:** {chats}
📝 **Feedback:** {feedbacks}
⚠️ **Complaints:** {complaints}
📚 **Notes:** {notes}
🃏 **Flashcards:** {cards}

**Status:** 🟢 Active
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
    await update.message.reply_text("✅ Group added!")

async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/removegroup [group_id]`", parse_mode='Markdown')
        return
    conn, cursor = ensure_connection()
    cursor.execute("UPDATE groups SET is_active = 0 WHERE group_id = ?", (int(context.args[0]),))
    conn.commit()
    await update.message.reply_text("✅ Group removed!")

async def get_all_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    conn, cursor = ensure_connection()
    cursor.execute("SELECT id, username, user_name, feedback_text, created_at FROM feedback ORDER BY created_at DESC LIMIT 30")
    fb = cursor.fetchall()
    if not fb:
        await update.message.reply_text("📭 No feedback yet!")
        return
    text = "📝 **Recent Feedback:**\n\n"
    for f in fb:
        text += f"🆔 `{f[0]}` | {f[2]} (@{f[1]})\n📝 {f[3][:100]}\n📅 {f[4]}\n\n"
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
        await update.message.reply_text("❌ Usage: `/resolve [id]`", parse_mode='Markdown')
        return
    try:
        cid = int(context.args[0])
        conn, cursor = ensure_connection()
        cursor.execute("SELECT user_id FROM complaints WHERE id = ?", (cid,))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE complaints SET status = 'resolved', resolved_at = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cid))
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
        await update.message.reply_text("❌ Usage: `/block [user_id]`", parse_mode='Markdown')
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
        await update.message.reply_text("❌ Usage: `/unblock [user_id]`", parse_mode='Markdown')
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
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("✨ **Quick Image**\n\n.gen [prompt]", parse_mode='Markdown')
        return
    
    prompt = " ".join(parts[1:])
    msg = await update.message.reply_text("🎨 Generating...")
    filename = await generate_image(prompt)
    if filename:
        with open(filename, "rb") as f:
            await update.message.reply_photo(photo=f, caption=f"🖼️ {prompt}")
        os.remove(filename)
        await msg.delete()
    else:
        await msg.edit_text("❌ Failed!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or update.message.from_user.is_bot:
        return
    
    conn, cursor = ensure_connection()
    cursor.execute("SELECT is_blocked FROM users WHERE id = ?", (update.message.from_user.id,))
    result = cursor.fetchone()
    if result and result[0] == 1:
        return
    
    if update.message.text and update.message.text.startswith(".gen"):
        await handle_gen_command(update, context)
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
        await query.edit_message_text("📚 **Study Commands**\n\n/notes [topic]\n/explain [topic]\n/mcq [topic]\n/pyq [subject]\n/doubt [q]\n/quiz [topic] [q]", parse_mode='Markdown')
    elif data == "pdf_help":
        await query.edit_message_text("📄 **PDF Commands**\n\n/pdf [topic] - Complete PDF with diagram\n/pdfnotes [topic] - Simple PDF\n/pdfdiagram [topic] - PDF with diagram only", parse_mode='Markdown')
    elif data == "creative":
        await query.edit_message_text("🎨 **Creative Commands**\n\n/imagine [prompt]\n/draw [prompt]\n/voice [text]\n.gen [prompt]\n/analyze", parse_mode='Markdown')
    elif data == "notes_menu":
        await query.edit_message_text("📝 **Note Commands**\n\n/addnote [title] [content]\n/mynotes\n/editnote [id] [content]\n/deletenote [id]", parse_mode='Markdown')
    elif data == "flashcards_menu":
        await query.edit_message_text("🃏 **Flashcard Commands**\n\n/addcard [q] [a]\n/mycards\n/study", parse_mode='Markdown')
    elif data == "reminders":
        await query.edit_message_text("⏰ **Reminder Commands**\n\n/remind [time] [msg]\n/myreminders\n/cancel [id]\n/clearreminders", parse_mode='Markdown')
    elif data == "stats":
        stats = get_user_stats(user_id)
        if stats:
            await query.edit_message_text(f"📊 **Your Stats**\n\n💬 Total: {stats[0]}\n📊 Today: {stats[3]}\n📅 Joined: {stats[1]}", parse_mode='Markdown')
        else:
            await query.edit_message_text("No stats found", parse_mode='Markdown')
    elif data == "settings":
        prefs = get_user_preferences(user_id)
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_lang"),
             InlineKeyboardButton("📝 Style", callback_data="set_style")],
            [InlineKeyboardButton("🎨 Theme", callback_data="set_theme"),
             InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ]
        await query.edit_message_text(f"⚙️ **Settings**\n\nLanguage: {prefs['language']}\nStyle: {prefs['response_style']}\nTheme: {prefs['theme']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "set_lang":
        keyboard = [[InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"), InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi")], [InlineKeyboardButton("🔙 Back", callback_data="settings")]]
        await query.edit_message_text("🌐 **Select Language**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("lang_"):
        set_user_preference(user_id, "language", data.replace("lang_", ""))
        await query.edit_message_text("✅ Language set!")
    elif data == "set_style":
        keyboard = [[InlineKeyboardButton("📌 Concise", callback_data="style_concise"), InlineKeyboardButton("⚖️ Balanced", callback_data="style_balanced")], [InlineKeyboardButton("📚 Detailed", callback_data="style_detailed"), InlineKeyboardButton("🔙 Back", callback_data="settings")]]
        await query.edit_message_text("📝 **Response Style**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("style_"):
        set_user_preference(user_id, "response_style", data.replace("style_", ""))
        await query.edit_message_text("✅ Style set!")
    elif data == "set_theme":
        keyboard = [[InlineKeyboardButton("🌞 Light", callback_data="theme_light"), InlineKeyboardButton("🌙 Dark", callback_data="theme_dark")], [InlineKeyboardButton("🔙 Back", callback_data="settings")]]
        await query.edit_message_text("🎨 **Select Theme**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("theme_"):
        set_user_preference(user_id, "theme", data.replace("theme_", ""))
        await query.edit_message_text("✅ Theme set!")
    elif data == "clear_history":
        clear_user_history(user_id)
        await query.edit_message_text("✅ Chat history cleared!")
    elif data == "back_main":
        keyboard = [
            [InlineKeyboardButton("📚 Study", callback_data="study_help"), InlineKeyboardButton("📄 PDF", callback_data="pdf_help")],
            [InlineKeyboardButton("🎨 Creative", callback_data="creative"), InlineKeyboardButton("📝 Notes", callback_data="notes_menu")],
            [InlineKeyboardButton("🃏 Flashcards", callback_data="flashcards_menu"), InlineKeyboardButton("⏰ Reminders", callback_data="reminders")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings"), InlineKeyboardButton("📊 Stats", callback_data="stats")]
        ]
        await query.edit_message_text("🌟 **Welcome back!**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("show_answer_"):
        card_id = int(data.split("_")[2])
        conn, cursor = ensure_connection()
        cursor.execute("SELECT question, answer FROM flashcards WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        if result:
            await query.edit_message_text(f"❓ **Question:** {result[0]}\n\n💡 **Answer:** {result[1]}", parse_mode='Markdown')

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

# ================= POST INIT =================
async def post_init(application):
    logger.info(f"🚀 Study Controller Bot Started!")
    logger.info(f"Bot: @{application.bot.username}")
    logger.info("PDF Generation with Diagrams: ✅ Active")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", user_stats))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("daily", daily_usage))
    
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
    
    # PDF commands
    app.add_handler(CommandHandler("pdf", pdf_full))
    app.add_handler(CommandHandler("pdfnotes", pdf_notes))
    app.add_handler(CommandHandler("pdfdiagram", pdf_diagram))
    
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
    app.add_handler(CommandHandler("feedbacklist", get_all_feedback))
    app.add_handler(CommandHandler("complaintslist", get_all_complaints))
    app.add_handler(CommandHandler("resolve", resolve_complaint))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("unblock", unblock_user))
    
    # Callback handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Main message handler
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, handle_message))
    
    # Job queue
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_reminders, interval=30, first=10)
    
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
