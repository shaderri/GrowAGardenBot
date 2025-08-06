import types
import sys
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ====== Логирование ======
logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====== Monkey-patch imghdr для Python 3.13 ======
if "imghdr" not in sys.modules:
    mod = types.ModuleType("imghdr")
    mod.what = lambda *args, **kwargs: None
    sys.modules["imghdr"] = mod

# ====== Переменные окружения ======
load_dotenv()
BOT_TOKEN      = os.getenv("BOT_TOKEN")
CHANNEL_ID     = os.getenv("CHANNEL_ID")
KEEPALIVE_PORT = int(os.getenv("PORT", 10000))
JSTUDIO_KEY    = os.getenv("JSTUDIO_KEY")

# ====== API эндпоинты ======
STOCK_API   = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"

# ====== Эмодзи, переводы, цена ======
CATEGORY_EMOJI = {
    "seed_stock":     "🌱",
    "gear_stock":     "🧰",
    "egg_stock":      "🥚",
    "cosmetic_stock": "💄",
}
ITEM_EMOJI = {
    "grape":"🍇","mushroom":"🍄","pepper":"🌶️","cacao":"🍫",
    "beanstalk":"🫛","ember_lily":"🌸","sugar_apple":"🍏",
    "burning_bud":"🔥","giant_pinecone":"🌰",
    "master_sprinkler":"🌧️","grandmaster_sprinkler":"💦",
    "levelup_lollipop":"🍭","elder_strawberry":"🍓",
    "paradise_egg":"🐣","bug_egg":"🐣",
}
ITEM_NAME_RU = {
    "paradise_egg":"Райское яйцо","bug_egg":"Яйцо жука",
    "grape":"Виноград","mushroom":"Грибы","pepper":"Перец",
    "cacao":"Какао","beanstalk":"Бобовый стебель",
    "ember_lily":"Эмбер лили","sugar_apple":"Сахарное яблоко",
    "burning_bud":"Горящий бутон","giant_pinecone":"Гигантская шишка",
    "master_sprinkler":"Мастер-спринклер",
    "grandmaster_sprinkler":"Грандмастер-спринклер",
    "levelup_lollipop":"Леденец уровня","elder_strawberry":"Бузинная клубника",
}
NOTIFY_ITEMS = [
    "grape","mushroom","pepper","cacao","beanstalk","ember_lily",
    "sugar_apple","burning_bud","giant_pinecone",
    "master_sprinkler","grandmaster_sprinkler",
    "levelup_lollipop","elder_strawberry",
    "paradise_egg","bug_egg"
]
PRICE_MAP = {
    "paradise_egg":50_000_000,"bug_egg":50_000_000,
    "grape":850_000,"mushroom":150_000,"pepper":1_000_000,
    "cacao":2_500_000,"beanstalk":10_000_000,
    "ember_lily":15_000_000,"sugar_apple":25_000_000,
    "burning_bud":40_000_000,"giant_pinecone":55_000_000,
    "master_sprinkler":10_000_000,"grandmaster_sprinkler":1_000_000_000,
    "levelup_lollipop":10_000_000_000,"elder_strawberry":70_000_000
}

# ====== Flask для keep-alive ======
flask_app = Flask(__name__)
@flask_app.route("/")
def home():
    return "Bot is running", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=KEEPALIVE_PORT)

# ====== Запросы к API ======
def fetch_all_stock():
    try:
        resp = requests.get(
            STOCK_API,
            headers={"jstudio-key": JSTUDIO_KEY},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Stock fetch error: {e}")
        return {}

def fetch_weather():
    try:
        resp = requests.get(
            WEATHER_API,
            headers={"jstudio-key": JSTUDIO_KEY},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json().get("weather", [])
    except Exception as e:
        logger.error(f"Weather fetch error: {e}")
        return []

# ====== Форматирование сообщений ======
def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it["item_id"], "•")
        lines.append(f"   {em} {it['display_name']}: x{it['quantity']}")
    return "\n".join(lines) + "\n\n"

def format_weather_block(weather_list: list) -> str:
    active = next((w for w in weather_list if w.get("active")), None)
    if not active:
        return "━ ☁️ *Погода* ━\nНет активных погодных событий"
    end_ts = active.get("end_duration_unix", 0)
    ends = datetime.fromtimestamp(end_ts, tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK") if end_ts else "--"
    return (
        f"━ ☁️ *Погода* ━\n"
        f"*Текущая:* {active['weather_name']}\n"
        f"*Заканчивается в:* {ends}\n"
        f"*Длительность:* {active.get('duration',0)} сек"
    )

# ====== Обработчики команд ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📦 Стоки",    callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода",     callback_data="show_weather")],
    ]
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    for sec in ["seed_stock", "gear_stock", "egg_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_markdown(text)

async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock().get("cosmetic_stock", [])
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    await tgt.reply_markdown(f"*🕒 {now}*\n\n" + format_block("cosmetic_stock", data))

async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    weather = fetch_weather()
    await tgt.reply_markdown(format_weather_block(weather))

# ====== Мониторинг стока через job_queue ======
last_qty = {}

async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    data = fetch_all_stock()
    if not data:
        return
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    for sec in ["seed_stock", "gear_stock", "cosmetic_stock", "egg_stock"]:
        for it in data.get(sec, []):
            iid, qty = it["item_id"], it["quantity"]
            prev = last_qty.get(iid, 0)
            if qty > prev and iid in NOTIFY_ITEMS:
                name_ru = ITEM_NAME_RU.get(iid, it["display_name"])
                emoji   = ITEM_EMOJI.get(iid, "")
                price   = PRICE_MAP.get(iid, 0)
                msg = (
                    f"*{emoji} {name_ru}: x{qty} в стоке!*\n"
                    f"💰 Цена — {price:,}¢\n"
                    f"🕒 {now}\n\n*@GrowAGarden*"
                )
                await context.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")
            last_qty[iid] = qty

# ====== Инициализация бота ======
app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)

# Регистрируем команды
app.add_handler(CommandHandler("start",    start))
app.add_handler(CommandHandler("stock",    handle_stock))
app.add_handler(CommandHandler("cosmetic", handle_cosmetic))
app.add_handler(CommandHandler("weather",  handle_weather))
app.add_handler(CallbackQueryHandler(handle_stock,    pattern="show_stock"))
app.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
app.add_handler(CallbackQueryHandler(handle_weather,  pattern="show_weather"))

# Регистрируем job: каждые 10 сек, первый запуск через 10 сек
app.job_queue.run_repeating(monitor_job, interval=10, first=10)

if __name__ == "__main__":
    # Запускаем Flask для keep-alive
    threading.Thread(target=run_flask, daemon=True).start()
    # Только polling, без webhook
    app.run_polling()