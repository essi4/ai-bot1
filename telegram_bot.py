import logging
import requests
import os
import json
import httpx
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN = "8764134577:AAEPIJZgsRDlrbALWTf_pif7ny81pcwB5lc"
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CARD_NUMBER = os.environ.get("CARD_NUMBER", "XXXX")
CARD_NAME = os.environ.get("CARD_NAME", "نام")
FREE_LIMIT = 10

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DB_FILE = "users.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

def get_user(user_id):
    db = load_db()
    if user_id not in db:
        db[user_id] = {"premium": False, "messages_today": 0, "last_date": str(datetime.now().date())}
        save_db(db)
    return db[user_id]

def update_user(user_id, data):
    db = load_db()
    if user_id not in db:
        db[user_id] = {}
    db[user_id].update(data)
    save_db(db)

def reset_daily_if_needed(user_id):
    user = get_user(user_id)
    today = str(datetime.now().date())
    if user["last_date"] != today:
        update_user(user_id, {"messages_today": 0, "last_date": today})

def can_send_message(user_id):
    reset_daily_if_needed(user_id)
    user = get_user(user_id)
    if user["premium"]:
        return True
    return user["messages_today"] < FREE_LIMIT

def increment_message(user_id):
    user = get_user(user_id)
    update_user(user_id, {"messages_today": user["messages_today"] + 1})

async def ask_claude(question):
    headers = {
        "x-api-key": CLAUDE_AP
