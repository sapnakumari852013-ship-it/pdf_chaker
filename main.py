import io
import os
from quart import Quart, jsonify, request
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


# 1. फोटो गैलरी फ़ैच करना (Telegram से ऑन-डिमांड)
@app.route("/api/gallery", methods=["GET"])
async def get_gallery():
    try:
        photos = []
        async for msg in client.iter_messages(CHANNEL, limit=50):
            if msg.photo:
                # टेलीग्राम फोटो को सीधे URL/Bytes की तरह Serve करने के लिए
                photos.append(
                    {
                        "id": msg.id,
                        "date": msg.date.isoformat(),
                        "url": f"https://pdf-chaker-1.onrender.com/api/photo/{msg.id}",
                    }
                )
        return jsonify(photos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 2. टेलीग्राम से फोटो डाउनलोड करके HTML को दिखाना
@app.route("/api/photo/<int:msg_id>", methods=["GET"])
async def get_photo(msg_id):
    try:
        msg = await client.get_messages(CHANNEL, ids=msg_id)
        if msg and msg.photo:
            photo_bytes = await client.download_media(msg.photo, file=bytes)
            return (
                photo_bytes,
                200,
                {"Content-Type": "image/jpeg", "Cache-Control": "max-age=86400"},
            )
        return "Photo Not Found", 404
    except Exception as e:
        return str(e), 500


# 3. HTML से फोटो टेलीग्राम चैनल में अपलोड करना
@app.route("/api/upload", methods=["POST"])
async def upload_photo():
    try:
        files = await request.files
        if "file" not in files:
            return jsonify({"error": "No file uploaded"}), 400

        file = files["file"]
        file_bytes = file.read()

        # टेलीग्राम चैनल में फोटो भेजना
        await client.send_file(CHANNEL, io.BytesIO(file_bytes), voice_note=False)
        return jsonify({"success": True, "message": "Photo uploaded to Telegram!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.before_serving
async def startup():
    await client.start()
    print("Gallery Server Live!", flush=True)


if __name__ == "__main__":
    import asyncio
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 10000)}"]
    asyncio.run(hypercorn.asyncio.serve(app, config))
