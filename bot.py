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
    "weather":        "☁️"
}

# Эмодзи по названиям предметов
ITEM_EMOJI = {
    # Seeds
    "Carrot": "🥕", "Strawberry": "🍓", "Blueberry": "🫐", "Tomato": "🍅",
    "Banana": "🍌",
    # Gear
    "Harvest Tool": "🧲", "Trowel": "⛏️", "Cleaning Spray": "🧴",
    "Recall Wrench": "🔧", "Favorite Tool": "❤️", "Watering Can": "🚿",
    # Eggs
    "Common Egg": "🥚"
}

# Функция запроса стока по типу
def fetch_stock(stock_type: str):
    params = {
        "select": "*",
        "type": f"eq.{stock_type}",
        "active": "eq.true",
        "order": "created_at.desc"
    }
    resp = requests.get(BASE_URL, headers=HEADERS, params=params)
    return resp.json() if resp.ok else []

# Функция запроса погоды
def fetch_weather():
    params = {
        "select": "*",
        "type": "eq.weather",
        "active": "eq.true",
        "order": "date.desc",
        "limit": 1
    }
    resp = requests.get(BASE_URL, headers=HEADERS, params=params)
    return resp.json() if resp.ok else []

# Форматирование блока стока
def format_block(title: str, emoji: str, items: list) -> str:
    if not items:
        return ""
    header = title.replace("_", " ").title().replace(" Stock", "")
    text = f"**━ {emoji} {header} Stock ━**\n"
    for it in items:
        name = it.get("display_name", "Unknown")
        qty  = it.get("multiplier", 0)
        em   = ITEM_EMOJI.get(name, "•")
        text += f"   {em} {name}: x{qty}\n"
    return text + "\n"

# Форматирование погоды
def format_weather(item: dict) -> str:
    if not item:
        return "**☁️ Погода отсутствует**"
    # Парсим дату UTC и конвертируем в MSK
    iso_date = item.get("date")
    try:
        dt_utc = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        dt_msk = dt_utc.astimezone(ZoneInfo("Europe/Moscow"))
        time_msk = dt_msk.strftime("%d.%m.%Y %H:%M:%S MSK")
    except Exception:
        time_msk = iso_date
    desc = item.get("display_name", "?")
    mult = item.get("multiplier", "?")
    # Собираем текст построчно
    lines = []
    lines.append("**━ ☁️ Weather ━**")
    lines.append(f"   🕒 {time_msk}")
    lines.append(f"   🌡️ {desc}: x{mult}")
    return "\n".join(lines)


# Клавиатура
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Показать стоки", callback_data="show_stock")],
        [InlineKeyboardButton("☁️ Показать погоду", callback_data="show_weather")]
    ])

# Обработчики Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Выбери действие:",
        reply_markup=get_keyboard()
    )

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # Собираем стоки
    stocks = {
        "seeds_stock":    fetch_stock("seeds_stock"),
        "cosmetic_stock": fetch_stock("cosmetic_stock"),
        "gear_stock":     fetch_stock("gear_stock"),
        "egg_stock":      fetch_stock("egg_stock"),
    }
    now = datetime.utcnow().strftime("**🕒 %d.%m.%Y %H:%M:%S UTC**\n\n")
    text = now + "**📊 Стоки Grow a Garden:**\n\n"
    for key, items in stocks.items():
        text += format_block(key, CATEGORY_EMOJI.get(key, "📦"), items)
    await update.callback_query.message.reply_markdown(text)

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = fetch_weather()
    item = data[0] if data else None
    text = format_weather(item)
    await update.callback_query.message.reply_markdown(text)

# Flask для healthcheck
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "Bot is alive!"

# Запуск
if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000))),
        daemon=True
    ).start()

    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(handle_stock,   pattern="show_stock"))
    app_bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))
    # Обработчик команды /weather
    app_bot.add_handler(CommandHandler("weather", handle_weather))
    print("✅ Bot is running…")
    app_bot.run_polling()