import asyncio
import os
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Flask Web Server setup (UptimeRobot के PING के लिए)
app = Flask(__name__)


@app.route("/")
def home():
    return "Server is Live!", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# Telethon Setup
API_ID = int(os.environ.get("API_ID", 1234567))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING", "YOUR_STRING_SESSION")
CHANNEL = "sxhckfufig"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@client.on(events.NewMessage(chats=CHANNEL))
async def handler(event):
    print(f"[LIVE DATA]: {event.message.text}", flush=True)


async def start_telethon():
    await client.start()
    print(f"Telethon listening to @{CHANNEL}", flush=True)
    await client.run_until_disconnected()


if __name__ == "__main__":
    # Flask को अलग Background Thread में चलाएं
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Telethon Async Loop चलाएं
    asyncio.run(start_telethon())
