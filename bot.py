import asyncio
import logging
import os
import json
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, exceptions
from aiogram.types import Message, ChatPermissions
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

bot = Bot(token=TOKEN)
dp = Dispatcher()

ADMINS_FILE = "admins.json"
BANNED_FILE = "banned.json"
MUTED_FILE = "muted.json"

ROLES = ["Стажер", "Модератор", "Старший модератор", "Заместитель", "Владелец"]
OWNER_ID = 7294123971

def load_data(filename, default=None):
    if not os.path.exists(filename):
        return default if default is not None else {}
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

admins = load_data(ADMINS_FILE, {})
banned = load_data(BANNED_FILE, {})
muted = load_data(MUTED_FILE, {})

permissions = {
    "Стажер": ["mute", "unmute"],
    "Модератор": ["mute", "unmute", "ban"],
    "Старший модератор": ["mute", "unmute", "ban", "unban"],
    "Заместитель": ["mute", "unmute", "ban", "unban", "setadm", "nahuisadm", "setperm"],
    "Владелец": ["*"]
}

BOT_ID = None

async def init_bot_vars():
    global BOT_ID
    me = await bot.get_me()
    BOT_ID = me.id
    logging.info("Bot id: %s", BOT_ID)

def get_role(user_id):
    if str(user_id) == str(OWNER_ID):
        return "Владелец"
    for username, info in admins.items():
        if str(info.get("id")) == str(user_id):
            return info.get("role")
    return None

def can_execute(user_id, command):
    role = get_role(user_id)
    if role == "Владелец":
        return True
    allowed = permissions.get(role, [])
    return "*" in allowed or command in allowed

def has_permission(user_id, required_role):
    user_role = get_role(user_id)
    if user_role == "Владелец":
        return True
    if user_role is None:
        return False
    try:
        return ROLES.index(user_role) >= ROLES.index(required_role)
    except ValueError:
        return False

async def bot_has_rights(chat_id):
    try:
        bot_member = await bot.get_chat_member(chat_id, BOT_ID)
        # check if bot is admin and can_restrict_members (for mute/ban)
        is_admin = getattr(bot_member, "status", "") in ("administrator", "creator")
        can_restrict = getattr(bot_member, "can_restrict_members", False)
        can_ban = getattr(bot_member, "can_restrict_members", False) or getattr(bot_member, "can_promote_members", False)
        return is_admin, can_restrict or can_ban
    except Exception:
        return False, False

async def resolve_target(message: Message, arg: str = None):
    """Try to resolve target user id and name.
    Supports: reply, numeric id, @username (if user is in chat or public), and admins list.
    Returns (user_id:int, display_name:str) or (None, None).
    """
    # 1) reply
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, (u.full_name or u.username or str(u.id))

    # 2) provided arg?
    if not arg:
        return None, None

    arg = arg.strip()
    # numeric id
    if arg.isdigit():
        return int(arg), None

    # username without @
    username = arg.lstrip("@")

    # 3) check admins.json mapping (may contain id)
    if username in admins and admins[username].get("id"):
        return int(admins[username]["id"]), username

    # 4) try get_chat_member by searching among recent members (get_chat_member expects user_id; so skip)
    # 5) try get_chat for public username (works if username is public user or channel)
    try:
        ch = await bot.get_chat("@" + username)
        # if it's a user chat, ch.id will be user's id (positive)
        return ch.id, (getattr(ch, "full_name", None) or getattr(ch, "title", None) or getattr(ch, "username", None) or str(ch.id))
    except exceptions.TelegramBadRequest as e:
        # not found as public @username
        pass
    except Exception:
        pass

    # 6) as last resort, try to fetch via chat member search by iterating admins? Not available.
    return None, None

async def ensure_group(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в группах.")
        return False
    return True

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Модераторный бот. Используй команды в группе: /ban, /unban, /mute, /unmute. Поддерживается reply, @username и id.")

@dp.message(Command("resetbase"))
async def start_handler(message: Message):
    await message.answer("База обновлена✅")

@dp.message(Command("ban"))
async def ban_handler(message: Message):
    if not can_execute(message.from_user.id, "ban"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось найти пользователя. Попробуйте: 1) ответить на сообщение пользователя и ввести /ban  2) указать числовой ID: /ban 123456789  3) убедиться, что пользователь писал в этом чате или является публичным @username.")
    # check bot rights
    is_admin, can_restrict = await bot_has_rights(message.chat.id)
    if not is_admin or not can_restrict:
        return await message.answer("⚠️ У бота нет прав администратора с возможностью банить/ограничивать. Дайте права 'Ban users' и 'Restrict members'.")
    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=int(user_id))
        key = f"{message.chat.id}:{user_id}"
        banned[key] = True
        save_data(BANNED_FILE, banned)
        await message.answer(f"⛔ Пользователь {name or user_id} забанен.")
    except exceptions.TelegramForbidden:
        await message.answer("⚠️ Бот не может забанить этого пользователя (возможно у него более высокий статус)." )
    except Exception as e:
        await message.answer(f"Ошибка при бане: {e}")

