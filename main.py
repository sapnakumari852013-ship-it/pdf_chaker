import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHANNEL_ID = "@your_channel_username"  # या चैनल की ID जैसे -100123456789

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ----------------- Helper Functions -----------------

def get_channel_updates():
    """चैनल के हालिया मैसेज पढ़ता है (डेटाबेस का विकल्प)"""
    url = f"{TELEGRAM_API}/getUpdates"
    res = requests.get(url).json()
    return res.get("result", [])

def delete_telegram_msg(message_id):
    """पुराना मैसेज या फोटो चैनल से डिलीट करता है"""
    try:
        requests.post(f"{TELEGRAM_API}/deleteMessage", data={'chat_id': CHANNEL_ID, 'message_id': message_id})
    except Exception as e:
        print("Delete error:", e)

# ----------------- API Endpoints -----------------

# 1. Normal Photo Upload
@app.route('/api/upload', methods=['POST'])
def upload_photo():
    device_id = request.form.get('device_id')
    file = request.files.get('file')

    if not device_id or not file:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    url = f"{TELEGRAM_API}/sendPhoto"
    files = {'photo': file}
    data = {'chat_id': CHANNEL_ID, 'caption': f"PHOTO|{device_id}"}
    
    res = requests.post(url, files=files, data=data).json()
    return jsonify({'success': res.get("ok", False)})

# 2. PFP Upload (पुराना डिलीट करके नया अपलोड)
@app.route('/api/upload-pfp', methods=['POST'])
def upload_pfp():
    device_id = request.form.get('device_id')
    file = request.files.get('file')

    if not device_id or not file:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    # पुराने PFP मैसेज ढूंढकर डिलीट करना
    updates = get_channel_updates()
    for item in updates:
        msg = item.get("channel_post") or item.get("message")
        if msg and "caption" in msg:
            if msg["caption"] == f"PFP|{device_id}":
                delete_telegram_msg(msg["message_id"])

    # नया PFP अपलोड करना
    url = f"{TELEGRAM_API}/sendPhoto"
    files = {'photo': file}
    data = {'chat_id': CHANNEL_ID, 'caption': f"PFP|{device_id}"}
    
    res = requests.post(url, files=files, data=data).json()
    if res.get("ok"):
        file_id = res["result"]["photo"][-1]["file_id"]
        file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={file_id}").json()
        file_path = file_info["result"]["file_path"]
        img_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        return jsonify({'success': True, 'url': img_url})

    return jsonify({'success': False}), 500

# 3. Get Profile Photo
@app.route('/api/get-pfp', methods=['GET'])
def get_pfp():
    device_id = request.args.get('device_id')
    updates = get_channel_updates()
    
    # लेटेस्ट PFP खोजना
    for item in reversed(updates):
        msg = item.get("channel_post") or item.get("message")
        if msg and msg.get("caption") == f"PFP|{device_id}" and "photo" in msg:
            file_id = msg["photo"][-1]["file_id"]
            file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            img_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            return jsonify({'success': True, 'url': img_url})

    return jsonify({'success': False, 'url': None})

# 4. Get Gallery (PFP को छोड़कर केवल PHOTO टैग वाली इमेजेस)
@app.route('/api/gallery', methods=['GET'])
def get_gallery():
    device_id = request.args.get('device_id')
    updates = get_channel_updates()
    photos = []

    for item in reversed(updates):
        msg = item.get("channel_post") or item.get("message")
        if msg and msg.get("caption") == f"PHOTO|{device_id}" and "photo" in msg:
            file_id = msg["photo"][-1]["file_id"]
            file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            img_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            photos.append({
                'id': msg["message_id"],
                'url': img_url,
                'date': msg.get("date")
            })

    return jsonify(photos)

# 5. Delete Gallery Photo
@app.route('/api/delete', methods=['POST'])
def delete_photos():
    data = request.json
    for msg_id in data.get('photo_ids', []):
        delete_telegram_msg(msg_id)
    return jsonify({'success': True})

# ----------------- Notes Endpoints (Telegram Message Based) -----------------

@app.route('/api/notes', methods=['GET'])
def get_notes():
    device_id = request.args.get('device_id')
    updates = get_channel_updates()
    notes = []

    for item in reversed(updates):
        msg = item.get("channel_post") or item.get("message")
        if msg and "text" in msg and msg["text"].startswith(f"NOTE|{device_id}|"):
            text = msg["text"].split(f"NOTE|{device_id}|")[1]
            notes.append({'id': msg["message_id"], 'text': text})

    return jsonify(notes)

@app.route('/api/notes/add', methods=['POST'])
def add_note():
    data = request.json
    text_msg = f"NOTE|{data['device_id']}|{data['text']}"
    requests.post(f"{TELEGRAM_API}/sendMessage", data={'chat_id': CHANNEL_ID, 'text': text_msg})
    return jsonify({'success': True})

@app.route('/api/notes/delete', methods=['POST'])
def delete_note():
    data = request.json
    delete_telegram_msg(data['note_id'])
    return jsonify({'success': True})

@app.route('/api/register', methods=['POST'])
@app.route('/api/login', methods=['POST'])
def auth():
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
