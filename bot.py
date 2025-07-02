# bot.py
import os
import threading
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# 1) Загрузим переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")  # твой Supabase API key

# 2) Старый Supabase REST endpoint Arcaiuz
BASE_URL = "https://vextbzatpprnksyutbcp.supabase.co/rest/v1/growagarden_stock"
HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}"
}

# Эмодзи по категориям и предметам
CATEGORY_EMOJI = {"seeds":"🌱","cosmetic":"💎","gear":"🧰","event":"🌴","eggs":"🥚"}
ITEM_EMOJI = {
    # Seeds
    "Feijoa":"🥝","Kiwi":"🥝","Avocado":"🥑","Sugar Apple":"🍏","Tomato":"🍅",
    "Bell Pepper":"🌶️","Pitcher Plant":"🌱","Prickly Pear":"🌵","Cauliflower":"🥦",
    "Blueberry":"🫐","Carrot":"🥕","Loquat":"🍑","Green Apple":"🍏","Strawberry":"🍓",
    "Watermelon":"🍉","Banana":"🍌","Rafflesia":"🌺","Pineapple":"🍍",
    # Cosmetic
    "Green Tractor":"🚜","Large Wood Flooring":"🪵","Sign Crate":"📦","Small Wood Table":"🪑",
    "Large Path Tile":"🛤️","Medium Path Tile":"⬛","Wood Fence":"🪵","Axe Stump":"🪨","Shovel":"🪓",
    # Gear
    "Advanced Sprinkler":"💦","Master Sprinkler":"💧","Basic Sprinkler":"🌦️","Godly Sprinkler":"⚡",
    "Trowel":"⛏️","Harvest Tool":"🧲","Cleaning Spray":"🧴","Recall Wrench":"🔧",
    "Favorite Tool":"❤️","Watering Can":"🚿","Magnifying Glass":"🔍","Tanning Mirror":"🪞","Friendship Pot":"🌻",
    # Eggs
    "Common Egg":"🥚"
}

# 4) Функция запроса стока по типу
def fetch_stock(stock_type: str):
    params = {
        "select": "*",
        "type": f"eq.{stock_type}",
        "active": "eq.true",
        "order": "created_at.desc"
    }
    resp = requests.get(BASE_URL, headers=HEADERS, params=params)
    return resp.json() if resp.ok else []

# 5) Форматирование блока
def format_block(title: str, emoji: str, items: list) -> str:
    if not items:
        return ""
    # Преобразуем ключ в читаемый заголовок
    header = title.replace("_", " ").title()
    text = f"━ {emoji} {header} ━\n"
    for it in items:
        name = it.get("display_name")
        qty = it.get("multiplier")
        em = ITEM_EMOJI.get(name, "•")
        text += f"   {em} {name}: x{qty}\n"
    return text + "\n"

# 6) Клавиатура Telegram
def get_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")]])

# 7) Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Нажми кнопку, чтобы получить текущие стоки:",
        reply_markup=get_keyboard()
    )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # Получаем четыре категории
    seeds    = fetch_stock("seeds_stock")
    cosmetic = fetch_stock("cosmetic_stock")
    gear     = fetch_stock("gear_stock")
    egg      = fetch_stock("egg_stock")

    now = datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S UTC")
    text = f"🕒 {now}\n\n📊 *Стоки Grow a Garden:*\n\n"
    text += format_block("seeds_stock",   CATEGORY_EMOJI["seeds_stock"],   seeds)
    text += format_block("cosmetic_stock",CATEGORY_EMOJI["cosmetic_stock"],cosmetic)
    text += format_block("gear_stock",    CATEGORY_EMOJI["gear_stock"],    gear)
    text += format_block("egg_stock",     CATEGORY_EMOJI["egg_stock"],     egg)

    await update.callback_query.message.reply_markdown(text)

# 8) Flask для healthcheck
app = Flask(__name__)

@app.route("/")
def healthcheck():
    return "Bot is alive!"

# 9) Запуск
if __name__ == "__main__":
    # Запускаем Flask в фоновом потоке
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))),
        daemon=True
    ).start()

    # Запускаем Telegram-бот
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(on_button, pattern="show_stock"))
    print("✅ Bot running…")
    app_bot.run_polling()
