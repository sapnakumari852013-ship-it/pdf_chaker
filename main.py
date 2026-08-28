import io
import json
import os
import asyncio
import time
import gc
import firebase_admin
from firebase_admin import credentials, db
from quart import Quart, jsonify, request
from quart_cors import cors
from telethon import TelegramClient
from telethon.sessions import StringSession

app = Quart(__name__)
app = cors(app, allow_origin="*")

API_ID = int(os.environ.get("API_ID", 1234567))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING", "YOUR_STRING_SESSION")
CHANNEL = int(os.environ.get("CHANNEL_ID", -1001234567890))
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL")

cred_json_str = os.environ.get("FIREBASE_CRED_JSON")
if cred_json_str and not firebase_admin._apps:
    cred_dict = json.loads(cred_json_str)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

last_heartbeat_time = time.time()

# ----------------- HEARTBEAT & AUTO CLEANUP -----------------
@app.route("/api/heartbeat", methods=["POST"])
async def heartbeat():
    global last_heartbeat_time
    last_heartbeat_time = time.time()
    return jsonify({"status": "active"})

async def periodic_cleanup():
    global last_heartbeat_time
    while True:
        await asyncio.sleep(30)
        try:
            if time.time() - last_heartbeat_time > 45:
                print("[Auto-Cleanup] HTML is closed. Skipping cleanup.", flush=True)
                continue
            
            gc.collect()
            print("[Auto-Cleanup] HTML is OPEN. RAM cache cleared.", flush=True)
        except Exception as e:
            print(f"[Auto-Cleanup Error]: {e}", flush=True)
# -----------------------------------------------------------

@app.route("/")
async def home():
    return "Private Cloud Server Active!", 200

@app.route("/api/register", methods=["POST"])
async def register_user():
    try:
        data = await request.get_json()
        device_id, password = data.get("device_id"), data.get("password")
        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400
        user_ref = db.reference(f"users/{device_id}")
        if user_ref.get():
            return jsonify({"success": False, "error": "यह ID पहले से रजिस्टर्ड है!"}), 400
        user_ref.set({"password": password})
        return jsonify({"success": True, "message": "Password saved successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/login", methods=["POST"])
async def login_user():
    try:
        data = await request.get_json()
        device_id, password = data.get("device_id"), data.get("password")
        if not device_id or not password:
            return jsonify({"success": False, "error": "Missing ID or Password"}), 400
        user_data = db.reference(f"users/{device_id}").get()
        if not user_data or user_data.get("password") != password:
            return jsonify({"success": False, "error": "गलत ID या पासवर्ड!"}), 401
        return jsonify({"success": True, "message": "Login successful!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
        filename = file.filename or "media.jpg"
        img_io.name = filename

        is_video = filename.lower().endswith(('.mp4', '.mov', '.webm', '.mkv', '.avi', '.3gp'))
        msg = await client.send_file(CHANNEL, img_io, caption=f"DEV-{device_id}", force_document=False)

        db.reference(f"photos/{device_id}/{msg.id}").set({
            "id": msg.id,
            "date": msg.date.isoformat(),
            "url": f"https://pdf-chaker-1.onrender.com/api/photo/{msg.id}",
            "is_video": is_video
        })

        del file_bytes, img_io
        gc.collect()
        return jsonify({"success": True, "message": "Uploaded successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/gallery", methods=["GET"])
async def get_gallery():
    try:
        device_id = request.args.get("device_id", "")
        if not device_id:
            return jsonify({"photos": [], "has_more": False})
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 12))

        photos_data = db.reference(f"photos/{device_id}").get()
        if not photos_data:
            return jsonify({"photos": [], "has_more": False})

        photos_list = list(photos_data.values())
        photos_list.reverse()
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit

        return jsonify({
            "photos": photos_list[start_idx:end_idx],
            "has_more": end_idx < len(photos_list),
            "total": len(photos_list)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/delete", methods=["POST"])
async def delete_photos():
    try:
        data = await request.get_json()
        device_id, photo_ids = data.get("device_id"), data.get("photo_ids", [])
        if not photo_ids or not device_id:
            return jsonify({"error": "Missing data"}), 400
        await client.delete_messages(CHANNEL, photo_ids)
        for pid in photo_ids:
            db.reference(f"photos/{device_id}/{pid}").delete()
        return jsonify({"success": True, "message": "Deleted successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/photo/<int:msg_id>", methods=["GET"])
async def get_photo(msg_id):
    try:
        msg = await client.get_messages(CHANNEL, ids=msg_id)
        if msg and (msg.photo or msg.document):
            file_bytes = await client.download_media(msg, file=bytes)
            content_type = "image/jpeg"
            if msg.document:
                for attr in msg.document.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        if attr.file_name.lower().endswith(('.mp4', '.mov', '.webm', '.mkv', '.avi', '.3gp')):
                            content_type = "video/mp4"
            response_data = (file_bytes, 200, {"Content-Type": content_type, "Cache-Control": "max-age=86400"})
            del file_bytes
            gc.collect()
            return response_data
        return "Media Not Found", 404
    except Exception as e:
        return str(e), 500

@app.route("/api/notes/add", methods=["POST"])
async def save_note():
    try:
        data = await request.get_json()
        device_id, note_content = data.get("device_id"), data.get("text")
        if not device_id or not note_content:
            return jsonify({"success": False, "error": "Missing data"}), 400
        new_ref = db.reference(f"notes/{device_id}").push()
        new_ref.set({"id": new_ref.key, "text": note_content})
        return jsonify({"success": True, "message": "Saved!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/notes", methods=["GET"])
async def get_notes():
    try:
        device_id = request.args.get("device_id", "")
        if not device_id: return jsonify([])
        notes_data = db.reference(f"notes/{device_id}").get()
        return jsonify(list(notes_data.values())) if notes_data else jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/notes/delete", methods=["POST", "OPTIONS"])
async def delete_note():
    if request.method == "OPTIONS": return "", 200
    try:
        data = await request.get_json() or {}
        device_id = data.get("device_id")
        note_id = data.get("note_id") or data.get("id")
        if not device_id or not note_id:
            return jsonify({"success": False, "error": "Missing data"}), 400
        db.reference(f"notes/{device_id}/{note_id}").delete()
        return jsonify({"success": True, "message": "Deleted!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.before_serving
async def startup():
    await client.start()
    asyncio.create_task(periodic_cleanup())
    print("Server Started with Smart Heartbeat Cleaning!", flush=True)

if __name__ == "__main__":
    import hypercorn.asyncio
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 10000)}"]
    asyncio.run(hypercorn.asyncio.serve(app, config))
