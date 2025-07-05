import os
import requests
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo
import threading

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Supabase API key
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY") or "eyJhbGci..."

# Endpoints
SEEDS_API    = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?select=*&type=eq.seeds_stock&active=eq.true&created_at=gte.2025-07-05T09%3A15%3A00.000Z&order=created_at.desc"
GEAR_API     = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?select=*&type=eq.gear_stock&active=eq.true&created_at=gte.2025-07-05T09%3A15%3A00.000Z&order=created_at.desc"
EGG_API      = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?select=*&type=eq.egg_stock&active=eq.true&order=created_at.desc"
EVENT_URL    = "https://growagardenstock.com/api/special-stock?type=honey"
COSMETIC_URL = "https://growagardenstock.com/api/special-stock?type=cosmetics"
WEATHER_API  = "https://api.joshlei.com/v2/growagarden/weather"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}"
}

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "egg": "🥚",
    "event": "🎉", "cosmetic": "💄", "weather": "☁️"
}
ITEM_EMOJI = {
    # ... прежние эмодзи для items ...
}
WEATHER_EMOJI = {
    "rain": "🌧️", "heatwave": "🔥", "summerharvest": "☀️",
    "tornado": "🌪️", "windy": "🌬️", "auroraborealis": "🌌",
    "tropicalrain": "🌴🌧️", "nightevent": "🌙", "sungod": "☀️",
    "megaharvest": "🌾", "gale": "🌬️", "thunderstorm": "⛈️",
    "bloodmoonevent": "🌕🩸", "meteorshower": "☄️", "spacetravel": "🪐",
    "disco": "💃", "djjhai": "🎵", "blackhole": "🕳️",
    "jandelstorm": "🌩️", "sandstorm": "🏜️"
}

# Helpers

def parse_supabase(entries: list) -> list:
    return [{
        "item_id": e.get("item_id"),
        "display_name": e.get("display_name"),
        "quantity": e.get("multiplier", 1)
    } for e in entries]

# Fetch functions

def fetch_all_stock() -> dict:
    seeds = requests.get(SEEDS_API, headers=HEADERS).json()
    gear = requests.get(GEAR_API, headers=HEADERS).json()
    eggs = requests.get(EGG_API, headers=HEADERS).json()
    ev = requests.get(EVENT_URL).json()
    return {
        "seeds": parse_supabase(seeds),
        "gear": parse_supabase(gear),
        "egg": parse_supabase(eggs),
        "event": parse_stock_entries(ev.get("honey", []))
    }

# New weather fetch & format

def fetch_weather() -> list:
    data = requests.get(WEATHER_API).json().get("weather", [])
    return data


def format_weather(weather_list: list) -> str:
    # find active
    active = next((w for w in weather_list if w.get("active")), None)
    if not active:
        return "**━ ☁️ Погода ━**\nНет активных погодных событий"
    name = active.get("weather_name")
    icon_url = active.get("icon")
    eid = active.get("weather_id")
    emoji = WEATHER_EMOJI.get(eid, "☁️")
    end_ts = active.get("end_duration_unix", 0)
    if end_ts:
        dt = datetime.fromtimestamp(end_ts, tz=ZoneInfo("Europe/Moscow"))
        ends_str = dt.strftime("%H:%M MSK")
    else:
        ends_str = "--"
    dur = active.get("duration", 0)
    lines = [f"━ {emoji} **Погода** ━", f"**Текущая:** {name}", f"**Заканчивается в:** {ends_str}", f"**Длительность:** {dur} сек"]
    return "\n".join(lines)

# ... остальной код (format_block, cosmetic, polling, Flask) без изменений ...

# Formatters

def format_block(category: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(category, "•")
    title = category.capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it['item_id'], "•")
        lines.append(f"   {em} {it['display_name']}: x{it['quantity']}")
    return "\n".join(lines) + "\n\n"


def format_weather(data: dict) -> str:
    icon = data.get("icon", "☁️")
    curr = data.get("currentWeather", "--")
    end_ms = data.get("endTime")
    dur = data.get("duration")
    ends_str = None
    if end_ms:
        try:
            dt = datetime.fromtimestamp(end_ms / 1000, tz=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Moscow"))
            ends_str = dt.strftime("%H:%M MSK")
        except:
            ends_str = "--"
    lines = [f"━ {icon} *Погода* ━", f"*Текущая:* {curr}"]
    if ends_str:
        lines.append(f"*Заканчивается в:* {ends_str}")
    if dur:
        lines.append(f"*Длительность:* {dur}")
    return "\n".join(lines)

# Keyboard layout
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода", callback_data="show_weather")]
    ])

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    stock = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n*📊 Стоки Grow a Garden:*\n\n"
    for cat in ["seeds", "gear", "egg", "event"]:
        text += format_block(cat, stock[cat])
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    items = fetch_cosmetic()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n*💄 Косметический сток:*\n\n"
    text += format_block("cosmetic", items)
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        tgt = update.callback_query.message
    else:
        tgt = update.message
    await tgt.reply_markdown(format_weather(fetch_weather()))

# Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "OK"

# Run
if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000))),
        daemon=True
    ).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    # Command handlers
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CommandHandler("cosmetic", handle_cosmetic))
    bot.add_handler(CommandHandler("weather", handle_weather))
    # Callback handlers
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    bot.run_polling()
