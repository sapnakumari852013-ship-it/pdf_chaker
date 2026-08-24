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


# 1. टेलीग्राम चैनल पर पासवर्ड सेट/रजिस्टर करना
@app.route("/api/register", methods=["POST"])
async def register_user():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        password = data.get("password")

        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400

        # चेक करें कि क्या इस ID का पासवर्ड पहले से मौजूद है
        async for msg in client.iter_messages(CHANNEL, limit=200):
            if msg.text and msg.text.startswith(f"PASS-{device_id}:"):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "यह ID पहले से रजिस्टर्ड है! कृपया लॉगिन करें।",
                        }
                    ),
                    400,
                )

        # चैनल पर पासवर्ड सेव करें
        await client.send_message(CHANNEL, f"PASS-{device_id}:{password}")
        return jsonify(
            {"success": True, "message": "Password saved successfully!"}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 2. टेलीग्राम चैनल से पासवर्ड मैच करके लॉगिन करना
@app.route("/api/login", methods=["POST"])
async def login_user():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        password = data.get("password")

        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400

        saved_password = None
        # टेलीग्राम चैनल से पासवर्ड ढूँढना
        async for msg in client.iter_messages(CHANNEL, limit=500):
            if msg.text and msg.text.startswith(f"PASS-{device_id}:"):
                saved_password = msg.text.split(":", 1)[1]
                break

        if not saved_password:
            return (
                jsonify(
                    {"success": False, "error": "यह ID टेलीग्राम पर मौजूद नहीं है!"}
                ),
                404,
            )

        if saved_password != password:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "गलत पासवर्ड! (Invalid Password)",
                    }
                ),
                401,
            )

        return jsonify({"success": True, "message": "Login successful!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 3. गैलरी फोटो फेच करना
@app.route("/api/gallery", methods=["GET"])
async def get_gallery():
    try:
        device_id = request.args.get("device_id", "")
        if not device_id:
            return jsonify([])

        photos = []
        async for msg in client.iter_messages(CHANNEL, limit=200):
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


# 4. फोटो स्ट्रीम करना
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


# 5. फोटो अपलोड करना
@app.route("/api/upload", methods=["POST"])
async def upload_photo():
    try:
        files = await request.files
        form_data = await request.form

        device_id = form_data.get("device_id", "")
        if "file" not in files or not device_id:
            return jsonify({"error": "File or Device ID missing"}), 400

        file = files["file"]
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
