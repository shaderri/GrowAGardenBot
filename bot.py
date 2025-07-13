import os
import requests
import time
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

# Cooldown settings
COOLDOWN_SECONDS = 5  # изменено с 10 на 5
last_invocation = {}  # {user_id: timestamp}

# Emoji mappings
CATEGORY_EMOJI = {
    "seeds": "🌱", "gear": "🧰", "egg": "🥚", "cosmetic": "💄", "weather": "☁️"
}
ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "orange_tulip": "🌷", "tomato": "🍅", "corn": "🌽",
    "daffodil": "🌼", "watermelon": "🍉", "pumpkin": "🎃", "apple": "🍎", "bamboo": "🎍",
    "coconut": "🥥", "cactus": "🌵", "dragon_fruit": "🐲", "mango": "🥭", "grape": "🍇",
    "mushroom": "🍄", "pepper": "🌶️", "cacao": "🍫", "beanstalk": "🌿", "ember_lily": "🌸",
    "sugar_apple": "🍏", "burning_bud": "🔥", "giant_pinecone": "🌰",
    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝",
    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",
    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "stone_lantern": "🏮", "brown_bench": "🪑", "red_cooler_chest": "📦", "log_bench": "🛋️", "light_on_ground": "💡", "small_circle_tile": "⚪", "beach_crate": "📦", "blue_cooler_chest": "🧊", "large_wood_flooring": "🪚", "medium_stone_table": "🪨", "wood_pile": "🪵", "medium_path_tile": "🛤️", "shovel_grave": "⛏️", "frog_fountain": "🐸", "small_stone_lantern": "🕯️", "small_wood_table": "🪑", "medium_circle_tile": "🔘", "small_path_tile": "🔹", "mini_tv": "📺", "rock_pile": "🗿", "brown_stone_pillar": "🧱", "red_cooler_chest": "🧊", "bookshelf": "📚", "brown_bench": "🪑", "log_bench": "🪵",
    # Added missing items
    "large_path_tile": "◼️",  # Large Path Tile
    "axe_stump": "🪵",          # Axe Stump
    "shovel": "⛏️"             # Shovel
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
    return r.json() if r.ok else {}

# Fetch weather
def fetch_weather() -> list:
    r = requests.get(WEATHER_API)
    return r.json().get("weather", [])

# Cooldown checker
def check_cooldown(user_id: int) -> bool:
    now = time.time()
    last = last_invocation.get(user_id, 0)
    if now - last < COOLDOWN_SECONDS:
        return False
    last_invocation[user_id] = now
    return True

# Formatters remain unchanged
# ... format_block, format_weather, get_keyboard ...

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /start всегда отвечает, без кулдауна
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text(
            "⏳ Пожалуйста, подождите 5 секунд перед повторным запросом."
        )
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n"
    for section in ["seed_stock", "gear_stock", "egg_stock"]:
        text += format_block(section, data.get(section, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text(
            "⏳ Пожалуйста, подождите 5 секунд перед повторным запросом."
        )
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n"
    text += format_block("cosmetic_stock", data.get("cosmetic_stock", []))
    await tgt.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text(
            "⏳ Пожалуйста, подождите 5 секунд перед повторным запросом."
        )
    if update.callback_query:
        await update.callback_query.answer()
    await tgt.reply_markdown(format_weather(fetch_weather()))

# Flask healthcheck and bot setup remain unchanged
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "OK"

if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000))),
        daemon=True
    ).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    bot.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
    bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    bot.add_handler(CommandHandler("stock", handle_stock))
    bot.add_handler(CommandHandler("cosmetic", handle_cosmetic))
    bot.add_handler(CommandHandler("weather", handle_weather))
    bot.run_polling()