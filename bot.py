import types
import sys
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
import asyncio
from typing import Any, Dict

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
CHANNEL_ID_ENV = os.getenv("CHANNEL_ID")
KEEPALIVE_PORT = int(os.getenv("PORT", 10000))
JSTUDIO_KEY    = os.getenv("JSTUDIO_KEY")

# Проверки
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не задан в окружении. Бот не запустится.")
if not CHANNEL_ID_ENV:
    logger.error("CHANNEL_ID не задан в окружении. Сообщения не будут отправляться.")
if not JSTUDIO_KEY:
    logger.warning("JSTUDIO_KEY не задан — запросы к API могут падать.")

# Попробуем привести CHANNEL_ID к int, если это число (например "-1001234567890")
def parse_channel_id(val: str):
    if val is None:
        return None
    try:
        # убираем пробелы
        s = val.strip()
        # если это число (включая минус), приводим к int
        if s.lstrip('-').isdigit():
            return int(s)
        # иначе возвращаем как есть (например "@channelname")
        return s
    except Exception:
        return val

CHANNEL_ID = parse_channel_id(CHANNEL_ID_ENV)

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
NOTIFY_ITEMS = list(ITEM_EMOJI.keys())
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

# ====== Запросы к API (не блокируем event loop) ======
def _sync_fetch_stock() -> Dict[str, Any]:
    try:
        resp = requests.get(
            STOCK_API,
            headers={"jstudio-key": JSTUDIO_KEY} if JSTUDIO_KEY else {},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Stock fetch error (sync): {e}")
        return {}

async def fetch_all_stock() -> Dict[str, Any]:
    # Запускаем blocking requests.get в отдельном потоке
    try:
        return await asyncio.to_thread(_sync_fetch_stock)
    except Exception as e:
        logger.exception("Stock fetch error (async wrapper): %s", e)
        return {}

# ====== Логика форматирования ======
def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} *{title}* ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get("item_id"), "•")
        # защищаемся от отсутствующих полей
        display = it.get('display_name') or it.get('item_id') or "Unknown"
        qty = it.get('quantity', 0)
        lines.append(f"   {em} {display}: x{qty}")
    return "\n".join(lines) + "\n\n"

# ====== Обработчики команд ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📦 Стоки",    callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
    ]
    # Для safety: если сообщение пришло из callback_query — отправляем ответ туда
    if update.callback_query:
        tgt = update.callback_query.message
        await update.callback_query.answer()
        await tgt.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text("Привет! Выбери действие:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Этот обработчик вызывается и при /stock, и при callback'ах
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = await fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"*🕒 {now}*\n\n"
    # Если callback указывает на косметику — показываем только cosmetic_stock
    pattern = None
    if update.callback_query and update.callback_query.data:
        pattern = update.callback_query.data
    sections = ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]
    if pattern == "show_cosmetic":
        sections = ["cosmetic_stock"]
    for sec in sections:
        text += format_block(sec, data.get(sec, []))
    # Безопасная отправка (reply_markdown может быть устаревшим — используем reply_text с parse_mode)
    await tgt.reply_text(text, parse_mode="Markdown")

# ====== Мониторинг стока через job_queue ======
last_qty: Dict[str, int] = {}
last_in_stock: Dict[str, bool] = {}

async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await fetch_all_stock()
        if not data:
            logger.debug("Empty stock data — пропуск мониторинга.")
            return
        now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")

        send_coros = []  # список корутин для отправки (мы будем отправлять последовательно)
        # Собираем события для отправки
        for sec in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
            for it in data.get(sec, []):
                iid = it.get('item_id')
                if iid is None:
                    continue
                qty = int(it.get('quantity', 0))
                prev_qty = last_qty.get(iid, 0)
                was_in = last_in_stock.get(iid, False)
                now_in = qty > 0

                # Условие уведомления: предмет в списке отслеживаемых, и он появился (was_in False, now True)
                # или его количество выросло (qty > prev_qty)
                if iid in NOTIFY_ITEMS and ((now_in and not was_in) or (qty > prev_qty)):
                    name_ru = ITEM_NAME_RU.get(iid, it.get('display_name') or iid)
                    emoji = ITEM_EMOJI.get(iid, "")
                    price = PRICE_MAP.get(iid, 0)
                    # форматируем цену с разделителем тысяч
                    price_str = f"{price:,}" if isinstance(price, int) else str(price)
                    msg = (
                        f"*{emoji} {name_ru}: x{qty} в стоке!*\n"
                        f"💰 Цена — {price_str}¢\n"
                        f"🕒 {now}\n\n*@GroowAGarden*"
                    )
                    # Вместо непосредственной отправки — добавляем корутину в список
                    try:
                        coro = context.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")
                        send_coros.append((iid, coro))
                    except Exception as e:
                        # теоретически создание корутины не падает, но логируем на всякий
                        logger.exception("Ошибка при создании send_message coroutine для %s: %s", iid, e)

                # Обновляем состояния независимо от того, отправляли ли сообщение
                last_qty[iid] = qty
                last_in_stock[iid] = now_in

        # Отправляем все сообщения последовательно, в try/except — чтобы одна ошибка не мешала остальным
        if send_coros:
            logger.info("Отправка %d сообщений о стоке...", len(send_coros))
            for iid, coro in send_coros:
                try:
                    await coro
                    # небольшая задержка между отправками (уменьшает шанс получить rate limit)
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.exception("Не удалось отправить сообщение для %s: %s", iid, e)
    except Exception as e:
        logger.exception("Ошибка в monitor_job: %s", e)

# ====== Инициализация бота ======
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stock", handle_stock))
    app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_cosmetic"))

    # В job_queue передаётся функция с signature async def job(context)
    # Интервал 10 секунд — можно настроить при необходимости
    app.job_queue.run_repeating(monitor_job, interval=10, first=10)

    # Keepalive: запуск flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()

    # Запуск polling (блокирует текущий поток)
    logger.info("Запуск бота...")
    app.run_polling()

if __name__ == "__main__":
    main()