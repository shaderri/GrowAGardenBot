import os
import threading
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Endpoints
JOSH_URL    = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_URL = "https://growagardenstock.com/api/stock/weather"

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds":   "🌱",
    "gear":    "🧰",
    "egg":     "🥚",
    "event":   "🎉",
    "weather": "☁️"
}
ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "tomato": "🍅", "banana": "🍌",
    "cauliflower": "🥦", "watermelon": "🍉", "rafflesia": "🌺", "green_apple": "🍏",
    "avocado": "🥑", "pineapple": "🍍", "kiwi": "🥝", "bell_pepper": "🌶️",
    "prickly_pear": "🌵", "loquat": "🍑", "feijoa": "🥝", "pitcher_plant": "🌱",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝",
    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐞", "common_summer_egg": "☀️", "rare_summer_egg": "🌞", "paradise_egg": "🐤", "bee_egg": "🐝",
    # Event
    "summer_seed_pack": "🌞", "delphinium": "🌸", "lily_of_the_valley_seed": "💐", "traveller_fruit_seed": "✈️", "burnt_mutation_spray": "🔥", "oasis_crate": "🏝️", "oasis_egg": "🥚", "hamster": "🐹"
}

# Fetch all stock
def fetch_all_stock():
    r = requests.get(JOSH_URL)
    if not r.ok:
        return {"seeds":[], "gear":[], "egg":[], "event":[]}
    data = r.json()
    return {
        "seeds": data.get("seed_stock", []),
        "gear":  data.get("gear_stock", []),
        "egg":   data.get("egg_stock", []),
        "event": data.get("eventshop_stock", [])
    }

# Format a stock category block
def format_block(category: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI[category]
    title = category.capitalize() + " Stock"
    lines = [f"**━ {emoji} {title} ━**"]
    for it in items:
        key = it.get("item_id", "").lower()
        name = it.get("display_name", key.title())
        qty  = it.get("quantity", 0)
        em   = ITEM_EMOJI.get(key, "•")
        lines.append(f"   {em} {name}: x{qty}")
    return "\n".join(lines) + "\n\n"

# Fetch weather
def fetch_weather():
    ts = int(time.time() * 1000)
    r = requests.get(WEATHER_URL, params={"ts": ts, "_": ts})
    return r.json() if r.ok else {}

# Format weather block
def format_weather(data: dict) -> str:
    icon = data.get("icon", "☁️")
    current = data.get("currentWeather", "")
    updated = data.get("updatedAt", 0)
    # convert updatedAt ms to MSK
    try:
        dt = datetime.fromtimestamp(updated/1000, tz=ZoneInfo("Europe/Moscow"))
        time_str = dt.strftime("%d.%m.%Y %H:%M:%S MSK")
    except:
        time_str = ""
    effect = data.get("effectDescription", "").strip()
    # Remove Ends lines
    lines_effect = [line for line in effect.splitlines() if not line.startswith("- Ends:")]

    lines = [f"**━ {icon} Погода ━**"]
    if current.lower() == "sunny":
        lines.append("**❗ Нет активной погоды в данный момент**")
    else:
        lines.append(f"**Текущая погода:** {current}")
        lines.append(f"**Обновлено:** {time_str}")
        lines.append(f"**Длительность:** {lines_effect[1].replace('- Duration:', '').strip()}")
    if lines_effect:
        lines.append("\n**Последняя погода:**")
        lines.extend(lines_effect)
    return "\n".join(lines)

# Keyboard layout
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
    stock = fetch_all_stock()
    dt = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    header = f"**🕒 {dt.strftime('%d.%m.%Y %H:%M:%S MSK')}**\n\n**📊 Стоки Grow a Garden:**\n\n"
    text = header
    for cat in ["seeds", "gear", "egg", "event"]:
        text += format_block(cat, stock.get(cat, []))
    await target.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    data = fetch_weather()
    text = format_weather(data)
    await target.reply_markdown(text)

# Flask healthcheck
app = Flask(__name__)
@app.route("/")
def home():
    return "Grow a Garden Bot is running!"