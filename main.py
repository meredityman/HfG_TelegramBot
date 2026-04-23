from dotenv import load_dotenv
import asyncio
import os
from uuid import uuid4 
import json

from pathlib import Path

from telethon import events, Button
from telethon.sync import TelegramClient, functions, types
from telethon.sessions import StringSession

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from typing import Callable, Any, Optional
import logging

import bot
from bot import Bot, BotData
import inspect  


@dataclass_json
@dataclass
class UserSessionData:
    active_bot: BotData = None
    is_started: bool = False

@dataclass_json
@dataclass
class SessionData:
    user_sessions: dict[int, UserSessionData] = field(default_factory=dict)


class CommandStruct:
    def __init__(self, command, description):
        self.command = command
        self.description = description


BOT_COMMANDS = [
    CommandStruct('start', 'Start the session and set up bot commands'),
    CommandStruct('help', 'Get help information'),
    CommandStruct('list', 'List available bots'),
    CommandStruct('talk <bot_username>', 'Start a conversation with the specified bot'),
    CommandStruct('exit', 'Shut down the bot')
]

BOT_CONFIGS = []


def load_bot_configs():
    for config_path in Path("./configs").glob("*.json"):
        logging.info(f"Loading bot configuration from {config_path}...")
        try:
            config_data = json.loads(config_path.read_text())

            if 'bot_class' in config_data:
                bot_class_name = config_data['bot_class']
                
                if inspect.isclass(getattr(bot, bot_class_name, None)) and issubclass(getattr(bot, bot_class_name), Bot):
                    bot_class = getattr(bot, bot_class_name)
                    bot_data_class = getattr(bot_class, 'config_type', None)
                    if bot_data_class and not issubclass(bot_data_class, BotData):
                        logging.error(f"Invalid config_type for bot class '{bot_class_name}' in {config_path}. Must be a subclass of BotData.")
                        continue

                    if 'configs' in config_data:
                        for bot_config in config_data['configs']:
                            BOT_CONFIGS.append((bot_config, bot_class))
                            logging.info(f"Loaded bot configuration: {bot_config['name']} (model: {bot_config.get('model', 'N/A')}) using class '{bot_class_name}'")
 
                else:
                    logging.error(f"Bot class '{bot_class_name}' specified in {config_path} does not exist or is not a subclass of Bot.")
                    continue

            else:  
                logging.error(f"No 'bot_class' specified in {config_path}.")
                continue

        except Exception as e:
            print(f"Error loading bot configuration from {config_path}: {e}")

async def get_session_data(client, chat_id):
    if not session_store or not session_store.user_sessions:
        return None
    return session_store.user_sessions.get(chat_id)


async def get_active_bot(client, chat_id):
    session = await get_session_data(client, chat_id)
    if not session or not session.active_bot_config:
        return None, None
    if session and session.active_bot_config:
        return session.active_bot_config
    return None, None


async def set_active_bot(client, chat_id, bot_data, bot_class):
    session = await get_session_data(client, chat_id)
    if not session:
        session = UserSessionData()
        session_store.user_sessions[chat_id] = session

    session.active_bot_config = bot_class, bot_data

    data_path = Path("./data/sessions.json")
    data_path.write_text(json.dumps(session_store.to_dict()))
    print(f"Updated active bot for chat_id {chat_id} to {bot_data['name'] if bot_data else None}")

async def handle_list_bots_command(event):
    if not BOT_CONFIGS:
        await event.reply("No bots are currently available.")
        return
    
    bot_list = "\n".join(f"- {bot['name']}" for bot, _ in BOT_CONFIGS)
    await event.client.send_message(event.chat_id, f"Available bots:\n{bot_list}")

async def handle_help_command(event):
    available_commands = "\n".join(f"/{c.command} - {c.description}" for c in BOT_COMMANDS)
    await event.client.send_message(event.chat_id, f"Available commands:\n{available_commands}")

async def handle_start_command(event):

    await handle_help_command(event)
    await handle_list_bots_command(event)

    session_data = await get_session_data(event.client, event.chat_id)
    if not session_data:
        session_store.user_sessions[event.chat_id] = UserSessionData()
        data_path = Path("./data/sessions.json")
        data_path.write_text(json.dumps(session_store.to_dict()))
        print(f"Initialized session data for chat_id {event.chat_id}")
    else:
        print(f"Session data already exists for chat_id {event.chat_id}")
        await event.reply("Session already initialized. Use /help to see available commands.")

