# bot_improved.py
import types
import sys
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
import asyncio
from typing import Any, Dict, List, Tuple

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

# ====== Monkey-patch imghdr для Python 3.13 (если нужно) ======
if "imghdr" not in sys.modules:
    mod = types.ModuleType("imghdr")
    mod.what = lambda *args, **kwargs: None
    sys.modules["imghdr"] = mod

# ====== Переменные окружения ======
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID_ENV = os.getenv("CHANNEL_ID")
KEEPALIVE_PORT = int(os.getenv("PORT", 10000))
JSTUDIO_KEY = os.getenv("JSTUDIO_KEY")

def parse_channel_id(val: str):
    if val is None:
        return None
    s = val.strip()
    if s.startswith("@"):
        return s
    try:
        return int(s)
    except Exception:
        return s

CHANNEL_ID = parse_channel_id(CHANNEL_ID_ENV)

# ====== Конфигурация API ======
STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"

# ====== Эмоджи и карты ======
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

# ====== Flask keepalive (опционально) ======
flask_app = Flask(__name__)
@flask_app.route("/")
def home():
    return "Bot is running", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=KEEPALIVE_PORT)

# ====== Сетевые вызовы: выполняем blocking requests в thread, с retry ======
def _sync_fetch_stock_once() -> Dict[str, Any]:
    headers = {"jstudio-key": JSTUDIO_KEY} if JSTUDIO_KEY else {}
    resp = requests.get(STOCK_API, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _sync_fetch_stock_with_retries(retries: int = 2) -> Dict[str, Any]:
    last_exc = None
    for i in range(retries + 1):
        try:
            return _sync_fetch_stock_once()
        except Exception as e:
            last_exc = e
            logger.warning("fetch attempt %d failed: %s", i+1, e)
    logger.exception("All fetch attempts failed: %s", last_exc)
    return {}

async def fetch_all_stock() -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_fetch_stock_with_retries)

# ====== Форматирование вывода ======
def format_block(key: str, items: list) -> str:
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = key.replace("_stock", "").capitalize()
    lines = [f"━ {emoji} <b>{title}</b> ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get("item_id"), "•")
        display = it.get("display_name") or it.get("item_id") or "Unknown"
        qty = it.get("quantity", 0)
        lines.append(f"   {em} {display}: x{qty}")
    return "\n".join(lines) + "\n\n"

# ====== Очередь сообщений и состояния ======
# messages_queue: список кортежей (iid, qty, text)
messages_queue: List[Tuple[str, int, str]] = []
# для предотвращения дублей в короткий промежуток (iid -> last sent qty)
recently_sent: Dict[str, int] = {}

last_qty: Dict[str, int] = {}
last_in_stock: Dict[str, bool] = {}
monitor_lock = asyncio.Lock()

# ====== Обработчики команд ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
    ]
    try:
        await update.message.reply_text("Бот запущен. Используй /stock для ручного запроса.", reply_markup=InlineKeyboardMarkup(kb))
    except Exception:
        pass

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgt = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    data = await fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
    text = f"🕒 <b>{now}</b>\n\n"
    for sec in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
        text += format_block(sec, data.get(sec, []))
    await tgt.reply_text(text, parse_mode="HTML")

# ====== Утилита: надежная отправка с ретраями и fallback ======
async def send_with_retries_and_fallback(bot, chat_id, text_html: str, attempts: int = 3):
    """
    Сначала пытаемся отправить как HTML. Если ошибка (BadRequest-parse),
    пробуем отправить без parse_mode (чистый текст). Повторяем attempts раз.
    """
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            await bot.send_message(chat_id=chat_id, text=text_html, parse_mode="HTML")
            return True
        except Exception as e:
            last_exc = e
            # Если ошибка парсинга (часто telegram.error.BadRequest с сообщением о parse mode),
            # попробуем отправить как чистый текст (без parse_mode).
            logger.warning("send attempt %d failed: %s", attempt, e)
            if attempt == attempts:
                # окончательная попытка — без parse_mode
                try:
                    await bot.send_message(chat_id=chat_id, text=text_html)
                    return True
                except Exception as e2:
                    logger.exception("Final fallback send also failed: %s", e2)
                    return False
            await asyncio.sleep(0.5 * attempt)
    logger.exception("All send attempts failed, last error: %s", last_exc)
    return False

