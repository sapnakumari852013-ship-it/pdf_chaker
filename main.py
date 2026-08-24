import asyncio
import os
import threading
from flask import Flask, jsonify
from flask_cors import CORS
from telethon import TelegramClient
from telethon.sessions import StringSession

app = Flask(__name__)
CORS(app)

API_ID = int(os.environ.get("API_ID", 1234567))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING", "YOUR_STRING_SESSION")
CHANNEL = "sxhckfufig"

# Async Loop और Telethon Client
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, loop=loop)


@app.route("/")
def home():
    return "Server is Active (Zero-Storage)", 200


# सीधे Telegram Server से On-Demand 100 Messages खींचकर HTML को देना
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

    try:
        # Background Event Loop में सुरक्षित Execution
        future = asyncio.run_coroutine_threadsafe(fetch_history(), loop)
        data = future.result(timeout=15)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def start_telethon_thread():
    async def main():
        await client.start()
        print(f"Telethon Connected Successfully to @{CHANNEL}!", flush=True)

    loop.run_until_complete(main())


if __name__ == "__main__":
    # 1. Telethon Connection को स्टार्ट करें
    t = threading.Thread(target=start_telethon_thread)
    t.daemon = True
    t.start()

    # 2. Flask Server चलाएं
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
