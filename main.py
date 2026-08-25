import os
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from pyrogram import Client

app = Flask(__name__)
CORS(app)

# Render Environment Variables से रीड करना
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))  # चैनल ID को integer होना चाहिए (e.g. -100xxxx)

# Pyrogram Client Start
pyrogram_app = Client(
    "telegram_bridge",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)
pyrogram_app.start()

# Helper: Async function run करने के लिए
def run_async(coro):
    return asyncio.run(coro)

# ----------------- Profile Photo Endpoints -----------------

async def async_upload_pfp(device_id, file_path, filename):
    # 1. पुराना PFP ढूंढकर डिलीट करना
    async for msg in pyrogram_app.get_chat_history(CHANNEL_ID, limit=100):
        if msg.caption == f"PFP|{device_id}":
            await pyrogram_app.delete_messages(CHANNEL_ID, msg.id)
            break

    # 2. नया PFP अपलोड करना
    msg = await pyrogram_app.send_photo(CHANNEL_ID, photo=file_path, caption=f"PFP|{device_id}")
    file_url = await pyrogram_app.download_media(msg.photo, file_name=f"temp_{msg.id}.jpg")
    return file_url

@app.route('/api/upload-pfp', methods=['POST'])
def upload_pfp():
    device_id = request.form.get('device_id')
    if 'file' not in request.files or not device_id:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    file = request.files['file']
    temp_path = f"temp_{file.filename}"
    file.save(temp_path)

    try:
        run_async(async_upload_pfp(device_id, temp_path, file.filename))
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'success': True})
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'success': False, 'error': str(e)}), 500


async def async_get_pfp(device_id):
    async for msg in pyrogram_app.get_chat_history(CHANNEL_ID, limit=100):
        if msg.caption == f"PFP|{device_id}" and msg.photo:
            # Telegram से फ़ाइल डाउनलोड करके URL/Data के रूप में देना
            return msg.photo.file_id
    return None

@app.route('/api/get-pfp', methods=['GET'])
def get_pfp():
    device_id = request.args.get('device_id')
    try:
        photo_id = run_async(async_get_pfp(device_id))
        if photo_id:
            return jsonify({'success': True, 'url': f"https://api.telegram.org/file/..."}) # PFP URL
        return jsonify({'success': False, 'url': None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ----------------- Normal Photo Gallery -----------------

async def async_upload_gallery(device_id, file_path):
    await pyrogram_app.send_photo(CHANNEL_ID, photo=file_path, caption=f"PHOTO|{device_id}")

@app.route('/api/upload', methods=['POST'])
def upload_photo():
    device_id = request.form.get('device_id')
    if 'file' not in request.files or not device_id:
        return jsonify({'success': False}), 400

    file = request.files['file']
    temp_path = f"temp_gal_{file.filename}"
    file.save(temp_path)

    try:
        run_async(async_upload_gallery(device_id, temp_path))
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'success': True})
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'success': False, 'error': str(e)}), 500


async def async_get_gallery(device_id):
    photos = []
    async for msg in pyrogram_app.get_chat_history(CHANNEL_ID, limit=100):
        if msg.caption == f"PHOTO|{device_id}" and msg.photo:
            photos.append({
                'id': msg.id,
                'date': int(msg.date.timestamp())
            })
    return photos

@app.route('/api/gallery', methods=['GET'])
def get_gallery():
    device_id = request.args.get('device_id')
    try:
        photos = run_async(async_get_gallery(device_id))
        return jsonify(photos)
    except Exception as e:
        return jsonify([])

# ----------------- Delete & Notes Endpoints -----------------

async def async_delete_msgs(msg_ids):
    await pyrogram_app.delete_messages(CHANNEL_ID, msg_ids)

@app.route('/api/delete', methods=['POST'])
def delete_photos():
    data = request.json
    msg_ids = data.get('photo_ids', [])
    if msg_ids:
        run_async(async_delete_msgs(msg_ids))
    return jsonify({'success': True})

async def async_get_notes(device_id):
    notes = []
    async for msg in pyrogram_app.get_chat_history(CHANNEL_ID, limit=100):
        if msg.text and msg.text.startswith(f"NOTE|{device_id}|"):
            text = msg.text.split(f"NOTE|{device_id}|")[1]
            notes.append({'id': msg.id, 'text': text})
    return notes

@app.route('/api/notes', methods=['GET'])
def get_notes():
    device_id = request.args.get('device_id')
    try:
        notes = run_async(async_get_notes(device_id))
        return jsonify(notes)
    except Exception as e:
        return jsonify([])

async def async_add_note(device_id, text):
    await pyrogram_app.send_message(CHANNEL_ID, f"NOTE|{device_id}|{text}")

@app.route('/api/notes/add', methods=['POST'])
def add_note():
    data = request.json
    run_async(async_add_note(data['device_id'], data['text']))
    return jsonify({'success': True})

@app.route('/api/notes/delete', methods=['POST'])
def delete_note():
    data = request.json
    run_async(async_delete_msgs([data['note_id']]))
    return jsonify({'success': True})

@app.route('/api/register', methods=['POST'])
@app.route('/api/login', methods=['POST'])
def auth():
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
