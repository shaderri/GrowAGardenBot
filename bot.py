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
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Endpoints
SEEDS_API    = (
    "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?"
    "select=*&type=eq.seeds_stock&active=eq.true&"
    "created_at=gte.2025-07-05T09%3A15%3A00.000Z&order=created_at.desc"
)
GEAR_API     = (
    "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?"
    "select=*&type=eq.gear_stock&active=eq.true&"
    "created_at=gte.2025-07-05T09%3A15%3A00.000Z&order=created_at.desc"
)
EGG_API      = (
    "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?"
    "select=*&type=eq.egg_stock&active=eq.true&order=created_at.desc"
)
# EVENT_API    = "https://growagardenstock.com/api/special-stock?type=honey"
COSMETIC_API = "https://growagardenstock.com/api/special-stock?type=cosmetics"
WEATHER_API  = "https://api.joshlei.com/v2/growagarden/weather"

HEADERS = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZleHRiemF0cHBybmtzeXV0YmNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcxODQwODEsImV4cCI6MjA2Mjc2MDA4MX0.NKrxJnejTBezJ9R1uKE1B1bTp6Pgq5SMiqpAokCC_-o",
    "Authorization": f"Bearer {"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZleHRiemF0cHBybmtzeXV0YmNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcxODQwODEsImV4cCI6MjA2Mjc2MDA4MX0.NKrxJnejTBezJ9R1uKE1B1bTp6Pgq5SMiqpAokCC_-o"}"
}

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "egg": "🥚",
    "event": "🎉", "cosmetic": "💄", "weather": "☁️"
}
ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "tomato": "🍅", "banana": "🍌",
    "cauliflower": "🥦", "watermelon": "🍉", "rafflesia": "🌺", "green_apple": "🍏",
    "avocado": "🥑", "pineapple": "🍍", "kiwi": "🥝", "bell_pepper": "🌶️",
    "prickly_pear": "🌵", "loquat": "🍑", "feijoa": "🥝", "pitcher_plant": "🌱", "sugar_apple": "🍎",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝",
    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",
    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "wood_pile": "🪵", "lemonade_stand": "🍋",
    # Additional cosmetics emojis
    "shovel": "🕳️", "brown_stone_pillar": "🪨", "large_path_tile": "🛤️",
    "cooking_pot": "🍲", "large_stone_pad": "🪨", "rock_pile": "⛰️", "bookshelf": "📚"
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

def parse_stock_entries(entries: list) -> list:
    parsed = []
    for entry in entries:
        m = re.match(r"(.+?) \*\*x(\d+)\*\*", entry)
        if not m:
            continue
        name = m.group(1)
        qty = int(m.group(2))
        key = name.lower().replace(" ", "_").replace("'", "")
        parsed.append({"item_id": key, "display_name": name, "quantity": qty})
    return parsed


def parse_supabase(entries: list) -> list:
    result = []
    for e in entries:
        if isinstance(e, dict):
            name = e.get("display_name")
            key = e.get("item_id")
            qty = e.get("multiplier", 1)
            if name and key:
                result.append({"item_id": key, "display_name": name, "quantity": qty})
    return result

# Fetch functions

def fetch_all_stock() -> dict:
    seeds_resp = requests.get(SEEDS_API, headers=HEADERS)
    gear_resp = requests.get(GEAR_API, headers=HEADERS)
    eggs_resp = requests.get(EGG_API, headers=HEADERS)
    seeds = seeds_resp.json() if seeds_resp.headers.get('content-type','').startswith('application/json') else []
    gear = gear_resp.json() if gear_resp.headers.get('content-type','').startswith('application/json') else []
    eggs = eggs_resp.json() if eggs_resp.headers.get('content-type','').startswith('application/json') else []
    return {
        "seeds": parse_supabase(seeds),
        "gear": parse_supabase(gear),
        "egg": parse_supabase(eggs),
        # "event": parse_stock_entries(ev.get("honey", []))
    }
    # else []
    # ev = requests.get(EVENT_API).json()


def fetch_cosmetic() -> list:
    cr = requests.get(COSMETIC_API).json()
    return parse_stock_entries(cr.get("cosmetics", []))


def fetch_weather() -> list:
    return requests.get(WEATHER_API).json().get("weather", [])

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


def format_weather(weather_list: list) -> str:
    active = next((w for w in weather_list if w.get("active")), None)
    if not active:
        return "**━ ☁️ Погода ━**\nНет активных погодных событий"
    name = active.get("weather_name")
    eid = active.get("weather_id")
    emoji = WEATHER_EMOJI.get(eid, "☁️")
    end_ts = active.get("end_duration_unix", 0)
    if end_ts:
        dt = datetime.fromtimestamp(end_ts, tz=ZoneInfo("Europe/Moscow"))
        ends_str = dt.strftime("%H:%M MSK")
    else:
        ends_str = "--"
    dur = active.get("duration", 0)
    lines = [
        f"━ {emoji} *Погода* ━",
        f"*Текущая:* {name}",
        f"*Заканчивается в:* {ends_str}",
        f"*Длительность:* {dur} сек"
    ]
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
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query: await update.callback_query.answer()
    stock = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n*📊 Стоки Grow a Garden:*\n\n"
    for cat in ["seeds","gear","egg","event"]:
        text += format_block(cat, stock[cat])
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query: await update.callback_query.answer()
    items = fetch_cosmetic()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n*💄 Косметический сток:*\n\n" + format_block("cosmetic", items)
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query: await update.callback_query.answer()
    await tgt.reply_markdown(format_weather(fetch_weather()))

# Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck(): return "OK"

# Run
if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000))), daemon=True).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CommandHandler("cosmetic", handle_cosmetic))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    bot.run_polling()