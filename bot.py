import os
import threading
import requests
import time
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo

# Load environment\load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# New Endpoints
GEAR_SEEDS_URL = "https://growagardenstock.com/api/stock?type=gear-seeds"
EGG_URL        = "https://growagardenstock.com/api/stock?type=egg"
EVENT_URL      = "https://growagardenstock.com/api/special-stock?type=honey"
WEATHER_URL    = "https://growagardenstock.com/api/stock/weather"

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds":   "🌱",
    "gear":    "🧰",
    "egg":     "🥚",
    "event":   "🎉",
    "weather": "☁️"
}
ITEM_EMOJI = {
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "tomato": "🍅",
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "common_egg": "🥚", "common_summer_egg": "🥚",
    "summer_seed_pack": "🌞", "delphinium": "🌸"
}

# Helper to parse entries like "Item Name **xN**"
def parse_stock_entries(entries: list) -> list:
    parsed = []
    for entry in entries:
        match = re.match(r"(.+?) \*\*x(\d+)\*\*", entry)
        if not match:
            continue
        name = match.group(1)
        qty  = int(match.group(2))
        key  = name.lower().replace(" ", "_").replace("'", "")
        parsed.append({"item_id": key, "display_name": name, "quantity": qty})
    return parsed

# Fetch all stock
def fetch_all_stock() -> dict:
    ts = int(time.time() * 1000)
    r1 = requests.get(GEAR_SEEDS_URL, params={"ts": ts})
    gs = r1.json() if r1.ok else {}
    gear_list  = parse_stock_entries(gs.get("gear", []))
    seeds_list = parse_stock_entries(gs.get("seeds", []))

    r2 = requests.get(EGG_URL, params={"ts": ts + 2})
    eg = r2.json() if r2.ok else {}
    egg_list = parse_stock_entries(eg.get("egg", []))

    r3 = requests.get(EVENT_URL, params={"ts": ts + 4})
    ev = r3.json() if r3.ok else {}
    event_list = parse_stock_entries(ev.get("honey", []))

    return {"seeds": seeds_list, "gear": gear_list, "egg": egg_list, "event": event_list}

# Format blocks
def format_block(category: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI[category]
    lines = [f"━ {emoji} **{category.capitalize()}** ━"]
    for it in items:
        key = it["item_id"]
        lines.append(f"   {ITEM_EMOJI.get(key, '•')} {it['display_name']}: x{it['quantity']}")
    return "\n".join(lines) + "\n\n"

# Fetch weather
def fetch_weather():
    ts = int(time.time() * 1000)
    r = requests.get(WEATHER_URL, params={"ts": ts, "_": ts})
    return r.json() if r.ok else {}

# Format weather
def format_weather(data: dict) -> str:
    icon    = data.get("icon", "☁️")
    current = data.get("currentWeather", "--")
    ends    = data.get("ends")
    dur     = data.get("duration")
    ends_str = None
    if ends:
        try:
            t = datetime.strptime(ends, "%H:%M") + timedelta(hours=3)
            ends_str = t.time().strftime("%H:%M")
        except:
            ends_str = ends
    parts = [f"**━ {icon} Погода ━**", f"**Текущая:** {current}"]
    if ends_str: parts.append(f"**Заканчивается в:** {ends_str}")
    if dur:      parts.append(f"**Длительность:** {dur}")
    return "\n".join(parts)

# Keyboard
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")],
        [InlineKeyboardButton("☁️ Показать погоду", callback_data="show_weather")]
    ])

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    stock   = fetch_all_stock()
    dt      = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    header  = f"**🕒 {dt.strftime('%d.%m.%Y %H:%M:%S MSK')}**\n\n**📊 Стоки Grow a Garden:**\n\n"
    text    = header + "".join(format_block(c, stock[c]) for c in ["seeds","gear","egg","event"] )
    await target.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    await target.reply_markdown(format_weather(fetch_weather()))

# Initialize Telegram bot
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
telegram_app.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))

# Запуск polling в фоне
threading.Thread(target=lambda: telegram_app.run_polling(), daemon=True).start()

# Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
