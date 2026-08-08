import os
import logging
import threading
import requests
import pdfplumber
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# -------------------------------------------------------------
# FLASK WEB SERVER (Render Port Binding ke liye)
# -------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is Active and Running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🌐 Starting Flask Web Server on Port {port}...")
    flask_app.run(host="0.0.0.0", port=port)

# -------------------------------------------------------------
# PDF PROCESSING FUNCTIONS
# -------------------------------------------------------------
def download_file(url, output_path):
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    f.write(chunk)
            return True
    except Exception as e:
        logging.error(f"Download Error: {e}")
    return False

def analyze_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:3]:
                extracted = page.extract_text()
                if extracted:
                    text += " " + extracted.lower()
    except Exception as e:
        logging.error(f"PDF Reading Error: {e}")
        return "@notes"

    dpp_keywords = ["q1.", "q2.", "question", "option", "(a)", "(b)", "(c)", "(d)", "dpp", "practice paper", "exercise", "solution"]
    notes_keywords = ["chapter", "introduction", "definition", "formula", "theory", "summary", "explanation", "concept"]

    dpp_score = sum(1 for word in dpp_keywords if word in text)
    notes_score = sum(1 for word in notes_keywords if word in text)

    return "@dpp" if dpp_score > notes_score else "@notes"

# -------------------------------------------------------------
# TELEGRAM BOT HANDLER
# -------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    pdf_path = f"temp_{msg.message_id}.pdf"
    status_msg = await msg.reply_text("⏳ PDF का विश्लेषण (Analyze) किया जा रहा है...")

    try:
        # 1. Agar Direct PDF Document aaya hai
        if msg.document:
            file = await context.bot.get_file(msg.document.file_id)
            await file.download_to_drive(pdf_path)
            
        # 2. Agar PDF ka Direct Link aaya hai
        elif msg.text and (msg.text.startswith("http://") or msg.text.startswith("https://")):
            pdf_url = msg.text.strip()
            if not download_file(pdf_url, pdf_path):
                await status_msg.edit_text("❌ PDF डाउनलोड करने में समस्या आई।")
                return
        else:
            await status_msg.edit_text("⚠️ कृपया एक PDF फ़ाइल या सही PDF लिंक भेजें।")
            return

        result_tag = analyze_pdf(pdf_path)
        await status_msg.edit_text(f"🎯 यह फ़ाइल **{result_tag}** है!", parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Error handling message: {e}")
        await status_msg.edit_text("❌ फ़ाइल प्रोसेस करने में समस्या आई।")

    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            logging.info(f"🧹 Temporary file {pdf_path} deleted.")

# -------------------------------------------------------------
# MAIN STARTUP
# -------------------------------------------------------------
if __name__ == "__main__":
    if not BOT_TOKEN:
        logging.error("❌ BOT_TOKEN missing!")
        exit(1)

    # 1. Start Web Server in Background Thread
    threading.Thread(target=run_flask, daemon=True).start()

    # 2. Start Telegram Bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Correct Syntax for v20+ filters
    app.add_handler(MessageHandler(filters.Document.ALL | filters.TEXT, handle_message))

    logging.info("🚀 Starting Telegram Bot Polling...")
    app.run_polling(drop_pending_updates=True)
