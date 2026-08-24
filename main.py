import os
from quart import Quart, jsonify
from quart_cors import cors
from telethon import TelegramClient
from telethon.sessions import StringSession

app = Quart(__name__)
app = cors(app, allow_origin="*")

API_ID = int(os.environ.get("API_ID", 1234567))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING", "YOUR_STRING_SESSION")
CHANNEL = "sxhckfufig"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@app.route("/")
async def home():
    return "Server Active (Quart Async)", 200


@app.route("/api/history")
async def get_history():
    try:
        messages = []
        # Telegram से लाइव 100 मैसेज ऑन-डिमांड फैच
        async for message in client.iter_messages(CHANNEL, limit=100):
            if message.text:
                messages.append(
                    {
                        "text": message.text,
                        "timestamp": message.date.isoformat(),
                    }
                )
        return jsonify(messages)
    except Exception as e:
        print(f"Error in /api/history: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.before_serving
async def startup():
    await client.start()
    print(f"Telethon Connected Successfully to @{CHANNEL}!", flush=True)


if __name__ == "__main__":
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 10000)}"]

    import asyncio

    asyncio.run(hypercorn.asyncio.serve(app, config))
