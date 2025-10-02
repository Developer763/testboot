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
CHATS_FILE = "chats.json"

ROLES = ["Стажер", "Модератор", "Старший модератор", "Заместитель", "Владелец"]
OWNER_ID = 123456789  # <-- замени на свой Telegram ID

# --- Служебные функции ---
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
chats = load_data(CHATS_FILE)

def get_role(user_id):
    if str(user_id) == str(OWNER_ID):
        return "Владелец"
    for username, info in admins.items():
        if str(info["id"]) == str(user_id):
            return info["role"]
    return None

def has_permission(user_id, required_role):
    user_role = get_role(user_id)
    if user_role == "Владелец":
        return True
    if user_role is None:
        return False
    return ROLES.index(user_role) >= ROLES.index(required_role)

# --- START ---
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Я бот для модерации. Команды: /setadm, /nahuisadm, /ban, /unban, /mute, /unmute, /admins, /chats")

# --- SET ADM ---
@dp.message(Command("setadm"))
async def setadm_handler(message: Message):
    if str(message.from_user.id) != str(OWNER_ID) and not has_permission(message.from_user.id, "Заместитель"):
        return await message.answer("❌ У вас нет прав назначать админов.")

    args = message.text.split()
    if len(args) < 3:
        return await message.answer("⚠️ Использование: /setadm @username Роль")

    username = args[1].lstrip("@")
    role = args[2]

    if role not in ROLES or role == "Владелец":
        return await message.answer("⚠️ Доступные роли: Стажер, Модератор, Старший модератор, Заместитель")

    admins[username] = {"id": message.from_user.id, "role": role}
    save_data(ADMINS_FILE, admins)
    await message.answer(f"✅ @{username} назначен как {role}.")

# --- REMOVE ADM ---
@dp.message(Command("nahuisadm"))
async def nahuisadm_handler(message: Message):
    if str(message.from_user.id) != str(OWNER_ID) and not has_permission(message.from_user.id, "Заместитель"):
        return await message.answer("❌ У вас нет прав снимать админов.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /nahuisadm @username")

    username = args[1].lstrip("@")
    if username in admins:
        role = admins[username]["role"]
        del admins[username]
        save_data(ADMINS_FILE, admins)
        await message.answer(f"❌ @{username} снят с должности {role}.")
    else:
        await message.answer("⚠️ Такого админа нет.")

# --- ADMINS LIST ---
@dp.message(Command("admins"))
async def admins_handler(message: Message):
    if not admins:
        return await message.answer("👤 Администраторов пока нет.")
    admin_list = "\n".join([f"@{u} — {info['role']}" for u, info in admins.items()])
    await message.answer(f"📋 Администраторы:\n{admin_list}\n\n👑 Владелец всегда имеет полный доступ.")

# --- BAN ---
@dp.message(Command("ban"))
async def ban_handler(message: Message):
    if not has_permission(message.from_user.id, "Модератор"):
        return await message.answer("❌ У вас нет прав банить.")
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /ban @username")
    username = args[1].lstrip("@")
    banned[username] = True
    save_data(BANNED_FILE, banned)
    await message.answer(f"⛔ @{username} забанен.")

# --- UNBAN ---
@dp.message(Command("unban"))
async def unban_handler(message: Message):
    if not has_permission(message.from_user.id, "Старший модератор"):
        return await message.answer("❌ У вас нет прав разбанивать.")
    args = message.text.split()
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
    if not has_permission(message.from_user.id, "Стажер"):
        return await message.answer("❌ У вас нет прав мутить.")
    args = message.text.split()
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
    if not has_permission(message.from_user.id, "Стажер"):
        return await message.answer("❌ У вас нет прав размьючивать.")
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("⚠️ Использование: /unmute @username")
    username = args[1].lstrip("@")
    if username in muted:
        del muted[username]
        save_data(MUTED_FILE, muted)
        await message.answer(f"✅ @{username} размьючен.")
    else:
        await message.answer("⚠️ Этот пользователь не в муте.")

# --- TRACK CHATS ---
@dp.message()
async def track_chats(message: Message):
    chat_id = message.chat.id
    chat_title = message.chat.title or message.chat.full_name or str(chat_id)

    if str(chat_id) not in chats:
        chats[str(chat_id)] = chat_title
        save_data(CHATS_FILE, chats)

# --- CHATS LIST ---
@dp.message(Command("chats"))
async def chats_handler(message: Message):
    if not has_permission(message.from_user.id, "Заместитель"):
        return await message.answer("❌ У вас нет прав смотреть список чатов.")

    if not chats:
        return await message.answer("📭 Бот пока ни в одном чате не замечен.")

    chat_list = "\n".join([f"{title} (`{chat_id}`)" for chat_id, title in chats.items()])
    await message.answer(f"📋 Чаты, где есть бот:\n{chat_list}", parse_mode="Markdown")

# --- MAIN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
