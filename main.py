import asyncio
import os
import threading
from flask import Flask, Response, jsonify
from flask_cors import CORS
from telethon import TelegramClient, events
from telethon.sessions import StringSession

app = Flask(__name__)
CORS(app)

API_ID = int(os.environ.get("API_ID", 1234567))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING", "YOUR_STRING_SESSION")
CHANNEL = "sxhckfufig"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

loop = asyncio.new_event_loop()


def run_async_loop():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.start())
    print("Telethon Client Connected and Ready!", flush=True)
    loop.run_forever()


# 1. सीधे Telegram से मैसेज इतिहास (History) लाकर HTML को देना (Render में 0% storage)
@app.route("/api/history")
def get_history():
    async def fetch_history():
        messages = []
        async for message in client.iter_messages(CHANNEL, limit=100):
            if message.text:
                messages.append(
                    {
                        "text": message.text,
                        "timestamp": message.date.isoformat(),
                    }
                )
        return messages

    future = asyncio.run_coroutine_threadsafe(fetch_history(), loop)
    return jsonify(future.result())


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    t = threading.Thread(target=run_async_loop)
    t.daemon = True
    t.start()

    run_flask()
