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


@app.route("/")
async def home():
    return "Private Cloud Gallery Server Active!", 200


# 1. यूजर की डिवाइस ID के हिसाब से फोटो फैच करना
@app.route("/api/gallery", methods=["GET"])
async def get_gallery():
    try:
        device_id = request.args.get("device_id", "")
        if not device_id:
            return jsonify([])

        photos = []
        async for msg in client.iter_messages(CHANNEL, limit=100):
            if msg.photo and msg.text:
                if f"DEV-{device_id}" in msg.text:
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


# 2. Telegram से फोटो स्ट्रीम करना
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


# 3. फोटो अपलोड (Fixed Quart File Handling)
@app.route("/api/upload", methods=["POST"])
async def upload_photo():
    try:
        files = await request.files
        form_data = await request.form

        device_id = form_data.get("device_id", "")
        if "file" not in files or not device_id:
            return jsonify({"error": "File or Device ID missing"}), 400

        file = files["file"]

        # Quart में file.read() एक साधारण method होता है, इसे await नहीं करना है
        file_bytes = file.read()

        img_io = io.BytesIO(file_bytes)
        img_io.name = file.filename or "photo.jpg"

        caption = f"DEV-{device_id}"
        await client.send_file(
            CHANNEL, img_io, caption=caption, force_document=False
        )

        return jsonify({"success": True, "message": "Uploaded successfully!"})
    except Exception as e:
        print(f"Upload error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.before_serving
async def startup():
    await client.start()
    print("Private Gallery Server Ready!", flush=True)


if __name__ == "__main__":
    import asyncio
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 10000)}"]
    asyncio.run(hypercorn.asyncio.serve(app, config))
