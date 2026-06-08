import asyncio
import json
import os
from telethon import TelegramClient, events
from telethon.tl.types import UpdateDeleteMessages, UpdateDeleteChannelMessages

from config import BOT_TOKEN, SOURCE_CHAT_ID, TARGET_CHAT_ID
from filters import ALLOWED_KEYWORDS, BLOCKED_WORDS

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient("session", api_id, api_hash)

MESSAGE_MAP_FILE = "message_map.json"
BANNED_FILE = "banned_users.json"

# ====== ЗАГРУЗКА ======
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

message_map = load_json(MESSAGE_MAP_FILE, {})
banned_users = set(load_json(BANNED_FILE, []))

def save_message_map():
    save_json(MESSAGE_MAP_FILE, message_map)

def save_banned():
    save_json(BANNED_FILE, list(banned_users))

# ====== ФИЛЬТРЫ ======
def check_filters(text: str) -> bool:
    if not text:
        return False
    for w in BLOCKED_WORDS:
        if w.lower() in text.lower():
            return False
    for w in ALLOWED_KEYWORDS:
        if w in text:
            return True
    return False

def is_banned(user_id: int) -> bool:
    return user_id in banned_users

# ====== НОВЫЕ СООБЩЕНИЯ ======
@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def new_message(event):
    msg = event.message
    user = msg.sender_id

    if is_banned(user):
        return

    text = msg.text or msg.message or ""

    if not check_filters(text):
        return

    # Фото / видео
    if msg.media:
        sent = await client.send_message(
            TARGET_CHAT_ID,
            text,
            file=msg.media
        )
    else:
        sent = await client.send_message(
            TARGET_CHAT_ID,
            text
        )

    message_map[str(msg.id)] = sent.id
    save_message_map()

# ====== РЕДАКТИРОВАНИЕ ======
@client.on(events.MessageEdited(chats=SOURCE_CHAT_ID))
async def edit_message(event):
    msg = event.message
    key = str(msg.id)
    text = msg.text or ""

    if is_banned(msg.sender_id):
        return

    # Если не было переслано — переслать
    if key not in message_map:
        if check_filters(text):
            await new_message(event)
        return

    target_id = message_map[key]

    # Если после редактирования не проходит фильтр → удалить
    if not check_filters(text):
        await client.delete_messages(TARGET_CHAT_ID, target_id)
        del message_map[key]
        save_message_map()
        return

    # Обновление
    if msg.media:
        await client.edit_message(
            TARGET_CHAT_ID,
            target_id,
            text,
            file=msg.media
        )
    else:
        await client.edit_message(
            TARGET_CHAT_ID,
            target_id,
            text
        )

# ====== УДАЛЕНИЕ (МГНОВЕННОЕ) ======
@client.on(events.Raw(UpdateDeleteMessages))
async def deleted_private(event):
    for deleted_id in event.messages:
        key = str(deleted_id)
        if key in message_map:
            try:
                await client.delete_messages(
                    TARGET_CHAT_ID,
                    message_map[key]
                )
            except:
                pass
            del message_map[key]
            save_message_map()

@client.on(events.Raw(UpdateDeleteChannelMessages))
async def deleted_channel(event):
    if event.channel_id != abs(SOURCE_CHAT_ID):
        return

    for deleted_id in event.messages:
        key = str(deleted_id)
        if key in message_map:
            try:
                await client.delete_messages(
                    TARGET_CHAT_ID,
                    message_map[key]
                )
            except:
                pass
            del message_map[key]
            save_message_map()

# ====== ЗАПУСК ======
async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("Бот запущен!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
