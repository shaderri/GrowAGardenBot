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

load_dotenv()

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@GroowAGarden")
CHANNEL_USERNAME = "GroowAGarden"

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tcsmfiixhflzrxkrbslk.supabase.co")
SUPABASE_API_KEY = os.getenv("SUPABASE_KEY", "")

AUTOSTOCKS_URL = f"{SUPABASE_URL}/rest/v1/user_autostocks"
USERS_URL = f"{SUPABASE_URL}/rest/v1/users"

# Discord каналы
DISCORD_CHANNELS = {
    "stock": 1373218015042207804,
    "egg_stock": 1373218102313091072,
    "cosmetics_stock": 1376539587949887499,
    "event_content": 1396257564311949503,
}

CHECK_INTERVAL_MINUTES = 5
CHECK_DELAY_SECONDS = 10

RAREST_SEEDS = ["Crimson Thorn", "Great Pumpkin"]

if not BOT_TOKEN or not DISCORD_TOKEN:
    raise ValueError("BOT_TOKEN и DISCORD_TOKEN должны быть установлены!")

# ========== ЛОГИРОВАНИЕ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)

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
    "Pepper": {"emoji": "🌶️", "price": "1,000,000"},
    "Cacao": {"emoji": "🍫", "price": "2,500,000"},
    "Beanstalk": {"emoji": "🪜", "price": "10,000,000"},
    "Ember Lily": {"emoji": "🔥", "price": "15,000,000"},
    "Sugar Apple": {"emoji": "🍎", "price": "25,000,000"},
    "Burning Bud": {"emoji": "🔥", "price": "40,000,000"},
    "Giant Pinecone": {"emoji": "🌲", "price": "55,000,000"},
    "Elder Strawberry": {"emoji": "🍓", "price": "70,000,000"},
    "Romanesco": {"emoji": "🥦", "price": "88,000,000"},
    "Crimson Thorn": {"emoji": "🌹", "price": "10B"},
    "Great Pumpkin": {"emoji": "🎃", "price": "1T"},
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
user_autostocks_time: Dict[int, datetime] = {}
user_cooldowns: Dict[int, Dict[str, datetime]] = {}
subscription_cache: Dict[int, tuple] = {}

# Кеш для стока
cached_stock_data: Optional[Dict] = None
cached_stock_time: Optional[datetime] = None
STOCK_CACHE_TTL = 30  # 30 секунд

AUTOSTOCK_CACHE_TTL = 180
MAX_CACHE_SIZE = 15000
COMMAND_COOLDOWN = 3  # Уменьшен до 3 секунд
AUTOSTOCK_NOTIFICATION_COOLDOWN = 600
SUBSCRIPTION_CACHE_TTL = 300

NAME_TO_ID: Dict[str, str] = {}
ID_TO_NAME: Dict[str, str] = {}

SEED_ITEMS_LIST = [(name, info) for name, info in ITEMS_DATA.items() if info['category'] == 'seed']
GEAR_ITEMS_LIST = [(name, info) for name, info in ITEMS_DATA.items() if info['category'] == 'gear']
EGG_ITEMS_LIST = [(name, info) for name, info in ITEMS_DATA.items() if info['category'] == 'egg']
EVENT_ITEMS_LIST = [(name, info) for name, info in ITEMS_DATA.items() if info['category'] == 'event']

telegram_app: Optional[Application] = None
discord_client: Optional[discord.Client] = None

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
    sleep_seconds = (next_check - now).total_seconds()
    return max(sleep_seconds, 0)

