import os
import requests
import time
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo
import threading

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Endpoints
GEAR_SEEDS_URL   = "https://growagardenstock.com/api/stock?type=gear-seeds"
EGG_URL           = "https://growagardenstock.com/api/stock?type=egg"
EVENT_URL         = "https://growagardenstock.com/api/special-stock?type=honey"
COSMETIC_URL      = "https://growagardenstock.com/api/special-stock?type=cosmetics"
WEATHER_URL       = "https://growagardenstock.com/api/stock/weather"

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds":      "🌱",
    "gear":       "🧰",
    "egg":        "🥚",
    "event":      "🎉",
    "cosmetic":   "💄",
    "weather":    "☁️"
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
    # Event
    "summer_seed_pack": "🌞", "delphinium": "🌸", "lily_of_the_valley": "💐", "traveler's_fruit": "✈️", "mutation_spray_burnt": "🔥",
    "oasis_crate": "🏝️", "oasis_egg": "🥚", "hamster": "🐹",
    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "wood_pile": "🪵", "lemonade_stand": "🍋"
}

# Parse helper for entries like "Name **xN**"
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

# Fetch functions

def fetch_all_stock() -> dict:
    ts = int(time.time() * 1000)
    gs = requests.get(GEAR_SEEDS_URL, params={"ts": ts}).json()
    eg = requests.get(EGG_URL, params={"ts": ts + 1}).json()
    ev = requests.get(EVENT_URL, params={"ts": ts + 2}).json()
    return {
        "gear":   parse_stock_entries(gs.get("gear", [])),
        "seeds":  parse_stock_entries(gs.get("seeds", [])),
        "egg":    parse_stock_entries(eg.get("egg", [])),
        "event":  parse_stock_entries(ev.get("honey", []))
    }


def fetch_cosmetic() -> list:
    ts = int(time.time() * 1000)
    cr = requests.get(COSMETIC_URL, params={"ts": ts}).json()
    return parse_stock_entries(cr.get("cosmetics", []))


def fetch_weather() -> dict:
    ts = int(time.time() * 1000)
    return requests.get(WEATHER_URL, params={"ts": ts, "_": ts}).json()

# Formatters

def format_block(category: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(category, "•")
    title = category.capitalize()
    lines = [f"━ {emoji} **{title}** ━"]
    for it in items:
        em = ITEM_EMOJI.get(it['item_id'], "•")
        lines.append(f"   {em} {it['display_name']}: x{it['quantity']}")
    return "\n".join(lines) + "\n\n"


def format_weather(data: dict) -> str:
    icon = data.get("icon", "☁️")
    curr = data.get("currentWeather", "--")
    ends = data.get("ends")
    dur = data.get("duration")
    ends_str = None
    if ends:
        try:
            t = datetime.strptime(ends, "%H:%M") + timedelta(hours=3)
            ends_str = t.strftime("%H:%M")
        except:
            ends_str = ends
    parts = [f"**━ {icon} Погода ━**", f"**Текущая:** {curr}"]
    if ends_str:
        parts.append(f"**Заканчивается в:** {ends_str}")
    if dur:
        parts.append(f"**Длительность:** {dur}")
    return "\n".join(parts)

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
    text = f"**🕒 {now}**\n\n**📊 Стоки Grow a Garden:**\n\n"
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
    text = f"**🕒 {now}**\n\n**💄 Косметический сток:**\n\n"
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
