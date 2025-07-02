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

# Основной API URL
API_URL = "https://www.gamersberg.com/api/grow-a-garden/stock"

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
    # Event
    "Hamster":"🐹","Summer Seed Pack":"🌞","Oasis Crate":"🏝️","Traveler's Fruit":"✈️",
    "Delphinium":"🌸","Oasis Egg":"🥚","Lily of the Valley":"💐","Mutation Spray Burnt":"🔥",
    # Eggs
    "Common Egg":"🥚"
}

# Форматирование секций
def format_dict_block(name: str, data: dict) -> str:
    filtered = {k: v for k, v in data.items() if int(v) > 0}
    if not filtered:
        return ""
    title = "Summer Stock" if name == "event" else f"{name.capitalize()} Stock"
    text = f"━ {CATEGORY_EMOJI.get(name)} {title} ━\n"
    for item, qty in filtered.items():
        emoji = ITEM_EMOJI.get(item, "•")
        text += f"   {emoji} {item}: x{qty}\n"
    return text + "\n"

def format_eggs_block(eggs: list) -> str:
    filtered = [e for e in eggs if e.get("name") != "Location" and int(e.get("quantity", 0)) > 0]
    if not filtered:
        return ""
    text = f"━ {CATEGORY_EMOJI.get('eggs')} Egg Stock ━\n"
    for egg in filtered:
        name = egg.get("name")
        qty = egg.get("quantity")
        emoji = ITEM_EMOJI.get(name, "🥚")
        text += f"   {emoji} {name}: x{qty}\n"
    return text + "\n"

# Клавиатура для Telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_keyboard():
    btn = InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")
    return InlineKeyboardMarkup([[btn]])

# Обработчики Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Нажми кнопку, чтобы получить стоки Grow a Garden:",
        reply_markup=get_keyboard()
    )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # добавляем cookie для авторизации на Gamersberg
    cookie = os.getenv("API_COOKIE")  # установите в .env: API_COOKIE=session_start=...
    headers = {"Cookie": cookie}
    resp = requests.get(API_URL, headers=headers)
    data = resp.json().get("data", [])
    if not data:
        await update.callback_query.message.reply_text("⚠️ Данные отсутствуют")
        return
    info = data[0]
    ts = int(info.get("timestamp", 0))
    now = datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M:%S")
    text = f"🕒 {now}\n\n📊 *Стоки Grow a Garden:*\n\n"
    text += format_dict_block("seeds", info.get("seeds", {}))
    text += format_dict_block("cosmetic", info.get("cosmetic", {}))
    text += format_dict_block("gear", info.get("gear", {}))
    text += format_dict_block("event", info.get("event", {}))
    text += format_eggs_block(info.get("eggs", []))
    await update.callback_query.message.reply_markdown(text)

# Запуск
from flask import Flask
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "Bot is alive!"

if __name__ == "__main__":
    # Запускаем Flask в фоне
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True)
    flask_thread.start()

    # Запускаем Telegram-бот в главном потоке
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(on_button, pattern="show_stock"))
    print("✅ Bot running…")
    app_bot.run_polling()