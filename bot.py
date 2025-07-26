# bot.py
import types, sys
# Monkey-patch imghdr stub for Python 3.13 compatibility
if 'imghdr' not in sys.modules:
    mod = types.ModuleType('imghdr')
    mod.what = lambda *args, **kwargs: None
    sys.modules['imghdr'] = mod

import os
import asyncio
import logging
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
import time

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Flask app to keep bot alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return 'Bot is running', 200

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
}

# Переводы отслеживаемых предметов на русский
ITEM_NAME_RU = {
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
    name = active.get("weather_name")
    eid = active.get("weather_id")
    emoji = WEATHER_EMOJI.get(eid, "☁️")
    end_ts = active.get("end_duration_unix", 0)
    ends = datetime.fromtimestamp(end_ts, tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M MSK") if end_ts else "--"
    dur = active.get("duration", 0)
    return (f"━ {emoji} *Погода* ━\n"
            f"*Текущая:* {name}\n"
            f"*Заканчивается в:* {ends}\n"
            f"*Длительность:* {dur} сек")

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода", callback_data="show_weather")]
    ]
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cooldown 10 sec for stock button
    last = context.user_data.get("last_stock", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного прежде чем снова нажать", show_alert=True)
        return
    context.user_data["last_stock"] = time.time()
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    for sec in ["seed_stock","gear_stock","egg_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_cosmetic", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного прежде чем снова нажать", show_alert=True)
        return
    context.user_data["last_cosmetic"] = time.time()
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Mосква")).strftime("%d.%m.%Y %H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n" + format_block("cosmetic_stock", data.get("cosmetic_stock", []))
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = context.user_data.get("last_weather", 0)
    if time.time() - last < 10:
        await update.callback_query.answer("⏳ Подожди немного прежде чем снова нажать", show_alert=True)
        return
    context.user_data["last_weather"] = time.time()
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    weather = fetch_weather()
    await tgt.reply_markdown(format_weather_block(weather))

# Command wrappers
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_stock(update, context)

async def cosmetic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_cosmetic(update, context)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_weather(update, context)

# Notification Task
def compute_delay():
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    minute = now.minute
    next_min = ((minute // 5) + 1) * 5
    hour = now.hour
    if next_min >= 60:
        next_min = 0
        hour = (hour + 1) % 24
    next_run = now.replace(hour=hour, minute=next_min, second=7, microsecond=0)
    delta = (next_run - now).total_seconds()
    if delta < 0:
        delta += 24*3600
    return delta

async def monitor_stock(app):
    while True:
        delay = compute_delay()
        logging.info(f"Sleeping {delay:.1f}s until next check...")
        await asyncio.sleep(delay)
        data = fetch_all_stock()
        ts = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")
        for section in ["seed_stock","gear_stock","egg_stock","cosmetic_stock"]:
            for it in data.get(section, []):
                iid, qty = it.get("item_id"), it.get("quantity",0)
                if iid in NOTIFY_ITEMS and qty > 0:
                    # Получаем и форматируем цену
                    price = PRICE_MAP.get(iid)
                    price_str = f"{price:,}¢" if price is not None else "—"
                    msg = (
                        f"*{ITEM_EMOJI[iid]} {it.get('display_name')}: x{qty} в стоке!*\n"
                        f"💰 Цена — {price_str}\n"
                        f"🕒 {ts}\n"
                        f"\n*@GroowAGarden*")
                    logging.info(f"Notify {iid} x{qty}")
                    await app.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")

# Application setup
async def post_init(app):
    app.create_task(monitor_stock(app))

    # Start Flask in separate thread
def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()


app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .post_init(post_init)
    .build()
)
# Register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stock", stock_command))
app.add_handler(CommandHandler("cosmetic", cosmetic_command))
app.add_handler(CommandHandler("weather", weather_command))
app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
app.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
app.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT",5000)),
        webhook_url=f"https://{os.getenv('DOMAIN')}/webhook/{BOT_TOKEN}"
    )
    print("Listening on port", os.getenv("PORT"))