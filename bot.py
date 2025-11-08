import asyncio
import logging
import os
import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError
import pytz
from dotenv import load_dotenv
import discord
import aiohttp

load_dotenv()

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@GroowAGarden")
CHANNEL_USERNAME = "GroowAGarden"

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tcsmfiixhflzrxkrbslk.supabase.co")
SUPABASE_API_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRjc21maWl4aGZsenJ4a3Jic2xrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA1MDUzOTYsImV4cCI6MjA3NjA4MTM5Nn0.VcAK7QYvUFuKd96OgOdadS2s_9N08pYt9mMIu73Jeiw")

AUTOSTOCKS_URL = f"{SUPABASE_URL}/rest/v1/user_autostocks"
USERS_URL = f"{SUPABASE_URL}/rest/v1/users"

DISCORD_CHANNELS = {
    "stock": 1373218015042207804,
    "egg_stock": 1373218102313091072,
    "event_content": 1396257564311949503,
}

CHECK_INTERVAL_MINUTES = 5
CHECK_DELAY_SECONDS = 10
RAREST_SEEDS = ["Crimson Thorn", "Trinity Fruit"]

if not BOT_TOKEN or not DISCORD_TOKEN:
    raise ValueError("BOT_TOKEN и DISCORD_TOKEN должны быть установлены!")

# ========== ЛОГИРОВАНИЕ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# ========== ДАННЫЕ ПРЕДМЕТОВ ==========
SEEDS_DATA = {
    "Carrot": {"emoji": "🥕", "price": "10"},
    "Strawberry": {"emoji": "🍓", "price": "50"},
    "Blueberry": {"emoji": "🫐", "price": "400"},
    "Orange Tulip": {"emoji": "🧡", "price": "600"},
    "Tomato": {"emoji": "🍅", "price": "800"},
    "Corn": {"emoji": "🌽", "price": "1,300"},
    "Daffodil": {"emoji": "🌼", "price": "1,000"},
    "Watermelon": {"emoji": "🍉", "price": "2,500"},
    "Pumpkin": {"emoji": "🎃", "price": "3,000"},
    "Apple": {"emoji": "🍎", "price": "3,250"},
    "Bamboo": {"emoji": "🎋", "price": "4,000"},
    "Coconut": {"emoji": "🥥", "price": "6,000"},
    "Cactus": {"emoji": "🌵", "price": "15,000"},
    "Dragon Fruit": {"emoji": "🐉", "price": "50,000"},
    "Mango": {"emoji": "🥭", "price": "100,000"},
    "Grape": {"emoji": "🍇", "price": "850,000"},
    "Mushroom": {"emoji": "🍄", "price": "150,000"},
    "Pepper": {"emoji": "🌶️", "price": "1M"},
    "Cacao": {"emoji": "🍫", "price": "2.5M"},
    "Beanstalk": {"emoji": "🪜", "price": "10M"},
    "Ember Lily": {"emoji": "🔥", "price": "15M"},
    "Sugar Apple": {"emoji": "🍎", "price": "25M"},
    "Burning Bud": {"emoji": "🔥", "price": "40M"},
    "Giant Pinecone": {"emoji": "🌲", "price": "55M"},
    "Elder Strawberry": {"emoji": "🍓", "price": "70M"},
    "Romanesco": {"emoji": "🥦", "price": "88M"},
    "Crimson Thorn": {"emoji": "🌹", "price": "10B"},
    "Trinity Fruit": {"emoji": "🔱", "price": "100B"},
    "Broccoli": {"emoji": "🥦", "price": "600"},
    "Potato": {"emoji": "🥔", "price": "500"},
    "Cocomango": {"emoji": "🥥", "price": "5,000"},
}

GEAR_DATA = {
    "Watering Can": {"emoji": "💧", "price": "50k"},
    "Trowel": {"emoji": "🔨", "price": "100k"},
    "Trading Ticket": {"emoji": "🎫", "price": "100k"},
    "Recall Wrench": {"emoji": "🔧", "price": "150k"},
    "Basic Sprinkler": {"emoji": "💦", "price": "25k"},
    "Advanced Sprinkler": {"emoji": "💦", "price": "50k"},
    "Medium Treat": {"emoji": "🍖", "price": "4M"},
    "Medium Toy": {"emoji": "🎮", "price": "4M"},
    "Godly Sprinkler": {"emoji": "✨", "price": "120k"},
    "Magnifying Glass": {"emoji": "🔍", "price": "10M"},
    "Master Sprinkler": {"emoji": "👑", "price": "10M"},
    "Cleaning Spray": {"emoji": "🧼", "price": "15M"},
    "Favorite Tool": {"emoji": "⭐", "price": "20M"},
    "Harvest Tool": {"emoji": "✂️", "price": "30M"},
    "Friendship Pot": {"emoji": "🪴", "price": "15M"},
    "Level Up Lollipop": {"emoji": "🍭", "price": "10B"},
    "Grandmaster Sprinkler": {"emoji": "🏆", "price": "1B"},
    "Pet Name Reroller": {"emoji": "🎲", "price": "5M"},
    "Cleansing Pet Shard": {"emoji": "✨", "price": "3M"},
}