async def handle_start_bot_command(event, bot_username):

    active_bot = await get_active_bot(event.client, bot_username)

    if active_bot:
        await handle_exit_command(event)

    bot_config, bot_class = next(((b, c) for b, c in BOT_CONFIGS if b['name'].lower() == bot_username.lower()), (None, None))
    if not bot_config:
        await event.reply(f"No bot found with the name '{bot_username}'. Use /list to see available bots.")
        return
    
    await event.reply(f"Started conversation with {bot_config['name']} (model: {bot_config['model']}).")
    
    await set_active_bot(event.client, event.chat_id, bot_config, bot_class)
    
   

async def handle_exit_command(event):
    bot_active = await get_active_bot(event.client, event.chat_id)
    if not bot_active:
        await event.reply("No active bot to exit.")
        return
    
    await set_active_bot(event.client, event.chat_id, None, None)
    await event.reply("Exited the active bot.")

async def handle_commands(event):
    logging.info(f"Received command: {event.raw_text} from chat_id: {event.chat_id}")
    cmd = event.raw_text.lstrip('/').split()[0]

    bot_class, bot_config = await get_active_bot(event.client, event.chat_id)

    if not bot_class:
        print(f"Received command: {cmd}")
        if cmd == 'help':
            await handle_help_command(event)
        elif cmd == "start":
            await handle_start_command(event)
        elif cmd == "list":
            await handle_list_bots_command(event)
        elif cmd.startswith("talk"):
            parts = event.raw_text.split()
            if len(parts) < 2:
                await event.reply("Usage: /talk <bot_username>")
                return
            bot_username = parts[1]
            await handle_start_bot_command(event, bot_username)
        else:
            await event.reply(f"Unknown command: {cmd}. Use /help to see available commands.")
    elif cmd in ['help', 'exit']:
        if cmd == 'help':
            await handle_help_command(event)
        elif cmd == 'exit':
            await handle_exit_command(event)
        else:
            await handle_message(event)

async def handle_message(event):
    # chat = await event.get_chat()
    sender = await event.get_sender()
    chat_id = event.chat_id
    sender_id = event.sender_id

    bot_class, bot_config = await get_active_bot(event.client, chat_id)

    if not bot_class:
        await event.reply("No active bot. Use /list to see available bots.")
        return

    else:
        bot = bot_class(**bot_config)
        await event.client.send_message(chat_id, bot.get_completion(event.raw_text))
        await set_active_bot(event.client, chat_id, bot.config.to_dict(), bot_class)


load_dotenv()

print("Loading session data...")
data_path = Path(f"./data/sessions_{uuid4().hex}.json")
if not data_path.exists():
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(SessionData().to_dict()))
session_store = SessionData.from_dict(json.loads(data_path.read_text()))
print("Session data loaded.")

# session_path = Path(f"./sessions/session_{uuid4().hex}.session")
Path("./sessions").mkdir(parents=True, exist_ok=True)
session_path = Path(f"./sessions/session.session")


async def main():
    api_id    = os.getenv('TELEGRAM_API_ID')
    api_hash  = os.getenv('TELEGRAM_API_HASH')
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

    print(f"API ID: {int(api_id)}")
    print(f"API Hash: {api_hash}")
    print(f"Bot Token: {'*' * len(bot_token) if bot_token else None}")

    if not api_id or not api_hash or not bot_token:
        print("Please set the TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_BOT_TOKEN environment variables.")
        exit(1)

    load_bot_configs()

    client = TelegramClient(session_path, api_id=int(api_id), api_hash=api_hash)

    client.add_event_handler(handle_commands, event=events.NewMessage(incoming=True, pattern=r'^/'))  # Match any message that starts with '/'

    await client.start(bot_token=bot_token)

    try:
        me = await client.get_me()
        if not me:
            print('Failed to fetch bot identity after login.')
            exit(1)

        if not getattr(me, 'bot', False):
            print('The current session is not logged in as a bot account.')
            print('Delete the session files and restart:')
            print(f'  rm -f {session_path}.session {session_path}.session-journal')
            exit(1)

        print(f"Logged in as @{me.username} (id={me.id})")
        client.add_event_handler(handle_message, event=events.NewMessage(incoming=True, pattern=r'^(?!/).+'))  # Match any message that does not start with '/'

        print("Bot is running...")
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if '__main__' == __name__:
    asyncio.run(main())