@dp.message(Command("unban"))
async def unban_handler(message: Message):
    if not can_execute(message.from_user.id, "unban"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось найти пользователя. Попробуйте reply или ID.")
    is_admin, can_restrict = await bot_has_rights(message.chat.id)
    if not is_admin or not can_restrict:
        return await message.answer("⚠️ У бота нет прав администратора с возможностью разбанивать. Дайте соответствующие права.")
    try:
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=int(user_id))
        key = f"{message.chat.id}:{user_id}"
        if key in banned:
            del banned[key]
            save_data(BANNED_FILE, banned)
        await message.answer(f"✅ Пользователь {name or user_id} разбанен.")
    except exceptions.TelegramForbidden:
        await message.answer("⚠️ Бот не может разбанить этого пользователя (возможно у него более высокий статус)." )
    except Exception as e:
        await message.answer(f"Ошибка при разбане: {e}")

@dp.message(Command("mute"))
async def mute_handler(message: Message):
    if not can_execute(message.from_user.id, "mute"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось найти пользователя. Попробуйте: reply или ID.")
    if len(args) > 2 and args[2].isdigit():
        minutes = int(args[2])
    else:
        return await message.answer("⚠️ Использование: /mute @username 10  (в минутах)")
    is_admin, can_restrict = await bot_has_rights(message.chat.id)
    if not is_admin or not can_restrict:
        return await message.answer("⚠️ У бота нет прав администратора с возможностью мутить. Дайте права 'Restrict members'.")
    until = int(time.time()) + minutes * 60
    permissions_restrict = ChatPermissions(can_send_messages=False, can_send_media_messages=False, can_send_other_messages=False, can_add_web_page_previews=False)
    try:
        await bot.restrict_chat_member(chat_id=message.chat.id, user_id=int(user_id), permissions=permissions_restrict, until_date=until)
        key = f"{message.chat.id}:{user_id}"
        muted[key] = {"chat_id": message.chat.id, "user_id": int(user_id), "until": until}
        save_data(MUTED_FILE, muted)
        await message.answer(f"🔇 Пользователь {name or user_id} замьючен на {minutes} минут.")
    except exceptions.TelegramForbidden:
        await message.answer("⚠️ Бот не может замьютить этого пользователя (возможно у него более высокий статус)." )
    except Exception as e:
        await message.answer(f"Ошибка при муте: {e}")

@dp.message(Command("unmute"))
async def unmute_handler(message: Message):
    if not can_execute(message.from_user.id, "unmute"):
        return await message.answer("❌ У вас нет доступа к этой команде.")
    if not await ensure_group(message):
        return
    args = message.text.split()
    arg = args[1] if len(args) > 1 else None
    user_id, name = await resolve_target(message, arg)
    if not user_id:
        return await message.answer("❌ Не удалось найти пользователя. Попробуйте reply или ID.")
    is_admin, can_restrict = await bot_has_rights(message.chat.id)
    if not is_admin or not can_restrict:
        return await message.answer("⚠️ У бота нет прав администратора с возможностью размьючивать. Дайте соответствующие права.")
    try:
        permissions_allow = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
        await bot.restrict_chat_member(chat_id=message.chat.id, user_id=int(user_id), permissions=permissions_allow)
        key = f"{message.chat.id}:{user_id}"
        if key in muted:
            del muted[key]
            save_data(MUTED_FILE, muted)
        await message.answer(f"✅ Пользователь {name or user_id} размьючен.")
    except exceptions.TelegramForbidden:
        await message.answer("⚠️ Бот не может размьютить этого пользователя (возможно у него более высокий статус)." )
    except Exception as e:
        await message.answer(f"Ошибка при размьючивании: {e}")

async def unmute_watcher():
    while True:
        try:
            now = int(time.time())
            to_unmute = []
            for key, info in list(muted.items()):
                if info.get("until", 0) <= now:
                    to_unmute.append((key, info))
            for key, info in to_unmute:
                try:
                    permissions_allow = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
                    await bot.restrict_chat_member(chat_id=info["chat_id"], user_id=info["user_id"], permissions=permissions_allow)
                except Exception as e:
                    logging.exception("error while auto-unmuting: %s", e)
                if key in muted:
                    del muted[key]
                    save_data(MUTED_FILE, muted)
            await asyncio.sleep(10)
        except Exception:
            await asyncio.sleep(5)

async def on_startup():
    await init_bot_vars()
    asyncio.create_task(unmute_watcher())

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
