import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from zoneinfo import ZoneInfo
from collections import OrderedDict
import threading
from typing import Optional, Tuple, Dict, Any

# --------------------
# Конфигурация
# --------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
JSTUDIO_KEY = os.getenv("JSTUDIO_KEY")
PORT = int(os.getenv("PORT", 5000))

STOCK_API = "https://api.joshlei.com/v2/growagarden/stock"
WEATHER_API = "https://api.joshlei.com/v2/growagarden/weather"
REQUIRED_CHANNEL = "@GroowAGarden"  # поменяйте, если нужно

# Кеш подписок
CACHE_TTL_SECONDS = 300  # Время жизни кеша (секунд). Можно уменьшить/увеличить.
MAX_CACHE_ENTRIES = 20000  # Максимум записей в кеше (LRU)

# Ограничение по частоте
COOLDOWN_SECONDS = 5

def check_cooldown(user_id: int) -> bool:
    now = time.time()
    last = last_invocation.get(user_id, 0)
    if now - last < COOLDOWN_SECONDS:
        return False
    last_invocation[user_id] = now
    return True

# --------------------
# Внутреннее состояние
# --------------------
last_invocation: Dict[int, float] = {}  # user_id -> last timestamp
pending_actions: Dict[int, Tuple[Any, Any, Any]] = {}  # user_id -> (handler_func, saved_update, saved_context)

# LRU-кеш: user_id -> (status_bool, expires_at)
sub_cache: "OrderedDict[int, Tuple[Optional[bool], float]]" = OrderedDict()

# --------------------
# Утилиты: работа с кешем
# --------------------

def _cache_get(user_id: int) -> Optional[bool]:
    """Возвращает True/False, если в кеше есть актуальное значение. Иначе None."""
    now = time.time()
    item = sub_cache.get(user_id)
    if not item:
        return None
    status, expires = item
    if expires < now:
        # устарело
        try:
            del sub_cache[user_id]
        except KeyError:
            pass
        return None
    # обновим порядок LRU
    sub_cache.move_to_end(user_id)
    return status


def _cache_set(user_id: int, status: Optional[bool], ttl: int = CACHE_TTL_SECONDS) -> None:
    """Сохраняет результат в кеше с TTL. status может быть True/False/None (None = ошибка проверки).
    Если кеш превышает MAX_CACHE_ENTRIES — удаляем наименее используемые записи."""
    expires = time.time() + ttl
    sub_cache[user_id] = (status, expires)
    sub_cache.move_to_end(user_id)
    # Обрежем кеш, если слишком большой
    while len(sub_cache) > MAX_CACHE_ENTRIES:
        sub_cache.popitem(last=False)

# --------------------
# Fetchers (API calls)
# --------------------

