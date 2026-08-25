import os
import sqlite3
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Cross-Origin Requests allow करने के लिए

# --- आपकी Telegram Bot की डिटेल्स यहाँ डालें ---
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# ----------------- Database Setup -----------------
DB_NAME = "cloud_hub.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Normal Photos Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            url TEXT,
            message_id INTEGER,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Profile Photos Table (PFP के लिए अलग टेबल)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pfp_store (
            device_id TEXT PRIMARY KEY,
            url TEXT,
            message_id INTEGER
        )
    ''')

    # Notes Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            text TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ----------------- Helper Functions -----------------
def send_photo_to_telegram(file_obj, caption):
    """Telegram पर फोटो अपलोड करके उसका direct URL और message_id देता है"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {'photo': file_obj}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
    
    res = requests.post(url, files=files, data=data).json()
    
    if res.get("ok"):
        message_id = res["result"]["message_id"]
        file_id = res["result"]["photo"][-1]["file_id"]
        
        # Get Direct File Path
        file_path_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        file_res = requests.get(file_path_url).json()
        
        if file_res.get("ok"):
            file_path = file_res["result"]["file_path"]
            img_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            return img_url, message_id
            
    return None, None

def delete_telegram_message(message_id):
    """Telegram से पुराना मैसेज/फोटो डिलीट करता है"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'message_id': message_id})
    except Exception as e:
        print(f"Error deleting message: {e}")

# ----------------- API Endpoints -----------------

# 1. Upload Normal Photo (गैलरी के लिए)
@app.route('/api/upload', methods=['POST'])
def upload_photo():
    device_id = request.form.get('device_id')
    file = request.files.get('file')

    if not device_id or not file:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    img_url, msg_id = send_photo_to_telegram(file, f"PHOTO|{device_id}")

    if img_url:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO photos (device_id, url, message_id) VALUES (?, ?, ?)", 
                       (device_id, img_url, msg_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'url': img_url})
    
    return jsonify({'success': False, 'error': 'Upload failed'}), 500

# 2. Upload Profile Photo (PFP के लिए अलग API)
@app.route('/api/upload-pfp', methods=['POST'])
def upload_pfp():
    device_id = request.form.get('device_id')
    file = request.files.get('file')

    if not device_id or not file:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # चेक करें कि क्या पुरानी PFP मौजूद है
    cursor.execute("SELECT message_id FROM pfp_store WHERE device_id = ?", (device_id,))
    old_pfp = cursor.fetchone()

    # अगर पुरानी फोटो है, तो उसे टेलीग्राम से डिलीट करें
    if old_pfp and old_pfp[0]:
        delete_telegram_message(old_pfp[0])

    # नई प्रोफाइल फोटो टेलीग्राम पर भेजें
    img_url, msg_id = send_photo_to_telegram(file, f"PFP|{device_id}")

    if img_url:
        # DB में पुरानी PFP ओवरराइट / नई इंसर्ट करें
        cursor.execute("""
            INSERT INTO pfp_store (device_id, url, message_id) 
            VALUES (?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET url=excluded.url, message_id=excluded.message_id
        """, (device_id, img_url, msg_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'url': img_url})

    conn.close()
    return jsonify({'success': False, 'error': 'PFP Upload failed'}), 500

# 3. Get Profile Photo
@app.route('/api/get-pfp', methods=['GET'])
def get_pfp():
    device_id = request.args.get('device_id')
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM pfp_store WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({'success': True, 'url': row[0]})
    return jsonify({'success': False, 'url': None})

# 4. Get Gallery Photos (इसमें सिर्फ गैलरी की फोटो आएंगी, PFP नहीं)
@app.route('/api/gallery', methods=['GET'])
def get_gallery():
    device_id = request.args.get('device_id')
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, date FROM photos WHERE device_id = ? ORDER BY id DESC", (device_id,))
    rows = cursor.fetchall()
    conn.close()

    photos = [{'id': r[0], 'url': r[1], 'date': r[2]} for r in rows]
    return jsonify(photos)

# 5. Delete Photos from Gallery
@app.route('/api/delete', methods=['POST'])
def delete_photos():
    data = request.json
    photo_ids = data.get('photo_ids', [])

    if not photo_ids:
        return jsonify({'success': False}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    for pid in photo_ids:
        cursor.execute("SELECT message_id FROM photos WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if row and row[0]:
            delete_telegram_message(row[0])
        cursor.execute("DELETE FROM photos WHERE id = ?", (pid,))

    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ----------------- Notes Endpoints -----------------

@app.route('/api/notes', methods=['GET'])
def get_notes():
    device_id = request.args.get('device_id')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, text FROM notes WHERE device_id = ? ORDER BY id DESC", (device_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{'id': r[0], 'text': r[1]} for r in rows])

@app.route('/api/notes/add', methods=['POST'])
def add_note():
    data = request.json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notes (device_id, text) VALUES (?, ?)", (data['device_id'], data['text']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/notes/edit', methods=['POST'])
def edit_note():
    data = request.json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE notes SET text = ? WHERE id = ? AND device_id = ?", 
                   (data['text'], data['note_id'], data['device_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/notes/delete', methods=['POST'])
def delete_note():
    data = request.json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ?", (data['note_id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ----------------- Auth Mock -----------------
@app.route('/api/register', methods=['POST'])
@app.route('/api/login', methods=['POST'])
def auth():
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
