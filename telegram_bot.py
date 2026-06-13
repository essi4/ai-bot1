import logging
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

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # آیدی عددی تلگرام ادمین
CARD_NUMBER = os.environ.get("CARD_NUMBER", "6037-XXXX-XXXX-XXXX")
CARD_NAME = os.environ.get("CARD_NAME", "نام صاحب کارت")
PREMIUM_PRICE = "30,000 تومان"
FREE_LIMIT = 10

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- دیتابیس ساده (فایل JSON) ---
DB_FILE = "users.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

def get_user(user_id: str):
    db = load_db()
    if user_id not in db:
        db[user_id] = {
            "premium": False,
            "messages_today": 0,
            "last_date": str(datetime.now().date()),
            "name": ""
        }
        save_db(db)
    return db[user_id]

def update_user(user_id: str, data: dict):
    db = load_db()
    if user_id not in db:
        db[user_id] = {}
    db[user_id].update(data)
    save_db(db)

def reset_daily_if_needed(user_id: str):
    user = get_user(user_id)
    today = str(datetime.now().date())
    if user["last_date"] != today:
        update_user(user_id, {"messages_today": 0, "last_date": today})

def can_send_message(user_id: str) -> bool:
    reset_daily_if_needed(user_id)
    user = get_user(user_id)
    if user["premium"]:
        return True
    return user["messages_today"] < FREE_LIMIT

def increment_message(user_id: str):
    user = get_user(user_id)
    update_user(user_id, {"messages_today": user["messages_today"] + 1})

# --- Claude API ---
async def ask_claude(question: str) -> str:
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": question}]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=30
        )
        data = response.json()
        if "content" in data and len(data["content"]) > 0:
            return data["content"][0]["text"]
        elif "error" in data:
            return f"خطا از سرور: {data['error']['message']}"
        else:
            return "متاسفم، مشکلی پیش اومد."

# --- هندلرها ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    update_user(user_id, {"name": user.first_name})

    keyboard = [
        [InlineKeyboardButton("💎 پریمیوم بشم", callback_data="premium")],
        [InlineKeyboardButton("📊 وضعیت من", callback_data="status")],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"سلام {user.first_name}! 👋\n\n"
        f"من یه دستیار هوش مصنوعی فارسی هستم!\n\n"
        f"🆓 رایگان: {FREE_LIMIT} پیام در روز\n"
        f"💎 پریمیوم: نامحدود — {PREMIUM_PRICE} در ماه\n\n"
        f"هر سوالی داری بپرس! 🤖",
        reply_markup=markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text

    if not can_send_message(user_id):
        keyboard = [[InlineKeyboardButton("💎 پریمیوم بشم", callback_data="premium")]]
        markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"❌ امروز {FREE_LIMIT} پیام رایگانت تموم شد!\n\n"
            f"برای استفاده نامحدود پریمیوم بشو 👇",
            reply_markup=markup
        )
        return

    thinking = await update.message.reply_text("🤔 در حال فکر کردن...")

    try:
        answer = await ask_claude(text)
        increment_message(user_id)
        user = get_user(user_id)

        remaining = ""
        if not user["premium"]:
            left = FREE_LIMIT - user["messages_today"]
            remaining = f"\n\n📊 پیام‌های باقی‌مانده امروز: {left}/{FREE_LIMIT}"

        await thinking.edit_text(answer + remaining)

    except Exception as e:
        logger.error(f"خطا: {e}")
        await thinking.edit_text("❌ خطایی پیش اومد. دوباره امتحان کن.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    if query.data == "premium":
        await query.edit_message_text(
            f"💎 پریمیوم — {PREMIUM_PRICE} در ماه\n\n"
            f"✅ پیام نامحدود\n"
            f"✅ سرعت بیشتر\n"
            f"✅ اولویت پشتیبانی\n\n"
            f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
            f"👤 به نام: {CARD_NAME}\n\n"
            f"بعد از پرداخت، رسید رو به ادمین بفرست:\n"
            f"@admin_username",
            parse_mode="Markdown"
        )

    elif query.data == "status":
        user = get_user(user_id)
        reset_daily_if_needed(user_id)
        status = "💎 پریمیوم" if user["premium"] else "🆓 رایگان"
        left = "نامحدود" if user["premium"] else f"{FREE_LIMIT - user['messages_today']}/{FREE_LIMIT}"

        await query.edit_message_text(
            f"📊 وضعیت حساب شما:\n\n"
            f"🏷 نوع: {status}\n"
            f"💬 پیام‌های باقی‌مانده امروز: {left}"
        )

# --- دستورات ادمین ---
async def admin_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 1:
        await update.message.reply_text("استفاده: /addpremium USER_ID")
        return

    target_id = context.args[0]
    update_user(target_id, {"premium": True})
    await update.message.reply_text(f"✅ کاربر {target_id} پریمیوم شد!")

    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text="🎉 تبریک! حساب شما پریمیوم شد!\nحالا پیام‌های نامحدود داری! 💎"
        )
    except:
        pass

async def admin_remove_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 1:
        await update.message.reply_text("استفاده: /removepremium USER_ID")
        return

    target_id = context.args[0]
    update_user(target_id, {"premium": False})
    await update.message.reply_text(f"✅ پریمیوم کاربر {target_id} حذف شد!")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    db = load_db()
    total = len(db)
    premium = sum(1 for u in db.values() if u.get("premium"))

    await update.message.reply_text(
        f"📊 آمار ربات:\n\n"
        f"👥 کل کاربران: {total}\n"
        f"💎 کاربران پریمیوم: {premium}\n"
        f"🆓 کاربران رایگان: {total - premium}"
    )

# --- main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpremium", admin_premium))
    app.add_handler(CommandHandler("removepremium", admin_remove_premium))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ ربات هوش مصنوعی شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
