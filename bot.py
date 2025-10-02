import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Файлы
ADMINS_FILE = "admins.json"
BANNED_FILE = "banned.json"
MUTED_FILE = "muted.json"

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

admins = load_data(ADMINS_FILE)
banned = load_data(BANNED_FILE)
muted = load_data(MUTED_FILE)

OWNER_ID = 123456789  # <-- замени на свой Telegram ID

# Проверка админских прав
def is_admin(user_id):
    return str(user_id) == str(OWNER_ID) or str(user_id) in admins.values()

# --- START ---
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Я бот для модерации. Команды: /setadm, /nahuisadm, /ban, /unban, /mute, /unmute, /admins")

# --- SET ADM ---
@dp.message(Command("setadm"))
async def setadm_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.answer("❌ Только владелец может назначать админов.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /setadm @username")
    username = args[1].lstrip("@")
    admins[username] = str(message.from_user.id)
    save_data(ADMINS_FILE, admins)
    await message.answer(f"✅ @{username} теперь администратор.")

# --- REMOVE ADM ---
@dp.message(Command("nahuisadm"))
async def nahuisadm_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.answer("❌ Только владелец может снимать админов.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /nahuisadm @username")
    username = args[1].lstrip("@")
    if username in admins:
        del admins[username]
        save_data(ADMINS_FILE, admins)
        await message.answer(f"❌ @{username} снят с админов.")
    else:
        await message.answer("⚠️ Такого админа нет.")

# --- ADMINS LIST ---
@dp.message(Command("admins"))
async def admins_handler(message: Message):
    if not admins:
        return await message.answer("👤 Администраторов пока нет.")
    admin_list = "\n".join([f"@{u}" for u in admins.keys()])
    await message.answer(f"📋 Администраторы:\n{admin_list}")

# --- BAN ---
@dp.message(Command("ban"))
async def ban_handler(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /ban @username")
    username = args[1].lstrip("@")
    banned[username] = True
    save_data(BANNED_FILE, banned)
    await message.answer(f"⛔ @{username} забанен.")

# --- UNBAN ---
@dp.message(Command("unban"))
async def unban_handler(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /unban @username")
    username = args[1].lstrip("@")
    if username in banned:
        del banned[username]
        save_data(BANNED_FILE, banned)
        await message.answer(f"✅ @{username} разбанен.")
    else:
        await message.answer("⚠️ Этот пользователь не забанен.")

# --- MUTE ---
@dp.message(Command("mute"))
async def mute_handler(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer("⚠️ Использование: /mute @username 10")
    username = args[1].lstrip("@")
    try:
        minutes = int(args[2])
    except ValueError:
        return await message.answer("⚠️ Время должно быть числом (в минутах).")
    until = (datetime.now() + timedelta(minutes=minutes)).timestamp()
    muted[username] = until
    save_data(MUTED_FILE, muted)
    await message.answer(f"🔇 @{username} замьючен на {minutes} минут.")

# --- UNMUTE ---
@dp.message(Command("unmute"))
async def unmute_handler(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ У вас нет прав.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /unmute @username")
    username = args[1].lstrip("@")
    if username in muted:
        del muted[username]
        save_data(MUTED_FILE, muted)
        await message.answer(f"✅ @{username} размьючен.")
    else:
        await message.answer("⚠️ Этот пользователь не в муте.")

# --- MAIN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
