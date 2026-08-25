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
    return "Private Cloud Server Active!", 200


# 1. पासवर्ड रजिस्टर करना
@app.route("/api/register", methods=["POST"])
async def register_user():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        password = data.get("password")

        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400

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

        await client.send_message(CHANNEL, f"PASS-{device_id}:{password}")
        return jsonify(
            {"success": True, "message": "Password saved successfully!"}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 2. पासवर्ड मैच करके लॉगिन करना
@app.route("/api/login", methods=["POST"])
async def login_user():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        password = data.get("password")

        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400

        saved_password = None
        async for msg in client.iter_messages(CHANNEL, limit=500):
            if msg.text and msg.text.startswith(f"PASS-{device_id}:"):
                saved_password = msg.text.split(":", 1)[1]
                break

        if not saved_password:
            return (
                jsonify(
                    {"success": False, "error": "यह ID हमारे क्लाउड पर मौजूद नहीं है!"}
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
        form_data = await request.form
        files = await request.files

        device_id = form_data.get("device_id", "")
        file = files.get("file")

        if not file or not device_id:
            return jsonify({"error": "File or Device ID missing"}), 400

        file_bytes = file.read()
        img_io = io.BytesIO(file_bytes)
        img_io.name = file.filename or "photo.jpg"

        caption = f"DEV-{device_id}"
        await client.send_file(
            CHANNEL, img_io, caption=caption, force_document=False
        )

        return jsonify({"success": True, "message": "Photo uploaded successfully!"})
    except Exception as e:
        print(f"Upload error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


# 6. फोटो/मैसेज डिलीट करना
@app.route("/api/delete", methods=["POST"])
async def delete_photos():
    try:
        data = await request.get_json()
        photo_ids = data.get("photo_ids", [])

        if not photo_ids:
            return jsonify({"error": "No photo IDs provided"}), 400

        await client.delete_messages(CHANNEL, photo_ids)
        return jsonify(
            {"success": True, "message": "Photos deleted successfully!"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 7. नोट्स सेव करना
@app.route("/api/notes/add", methods=["POST"])
async def save_note():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        note_content = data.get("text") or data.get("note")

        if not device_id or not note_content:
            return jsonify({"success": False, "error": "Missing Device ID or Note content"}), 400

        await client.send_message(CHANNEL, f"NOTE-{device_id}:{note_content}")
        return jsonify({"success": True, "message": "Note saved successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 8. नोट्स फेच करना
@app.route("/api/notes", methods=["GET"])
async def get_notes():
    try:
        device_id = request.args.get("device_id", "")
        if not device_id:
            return jsonify([])

        notes = []
        async for msg in client.iter_messages(CHANNEL, limit=300):
            if msg.text and msg.text.startswith(f"NOTE-{device_id}:"):
                content = msg.text.split(":", 1)[1]
                notes.append({
                    "id": msg.id,
                    "date": msg.date.isoformat(),
                    "text": content
                })
        return jsonify(notes)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 9. नोट एडिट करना (नया रूट)
@app.route("/api/notes/edit", methods=["POST"])
async def edit_note():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        note_id = data.get("note_id")
        new_text = data.get("text")

        if not device_id or not note_id or not new_text:
            return jsonify({"success": False, "error": "Missing details"}), 400

        # टेलीग्राम चैनल में मौजूद पुराने नोट मैसेज का टेक्स्ट एडिट करना
        await client.edit_message(CHANNEL, int(note_id), f"NOTE-{device_id}:{new_text}")
        return jsonify({"success": True, "message": "Note updated successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 10. नोट डिलीट करना (नया रूट)
@app.route("/api/notes/delete", methods=["POST"])
async def delete_note():
    try:
        data = await request.get_json()
        note_id = data.get("note_id")

        if not note_id:
            return jsonify({"success": False, "error": "Note ID missing"}), 400

        # टेलीग्राम चैनल से नोट का मैसेज डिलीट करना
        await client.delete_messages(CHANNEL, [int(note_id)])
        return jsonify({"success": True, "message": "Note deleted successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.before_serving
async def startup():
    await client.start()
    print("Private Cloud Server Ready!", flush=True)


if __name__ == "__main__":
    import asyncio
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 10000)}"]
    asyncio.run(hypercorn.asyncio.serve(app, config))
