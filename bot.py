import os
import requests
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
API_KEY = os.getenv("API_KEY")

# Endpoints
SEEDS_API = (
    "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?"
    "select=*&type=eq.seeds_stock&active=eq.true&"
    "order=created_at.desc"
)
GEAR_API = (
    "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?"
    "select=*&type=eq.gear_stock&active=eq.true&"
    "order=created_at.desc"
)
EGG_API = (
    "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock?"
    "select=*&type=eq.egg_stock&active=eq.true&"
    "order=created_at.desc"
)
COSMETIC_API = "https://growagardenstock.com/api/special-stock?type=cosmetics"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}"
}

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "egg": "🥚", "cosmetic": "💄", "weather": "☁️"
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
    "torch": "🔥"
}

# Helpers

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
    seeds = requests.get(SEEDS_API, headers=HEADERS).json()
    gear = requests.get(GEAR_API, headers=HEADERS).json()
    eggs = requests.get(EGG_API, headers=HEADERS).json()
    return {
        "seeds": parse_supabase(seeds),
        "gear": parse_supabase(gear),
        "egg": parse_supabase(eggs)
    }


def fetch_cosmetic() -> list:
    cr = requests.get(COSMETIC_API).json()
    return parse_supabase([{"item_id": None, "display_name": e.split(' **x')[0], "quantity": int(e.split('**x')[1].strip())} for e in cr.get("cosmetics", [])])


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
    emoji = WEATHER_EMOJI.get(active.get("weather_id"), "☁️")
    end_ts = active.get("end_duration_unix", 0)
    ends_str = datetime.fromtimestamp(end_ts, tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M MSK") if end_ts else "--"
    dur = active.get("duration", 0)
    return ("━ {emoji} *Погода* ━\n"
            f"*Текущая:* {name}\n"
            f"*Заканчивается в:* {ends_str}\n"
            f"*Длительность:* {dur} сек")

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
    if update.callback_query: 
        await update.callback_query.answer()
    stock = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n*📊 Стоки Grow a Garden:*\n\n"
    for cat in ["seeds", "gear", "egg"]:
        text += format_block(cat, stock.get(cat, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query: 
        await update.callback_query.answer()
    items = fetch_cosmetic()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n*💄 Косметический сток:*\n\n" + format_block("cosmetic", items)
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query: 
        await update.callback_query.answer()
    await tgt.reply_markdown(format_weather(fetch_weather()))

# Flask healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "OK"

# Run
if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))),
        daemon=True
    ).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CommandHandler("cosmetic", handle_cosmetic))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    bot.run_polling()
