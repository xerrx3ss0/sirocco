import asyncio
import json
import os
import logging
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from dotenv import load_dotenv
from filters import ALLOW_KEYWORDS, BLOCK_KEYWORDS

load_dotenv()

# ========== КОНФИГ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SOURCE_CHAT = int(os.getenv("SOURCE_CHAT"))
TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

client = TelegramClient('bot_session', API_ID, API_HASH)

# Файл для хранения соответствий сообщений
MESSAGE_MAP_FILE = "message_map.json"
BANNED_FILE = "banned_users.json"

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
    text_lower = text.lower()
    for word in BLOCK_KEYWORDS:
        if word.lower() in text_lower:
            return False
    for word in ALLOW_KEYWORDS:
        if word in text:
            return True
    return False

def is_banned(user_id: int) -> bool:
    return user_id in banned_users

# ====== АЛЬБОМЫ ======
pending_albums = {}
album_timers = {}

async def send_album(album_id, messages):
    first_msg = messages[0]
    text = first_msg.text or first_msg.message or ""

    if is_banned(first_msg.sender_id):
        logger.info(f"Альбом {album_id} пропущен (пользователь забанен)")
        return

    if not check_filters(text):
        logger.info(f"Альбом {album_id} пропущен (фильтр)")
        return

    try:
        media_list = [msg.media for msg in messages if msg.media]

        sent = await client.send_file(
            TARGET_CHANNEL,
            media_list,
            caption=text
        )

        if isinstance(sent, list):
            for i, msg in enumerate(messages):
                message_map[str(msg.id)] = sent[i].id
        else:
            message_map[str(messages[0].id)] = sent.id

        save_message_map()
        logger.info(f"✅ Альбом {album_id} отправлен ({len(messages)} фото)")

    except Exception as e:
        logger.error(f"Ошибка отправки альбома: {e}")

# ====== НОВЫЕ СООБЩЕНИЯ ======
@client.on(events.NewMessage(chats=SOURCE_CHAT))
async def on_new_message(event):
    msg = event.message
    text = msg.text or msg.message or ""

    if is_banned(msg.sender_id):
        logger.info(f"Пользователь {msg.sender_id} забанен, пропуск")
        return

    # Альбом
    if msg.grouped_id:
        album_id = str(msg.grouped_id)

        if album_id not in pending_albums:
            pending_albums[album_id] = []

        pending_albums[album_id].append(msg)

        if album_id in album_timers:
            album_timers[album_id].cancel()

        async def process_album(aid):
            await asyncio.sleep(0.4)  # ускорено
            if aid in pending_albums:
                await send_album(aid, pending_albums.pop(aid))
            album_timers.pop(aid, None)

        album_timers[album_id] = asyncio.create_task(process_album(album_id))
        return

    # Обычное сообщение
    if not check_filters(text):
        return

    try:
        if msg.media:
            sent = await client.send_file(
                TARGET_CHANNEL,
                msg.media,
                caption=text
            )
        else:
            sent = await client.send_message(
                TARGET_CHANNEL,
                text
            )

        message_map[str(msg.id)] = sent.id
        save_message_map()
        logger.info(f"✅ {msg.id} -> {sent.id}")

    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ====== РЕДАКТИРОВАНИЕ ======
@client.on(events.MessageEdited(chats=SOURCE_CHAT))
async def on_edit(event):
    msg = event.message
    text = msg.text or msg.message or ""
    key = str(msg.id)

    if is_banned(msg.sender_id):
        return

    if key in message_map:
        target_id = message_map[key]
        try:
            if check_filters(text):
                if msg.media:
                    await client.edit_message(TARGET_CHANNEL, target_id, text, file=msg.media)
                else:
                    await client.edit_message(TARGET_CHANNEL, target_id, text)
                logger.info(f"✏️ Изменён {msg.id}")
            else:
                await client.delete_messages(TARGET_CHANNEL, target_id)
                del message_map[key]
                save_message_map()
                logger.info(f"🗑️ Удалён после редактирования {msg.id}")
        except Exception as e:
            logger.error(f"Ошибка редактирования: {e}")

# ====== УДАЛЕНИЕ ======
@client.on(events.MessageDeleted(chats=SOURCE_CHAT))
async def on_delete(event):
    for msg_id in event.deleted_ids:
        key = str(msg_id)
        if key in message_map:
            try:
                await client.delete_messages(TARGET_CHANNEL, message_map[key])
                del message_map[key]
                save_message_map()
                logger.info(f"🗑️ Удалён {msg_id}")
            except Exception as e:
                logger.error(f"Ошибка удаления {msg_id}: {e}")

# ====== ЗАПУСК ======
async def main():
    await client.start(bot_token=BOT_TOKEN)
    logger.info("🚀 Бот запущен!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
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
