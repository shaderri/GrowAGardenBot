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
SUPABASE_API_KEY = os.getenv("SUPABASE_KEY", "")

AUTOSTOCKS_URL = f"{SUPABASE_URL}/rest/v1/user_autostocks"
USERS_URL = f"{SUPABASE_URL}/rest/v1/users"

# Новые каналы Discord
DISCORD_CHANNELS = {
    "stock": 1376781142291648653,  # seed-gear-stocks
    "egg_stock": 1376606304189022349,  # egg-stocks
    "cosmetics": 1376606377983610972,  # cosmetics
    "weather": 1376606338762801373,  # weather
}

CHECK_INTERVAL_MINUTES = 5
CHECK_DELAY_SECONDS = 10
RAREST_SEEDS = ["Crimson Thorn", "Zebrazinkle"]

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
    "Buttercup": {"emoji": "🌼", "price": "600"},
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
    "Sunflower": {"emoji": "🌻", "price": "5.56M"},
    "Beanstalk": {"emoji": "🪜", "price": "10M"},
    "Ember Lily": {"emoji": "🔥", "price": "15M"},
    "Sugar Apple": {"emoji": "🍎", "price": "25M"},
    "Burning Bud": {"emoji": "🔥", "price": "40M"},
    "Giant Pinecone": {"emoji": "🌲", "price": "55M"},
    "Elder Strawberry": {"emoji": "🍓", "price": "70M"},
    "Romanesco": {"emoji": "🥦", "price": "88M"},
    "Crimson Thorn": {"emoji": "🌹", "price": "10B"},
    "Zebrazinkle": {"emoji": "🦓", "price": "21B"},
    "Broccoli": {"emoji": "🥦", "price": "600"},
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

COSMETICS_DATA = {
    "Beach Crate": {"emoji": "📦", "price": "?"},
    "Summer Fun Crate": {"emoji": "📦", "price": "?"},
    "Cooking Kit": {"emoji": "🍳", "price": "?"},
    "Stone Lantern": {"emoji": "🏮", "price": "?"},
    "Viney Beam": {"emoji": "🌿", "price": "?"},
    "Hay Bale": {"emoji": "🌾", "price": "?"},
    "Brick Stack": {"emoji": "🧱", "price": "?"},
    "Torch": {"emoji": "🔥", "price": "?"},
    "White Bench": {"emoji": "🪑", "price": "?"},
}

ITEMS_DATA = {}
ITEMS_DATA.update({k: {**v, "category": "seed"} for k, v in SEEDS_DATA.items()})
ITEMS_DATA.update({k: {**v, "category": "gear"} for k, v in GEAR_DATA.items()})
ITEMS_DATA.update({k: {**v, "category": "egg"} for k, v in EGGS_DATA.items()})
ITEMS_DATA.update({k: {**v, "category": "cosmetic"} for k, v in COSMETICS_DATA.items()})

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
last_stock_state: Dict[str, int] = {}
last_autostock_notification: Dict[str, datetime] = {}
user_autostocks_cache: Dict[int, Set[str]] = {}
subscription_cache: Dict[int, tuple] = {}
cached_stock_data: Optional[Dict] = None
cached_stock_time: Optional[datetime] = None
cached_weather_data: Optional[str] = None
cached_weather_time: Optional[datetime] = None
cached_cosmetics_data: Optional[Dict] = None
cached_cosmetics_time: Optional[datetime] = None

NAME_TO_ID: Dict[str, str] = {}
ID_TO_NAME: Dict[str, str] = {}