EGGS_DATA = {
    "Common Egg": {"emoji": "🥚", "price": "50k"},
    "Uncommon Egg": {"emoji": "🟡", "price": "150k"},
    "Rare Egg": {"emoji": "🔵", "price": "600k"},
    "Legendary Egg": {"emoji": "💜", "price": "3M"},
    "Mythical Egg": {"emoji": "🌈", "price": "8M"},
    "Bug Egg": {"emoji": "🐛", "price": "50M"},
    "Jungle Egg": {"emoji": "🦜", "price": "60M"},
}

EVENT_DATA = {
    "Orange Delight": {"emoji": "🍊", "price": "149", "category": "event"},
    "Explorer's Compass": {"emoji": "🧭", "price": "179", "category": "event"},
    "Safari Crate": {"emoji": "📦", "price": "179", "category": "event"},
    "Zebra Whistle": {"emoji": "🦓", "price": "179", "category": "event"},
    "Safari Egg": {"emoji": "🥚", "price": "149", "category": "event"},
    "Protea": {"emoji": "🌺", "price": "479", "category": "event"},
    "Lush Sprinkler": {"emoji": "💦", "price": "299", "category": "event"},
    "Mini Shipping Container": {"emoji": "🚢", "price": "179", "category": "event"},
    "Safari Totem Charm": {"emoji": "🗿", "price": "339", "category": "event"},
    "Baobab": {"emoji": "🌳", "price": "799", "category": "event"},
}

ITEMS_DATA = {}
ITEMS_DATA.update({k: {**v, "category": "seed"} for k, v in SEEDS_DATA.items()})
ITEMS_DATA.update({k: {**v, "category": "gear"} for k, v in GEAR_DATA.items()})
ITEMS_DATA.update({k: {**v, "category": "egg"} for k, v in EGGS_DATA.items()})
ITEMS_DATA.update(EVENT_DATA)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
last_stock_state: Dict[str, int] = {}
last_autostock_notification: Dict[str, datetime] = {}
user_autostocks_cache: Dict[int, Set[str]] = {}
subscription_cache: Dict[int, tuple] = {}
cached_stock_data: Optional[Dict] = None
cached_stock_time: Optional[datetime] = None
sent_rare_notifications: Set[str] = set()

NAME_TO_ID: Dict[str, str] = {}
ID_TO_NAME: Dict[str, str] = {}

SEED_ITEMS_LIST = []
GEAR_ITEMS_LIST = []
EGG_ITEMS_LIST = []

telegram_app: Optional[Application] = None
discord_client: Optional[discord.Client] = None
http_session: Optional[aiohttp.ClientSession] = None

# ========== УТИЛИТЫ ==========
def get_moscow_time() -> datetime:
    return datetime.now(pytz.timezone('Europe/Moscow'))

def format_moscow_time() -> str:
    return get_moscow_time().strftime('%H:%M:%S')

