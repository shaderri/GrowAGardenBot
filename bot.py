# bot.py
import os
import threading
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Загрузим переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY   = os.getenv("API_KEY")

# Supabase REST endpoint Arcaiuz
BASE_URL = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock"
HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}"
}

# Эмодзи по категориям
CATEGORY_EMOJI = {
    "seeds_stock":    "🌱",
    "cosmetic_stock": "💎",
    "gear_stock":     "🧰",
    "egg_stock":      "🥚",
}

# Эмодзи по названиям предметов
ITEM_EMOJI = {
    "Feijoa":"🥝", "Kiwi":"🥝", "Avocado":"🥑", "Sugar Apple":"🍏", "Tomato":"🍅",
    "Bell Pepper":"🌶️", "Pitcher Plant":"🌱", "Prickly Pear":"🌵", "Cauliflower":"🥦",
    "Blueberry":"🫐", "Carrot":"🥕", "Loquat":"🍑", "Green Apple":"🍏", "Strawberry":"🍓",
    "Watermelon":"🍉", "Banana":"🍌", "Rafflesia":"🌺", "Pineapple":"🍍",
    "Green Tractor":"🚜", "Large Wood Flooring":"🪵", "Sign Crate":"📦", "Small Wood Table":"🪑",
    "Large Path Tile":"🛤️", "Medium Path Tile":"⬛", "Wood Fence":"🪵", "Axe Stump":"🪨", "Shovel":"🪓",
    "Advanced Sprinkler":"💦", "Master Sprinkler":"💧", "Basic Sprinkler":"🌦️", "Godly Sprinkler":"⚡",
    "Trowel":"⛏️", "Harvest Tool":"🧲", "Cleaning Spray":"🧴", "Recall Wrench":"🔧",
    "Favorite Tool":"❤️", "Watering Can":"🚿", "Magnifying Glass":"🔍", "Tanning Mirror":"🪞", "Friendship Pot":"🌻",
    "Common Egg":"🥚"
}

# Получить стоки из Supabase
def fetch_stock(stock_type: str):
    params = {
        "select": "*",
        "type": f"eq.{stock_type}",
        "active": "eq.true",
        "order": "created_at.desc"
    }
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, params=params)
        return resp.json() if resp.ok else []
    except Exception as e:
        print(f"Error fetching {stock_type}: {e}")
        return []

# Форматирование блока для Telegram
def format_block(title: str, emoji: str, items: list) -> str:
    if not items:
        return ""
    title_pretty = title.replace("_stock", "").capitalize()
    text = f"━ {emoji} {title_pretty} ━\n"
    for it in items:
        name = it.get("display_name", "???")
        qty  = it.get("multiplier", 0)
        em   = ITEM_EMOJI.get(name, "•")
        text += f"   {em} {name}: x{qty}\n"
    return text + "\n"

# Клавиатура
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")]
    ])

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Нажми кнопку, чтобы получить текущие стоки:",
        reply_markup=get_keyboard()
    )

# Нажатие кнопки
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    # Запрос данных по категориям
    stocks = {
        "seeds_stock":    fetch_stock("seeds_stock"),
        "cosmetic_stock": fetch_stock("cosmetic_stock"),
        "gear_stock":     fetch_stock("gear_stock"),
        "egg_stock":      fetch_stock("egg_stock"),
    }

    # Сборка сообщения
    now = datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S UTC")
    text = f"🕒 {now}\n\n📊 *Стоки Grow a Garden:*\n\n"
    for category, items in stocks.items():
        text += format_block(category, CATEGORY_EMOJI.get(category, "📦"), items)

    await update.callback_query.message.reply_markdown(text)

# Flask для ping
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "Bot is alive!"

# Запуск
if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))),
        daemon=True
    ).start()

    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(on_button, pattern="show_stock"))
    print("✅ Bot is running…")
    app_bot.run_polling()