SEED_ITEMS_LIST = [(name, info) for name, info in sorted(ITEMS_DATA.items()) if info['category'] == 'seed']
GEAR_ITEMS_LIST = [(name, info) for name, info in sorted(ITEMS_DATA.items()) if info['category'] == 'gear']
EGG_ITEMS_LIST = [(name, info) for name, info in sorted(ITEMS_DATA.items()) if info['category'] == 'egg']

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
    global NAME_TO_ID, ID_TO_NAME
    for item_name in ITEMS_DATA.keys():
        hash_obj = hashlib.sha1(item_name.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()[:8]
        category = ITEMS_DATA[item_name]['category']
        safe_id = f"t_{category}_{hash_hex}"
        NAME_TO_ID[item_name] = safe_id
        ID_TO_NAME[safe_id] = item_name
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
            async with session.post(USERS_URL, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as response:
                return response.status in [200, 201]
        except:
            return False
    
    async def load_user_autostocks(self, user_id: int) -> Set[str]:
        if user_id in user_autostocks_cache:
            return user_autostocks_cache[user_id].copy()
        
        try:
            session = await self.get_session()
            params = {"user_id": f"eq.{user_id}", "select": "item_name"}
            async with session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=aiohttp.ClientTimeout(total=3)) as response:
                if response.status == 200:
                    data = await response.json()
                    items_set = {item['item_name'] for item in data}
                    user_autostocks_cache[user_id] = items_set
                    return items_set
                return set()
        except Exception as e:
            logger.error(f"❌ Загрузка: {e}")
            return user_autostocks_cache.get(user_id, set()).copy()
    
    async def save_user_autostock(self, user_id: int, item_name: str) -> bool:
        try:
            session = await self.get_session()
            data = {"user_id": user_id, "item_name": item_name}
            headers = {**self.headers, "Prefer": "resolution=merge-duplicates"}
            async with session.post(AUTOSTOCKS_URL, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as response:
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
            async with session.delete(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=aiohttp.ClientTimeout(total=3)) as response:
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
            async with session.get(AUTOSTOCKS_URL, headers=self.headers, params=params, timeout=aiohttp.ClientTimeout(total=3)) as response:
                if response.status == 200:
                    data = await response.json()
                    return [item['user_id'] for item in data]
                return []
        except:
            return []

# ========== DISCORD ПАРСЕР ==========
class DiscordStockParser:
    def __init__(self):
        self.db = SupabaseDB()
        self.telegram_bot: Optional[Bot] = None
    
    def parse_stock_message(self, content: str, channel_name: str) -> Dict:
        result = {"seeds": [], "gear": [], "eggs": [], "cosmetics": []}
        lines = content.split('\n')
        
        current_section = None
        for line in lines:
            line = line.strip()
            
            # Для stock канала (семена + гиры)
            if channel_name == "stock":
                if 'Seeds' in line or 'SEEDS' in line:
                    current_section = 'seeds'
                    continue
                elif 'Gear' in line or 'GEAR' in line:
                    current_section = 'gear'
                    continue
            
            # Для egg_stock
            elif channel_name == "egg_stock":
                current_section = 'eggs'
            
            # Для cosmetics
            elif channel_name == "cosmetics":
                if 'Crates:' in line:
                    current_section = 'cosmetics'
                    continue
                elif 'Items:' in line:
                    current_section = 'cosmetics'
                    continue
            
            # Парсинг предметов
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
            return "❌ *Не удалось получить данные*"
        
        message = "📊 *ТЕКУЩИЙ СТОК*\n\n"
        
        for category, emoji, title in [('seeds', '🌱', 'СЕМЕНА'), ('gear', '⚔️', 'ГИРЫ'), ('eggs', '🥚', 'ЯЙЦА')]:
            items = stock_data.get(category, [])
            if items:
                message += f"{emoji} *{title}:*\n"
                for item_name, quantity in items:
                    if category == 'seeds':
                        item_info = SEEDS_DATA.get(item_name, {"emoji": emoji, "price": "?"})
                    elif category == 'gear':
                        item_info = GEAR_DATA.get(item_name, {"emoji": "⚔️", "price": "?"})
                    else:
                        item_info = EGGS_DATA.get(item_name, {"emoji": "🥚", "price": "?"})
                    message += f"{item_info['emoji']} {item_name} x{quantity}\n"
                message += "\n"
            else:
                message += f"{emoji} *{title}:* _Пусто_\n\n"
        
        message += f"🕒 {format_moscow_time()}"
        return message
    
    def format_cosmetics_message(self, cosmetics_data: Dict) -> str:
        if not cosmetics_data:
            return "❌ *Не удалось получить данные*"
        
        message = "👗 *COSMETICS SHOP*\n\n"
        items = cosmetics_data.get('cosmetics', [])
        
        if items:
            for item_name, quantity in items:
                item_info = COSMETICS_DATA.get(item_name, {"emoji": "📦", "price": "?"})
                message += f"{item_info['emoji']} {item_name} x{quantity}\n"
        else:
            message += "_Пусто_"
        
        message += f"\n\n🕒 {format_moscow_time()}"
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
            logger.info(f"📤 {user_id} -> {item_name}")
        except Exception as e:
            logger.error(f"❌ {user_id}: {e}")
    
    async def check_user_autostocks(self, stock_data: Dict, bot: Bot):
        global last_autostock_notification
        if not stock_data:
            return

        current_stock = {}
        for stock_type in ['seeds', 'gear', 'eggs']:
            for item_name, quantity in stock_data.get(stock_type, []):
                if quantity > 0:
                    current_stock[item_name] = quantity

        items_to_check = []
        now = get_moscow_time()
        for item_name in current_stock.keys():
            if item_name not in last_autostock_notification:
                items_to_check.append(item_name)
            else:
                if (now - last_autostock_notification[item_name]).total_seconds() >= 300:
                    items_to_check.append(item_name)
        
        if not items_to_check:
            return
        
        logger.info(f"🔍 Проверка: {len(items_to_check)} предметов")
        
        tasks = [self.db.get_users_tracking_item(item_name) for item_name in items_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        send_count = 0
        for item_name, result in zip(items_to_check, results):
            if not isinstance(result, Exception) and result:
                count = current_stock[item_name]
                logger.info(f"📨 {item_name}: {len(result)} пользователей")
                for user_id in result:
                    asyncio.create_task(self.send_autostock_notification(bot, user_id, item_name, count))
                    send_count += 1
                last_autostock_notification[item_name] = now
        
        if send_count > 0:
            logger.info(f"✅ Отправлено {send_count} уведомлений")

parser = DiscordStockParser()

# ========== DISCORD CLIENT ==========
class StockDiscordClient(discord.Client):
    def __init__(self):
        super().__init__()
        self.stock_lock = asyncio.Lock()
    
    async def on_ready(self):
        logger.info(f'✅ Discord: {self.user}')
        for channel_name, channel_id in DISCORD_CHANNELS.items():
            channel = self.get_channel(channel_id)
            if channel:
                logger.info(f"✅ {channel_name}: {channel.name}")
    
    async def fetch_stock_data(self) -> Dict:
        global cached_stock_data, cached_stock_time
        
        now = get_moscow_time()
        if cached_stock_data and cached_stock_time:
            if (now - cached_stock_time).total_seconds() < 30:
                return cached_stock_data
        
        async with self.stock_lock:
            stock_data = {"seeds": [], "gear": [], "eggs": []}
            
            for channel_name in ["stock", "egg_stock"]:
                if channel_name not in DISCORD_CHANNELS:
                    continue
                    
                try:
                    channel = self.get_channel(DISCORD_CHANNELS[channel_name])
                    if not channel:
                        continue
                    
                    async for msg in channel.history(limit=2):
                        if msg.author.bot and ('bot' in msg.author.name.lower() or 'Ember' in msg.author.name or 'Dawn' in msg.author.name):
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
                                for category in ['seeds', 'gear', 'eggs']:
                                    stock_data[category].extend(parsed[category])
                                break
                except Exception as e:
                    logger.error(f"❌ {channel_name}: {e}")
            
            cached_stock_data = stock_data
            cached_stock_time = now
            return stock_data
    
    async def fetch_cosmetics_data(self) -> Dict:
        global cached_cosmetics_data, cached_cosmetics_time
        
        now = get_moscow_time()
        if cached_cosmetics_data and cached_cosmetics_time:
            if (now - cached_cosmetics_time).total_seconds() < 60:
                return cached_cosmetics_data
        
        try:
            channel = self.get_channel(DISCORD_CHANNELS["cosmetics"])
            if not channel:
                return {"cosmetics": []}
            
            async for msg in channel.history(limit=5):
                if msg.author.bot and 'resstock' in msg.content.lower():
                    content = msg.content
                    if msg.embeds and msg.embeds[0].description:
                        content += "\n" + msg.embeds[0].description
                    
                    parsed = parser.parse_stock_message(content, "cosmetics")
                    cached_cosmetics_data = parsed
                    cached_cosmetics_time = now
                    return parsed
            
            return {"cosmetics": []}
        except Exception as e:
            logger.error(f"❌ cosmetics: {e}")
            return {"cosmetics": []}
    
    async def fetch_weather_data(self) -> str:
        global cached_weather_data, cached_weather_time
        
        now = get_moscow_time()
        if cached_weather_data and cached_weather_time:
            if (now - cached_weather_time).total_seconds() < 60:
                return cached_weather_data
        
        try:
            channel = self.get_channel(DISCORD_CHANNELS["weather"])
            if not channel:
                return "❌ *Канал погоды недоступен*"
            
            message_text = "🌤️ *ТЕКУЩАЯ ПОГОДА*\n\n"
            
            async for msg in channel.history(limit=3):
                if msg.author.bot:
                    if msg.embeds:
                        for embed in msg.embeds:
                            if embed.title:
                                message_text += f"*{embed.title}*\n"
                            if embed.description:
                                message_text += f"{embed.description}\n\n"
                    elif msg.content:
                        lines = msg.content.split('\n')
                        for line in lines[:5]:
                            if line.strip():
                                message_text += f"{line}\n"
                        message_text += "\n"
            
            message_text += f"🕒 {format_moscow_time()}"
            cached_weather_data = message_text
            cached_weather_time = now
            return message_text
        except Exception as e:
            logger.error(f"❌ weather: {e}")
            return f"❌ *Ошибка получения погоды*"

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
        "👋 *GAG Stock Tracker*\n\n"
        "📊 /stock - Сток (семена, гиры, яйца)\n"
        "👗 /cosmetic - Косметика\n"
        "🌤️ /weather - Погода\n"
        "🔔 /autostock - Автостоки\n"
        "❓ /help - Справка",
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

async def cosmetic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    if not await check_subscription(context.bot, update.effective_user.id):
        await update.effective_message.reply_text("🔒 Подпишитесь на канал", reply_markup=get_subscription_keyboard())
        return
    
    if not discord_client or not discord_client.is_ready():
        await update.effective_message.reply_text("⚠️ *Discord загружается...*", parse_mode=ParseMode.MARKDOWN)
        return
    
    cosmetics_data = await discord_client.fetch_cosmetics_data()
    message = parser.format_cosmetics_message(cosmetics_data)
    await update.effective_message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    
    if not await check_subscription(context.bot, update.effective_user.id):
        await update.effective_message.reply_text("🔒 Подпишитесь на канал", reply_markup=get_subscription_keyboard())
        return
    
    if not discord_client or not discord_client.is_ready():
        await update.effective_message.reply_text("⚠️ *Discord загружается...*", parse_mode=ParseMode.MARKDOWN)
        return
    
    message = await discord_client.fetch_weather_data()
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
            await query.edit_message_text("✅ *Подписка подтверждена!*\n\n📊 /stock\n👗 /cosmetic\n🌤️ /weather\n🔔 /autostock", parse_mode=ParseMode.MARKDOWN)
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
        "/stock - Сток\n"
        "/cosmetic - Косметика\n"
        "/weather - Погода\n"
        "/autostock - Автостоки\n"
        "/help - Справка\n\n"
        "⏰ Проверка автостоков: каждые 5 минут",
        parse_mode=ParseMode.MARKDOWN
    )

# ========== ПЕРИОДИЧЕСКАЯ ПРОВЕРКА ==========
async def periodic_stock_check(application: Application):
    logger.info("🚀 Периодическая проверка запущена")
    
    while not discord_client or not discord_client.is_ready():
        await asyncio.sleep(1)
    
    parser.telegram_bot = application.bot
    
    try:
        initial_sleep = calculate_sleep_time()
        logger.info(f"⏰ Первая проверка через {int(initial_sleep)}с")
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
                
                sleep_time = calculate_sleep_time()
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
                await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass

async def post_init(application: Application):
    asyncio.create_task(periodic_stock_check(application))

# ========== MAIN ==========
def main():
    logger.info("="*60)
    logger.info("🌱 GAG Stock Tracker Bot v3.0 FINAL")
    logger.info("="*60)

    build_item_id_mappings()

    global discord_client
    discord_client = StockDiscordClient()
    
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("stock", stock_command))
    telegram_app.add_handler(CommandHandler("cosmetic", cosmetic_command))
    telegram_app.add_handler(CommandHandler("weather", weather_command))
    telegram_app.add_handler(CommandHandler("autostock", autostock_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CallbackQueryHandler(autostock_callback))

    telegram_app.post_init = post_init

    async def shutdown_callback(app: Application):
        logger.info("🛑 Остановка")
        if discord_client:
            await discord_client.close()
        if http_session and not http_session.closed:
            await http_session.close()

    telegram_app.post_shutdown = shutdown_callback

    async def run_both():
        discord_task = asyncio.create_task(discord_client.start(DISCORD_TOKEN))
        
        while not discord_client.is_ready():
            await asyncio.sleep(0.5)
        
        logger.info("✅ Discord готов")
        
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(allowed_updates=None, drop_pending_updates=True)
        
        logger.info("🚀 Бот запущен!")
        logger.info("="*60)
        
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
        logger.info("⚠️ Остановка")

if __name__ == "__main__":
    main()