def fetch_all_stock():
    try:
        r = requests.get(STOCK_API, headers={"jstudio-key": JSTUDIO_KEY}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("fetch_all_stock error:", e)
        return {}


def fetch_weather():
    try:
        r = requests.get(WEATHER_API, headers={"jstudio-key": JSTUDIO_KEY}, timeout=10)
        r.raise_for_status()
        return r.json().get("weather", [])
    except Exception as e:
        print("fetch_weather error:", e)
        return []

# --------------------
# Форматирование сообщений (оставлено ваше)
# --------------------
CATEGORY_EMOJI = {
    "seed_stock": "🌱",
    "gear_stock": "🧰",
    "egg_stock": "🥚",
    "eventshop_stock": "🫛",  # новая категория
}

ITEM_EMOJI = {
    # Seeds
    "carrot": "🥕", "strawberry": "🍓", "blueberry": "🫐", "orange_tulip": "🌷", "tomato": "🍅", "corn": "🌽",
    "daffodil": "🌼", "watermelon": "🍉", "pumpkin": "🎃", "apple": "🍎", "bamboo": "🎍",
    "coconut": "🥥", "cactus": "🌵", "dragon_fruit": "🐲", "mango": "🥭", "grape": "🍇",
    "mushroom": "🍄", "pepper": "🌶️", "cacao": "🍫", "beanstalk": "🌿", "ember_lily": "🌸",
    "sugar_apple": "🍏", "burning_bud": "🔥", "giant_pinecone": "🌰", "elder_strawberry": "🍓",
    "romanesco": "🥦",

    # Gear
    "cleaning_spray": "🧴", "trowel": "⛏️", "watering_can": "🚿", "recall_wrench": "🔧",
    "basic_sprinkler": "🌦️", "advanced_sprinkler": "💦", "godly_sprinkler": "⚡", "master_sprinkler": "🌧️",
    "magnifying_glass": "🔍", "tanning_mirror": "🪞", "favorite_tool": "❤️", "harvest_tool": "🧲", "friendship_pot": "🤝", "levelup_lollipop": "🍭", "trading_ticket": "🎟️", "grandmaster_sprinkler": "💦",

    # Eggs
    "common_egg": "🥚", "mythical_egg": "🐣", "bug_egg": "🐣", "common_summer_egg": "🥚", "rare_summer_egg": "🥚", "paradise_egg": "🐣", "bee_egg": "🐣",

    # Cosmetics
    "sign_crate": "📦", "medium_wood_flooring": "🪵", "market_cart": "🛒",
    "yellow_umbrella": "☂️", "hay_bale": "🌾", "brick_stack": "🧱",
    "torch": "🔥", "stone_lantern": "🏮", "brown_bench": "🪑", "red_cooler_chest": "📦", "log_bench": "🛋️", "light_on_ground": "💡", "small_circle_tile": "⚪", "beach_crate": "📦", "blue_cooler_chest": "🧊", "large_wood_flooring": "🪚", "medium_stone_table": "🪨", "wood_pile": "🪵", "medium_path_tile": "🛤️", "shovel_grave": "⛏️", "frog_fountain": "🐸", "small_stone_lantern": "🕯️", "small_wood_table": "🪑", "medium_circle_tile": "🔘", "small_path_tile": "🔹", "mini_tv": "📺", "rock_pile": "🗿", "brown_stone_pillar": "🧱", "red_cooler_chest": "🧊", "bookshelf": "📚", "brown_bench": "🪑", "log_bench": "🪵", "large_path_tile": "◼️", "axe_stump": "🪵", "shovel": "⛏️", "flat_canopy": "🏕️", "large_wood_table": "🪵", "small_wood_flooring": "🪵", "small_stone_pad": "◽️", "long_stone_table": "🪨",

    # Event shop items
    "zen_seed_pack": "🌱", "zen_egg": "🥚", "hot_spring": "♨️", "zen_sand": "🏖️", "zenflare": "✨",
    "zen_crate": "📦", "soft_sunshine": "☀️", "koi": "🐟", "zen_gnome_crate": "🧙", "spiked_mango": "🥭", "pet_shard_tranquil": "💠", "tranquil_radar": "🔫", "sakura_bush": "🌸", "corrupt_radar": "🧿", "raiju": "⚡", "pet_shard_corrupted": "🧩",

    # New Event items
    "sprout_seed_pack": "🌱",
    "sprout_egg": "🥚",
    "mandrake_seed": "🧙‍♂️🌱",
    "sprout_crate": "📦",
    "silver_fertilizer": "⚪🌱",
    "canary_melon_seed": "🍈",
    "amberheart": "💛",
    "spriggan": "🌿🧚",
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

TITLE_MAP = {
    "seed_stock": "*Seeds*",
    "gear_stock": "*Gear*",
    "egg_stock": "*Eggs*",
    "eventshop_stock": "*Event*",
}

def format_block(key, items):
    if not items:
        return ""
    emoji = CATEGORY_EMOJI.get(key, "•")
    title = TITLE_MAP.get(key, key.replace("_stock", "").capitalize())
    lines = [f"━ {emoji} {title} ━"]
    for it in items:
        em = ITEM_EMOJI.get(it.get("item_id"), "•")
        lines.append(f"   {em} {it.get('display_name')} x{it.get('quantity', 0)}")
    return "\n".join(lines) + "\n\n"


def format_weather(weather_list):
    active = next((w for w in weather_list if w.get("active")), None)
    if not active:
        return "━ ☁️ *Погода* ━\nНет активных погодных событий"
    eid = active.get("weather_id")
    ends = datetime.fromtimestamp(active.get("end_duration_unix", 0), tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M MSK")
    return (
        f"━ {WEATHER_EMOJI.get(eid, '☁️')} *Погода* ━\n"
        f"*Текущая:* {active.get('weather_name')}\n"
        f"*Заканчивается в:* {ends}\n"
        f"*Длительность:* {active.get('duration')} сек"
    )


def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Стоки", callback_data="show_stock")],
        [InlineKeyboardButton("💄 Косметика", callback_data="show_cosmetic")],
        [InlineKeyboardButton("☁️ Погода", callback_data="show_weather")]
    ])

# --------------------
# Проверка подписки с кешированием
# --------------------
async def _fetch_and_cache_sub(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Optional[bool]:
    """Выполняет реальный запрос к Telegram API и кеширует результат.
    Возвращает True/False/None (None = ошибка проверки).
    """
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        status = getattr(member, "status", None)
        if status in ("left", "kicked", "banned", None):
            _cache_set(user_id, False)
            return False
        _cache_set(user_id, True)
        return True
    except Exception as e:
        print("get_chat_member error:", e)
        # Кешируем ошибку ненадолго, чтобы не спамить API
        _cache_set(user_id, None, ttl=30)
        return None


async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Optional[bool]:
    """Проверка подписки с использованием LRU-кеша.
    Возвращает True/False/None.
    Сначала проверяется кеш; если нет актуального значения — делается реальный запрос.
    """
    cached = _cache_get(user_id)
    if cached is not None:
        return cached
    # Нет в кеше — запросим и закешируем
    return await _fetch_and_cache_sub(user_id, context)

# --------------------
# Декоратор: требовать подписку
# --------------------

def require_subscription(handler_func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        user_id = user.id
        tgt = update.callback_query.message if update.callback_query else update.message

        sub = await is_subscribed(user_id, context)
        if sub is None:
            return await tgt.reply_text(
                "Ошибка проверки подписки. Убедитесь, что бот добавлен в канал {0} и имеет права администратора.".format(REQUIRED_CHANNEL)
            )
        if not sub:
            # Сохраняем действие (чтобы выполнить его после проверки)
            pending_actions[user_id] = (handler_func, update, context)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Подписаться на {0}".format(REQUIRED_CHANNEL), url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")],
                [InlineKeyboardButton("Проверить подписку", callback_data=f"check_sub:{user_id}")]
            ])
            return await tgt.reply_text(
                "Для корректной работы бота, пожалуйста, подпишитесь на канал {0}.".format(REQUIRED_CHANNEL),
                reply_markup=kb
            )
        # Пользователь подписан — выполним исходную команду
        return await handler_func(update, context)
    return wrapper