# ====== Job: мониторим сток и кладём в очередь (только собираем) ======
async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    # предотвращаем параллельные запуски
    if monitor_lock.locked():
        logger.info("monitor_job пропущен: предыдущий ещё выполняется")
        return

    async with monitor_lock:
        try:
            data = await fetch_all_stock()
            if not data:
                logger.debug("fetch_all_stock вернул пусто — пропускаем обновление состояния")
                return

            now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S MSK")
            new_messages: List[Tuple[str, int, str]] = []
            local_qty_updates: Dict[str, int] = {}
            local_instock_updates: Dict[str, bool] = {}

            for sec in ["seed_stock", "gear_stock", "egg_stock", "cosmetic_stock"]:
                for it in data.get(sec, []):
                    iid = it.get("item_id")
                    if iid is None:
                        continue
                    try:
                        qty = int(it.get("quantity", 0))
                    except Exception:
                        qty = 0
                    prev_qty = last_qty.get(iid, 0)
                    was_in = last_in_stock.get(iid, False)
                    now_in = qty > 0

                    # уведомление: появление или рост количества
                    if iid in NOTIFY_ITEMS and ((now_in and not was_in) or (qty > prev_qty)):
                        name_ru = ITEM_NAME_RU.get(iid, it.get('display_name') or iid)
                        emoji = ITEM_EMOJI.get(iid, "")
                        price = PRICE_MAP.get(iid, 0)
                        price_str = f"{price:,}" if isinstance(price, int) else str(price)
                        text_html = (
                            f"<b>{emoji} {name_ru}: x{qty} в стоке!</b>\n"
                            f"💰 Цена — {price_str}¢\n"
                            f"🕒 {now}\n\n@GroowAGarden"
                        )
                        # Проверка на недавнюю отправку (избегаем дублей)
                        last_sent_qty = recently_sent.get(iid)
                        if last_sent_qty is not None and last_sent_qty == qty:
                            logger.info("Дубликат по количеству для %s (qty=%s) — пропускаем enqueue", iid, qty)
                        else:
                            new_messages.append((iid, qty, text_html))
                            logger.info("Enqueue: %s qty=%s (prev=%s, was_in=%s->now_in=%s)", iid, qty, prev_qty, was_in, now_in)

                    # собираем локальные обновления (будут применены единовременно)
                    local_qty_updates[iid] = qty
                    local_instock_updates[iid] = now_in

            # применяем обновления состояния
            last_qty.update(local_qty_updates)
            last_in_stock.update(local_instock_updates)

            # добавляем в основную очередь (в одном потоке — job_queue гарантирует последовательность)
            if new_messages:
                before = len(messages_queue)
                messages_queue.extend(new_messages)
                logger.info("Добавлено %d сообщений в очередь (до=%d, после=%d)", len(new_messages), before, len(messages_queue))
        except Exception as e:
            logger.exception("Ошибка в monitor_job: %s", e)

# ====== Job: отправщик очереди (в отдельном job, раз в 1s) ======
async def sender_job(context: ContextTypes.DEFAULT_TYPE):
    if not messages_queue:
        return
    # заберём до N сообщений за проход чтобы не перегрузить
    MAX_PER_PASS = 20
    to_send = []
    # извлекаем из общей очереди сначала
    while messages_queue and len(to_send) < MAX_PER_PASS:
        to_send.append(messages_queue.pop(0))

    logger.info("Sender job: отправляем %d сообщений (оставшихся в очереди: %d)", len(to_send), len(messages_queue))
    for iid, qty, text_html in to_send:
        try:
            ok = await send_with_retries_and_fallback(context.bot, CHANNEL_ID, text_html, attempts=3)
            if ok:
                # помечаем как отправленное, чтобы не задублировать при тех же qty
                recently_sent[iid] = qty
                logger.info("Sent: %s qty=%s", iid, qty)
            else:
                # если не удалось — ставим обратно в очередь в конец для повторной попытки позже
                messages_queue.append((iid, qty, text_html))
                logger.warning("Не удалось отправить %s — возвращаем в очередь (сейчас длина %d)", iid, len(messages_queue))
            # пауза между отправками
            await asyncio.sleep(0.25)
        except Exception as e:
            logger.exception("Ошибка при отправке %s: %s — возвращаем в очередь", iid, e)
            messages_queue.append((iid, qty, text_html))

# ====== Инициализация бота ======
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан — выходим.")
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stock", handle_stock))
    app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    app.add_handler(CallbackQueryHandler(handle_stock, pattern="show_cosmetic"))

    # Планирование: мониторим и кладём в очередь
    # monitor_job — проверка API (интервал можно увеличить)
    app.job_queue.run_repeating(monitor_job, interval=10, first=5)
    # sender_job — обрабатывает очередь и отправляет, часто (1 сек)
    app.job_queue.run_repeating(sender_job, interval=1, first=7)

    # Keepalive flask (опционально)
    threading.Thread(target=run_flask, daemon=True).start()

    logger.info("Запуск бота...")
    app.run_polling()

if __name__ == "__main__":
    main()