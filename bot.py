import os
import requests
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

# New stock endpoint
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "egg": "🥚", "cosmetic": "💄", "weather": "☁️"
}
ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "tomato": "🍅", "banana": "🍌",
    "cauliflower": "🥦", "watermelon": "🍉", "rafflesia": "🌺", "green_apple": "🍏",
    "avocado": "🥑", "pineapple": "🍍", "kiwi": "🥝", "bell_pepper": "🌶️",
    "prickly_pear": "🌵", "loquat": "🍑", "feijoa": "🥝", "pitcher_plant": "🌱", "sugar_apple": "🍎", "grape": "🍇", "coconut": "🥥", "pumpkin": "🎃", "pepper": "🌶️", "cacao": "🍫", "apple": "🍎", "bamboo": "🎍", "burning_bud": "🌼", "dragon_fruit": "🐲🥭", "orange_tulip": "🌷",
    "mango": "🥭", "cactus": "🌵", "ember_lily": "🌸", "beanstalk": "🌿", "mushroom": "🍄", "daffodil": "🌼",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝",
    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",
    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "stone_lantern": "🏮", "brown_bench": "🪑", "red_cooler_chest": "📦", "log_bench": "🛋️",
    "light_on_ground": "💡", "small_circle_tile": "⚪", "beach_crate": "📦","blue_cooler_chest": "🧊", "large_wood_flooring": "🪵", "medium_stone_table": "🗄️", "wood_pile": "🪵", "medium_path_tile": "🛤️", "shovel_grave": "⛏️"
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

# Fetch stock from unified endpoint

def fetch_all_stock() -> dict:
    r = requests.get(STOCK_API)
    data = r.json() if r.ok else {}
    return data  # data contains keys seed_stock, gear_stock, egg_stock, eventshop_stock, cosmetic_stock

# Fetch weather

def fetch_weather() -> list:
    r = requests.get(WEATHER_API)
    return r.json().get("weather", [])

# Formatters

def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        name = it.get("display_name")
        qty = it.get("quantity", 0)
        key_id = it.get("item_id")
        em = ITEM_EMOJI.get(key_id, "•")
        lines.append(f"   {em} {name}: x{qty}")
    return "\n".join(lines) + "\n\n"


def format_weather(weather_list: list) -> str:
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

# Keyboard
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
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    # Header with time and title
    text = f"*🕒 {now}*📊 Стоки Grow a Garden:*"
    # Sections
    section_map = [("seed_stock", "Seeds"), ("gear_stock", "Gear"), ("egg_stock", "Egg")]
    for key, title in section_map:
        items = data.get(key, [])
        if not items:
            continue
        emoji = CATEGORY_EMOJI.get(key, "•")
        text += f"━ {emoji} *{title}* ━"
        for it in items:
            name = it.get("display_name")
            qty = it.get("quantity", 0)
            em = ITEM_EMOJI.get(it.get("item_id"), "•")
            text += f"   {em} {name}: x{qty}"
        text += ""
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query: await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n"
    text += format_block("cosmetic_stock", data.get("cosmetic_stock", []))
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
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000))), daemon=True).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CommandHandler("cosmetic", handle_cosmetic))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.run_polling()
