import io
import json
import os
import firebase_admin
from firebase_admin import credentials, db
from quart import Quart, jsonify, request
from quart_cors import cors
from telethon import TelegramClient
from telethon.sessions import StringSession

app = Quart(__name__)
# CORS Allow for all origins
app = cors(app, allow_origin="*")

API_ID = int(os.environ.get("API_ID", 1234567))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING", "YOUR_STRING_SESSION")
CHANNEL = int(os.environ.get("CHANNEL_ID", -1001234567890))
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL")

# ----------------- FIREBASE SETUP -----------------
cred_json_str = os.environ.get("FIREBASE_CRED_JSON")

if cred_json_str and not firebase_admin._apps:
    cred_dict = json.loads(cred_json_str)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
# --------------------------------------------------

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@app.route("/")
async def home():
    return "Private Cloud Server Active with Direct Telegram Links!", 200


# 1. रजिस्टर करना (Firebase DB)
@app.route("/api/register", methods=["POST"])
async def register_user():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        password = data.get("password")

        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400

        user_ref = db.reference(f"users/{device_id}")
        if user_ref.get():
            return jsonify({"success": False, "error": "यह ID पहले से रजिस्टर्ड है!"}), 400

        user_ref.set({"password": password})
        return jsonify({"success": True, "message": "Password saved successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 2. लॉगिन करना (Firebase DB)
@app.route("/api/login", methods=["POST"])
async def login_user():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        password = data.get("password")

        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400

        user_data = db.reference(f"users/{device_id}").get()
        if not user_data:
            return jsonify({"success": False, "error": "यह ID मौजूद नहीं है!"}), 404

        if user_data.get("password") != password:
            return jsonify({"success": False, "error": "गलत पासवर्ड!"}), 401

        return jsonify({"success": True, "message": "Login successful!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 3. फोटो अपलोड करना (Telegram + Direct Web URL Generation)
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
        # फोटो को चैनल पर भेजें
        msg = await client.send_file(CHANNEL, img_io, caption=caption, force_document=False)

        # Telegram से डायरेक्ट वेब लिंक (Public/Web URL) प्राप्त करें
        # Telethon में .media.document या .photo से डायरेक्ट लिंक्स निकाले जा सकते हैं या Web File API इस्तेमाल होती है
        # चूंकि चैनल पब्लिक होना चाहिए ताकि डायरेक्ट लिंक काम करे, हम टेलीग्राम का सीधा फाइल वेब यूआरएल बना रहे हैं:
        
        # अगर आपका चैनल पब्लिक है (जैसे @username वाला):
        # डायरेक्ट लिंक का फॉर्मेट: https://t.me/c/CHANNEL_ID/MSG_ID (लेकिन प्राइवेट चैनल के लिए वेब प्रीव्यू काम नहीं करता)
        
        # इसलिए सबसे बेस्ट तरीका: हम फाइल का डायरेक्ट CDN लिंक निकाल सकते हैं या बॉट के जरिए फेच कर सकते हैं:
        file_web_url = await client.get_file_web_location(msg.photo) if hasattr(msg, 'photo') and msg.photo else None
        
        # यदि डायरेक्ट वेब लोकेशन नहीं मिलती, तो हम सुरक्षित रूप से टेलीथॉन का फाइल एक्सपोर्ट लिंक या फाइल आईडी सेव करेंगे
        # पर चूंकि आप क्रोम में डायरेक्ट खोलना चाहते हैं, चैनल को 'Public' रखना जरूरी है ताकि t.me लिंक सीधे क्रोम में खुले।
        
        # मान लीजिए आपका चैनल पब्लिक है और उसका यूजरनेम 'my_photo_channel_xyz' है:
        CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "your_channel_username")
        direct_url = f"https://t.me/{CHANNEL_USERNAME}/{msg.id}"

        db.reference(f"photos/{device_id}/{msg.id}").set({
            "id": msg.id,
            "date": msg.date.isoformat(),
            "url": direct_url  # अब यह सीधा टेलीग्राम का लिंक है!
        })

        return jsonify({"success": True, "message": "Photo uploaded successfully!", "url": direct_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 4. गैलरी फोटो फेच करना
@app.route("/api/gallery", methods=["GET"])
async def get_gallery():
    try:
        device_id = request.args.get("device_id", "")
        if not device_id:
            return jsonify([])

        photos_data = db.reference(f"photos/{device_id}").get()
        if not photos_data:
            return jsonify([])

        return jsonify(list(photos_data.values()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 5. फोटो डिलीट करना
@app.route("/api/delete", methods=["POST"])
async def delete_photos():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        photo_ids = data.get("photo_ids", [])

        if not photo_ids or not device_id:
            return jsonify({"error": "No photo IDs or Device ID provided"}), 400

        await client.delete_messages(CHANNEL, photo_ids)

        for pid in photo_ids:
            db.reference(f"photos/{device_id}/{pid}").delete()

        return jsonify({"success": True, "message": "Photos deleted successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# (Note: अब /api/photo/<int:msg_id> रूट की जरूरत नहीं है क्योंकि फोटो सीधा टेलीग्राम पर खुलेगी!)


# 7. नोट्स सेव करना (Firebase)
@app.route("/api/notes/add", methods=["POST"])
async def save_note():
    try:
        data = await request.get_json()
        device_id = data.get("device_id")
        note_content = data.get("text") or data.get("note")

        if not device_id or not note_content:
            return jsonify({"success": False, "error": "Missing Device ID or Note content"}), 400

        new_ref = db.reference(f"notes/{device_id}").push()
        new_ref.set({
            "id": new_ref.key,
            "text": note_content
        })
        return jsonify({"success": True, "message": "Note saved successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 8. नोट्स फेच करना (Firebase)
@app.route("/api/notes", methods=["GET"])
async def get_notes():
    try:
        device_id = request.args.get("device_id", "")
        if not device_id:
            return jsonify([])

        notes_data = db.reference(f"notes/{device_id}").get()
        if not notes_data:
            return jsonify([])

        return jsonify(list(notes_data.values()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 9. नोट्स डिलीट करना
@app.route("/api/notes/delete", methods=["POST", "OPTIONS"])
async def delete_note():
    if request.method == "OPTIONS":
        return "", 200

    try:
        data = await request.get_json() or {}
        device_id = data.get("device_id")
        note_id = data.get("note_id") or data.get("id")

        if not device_id or not note_id:
            return jsonify({"success": False, "error": "Missing device_id or note_id"}), 400

        db.reference(f"notes/{device_id}/{note_id}").delete()

        return jsonify({"success": True, "message": "Note deleted successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.before_serving
async def startup():
    await client.start()
    print("Private Cloud Server Ready with Direct Telegram Links!", flush=True)


if __name__ == "__main__":
    import asyncio
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 10000)}"]
    asyncio.run(hypercorn.asyncio.serve(app, config))