def get_next_check_time() -> datetime:
    now = get_moscow_time()
    current_minute = now.minute
    next_minute = ((current_minute // CHECK_INTERVAL_MINUTES) + 1) * CHECK_INTERVAL_MINUTES
    
    if next_minute >= 60:
        next_check = now.replace(minute=0, second=CHECK_DELAY_SECONDS, microsecond=0) + timedelta(hours=1)
    else:
        next_check = now.replace(minute=next_minute, second=CHECK_DELAY_SECONDS, microsecond=0)
    
    if next_check <= now:
        next_check += timedelta(minutes=CHECK_INTERVAL_MINUTES)
    
    return next_check

def calculate_sleep_time() -> float:
    next_check = get_next_check_time()
    now = get_moscow_time()
    return max((next_check - now).total_seconds(), 0)

def build_item_id_mappings():
    global NAME_TO_ID, ID_TO_NAME, SEED_ITEMS_LIST, GEAR_ITEMS_LIST, EGG_ITEMS_LIST
    
    for item_name in ITEMS_DATA.keys():
        hash_obj = hashlib.sha1(item_name.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()[:8]
        category = ITEMS_DATA[item_name]['category']
        safe_id = f"t_{category}_{hash_hex}"
        NAME_TO_ID[item_name] = safe_id
        ID_TO_NAME[safe_id] = item_name
    
    SEED_ITEMS_LIST = [(name, info) for name, info in sorted(ITEMS_DATA.items()) if info['category'] == 'seed']
    GEAR_ITEMS_LIST = [(name, info) for name, info in sorted(ITEMS_DATA.items()) if info['category'] == 'gear']
    EGG_ITEMS_LIST = [(name, info) for name, info in sorted(ITEMS_DATA.items()) if info['category'] == 'egg']
    
    logger.info(f"✅ Построены маппинги: {len(NAME_TO_ID)} предметов")

async def check_subscription(bot: Bot, user_id: int) -> bool:
    if user_id in subscription_cache:
        is_subscribed, cache_time = subscription_cache[user_id]
        if (get_moscow_time() - cache_time).total_seconds() < 300:
            return is_subscribed
    
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        is_subscribed = member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        subscription_cache[user_id] = (is_subscribed, get_moscow_time())
        return is_subscribed
    except:
        return True

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
    ])

# ========== БАЗА ДАННЫХ ==========
class SupabaseDB:
    def __init__(self):
        self.headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json"
        }
    
    async def get_session(self) -> aiohttp.ClientSession:
        global http_session
        if http_session is None or http_session.closed:
            http_session = aiohttp.ClientSession()
        return http_session
    
    async def save_user(self, user_id: int, username: str = None, first_name: str = None):
        try:
            session = await self.get_session()
            data = {"user_id": user_id, "username": username, "first_name": first_name, "last_seen": datetime.now(pytz.UTC).isoformat()}
            headers = {**self.headers, "Prefer": "resolution=merge-duplicates"}
            async with session.post(USERS_URL, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status in [200, 201]
        except Exception as e:
            logger.error(f"❌ Сохранение пользователя: {e}")
            return False
    
    async def load_user_autostocks(self, user_id: int) -> Set[str]:
        if user_id in user_autostocks_cache:
            return user_autostocks_cache[user_id].copy()
        
        try:
            session = await self.get_session()
            params = {"user_id": f"eq.{user_id}", "select": "item_name"}
            async with session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    items_set = {item['item_name'] for item in data}
                    user_autostocks_cache[user_id] = items_set
                    return items_set
                return set()
        except Exception as e:
            logger.error(f"❌ Загрузка автостоков: {e}")
            return user_autostocks_cache.get(user_id, set()).copy()
    
    async def save_user_autostock(self, user_id: int, item_name: str) -> bool:
        try:
            session = await self.get_session()
            data = {"user_id": user_id, "item_name": item_name}
            headers = {**self.headers, "Prefer": "resolution=merge-duplicates"}
            async with session.post(AUTOSTOCKS_URL, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                success = response.status in [200, 201]
                if success:
                    if user_id not in user_autostocks_cache:
                        user_autostocks_cache[user_id] = set()
                    user_autostocks_cache[user_id].add(item_name)
                    logger.info(f"✅ Добавлен: {user_id} -> {item_name}")
                return success
        except Exception as e:
            logger.error(f"❌ Сохранение: {e}")
            return False
    
    async def remove_user_autostock(self, user_id: int, item_name: str) -> bool:
        try:
            session = await self.get_session()
            params = {"user_id": f"eq.{user_id}", "item_name": f"eq.{item_name}"}
            async with session.delete(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                success = response.status in [200, 204]
                if success:
                    if user_id in user_autostocks_cache:
                        user_autostocks_cache[user_id].discard(item_name)
                    logger.info(f"✅ Удален: {user_id} -> {item_name}")
                return success
        except Exception as e:
            logger.error(f"❌ Удаление: {e}")
            return False
    
    async def get_users_tracking_item(self, item_name: str) -> List[int]:
        try:
            session = await self.get_session()
            params = {"item_name": f"eq.{item_name}", "select": "user_id"}
            logger.debug(f"🔍 Запрос пользователей для: {item_name}")
            async with session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    user_ids = [item['user_id'] for item in data]
                    logger.debug(f"✅ Найдено {len(user_ids)} пользователей для {item_name}: {user_ids}")
                    return user_ids
                else:
                    logger.warning(f"⚠️ Статус {response.status} для {item_name}")
                return []
        except Exception as e:
            logger.error(f"❌ Получение пользователей для {item_name}: {e}")
            return []

# ========== DISCORD ПАРСЕР ==========
class DiscordStockParser:
    def __init__(self):
        self.db = SupabaseDB()
        self.telegram_bot: Optional[Bot] = None
    
    def parse_stock_message(self, content: str, channel_name: str) -> Dict:
        result = {"seeds": [], "gear": [], "eggs": [], "events": []}
        lines = content.split('\n')
        
        logger.debug(f"🔍 Парсинг канала {channel_name}, строк: {len(lines)}")
        
        if channel_name == "event_content":
            for line in lines:
                line = line.strip()
                if 'x' in line and not any(skip in line.lower() for skip in ['shop', 'stock', 'safari', 'updated', 'limited', 'today']):
                    clean_line = re.sub(r'[•\*\-]', '', line)
                    match = re.search(r'([A-Za-z\s\'\-]+?)\s+(\d+)x', clean_line)
                    if match:
                        item_name = match.group(1).strip()
                        quantity = int(match.group(2))
                        if quantity > 0 and item_name in EVENT_DATA:
                            result['events'].append((item_name, quantity))
                            logger.debug(f"✅ Найден event: {item_name} x{quantity}")
            return result
        
        current_section = None
        for line in lines:
            line = line.strip()
            if 'SEEDS STOCK' in line.upper():
                current_section = 'seeds'
                logger.debug("📍 Секция: SEEDS")
            elif 'GEAR STOCK' in line.upper():
                current_section = 'gear'
                logger.debug("📍 Секция: GEAR")
            elif 'EGG STOCK' in line.upper():
                current_section = 'eggs'
                logger.debug("📍 Секция: EGGS")
            elif 'COSMETICS' in line.upper():
                current_section = None
                logger.debug("📍 Секция: COSMETICS (пропуск)")
            elif current_section and 'x' in line:
                clean_line = re.sub(r'[^\w\s\-]', '', line)
                match = re.search(r'([A-Za-z\s\-]+)\s*x(\d+)', clean_line)
                if match:
                    item_name = match.group(1).strip()
                    quantity = int(match.group(2))
                    if quantity > 0:
                        result[current_section].append((item_name, quantity))
                        logger.debug(f"✅ Найден {current_section}: {item_name} x{quantity}")
        
        total = len(result['seeds']) + len(result['gear']) + len(result['eggs']) + len(result['events'])
        logger.info(f"📦 Парсинг завершен: {total} предметов")
        return result
    
    def format_stock_message(self, stock_data: Dict) -> str:
        if not stock_data:
            return "❌ *Не удалось получить данные о стоке*"
        
        message = "📊 *ТЕКУЩИЙ СТОК*\n\n"
        
        for category, emoji, title in [('seeds', '🌱', 'СЕМЕНА'), ('gear', '⚔️', 'ГИРЫ'), ('eggs', '🥚', 'ЯЙЦА'), ('events', '🌴', 'SAFARI SHOP')]:
            items = stock_data.get(category, [])
            if items:
                message += f"{emoji} *{title}:*\n"
                for item_name, quantity in items:
                    if category == 'seeds':
                        item_info = SEEDS_DATA.get(item_name, {"emoji": emoji, "price": "?"})
                    elif category == 'gear':
                        item_info = GEAR_DATA.get(item_name, {"emoji": "⚔️", "price": "?"})
                    elif category == 'eggs':
                        item_info = EGGS_DATA.get(item_name, {"emoji": "🥚", "price": "?"})
                    else:
                        item_info = EVENT_DATA.get(item_name, {"emoji": "📦", "price": "?"})
                    message += f"{item_info['emoji']} {item_name} x{quantity}\n"
                message += "\n"
            else:
                message += f"{emoji} *{title}:* _Пусто_\n\n"
        
        message += f"🕒 {format_moscow_time()} МСК"
        return message
    
    async def send_autostock_notification(self, bot: Bot, user_id: int, item_name: str, count: int):
        try:
            item_info = ITEMS_DATA.get(item_name, {"emoji": "📦", "price": "?"})
            message = (
                f"🔔 *АВТОСТОК*\n\n"
                f"{item_info['emoji']} *{item_name}*\n"
                f"📦 x{count}\n"
                f"💰 {item_info['price']} ¢\n\n"
                f"🕒 {format_moscow_time()}"
            )
            await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"📤 Уведомление: {user_id} -> {item_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки {user_id}: {e}")
    
    async def send_rare_notification_to_channel(self, bot: Bot, item_name: str, count: int):
        try:
            item_info = ITEMS_DATA.get(item_name, {"emoji": "📦", "price": "?"})
            message = (
                f"🚨 *РЕДКИЙ СТОК!* 🚨\n\n"
                f"{item_info['emoji']} *{item_name}*\n"
                f"📦 x{count}\n"
                f"💰 {item_info['price']} ¢\n\n"
                f"🕒 {format_moscow_time()}"
            )
            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"🚨 Редкое уведомление в канал: {item_name} x{count}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки редкого уведомления: {e}")
    
    async def check_user_autostocks(self, stock_data: Dict, bot: Bot):
        global last_autostock_notification, sent_rare_notifications
        if not stock_data:
            logger.warning("⚠️ stock_data пустой")
            return

        current_stock = {}
        for stock_type in ['seeds', 'gear', 'eggs']:
            for item_name, quantity in stock_data.get(stock_type, []):
                if quantity > 0:
                    current_stock[item_name] = quantity
        
        logger.info(f"📦 Текущий сток: {list(current_stock.keys())}")

        # Проверка редких семян для канала
        for item_name in RAREST_SEEDS:
            if item_name in current_stock:
                notification_key = f"{item_name}_{current_stock[item_name]}"
                if notification_key not in sent_rare_notifications:
                    logger.info(f"🚨 Найдено редкое семя: {item_name} x{current_stock[item_name]}")
                    await self.send_rare_notification_to_channel(bot, item_name, current_stock[item_name])
                    sent_rare_notifications.add(notification_key)
                else:
                    logger.debug(f"🔕 Редкое семя {item_name} уже было отправлено")
        
        # Очистка старых редких уведомлений
        sent_rare_notifications_copy = sent_rare_notifications.copy()
        for notification_key in sent_rare_notifications_copy:
            item_name = notification_key.rsplit('_', 1)[0]
            if item_name not in current_stock:
                sent_rare_notifications.discard(notification_key)
                logger.info(f"🗑️ Очищено старое уведомление: {notification_key}")

        # Проверка автостоков пользователей
        items_to_check = []
        now = get_moscow_time()
        for item_name in current_stock.keys():
            if item_name not in last_autostock_notification:
                items_to_check.append(item_name)
                logger.info(f"🆕 Новый предмет для проверки: {item_name}")
            else:
                time_diff = (now - last_autostock_notification[item_name]).total_seconds()
                if time_diff >= 300:
                    items_to_check.append(item_name)
                    logger.info(f"⏰ Прошло {int(time_diff)}с для {item_name}, проверяем снова")
                else:
                    logger.debug(f"⏳ {item_name} проверялся {int(time_diff)}с назад, пропускаем")
        
        if not items_to_check:
            logger.info("✅ Нет предметов для проверки автостоков")
            return
        
        logger.info(f"🔍 Проверка автостоков: {items_to_check}")
        
        tasks = [self.db.get_users_tracking_item(item_name) for item_name in items_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        send_count = 0
        for item_name, result in zip(items_to_check, results):
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка получения пользователей для {item_name}: {result}")
                continue
                
            if result:
                count = current_stock[item_name]
                logger.info(f"📨 {item_name}: найдено {len(result)} пользователей - {result}")
                for user_id in result:
                    try:
                        asyncio.create_task(self.send_autostock_notification(bot, user_id, item_name, count))
                        send_count += 1
                    except Exception as e:
                        logger.error(f"❌ Ошибка создания задачи для {user_id}: {e}")
                last_autostock_notification[item_name] = now
            else:
                logger.info(f"👤 {item_name}: нет пользователей, отслеживающих этот предмет")
        
        if send_count > 0:
            logger.info(f"✅ Отправлено {send_count} уведомлений")
        else:
            logger.info("ℹ️ Уведомления не отправлены - нет отслеживающих пользователей")

parser = DiscordStockParser()

# ========== DISCORD CLIENT ==========
class StockDiscordClient(discord.Client):
    def __init__(self):
        super().__init__()
        self.stock_lock = asyncio.Lock()
    
    async def on_ready(self):
        logger.info(f'✅ Discord подключен: {self.user}')
        for channel_name, channel_id in DISCORD_CHANNELS.items():
            channel = self.get_channel(channel_id)
            if channel:
                logger.info(f"✅ Канал {channel_name}: {channel.name}")
            else:
                logger.warning(f"⚠️ Канал {channel_name} (ID: {channel_id}) не найден")
    
    async def fetch_stock_data(self) -> Dict:
        global cached_stock_data, cached_stock_time
        
        now = get_moscow_time()
        if cached_stock_data and cached_stock_time:
            if (now - cached_stock_time).total_seconds() < 30:
                return cached_stock_data
        
        async with self.stock_lock:
            stock_data = {"seeds": [], "gear": [], "eggs": [], "events": []}
            
            for channel_name, channel_id in DISCORD_CHANNELS.items():
                try:
                    channel = self.get_channel(channel_id)
                    if not channel:
                        logger.warning(f"⚠️ Канал {channel_name} не найден")
                        continue
                    
                    async for msg in channel.history(limit=5):
                        if msg.author.bot and ('Vulcan' in msg.author.name or 'Dawn' in msg.author.name):
                            content = ""
                            if msg.embeds:
                                for embed in msg.embeds:
                                    if embed.description:
                                        content += embed.description + "\n"
                                    for field in embed.fields:
                                        content += f"{field.name}\n{field.value}\n"
                            if msg.content:
                                content += msg.content
                            
                            if content:
                                parsed = parser.parse_stock_message(content, channel_name)
                                for category in parsed:
                                    stock_data[category].extend(parsed[category])
                                break
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга {channel_name}: {e}")
            
            cached_stock_data = stock_data
            cached_stock_time = now
            logger.info(f"📦 Собрано: {len(stock_data['seeds'])} семян, {len(stock_data['gear'])} гиров, {len(stock_data['eggs'])} яиц, {len(stock_data['events'])} ивентов")
            return stock_data

# ========== КОМАНДЫ ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    user = update.effective_user
    asyncio.create_task(parser.db.save_user(user.id, user.username, user.first_name))
    
    if not await check_subscription(context.bot, user.id):
        await update.effective_message.reply_text(
            f"👋 *Добро пожаловать!*\n\n🔒 Подпишитесь на @{CHANNEL_USERNAME}",
            reply_markup=get_subscription_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await update.effective_message.reply_text(
        "👋 *GAG Stock Tracker*\n\n📊 /stock - Текущий сток\n🔔 /autostock - Автостоки\n❓ /help - Помощь",
        parse_mode=ParseMode.MARKDOWN
    )

async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    if not await check_subscription(context.bot, update.effective_user.id):
        await update.effective_message.reply_text("🔒 Подпишитесь на канал", reply_markup=get_subscription_keyboard())
        return
    
    if not discord_client or not discord_client.is_ready():
        await update.effective_message.reply_text("⚠️ *Discord загружается...*", parse_mode=ParseMode.MARKDOWN)
        return
    
    stock_data = await discord_client.fetch_stock_data()
    message = parser.format_stock_message(stock_data)
    await update.effective_message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def autostock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    if not await check_subscription(context.bot, update.effective_user.id):
        await update.effective_message.reply_text("🔒 Подпишитесь на канал", reply_markup=get_subscription_keyboard())
        return
    
    keyboard = [
        [InlineKeyboardButton("🌱 Семена", callback_data="as_seeds")],
        [InlineKeyboardButton("⚔️ Гиры", callback_data="as_gear")],
        [InlineKeyboardButton("🥚 Яйца", callback_data="as_eggs")],
        [InlineKeyboardButton("📋 Мои автостоки", callback_data="as_list")],
    ]
    
    await update.effective_message.reply_text(
        "🔔 *АВТОСТОКИ*\n\nВыберите категорию\n⏰ Проверка: каждые 5 минут",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def autostock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not update.effective_user:
        await query.answer()
        return
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "check_sub":
        subscription_cache.pop(user_id, None)
        if await check_subscription(context.bot, user_id):
            await query.edit_message_text("✅ *Подписка подтверждена!*\n\n📊 /stock\n🔔 /autostock", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("❌ Вы не подписались", show_alert=True)
        return
    
    if not await check_subscription(context.bot, user_id):
        await query.answer("🔒 Подпишитесь на канал", show_alert=True)
        return
    
    try:
        if data in ["as_seeds", "as_gear", "as_eggs"]:
            user_items = await parser.db.load_user_autostocks(user_id)
            
            if data == "as_seeds":
                items_list, header = SEED_ITEMS_LIST, "🌱 *СЕМЕНА*"
            elif data == "as_gear":
                items_list, header = GEAR_ITEMS_LIST, "⚔️ *ГИРЫ*"
            else:
                items_list, header = EGG_ITEMS_LIST, "🥚 *ЯЙЦА*"
            
            keyboard = []
            for item_name, item_info in items_list:
                status = "✅" if item_name in user_items else "➕"
                keyboard.append([InlineKeyboardButton(
                    f"{status} {item_info['emoji']} {item_name}",
                    callback_data=NAME_TO_ID.get(item_name, "invalid")
                )])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="as_back")])
            
            await query.answer()
            await query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        
        elif data == "as_list":
            user_items = await parser.db.load_user_autostocks(user_id)
            if not user_items:
                message = "📋 *МОИ АВТОСТОКИ*\n\n_Пусто_"
            else:
                items_list = []
                for item_name in sorted(user_items):
                    item_info = ITEMS_DATA.get(item_name, {"emoji": "📦", "price": "?"})
                    items_list.append(f"{item_info['emoji']} {item_name}")
                message = f"📋 *МОИ АВТОСТОКИ*\n\n" + "\n".join(items_list)
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="as_back")]]
            await query.answer()
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        
        elif data == "as_back":
            keyboard = [
                [InlineKeyboardButton("🌱 Семена", callback_data="as_seeds")],
                [InlineKeyboardButton("⚔️ Гиры", callback_data="as_gear")],
                [InlineKeyboardButton("🥚 Яйца", callback_data="as_eggs")],
                [InlineKeyboardButton("📋 Мои автостоки", callback_data="as_list")],
            ]
            await query.answer()
            await query.edit_message_text("🔔 *АВТОСТОКИ*\n\nВыберите категорию", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        
        elif data.startswith("t_"):
            item_name = ID_TO_NAME.get(data)
            if not item_name:
                await query.answer("❌ Ошибка", show_alert=True)
                return
            
            category = ITEMS_DATA.get(item_name, {}).get('category', 'seed')
            user_autostocks_cache.pop(user_id, None)
            user_items = await parser.db.load_user_autostocks(user_id)
            
            if item_name in user_items:
                success = await parser.db.remove_user_autostock(user_id, item_name)
                if success:
                    await query.answer(f"❌ {item_name} удален")
                else:
                    await query.answer("⚠️ Ошибка", show_alert=True)
                    return
            else:
                success = await parser.db.save_user_autostock(user_id, item_name)
                if success:
                    await query.answer(f"✅ {item_name} добавлен")
                else:
                    await query.answer("⚠️ Ошибка", show_alert=True)
                    return
            
            user_autostocks_cache.pop(user_id, None)
            user_items = await parser.db.load_user_autostocks(user_id)
            
            if category == 'seed':
                items_list = SEED_ITEMS_LIST
            elif category == 'gear':
                items_list = GEAR_ITEMS_LIST
            else:
                items_list = EGG_ITEMS_LIST
            
            keyboard = []
            for name, info in items_list:
                status = "✅" if name in user_items else "➕"
                keyboard.append([InlineKeyboardButton(
                    f"{status} {info['emoji']} {name}",
                    callback_data=NAME_TO_ID.get(name, "invalid")
                )])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="as_back")])
            
            try:
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
            except:
                pass
    
    except Exception as e:
        logger.error(f"❌ Callback: {e}")
        await query.answer("⚠️ Ошибка", show_alert=True)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    if not await check_subscription(context.bot, update.effective_user.id):
        await update.effective_message.reply_text("🔒 Подпишитесь на канал", reply_markup=get_subscription_keyboard())
        return
    
    await update.effective_message.reply_text(
        "📚 *КОМАНДЫ*\n\n"
        "/start - Запуск бота\n"
        "/stock - Текущий сток\n"
        "/autostock - Настройка автостоков\n"
        "/test - Тестовая проверка\n"
        "/checknow - Проверить сейчас\n"
        "/help - Помощь\n\n"
        "⏰ Проверка: каждые 5 минут и 10 секунд\n"
        f"🌹 Редкие: {', '.join(RAREST_SEEDS)}",
        parse_mode=ParseMode.MARKDOWN
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    if not await check_subscription(context.bot, update.effective_user.id):
        await update.effective_message.reply_text("🔒 Подпишитесь на канал", reply_markup=get_subscription_keyboard())
        return
    
    user_id = update.effective_user.id
    
    # Проверяем автостоки пользователя
    user_items = await parser.db.load_user_autostocks(user_id)
    
    msg = f"🧪 *ТЕСТ АВТОСТОКОВ*\n\n"
    msg += f"👤 User ID: `{user_id}`\n"
    msg += f"📋 Отслеживаемых: {len(user_items)}\n\n"
    
    if user_items:
        msg += "*Ваши автостоки:*\n"
        for item in sorted(user_items):
            msg += f"• {item}\n"
    else:
        msg += "_Нет автостоков_"
    
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def check_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    if not await check_subscription(context.bot, update.effective_user.id):
        await update.effective_message.reply_text("🔒 Подпишитесь на канал", reply_markup=get_subscription_keyboard())
        return
    
    if not discord_client or not discord_client.is_ready():
        await update.effective_message.reply_text("⚠️ *Discord не готов*", parse_mode=ParseMode.MARKDOWN)
        return
    
    await update.effective_message.reply_text("🔄 *Запускаю проверку...*", parse_mode=ParseMode.MARKDOWN)
    
    try:
        stock_data = await discord_client.fetch_stock_data()
        if stock_data:
            await parser.check_user_autostocks(stock_data, context.bot)
            
            total = len(stock_data['seeds']) + len(stock_data['gear']) + len(stock_data['eggs'])
            msg = f"✅ *Проверка завершена*\n\n📦 Найдено: {total} предметов\n"
            msg += f"🌱 Семена: {len(stock_data['seeds'])}\n"
            msg += f"⚔️ Гиры: {len(stock_data['gear'])}\n"
            msg += f"🥚 Яйца: {len(stock_data['eggs'])}\n"
            
            await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.effective_message.reply_text("❌ *Не удалось получить данные*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"❌ Ошибка ручной проверки: {e}")
        await update.effective_message.reply_text(f"❌ *Ошибка:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

# ========== ПЕРИОДИЧЕСКАЯ ПРОВЕРКА ==========
async def periodic_stock_check(application: Application):
    logger.info("🚀 Периодическая проверка запущена")
    
    # Ждем пока Discord подключится
    wait_time = 0
    while (not discord_client or not discord_client.is_ready()) and wait_time < 60:
        await asyncio.sleep(1)
        wait_time += 1
    
    if not discord_client or not discord_client.is_ready():
        logger.error("❌ Discord не готов, периодическая проверка не запустится")
        return
    
    parser.telegram_bot = application.bot
    logger.info("✅ Периодическая проверка готова к работе")
    
    try:
        initial_sleep = calculate_sleep_time()
        logger.info(f"⏰ Первая проверка через {int(initial_sleep)}с ({get_next_check_time().strftime('%H:%M:%S')})")
        await asyncio.sleep(initial_sleep)

        check_count = 0
        while True:
            try:
                check_count += 1
                now = get_moscow_time()
                logger.info(f"🔍 Проверка #{check_count} - {now.strftime('%H:%M:%S')}")
                
                stock_data = await discord_client.fetch_stock_data()
                if stock_data:
                    await parser.check_user_autostocks(stock_data, application.bot)
                else:
                    logger.warning("⚠️ Нет данных о стоке")
                
                sleep_time = calculate_sleep_time()
                next_time = get_next_check_time()
                logger.info(f"💤 Следующая проверка в {next_time.strftime('%H:%M:%S')} (через {int(sleep_time)}с)")
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                logger.info("⚠️ Периодическая проверка отменена")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка проверки: {e}", exc_info=True)
                await asyncio.sleep(60)
    except asyncio.CancelledError:
        logger.info("⚠️ Периодическая проверка остановлена")

async def post_init(application: Application):
    asyncio.create_task(periodic_stock_check(application))

# ========== MAIN ==========
def main():
    logger.info("="*60)
    logger.info("🌱 GAG Stock Tracker Bot v3.2")
    logger.info("="*60)

    build_item_id_mappings()

    global discord_client
    discord_client = StockDiscordClient()
    
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("stock", stock_command))
    telegram_app.add_handler(CommandHandler("autostock", autostock_command))
    telegram_app.add_handler(CommandHandler("test", test_command))
    telegram_app.add_handler(CommandHandler("checknow", check_now_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CallbackQueryHandler(autostock_callback))

    telegram_app.post_init = post_init

    async def shutdown_callback(app: Application):
        logger.info("🛑 Остановка бота")
        if discord_client:
            await discord_client.close()
        if http_session and not http_session.closed:
            await http_session.close()

    telegram_app.post_shutdown = shutdown_callback

    async def run_both():
        discord_task = asyncio.create_task(discord_client.start(DISCORD_TOKEN))
        
        timeout = 30
        elapsed = 0
        while not discord_client.is_ready() and elapsed < timeout:
            await asyncio.sleep(0.5)
            elapsed += 0.5
        
        if not discord_client.is_ready():
            logger.error("❌ Discord не смог подключиться за 30 секунд")
            return
        
        logger.info("✅ Discord готов к работе")
        
        await telegram_app.initialize()
        await telegram_app.start()
        
        # Важно: drop_pending_updates=True убирает конфликты
        await telegram_app.updater.start_polling(
            allowed_updates=None, 
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=30
        )
        
        logger.info("🚀 Telegram бот запущен!")
        logger.info("="*60)
        logger.info(f"⏰ Интервал проверки: каждые {CHECK_INTERVAL_MINUTES} минут и {CHECK_DELAY_SECONDS} секунд")
        logger.info(f"🌹 Редкие семена: {', '.join(RAREST_SEEDS)}")
        logger.info("="*60)
        
        try:
            await discord_task
        except KeyboardInterrupt:
            logger.info("⚠️ Получен сигнал остановки")
        finally:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
    
    try:
        asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("⚠️ Остановка по Ctrl+C")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    main()