def build_item_id_mappings():
    global NAME_TO_ID, ID_TO_NAME
    NAME_TO_ID.clear()
    ID_TO_NAME.clear()
    
    for item_name in ITEMS_DATA.keys():
        hash_obj = hashlib.sha1(item_name.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()[:8]
        category = ITEMS_DATA[item_name]['category']
        safe_id = f"t_{category}_{hash_hex}"
        
        NAME_TO_ID[item_name] = safe_id
        ID_TO_NAME[safe_id] = item_name
        
    logger.info(f"✅ Построены маппинги: {len(NAME_TO_ID)} предметов")

def _cleanup_cache():
    global user_autostocks_cache, user_autostocks_time, subscription_cache
    
    now = get_moscow_time()
    
    if len(user_autostocks_cache) > MAX_CACHE_SIZE:
        to_delete = [uid for uid, ct in user_autostocks_time.items() 
                     if (now - ct).total_seconds() > 600]
        
        for user_id in to_delete:
            user_autostocks_cache.pop(user_id, None)
            user_autostocks_time.pop(user_id, None)
        
        if to_delete:
            logger.info(f"♻️ Очищено {len(to_delete)} автостоков")
    
    if len(subscription_cache) > 5000:
        to_delete = [uid for uid, (_, ct) in list(subscription_cache.items()) 
                     if (now - ct).total_seconds() > 600]
        
        for user_id in to_delete:
            subscription_cache.pop(user_id, None)

def check_command_cooldown(user_id: int, command: str) -> tuple:
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = {}
    
    if command in user_cooldowns[user_id]:
        last_time = user_cooldowns[user_id][command]
        now = get_moscow_time()
        elapsed = (now - last_time).total_seconds()
        
        if elapsed < COMMAND_COOLDOWN:
            seconds_left = int(COMMAND_COOLDOWN - elapsed)
            return (False, seconds_left)
    
    user_cooldowns[user_id][command] = get_moscow_time()
    return (True, None)

async def check_subscription(bot: Bot, user_id: int) -> bool:
    global subscription_cache
    
    if user_id in subscription_cache:
        is_subscribed, cache_time = subscription_cache[user_id]
        if (get_moscow_time() - cache_time).total_seconds() < SUBSCRIPTION_CACHE_TTL:
            return is_subscribed
    
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        is_subscribed = member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        
        subscription_cache[user_id] = (is_subscribed, get_moscow_time())
        return is_subscribed
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подписки для {user_id}: {e}")
        subscription_cache[user_id] = (True, get_moscow_time())
        return True

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== БАЗА ДАННЫХ ==========
class SupabaseDB:
    def __init__(self):
        self.headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    
    async def save_user(self, user_id: int, username: str = None, first_name: str = None):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                data = {
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_seen": datetime.now(pytz.UTC).isoformat()
                }
                
                async with session.post(
                    USERS_URL, 
                    json=data, 
                    headers={**self.headers, "Prefer": "resolution=merge-duplicates"},
                    timeout=5
                ) as response:
                    return response.status in [200, 201]
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя: {e}")
            return False
    
    async def load_user_autostocks(self, user_id: int, use_cache: bool = True) -> Set[str]:
        if use_cache and user_id in user_autostocks_cache:
            cache_time = user_autostocks_time.get(user_id)
            if cache_time:
                now = get_moscow_time()
                if (now - cache_time).total_seconds() < AUTOSTOCK_CACHE_TTL:
                    return user_autostocks_cache[user_id].copy()
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                params = {"user_id": f"eq.{user_id}", "select": "item_name"}
                
                async with session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        items_set = {item['item_name'] for item in data}
                        
                        user_autostocks_cache[user_id] = items_set
                        user_autostocks_time[user_id] = get_moscow_time()
                        
                        return items_set
                    return set()
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки автостоков: {e}")
            return user_autostocks_cache.get(user_id, set()).copy()
    
    async def save_user_autostock(self, user_id: int, item_name: str) -> bool:
        if user_id not in user_autostocks_cache:
            user_autostocks_cache[user_id] = set()
        user_autostocks_cache[user_id].add(item_name)
        user_autostocks_time[user_id] = get_moscow_time()
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                data = {"user_id": user_id, "item_name": item_name}
                
                async with session.post(AUTOSTOCKS_URL, json=data, headers=self.headers, timeout=5) as response:
                    return response.status in [200, 201]
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            return False
    
    async def remove_user_autostock(self, user_id: int, item_name: str) -> bool:
        if user_id in user_autostocks_cache:
            user_autostocks_cache[user_id].discard(item_name)
            user_autostocks_time[user_id] = get_moscow_time()
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                params = {"user_id": f"eq.{user_id}", "item_name": f"eq.{item_name}"}
                
                async with session.delete(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=5) as response:
                    return response.status in [200, 204]
        except Exception as e:
            logger.error(f"❌ Ошибка удаления: {e}")
            return False
    
    async def get_users_tracking_item(self, item_name: str) -> List[int]:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                params = {"item_name": f"eq.{item_name}", "select": "user_id"}
                
                async with session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [item['user_id'] for item in data]
                    return []
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей: {e}")
            return []

# ========== DISCORD ПАРСЕР ==========
class DiscordStockParser:
    def __init__(self):
        self.db = SupabaseDB()
        self.telegram_bot: Optional[Bot] = None
    
    def parse_stock_message(self, content: str, channel_name: str) -> Dict:
        """Парсинг с учетом типа канала"""
        result = {
            "seeds": [],
            "gear": [],
            "eggs": [],
            "events": []
        }
        
        lines = content.split('\n')
        
        # Для event_content всё идёт в events
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
            return result
        
        # Для остальных каналов
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if 'SEEDS STOCK' in line or 'Spooky Seeds' in line:
                current_section = 'seeds'
                continue
            elif 'GEAR STOCK' in line or 'Ghostly Gadgets' in line:
                current_section = 'gear'
                continue
            elif 'EGG STOCK' in line or 'Creepy Critters' in line:
                current_section = 'eggs'
                continue
            elif 'COSMETICS STOCK' in line or 'Devilish Decor' in line:
                current_section = None  # Пропускаем косметику
                continue
            
            if current_section and 'x' in line:
                clean_line = re.sub(r'[^\w\s\-]', '', line)
                match = re.search(r'([A-Za-z\s\-]+)\s*x(\d+)', clean_line)
                
                if match:
                    item_name = match.group(1).strip()
                    quantity = int(match.group(2))
                    
                    if quantity > 0:
                        result[current_section].append((item_name, quantity))
        
        return result
    
    def format_stock_message(self, stock_data: Dict) -> str:
        if not stock_data:
            return "❌ *Не удалось получить данные о стоке*\n\n_Discord клиент не готов или нет данных_"
        
        current_time = format_moscow_time()
        message = "📊 *ТЕКУЩИЙ СТОК*\n\n"
        
        # Семена
        seeds = stock_data.get('seeds', [])
        if seeds:
            message += "🌱 *СЕМЕНА:*\n"
            for item_name, quantity in seeds:
                item_info = SEEDS_DATA.get(item_name, {"emoji": "🌱", "price": "?"})
                message += f"{item_info['emoji']} {item_name} x{quantity}\n"
            message += "\n"
        else:
            message += "🌱 *СЕМЕНА:* _Пусто_\n\n"
        
        # Гиры
        gear = stock_data.get('gear', [])
        if gear:
            message += "⚔️ *ГИРЫ:*\n"
            for item_name, quantity in gear:
                item_info = GEAR_DATA.get(item_name, {"emoji": "⚔️", "price": "?"})
                message += f"{item_info['emoji']} {item_name} x{quantity}\n"
            message += "\n"
        else:
            message += "⚔️ *ГИРЫ:* _Пусто_\n\n"
        
        # Яйца
        eggs = stock_data.get('eggs', [])
        if eggs:
            message += "🥚 *ЯЙЦА:*\n"
            for item_name, quantity in eggs:
                item_info = EGGS_DATA.get(item_name, {"emoji": "🥚", "price": "?"})
                message += f"{item_info['emoji']} {item_name} x{quantity}\n"
            message += "\n"
        else:
            message += "🥚 *ЯЙЦА:* _Пусто_\n\n"
        
        # Ивент
        events = stock_data.get('events', [])
        if events:
            message += "🌴 *SAFARI SHOP (ИВЕНТ):*\n"
            for item_name, quantity in events:
                item_info = EVENT_DATA.get(item_name, {"emoji": "📦", "price": "?"})
                message += f"{item_info['emoji']} {item_name} x{quantity}\n"
        else:
            message += "🌴 *SAFARI SHOP:* _Пусто_"
        
        message += f"\n\n🕒 {current_time} МСК"
        return message
    
    async def send_notification(self, bot: Bot, channel_id: str, item_name: str, count: int):
        try:
            item_info = ITEMS_DATA.get(item_name, {"emoji": "📦", "price": "Unknown"})
            current_time = format_moscow_time()

            message = (
                f"🚨 *РЕДКИЙ ПРЕДМЕТ В СТОКЕ* 🚨\n\n"
                f"{item_info['emoji']} *{item_name}*\n"
                f"📦 Количество: *x{count}*\n"
                f"💰 Цена: {item_info['price']} ¢\n\n"
                f"🕒 {current_time} МСК"
            )

            await bot.send_message(chat_id=channel_id, text=message, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"✅ Уведомление: {item_name} x{count}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
    
    async def send_autostock_notification(self, bot: Bot, user_id: int, item_name: str, count: int):
        try:
            item_info = ITEMS_DATA.get(item_name, {"emoji": "📦", "price": "Unknown"})
            current_time = format_moscow_time()

            message = (
                f"🔔 *АВТОСТОК - {item_name}*\n\n"
                f"{item_info['emoji']} *{item_name}*\n"
                f"📦 Количество: *x{count}*\n"
                f"💰 Цена: {item_info['price']} ¢\n\n"
                f"🕒 {current_time} МСК"
            )

            await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.MARKDOWN)
        except:
            pass
    
    def can_send_autostock_notification(self, item_name: str) -> bool:
        global last_autostock_notification
        
        if item_name not in last_autostock_notification:
            return True
        
        now = get_moscow_time()
        last_time = last_autostock_notification[item_name]
        return (now - last_time).total_seconds() >= AUTOSTOCK_NOTIFICATION_COOLDOWN
    
    async def check_user_autostocks(self, stock_data: Dict, bot: Bot):
        global last_autostock_notification
        
        if not stock_data:
            return

        current_stock = {}
        
        for stock_type in ['seeds', 'gear', 'eggs', 'events']:
            items = stock_data.get(stock_type, [])
            for item_name, quantity in items:
                if quantity > 0:
                    current_stock[item_name] = quantity

        items_to_check = [item_name for item_name, count in current_stock.items() 
                         if count > 0 and self.can_send_autostock_notification(item_name)]
        
        if not items_to_check:
            return
        
        item_users_map = {}
        tasks = [self.db.get_users_tracking_item(item_name) for item_name in items_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for item_name, result in zip(items_to_check, results):
            if not isinstance(result, Exception) and result:
                item_users_map[item_name] = result
        
        send_tasks = []
        for item_name, count in current_stock.items():
            if item_name in item_users_map:
                users = item_users_map[item_name]
                for user_id in users:
                    send_tasks.append(self.send_autostock_notification(bot, user_id, item_name, count))
                    
                    if len(send_tasks) >= 50:
                        await asyncio.gather(*send_tasks, return_exceptions=True)
                        send_tasks = []
                        await asyncio.sleep(0.03)
        
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
        
        for item_name in items_to_check:
            last_autostock_notification[item_name] = get_moscow_time()
        
        total_sent = sum(len(item_users_map.get(item, [])) for item in current_stock.keys())
        if total_sent > 0:
            logger.info(f"📤 Отправлено {total_sent} автосток уведомлений")

    async def check_for_notifications(self, stock_data: Dict, bot: Bot, channel_id: str):
        global last_stock_state
        if not stock_data or not channel_id:
            return

        current_stock = {}
        for item_name, quantity in stock_data.get('seeds', []):
            current_stock[item_name] = quantity

        for item_name in RAREST_SEEDS:
            current_count = current_stock.get(item_name, 0)
            previous_count = last_stock_state.get(item_name, 0)
            
            if current_count > 0 and previous_count == 0:
                await self.send_notification(bot, channel_id, item_name, current_count)

        last_stock_state = current_stock.copy()

parser = DiscordStockParser()

# ========== DISCORD CLIENT ==========
class StockDiscordClient(discord.Client):
    def __init__(self):
        super().__init__()
        self.stock_data_cache = None
        self.stock_lock = asyncio.Lock()
    
    async def on_ready(self):
        logger.info(f'✅ Discord: Залогинен как {self.user}')
        
        for channel_name, channel_id in DISCORD_CHANNELS.items():
            channel = self.get_channel(channel_id)
            if channel:
                logger.info(f"✅ Канал {channel_name}: {channel.name}")
            else:
                logger.error(f"❌ Канал {channel_name} недоступен")
    
    async def fetch_stock_data(self) -> Dict:
        """Быстрое получение стока с кешем"""
        global cached_stock_data, cached_stock_time
        
        now = get_moscow_time()
        
        # Используем кеш если свежий
        if cached_stock_data and cached_stock_time:
            if (now - cached_stock_time).total_seconds() < STOCK_CACHE_TTL:
                return cached_stock_data
        
        async with self.stock_lock:
            # Двойная проверка после получения блокировки
            if cached_stock_data and cached_stock_time:
                if (now - cached_stock_time).total_seconds() < STOCK_CACHE_TTL:
                    return cached_stock_data
            
            try:
                stock_data = {
                    "seeds": [],
                    "gear": [],
                    "eggs": [],
                    "events": []
                }
                
                for channel_name, channel_id in DISCORD_CHANNELS.items():
                    try:
                        channel = self.get_channel(channel_id)
                        if not channel:
                            continue
                        
                        messages = []
                        async for msg in channel.history(limit=2):
                            messages.append(msg)
                            if len(messages) >= 2:
                                break
                        
                        for msg in messages:
                            if msg.author.bot and ('Vulcan' in msg.author.name or 'Dawn' in msg.author.name):
                                content_to_parse = ""
                                
                                if msg.embeds:
                                    for embed in msg.embeds:
                                        if embed.description:
                                            content_to_parse += embed.description + "\n"
                                        for field in embed.fields:
                                            content_to_parse += f"{field.name}\n{field.value}\n"
                                
                                if msg.content:
                                    content_to_parse += msg.content
                                
                                if content_to_parse:
                                    parsed = parser.parse_stock_message(content_to_parse, channel_name)
                                    
                                    for category in parsed:
                                        stock_data[category].extend(parsed[category])
                                    
                                    break
                    
                    except Exception as e:
                        logger.error(f"❌ Ошибка парсинга {channel_name}: {e}")
                        continue
                
                # Обновляем кеш
                cached_stock_data = stock_data
                cached_stock_time = get_moscow_time()
                
                return stock_data
                
            except Exception as e:
                logger.error(f"❌ Ошибка fetch_stock_data: {e}")
                return cached_stock_data or {"seeds": [], "gear": [], "eggs": [], "events": []}

# ========== КОМАНДЫ TELEGRAM БОТА ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    user = update.effective_user
    asyncio.create_task(parser.db.save_user(user.id, user.username, user.first_name))
    
    is_subscribed = await check_subscription(context.bot, user.id)
    
    if not is_subscribed:
        message = (
            "👋 *Добро пожаловать в GAG Stock Tracker!*\n\n"
            "🔒 Для использования бота необходимо подписаться на наш канал:\n\n"
            f"📢 @{CHANNEL_USERNAME}"
        )
        await update.effective_message.reply_text(
            message, 
            reply_markup=get_subscription_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    welcome_message = (
        "👋 *GAG Stock Tracker!*\n\n"
        "📊 /stock - Текущий сток\n"
        "🔔 /autostock - Автостоки\n"
        "❓ /help - Справка\n\n"
        f"📢 Канал: @{CHANNEL_USERNAME}"
    )
    await update.effective_message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)

async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    is_subscribed = await check_subscription(context.bot, user_id)
    if not is_subscribed:
        await update.effective_message.reply_text(
            "🔒 Для использования бота подпишитесь на канал:",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    can_execute, seconds_left = check_command_cooldown(user_id, 'stock')
    if not can_execute:
        await update.effective_message.reply_text(
            f"⏳ Подождите {seconds_left} сек. перед следующим запросом"
        )
        return
    
    if not discord_client or not discord_client.is_ready():
        await update.effective_message.reply_text(
            "⚠️ *Discord клиент загружается*\n\nПожалуйста, подождите и попробуйте снова.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Быстрое получение стока
    stock_data = await discord_client.fetch_stock_data()
    message = parser.format_stock_message(stock_data)
    await update.effective_message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def autostock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    is_subscribed = await check_subscription(context.bot, user_id)
    if not is_subscribed:
        await update.effective_message.reply_text(
            "🔒 Для использования бота подпишитесь на канал:",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    can_execute, seconds_left = check_command_cooldown(user_id, 'autostock')
    if not can_execute:
        await update.effective_message.reply_text(
            f"⏳ Подождите {seconds_left} сек. перед следующим запросом"
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("🌱 Семена", callback_data="as_seeds")],
        [InlineKeyboardButton("⚔️ Гиры", callback_data="as_gear")],
        [InlineKeyboardButton("🥚 Яйца", callback_data="as_eggs")],
        [InlineKeyboardButton("🌴 Safari Shop", callback_data="as_events")],
        [InlineKeyboardButton("📋 Мои автостоки", callback_data="as_list")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\n"
        "Выберите категорию предметов.\n"
        "⏰ Проверка: каждые 5 минут"
    )
    
    await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def autostock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not update.effective_user:
        return
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "check_sub":
        subscription_cache.pop(user_id, None)
        
        is_subscribed = await check_subscription(context.bot, user_id)
        if is_subscribed:
            welcome_message = (
                "✅ *Подписка подтверждена!*\n\n"
                "📊 /stock - Текущий сток\n"
                "🔔 /autostock - Автостоки\n"
                "❓ /help - Справка\n\n"
                f"📢 Канал: @{CHANNEL_USERNAME}"
            )
            await query.edit_message_text(welcome_message, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("❌ Вы еще не подписались на канал", show_alert=True)
        return
    
    is_subscribed = await check_subscription(context.bot, user_id)
    if not is_subscribed:
        await query.answer("🔒 Сначала подпишитесь на канал", show_alert=True)
        return
    
    try:
        if data == "as_seeds":
            user_items = await parser.db.load_user_autostocks(user_id, use_cache=False)
            keyboard = []
            for item_name, item_info in SEED_ITEMS_LIST:
                is_tracking = item_name in user_items
                status = "✅" if is_tracking else "➕"
                safe_callback = NAME_TO_ID.get(item_name, "invalid")
                keyboard.append([InlineKeyboardButton(
                    f"{status} {item_info['emoji']} {item_name}",
                    callback_data=safe_callback
                )])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="as_back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🌱 *СЕМЕНА*\n\nВыберите предметы:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        elif data == "as_gear":
            user_items = await parser.db.load_user_autostocks(user_id, use_cache=False)
            keyboard = []
            for item_name, item_info in GEAR_ITEMS_LIST:
                is_tracking = item_name in user_items
                status = "✅" if is_tracking else "➕"
                safe_callback = NAME_TO_ID.get(item_name, "invalid")
                keyboard.append([InlineKeyboardButton(
                    f"{status} {item_info['emoji']} {item_name}",
                    callback_data=safe_callback
                )])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="as_back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("⚔️ *ГИРЫ*\n\nВыберите предметы:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        elif data == "as_eggs":
            user_items = await parser.db.load_user_autostocks(user_id, use_cache=False)
            keyboard = []
            for item_name, item_info in EGG_ITEMS_LIST:
                is_tracking = item_name in user_items
                status = "✅" if is_tracking else "➕"
                safe_callback = NAME_TO_ID.get(item_name, "invalid")
                keyboard.append([InlineKeyboardButton(
                    f"{status} {item_info['emoji']} {item_name}",
                    callback_data=safe_callback
                )])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="as_back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🥚 *ЯЙЦА*\n\nВыберите предметы:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        elif data == "as_events":
            user_items = await parser.db.load_user_autostocks(user_id, use_cache=False)
            keyboard = []
            for item_name, item_info in EVENT_ITEMS_LIST:
                is_tracking = item_name in user_items
                status = "✅" if is_tracking else "➕"
                safe_callback = NAME_TO_ID.get(item_name, "invalid")
                keyboard.append([InlineKeyboardButton(
                    f"{status} {item_info['emoji']} {item_name}",
                    callback_data=safe_callback
                )])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="as_back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🌴 *SAFARI SHOP*\n\nВыберите предметы:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        elif data == "as_list":
            user_items = await parser.db.load_user_autostocks(user_id, use_cache=False)
            if not user_items:
                message = "📋 *МОИ АВТОСТОКИ*\n\n_Нет отслеживаемых предметов_"
            else:
                items_list = []
                for item_name in sorted(user_items):
                    item_info = ITEMS_DATA.get(item_name, {"emoji": "📦", "price": "Unknown"})
                    items_list.append(f"{item_info['emoji']} {item_name} ({item_info['price']} ¢)")
                message = f"📋 *МОИ АВТОСТОКИ*\n\n" + "\n".join(items_list)
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="as_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        elif data == "as_back":
            keyboard = [
                [InlineKeyboardButton("🌱 Семена", callback_data="as_seeds")],
                [InlineKeyboardButton("⚔️ Гиры", callback_data="as_gear")],
                [InlineKeyboardButton("🥚 Яйца", callback_data="as_eggs")],
                [InlineKeyboardButton("🌴 Safari Shop", callback_data="as_events")],
                [InlineKeyboardButton("📋 Мои автостоки", callback_data="as_list")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = "🔔 *УПРАВЛЕНИЕ АВТОСТОКАМИ*\n\nВыберите категорию."
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        elif data.startswith("t_"):
            item_name = ID_TO_NAME.get(data)
            if not item_name:
                return
            
            category = ITEMS_DATA.get(item_name, {}).get('category', 'seed')
            
            # Загружаем свежие данные без кеша
            user_items = await parser.db.load_user_autostocks(user_id, use_cache=False)
            
            if item_name in user_items:
                success = await parser.db.remove_user_autostock(user_id, item_name)
                if success:
                    user_items.discard(item_name)
            else:
                success = await parser.db.save_user_autostock(user_id, item_name)
                if success:
                    user_items.add(item_name)
            
            if category == 'seed':
                items_list = SEED_ITEMS_LIST
                header = "🌱 *СЕМЕНА*\n\nВыберите предметы:"
            elif category == 'gear':
                items_list = GEAR_ITEMS_LIST
                header = "⚔️ *ГИРЫ*\n\nВыберите предметы:"
            elif category == 'event':
                items_list = EVENT_ITEMS_LIST
                header = "🌴 *SAFARI SHOP*\n\nВыберите предметы:"
            else:
                items_list = EGG_ITEMS_LIST
                header = "🥚 *ЯЙЦА*\n\nВыберите предметы:"
            
            keyboard = []
            for name, info in items_list:
                is_tracking = name in user_items
                status = "✅" if is_tracking else "➕"
                safe_callback = NAME_TO_ID.get(name, "invalid")
                keyboard.append([InlineKeyboardButton(
                    f"{status} {info['emoji']} {name}",
                    callback_data=safe_callback
                )])
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="as_back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(header, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            except TelegramError:
                pass
    
    except Exception as e:
        logger.error(f"❌ Ошибка в autostock_callback: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    is_subscribed = await check_subscription(context.bot, user_id)
    if not is_subscribed:
        await update.effective_message.reply_text(
            "🔒 Для использования бота подпишитесь на канал:",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    help_message = (
        "📚 *КОМАНДЫ:*\n\n"
        "/start - Информация\n"
        "/stock - Текущий сток\n"
        "/autostock - Настроить автостоки\n"
        "/help - Справка\n\n"
        "⏰ Проверка каждые 5 минут\n"
        f"📢 Канал: @{CHANNEL_USERNAME}"
    )
    await update.effective_message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

# ========== ПЕРИОДИЧЕСКАЯ ПРОВЕРКА ==========
async def periodic_stock_check(application: Application):
    logger.info("🚀 Периодическая проверка запущена")
    
    while not discord_client or not discord_client.is_ready():
        await asyncio.sleep(1)
    
    parser.telegram_bot = application.bot
    
    try:
        initial_sleep = calculate_sleep_time()
        logger.info(f"⏰ Ожидание до первой проверки: {int(initial_sleep)}с")
        await asyncio.sleep(initial_sleep)

        check_count = 0
        while True:
            try:
                now = get_moscow_time()
                check_count += 1
                logger.info(f"🔍 Проверка #{check_count} - {now.strftime('%H:%M:%S')}")
                
                if check_count % 12 == 0:
                    _cleanup_cache()
                
                stock_data = await discord_client.fetch_stock_data()
                
                if stock_data:
                    tasks = []
                    if CHANNEL_ID:
                        tasks.append(parser.check_for_notifications(stock_data, application.bot, CHANNEL_ID))
                    tasks.append(parser.check_user_autostocks(stock_data, application.bot))
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                sleep_time = calculate_sleep_time()
                logger.info(f"💤 Следующая проверка через {int(sleep_time)}с")
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка проверки: {e}")
                await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("🛑 Периодическая проверка остановлена")

async def post_init(application: Application):
    asyncio.create_task(periodic_stock_check(application))

# ========== MAIN ==========
def main():
    logger.info("="*60)
    logger.info("🌱 GAG Stock Tracker Bot v2.0")
    logger.info("="*60)

    build_item_id_mappings()

    # Discord клиент
    global discord_client
    discord_client = StockDiscordClient()
    
    # Telegram бот
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("stock", stock_command))
    telegram_app.add_handler(CommandHandler("autostock", autostock_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    
    telegram_app.add_handler(CallbackQueryHandler(autostock_callback))

    telegram_app.post_init = post_init

    async def shutdown_callback(app: Application):
        logger.info("🛑 Остановка бота")
        if discord_client:
            await discord_client.close()

    telegram_app.post_shutdown = shutdown_callback

    # Запускаем оба клиента в одном event loop
    async def run_both():
        # Запускаем Discord
        discord_task = asyncio.create_task(discord_client.start(DISCORD_TOKEN))
        
        # Ждем пока Discord будет готов
        while not discord_client.is_ready():
            await asyncio.sleep(0.5)
        
        logger.info("✅ Discord готов, запускаем Telegram...")
        
        # Запускаем Telegram
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(allowed_updates=None, drop_pending_updates=True)
        
        logger.info("🚀 Бот полностью запущен!")
        logger.info("="*60)
        
        # Ждем завершения
        try:
            await discord_task
        except KeyboardInterrupt:
            pass
        finally:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
    
    try:
        asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал остановки")

if __name__ == "__main__":
    main()