# --------------------
# Обработчики команд
# --------------------
@require_subscription
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_keyboard())

@require_subscription
async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text("⏳ Подождите 5 сек перед повторным запросом.")
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    text = f"*🕒 {now}*\n\n" + "".join(
        format_block(sec, data.get(sec, []))
        for sec in ["seed_stock", "gear_stock", "egg_stock", "eventshop_stock"]
    )
    await tgt.reply_markdown(text)

@require_subscription
async def handle_cosmetic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text("⏳ Подождите 5 сек перед повторным запросом.")
    if update.callback_query:
        await update.callback_query.answer()
    data = fetch_all_stock()
    now = datetime.now(tz=ZoneInfo("Europe/Moscow")).strftime('%d.%m.%Y %H:%M:%S MSK')
    await tgt.reply_markdown(f"*🕒 {now}*\n\n" + format_block("cosmetic_stock", data.get("cosmetic_stock", [])))

@require_subscription
async def handle_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tgt = update.callback_query.message if update.callback_query else update.message
    if not check_cooldown(user_id):
        return await tgt.reply_text("⏳ Подождите 5 сек перед повторным запросом.")
    if update.callback_query:
        await update.callback_query.answer()
    weather = fetch_weather()
    await tgt.reply_markdown(format_weather(weather))

# --------------------
# Callback: проверка подписки и выполнение отложенного действия
# --------------------
async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        target_id = int(data.split(":", 1)[1])
    except Exception:
        return await q.message.reply_text("Неправильные данные.")

    caller_id = q.from_user.id
    if caller_id != target_id:
        return await q.answer("Эта кнопка не для вас.", show_alert=True)

    sub = await is_subscribed(target_id, context)
    if sub is None:
        return await q.message.reply_text(
            "Ошибка проверки подписки. Убедитесь, что бот добавлен в канал {0} и имеет права администратора.".format(REQUIRED_CHANNEL)
        )
    if not sub:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Подписаться на {0}".format(REQUIRED_CHANNEL), url=f"https://t.me/GroowAGarden")],
            [InlineKeyboardButton("Проверить снова", callback_data=f"check_sub:{target_id}")]
        ])
        return await q.message.reply_text("Вы ещё не подписаны. Пожалуйста, подпишитесь и нажмите кнопку снова.", reply_markup=kb)

    # Подписка подтверждена — выполним отложенную команду (если была)
    saved = pending_actions.pop(target_id, None)
    if saved:
        handler_func, saved_update, saved_context = saved
        await q.message.reply_text("Подписка подтверждена — выполняю команду.")
        try:
            await handler_func(saved_update, saved_context)
        except Exception as e:
            print("Error running pending action:", e)
            await q.message.reply_text("Произошла ошибка при выполнении команды.")
    else:
        await q.message.reply_text("Подписка подтверждена. Теперь можно использовать команды бота.")

# --------------------
# Healthcheck & запуск
# --------------------
app = Flask(__name__)
@app.route("/")
def healthcheck():
    return "OK"

if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=PORT),
        daemon=True
    ).start()

    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    # Команды
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("stock", handle_stock))
    app_bot.add_handler(CommandHandler("cosmetic", handle_cosmetic))
    app_bot.add_handler(CommandHandler("weather", handle_weather))

    # Callback для кнопок "Проверить подписку"
    app_bot.add_handler(CallbackQueryHandler(check_sub_callback, pattern=r"^check_sub:\d+$"))

    # Callback-ы для inline-кнопок в интерфейсе
    app_bot.add_handler(CallbackQueryHandler(handle_stock, pattern="show_stock"))
    app_bot.add_handler(CallbackQueryHandler(handle_cosmetic, pattern="show_cosmetic"))
    app_bot.add_handler(CallbackQueryHandler(handle_weather, pattern="show_weather"))

    app_bot.run_polling(drop_pending_updates=True)
