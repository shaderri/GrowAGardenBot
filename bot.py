import types, sys
# Monkey-patch imghdr stub for Python 3.13 compatibility
if 'imghdr' not in sys.modules:
    mod = types.ModuleType('imghdr')
    mod.what = lambda *args, **kwargs: None
    sys.modules['imghdr'] = mod

import os
import asyncio
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
import requests
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from flask import Flask
import threading

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
KEEPALIVE_PORT = int(os.getenv("PORT", 10000))

# Flask app to keep bot alive
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return 'Bot is running', 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=KEEPALIVE_PORT)

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "egg": "🥚", "cosmetic": "💄", "weather": "☁️"
}

ITEM_EMOJI = {
    # ... (остальные эмодзи) ...
    "grape": "🍇",
    "mushroom": "🍄",
    "pepper": "🌶️",
    "cacao": "🍫",
    "beanstalk": "🫛",
    "ember_lily": "🌸",
    "sugar_apple": "🍏",
    "burning_bud": "🔥",
    "giant_pinecone": "🌰",
    "master_sprinkler": "🌧️",
    "levelup_lollipop": "🍭",
    "elder_strawberry": "🍓",
    "paradise_egg": "🐣",
    "bug_egg": "🐣",
}

# Переводы отслеживаемых предметов на русский
ITEM_NAME_RU = {
    "paradise_egg": "Райское яйцо",
    "bug_egg": "Яйцо Жука",
    "grape": "Виноград",
    "mushroom": "Грибы",
    "pepper": "Перец",
    "cacao": "Какао",
    "beanstalk": "Бобовый стебель",
    "ember_lily": "Эмбер лили",
    "sugar_apple": "Сахарное яблоко",
    "burning_bud": "Горящий бутон",
    "giant_pinecone": "Гигантская шишка",
    "master_sprinkler": "Мастер спринклер",
    "levelup_lollipop": "Леденец уровня",
    "elder_strawberry": "Бузинная клубника"
}

# Items to notify about
NOTIFY_ITEMS = [
    "grape", "mushroom", "pepper", "cacao",
    "beanstalk", "ember_lily", "sugar_apple",
    "burning_bud", "giant_pinecone",
    "master_sprinkler", "levelup_lollipop", "elder_strawberry"
]

# Prices for notifications (in ¢)
PRICE_MAP = {
    "paradise_egg": 50_000_000,
    "bug_egg": 50_000_000,
    "grape": 850_000,
    "mushroom": 150_000,
    "pepper": 1_000_000,
    "cacao": 2_500_000,
    "beanstalk": 10_000_000,
    "ember_lily": 15_000_000,
    "sugar_apple": 25_000_000,
    "burning_bud": 40_000_000,
    "giant_pinecone": 55_000_000,
    "master_sprinkler": 10_000_000,
    "levelup_lollipop": 10_000_000_000,
    "elder_strawberry": 70_000_000
}

# APIs
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

# Fetchers
def fetch_all_stock():
    try:
        r = requests.get(STOCK_API, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error(f"Stock fetch error: {e}")
        return {}

def fetch_weather():
    try:
        r = requests.get(WEATHER_API, timeout=10)
        r.raise_for_status()
        return r.json().get("weather", [])
    except Exception as e:
        logging.error(f"Weather fetch error: {e}")
        return []

# Formatters
def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key.replace("_stock", ""), "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get("item_id"), "•")
        lines.append(f"   {em} {it.get('display_name')}: x{it.get('quantity',0)}")
    return "\n".join(lines) + "\n\n"

def format_weather_block(weather_list: list) -> str:
    active = next((w for w in weather_list if w.get("active")), None)
    if not active:
        return "━ ☁️ *Погода* ━\nНет активных погодных событий"
    emoji = CATEGORY_EMOJI.get("weather", "☁️")
    end_ts = active.get("end_duration_unix", 0)
    ends = datetime.fromtimestamp(end_ts, tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK") if end_ts else "--"
    return f"━ {emoji} *Погода* ━\n*Текущая:* {active.get('weather_name')}\n*Заканчивается в:* {ends}\n*Длительность:* {active.get('duration',0)} сек"

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
          [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
          [InlineKeyboardButton("☁️ Погода", callback_data="show_weather")]]
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_stock", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного", show_alert=True)
        return
    context.user_data["last_stock"] = time.time()
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    for sec in ["seed_stock","gear_stock","egg_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_cosmetic", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного", show_alert=True)
        return
    context.user_data["last_cosmetic"] = time.time()
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n" + format_block("cosmetic_stock", data.get("cosmetic_stock", []))
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_weather", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного", show_alert=True)
        return
    context.user_data["last_weather"] = time.time()
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    weather = fetch_weather()
    await tgt.reply_markdown(format_weather_block(weather))

# Scheduling helpers
def compute_delay():
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    next_min = ((now.minute // 5) + 1) * 5
    hour = now.hour + (next_min // 60)
    minute = next_min % 60
    run = now.replace(hour=hour%24, minute=minute, second=7, microsecond=0)
    delta = (run - now).total_seconds()
    return delta if delta>0 else delta + 86400

def compute_egg_delay():
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    if now.minute < 30:
        minute, hour = 30, now.hour
    else:
        minute, hour = 0, (now.hour+1)%24
    run = now.replace(hour=hour, minute=minute, second=7, microsecond=0)
    delta = (run - now).total_seconds()
    return delta if delta>0 else delta + 86400

# Notification tasks
async def monitor_stock(app):
    while True:
        await asyncio.sleep(compute_delay())
        data = fetch_all_stock()
        now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
        for sec in ["seed_stock","gear_stock","cosmetic_stock"]:
            for it in data.get(sec, []):
                iid, qty = it.get("item_id"), it.get("quantity",0)
                if iid in NOTIFY_ITEMS and qty>0:
                    msg = (f"*{ITEM_EMOJI[iid]} {ITEM_NAME_RU.get(iid,it['display_name'])}: x{qty} в стоке!*\n"
                           f"💰 Цена — {PRICE_MAP[iid]:,}¢\n"
                           f"🕒 {now}\n\n*@GroowAGarden*")
                    await app.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")

async def monitor_egg(app):
    while True:
        await asyncio.sleep(compute_egg_delay())
        data = fetch_all_stock()
        now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
        for it in data.get("egg_stock", []):
            iid, qty = it.get("item_id"), it.get("quantity",0)
            if iid in ["paradise_egg","bug_egg"] and qty>0:
                msg = (f"*{ITEM_EMOJI[iid]} {ITEM_NAME_RU.get(iid,it['display_name'])}: x{qty} в стоке!*\n"
                       f"💰 Цена — {PRICE_MAP[iid]:,}¢\n"
                       f"🕒 {now}\n\n*@GroowAGarden*")
                await app.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")

# Application setup
async def post_init(app):
    app.create_task(monitor_stock(app))
    app.create_task(monitor_egg(app))

app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stock", handle_stock))
app.add_handler(CommandHandler("cosmetic", handle_cosmetic))
app.add_handler(CommandHandler("weather", handle_weather))
app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
app.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
app.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))

if __name__ == "__main__":
    # Start Flask keepalive server
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    # Start Telegram bot polling
    app.run_polling()