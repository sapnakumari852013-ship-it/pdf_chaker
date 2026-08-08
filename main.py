import os
import re
import logging
import requests
import pdfplumber
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")

def download_file(url, output_path):
    """PDF डाउनलोड फ़ंक्शन"""
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
    """PDF का टेक्स्ट पढ़कर पहचानना"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:3]: # शुरुआती 3 पेज
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    pdf_path = f"temp_{msg.message_id}.pdf"
    
    status_msg = await msg.reply_text("⏳ PDF का विश्लेषण (Analyze) किया जा रहा है...")

    try:
        # 1. अगर यूज़र ने PDF Document डायरेक्ट भेजा है
        if msg.document and msg.document.mime_type == 'application/pdf':
            file = await context.bot.get_file(msg.document.file_id)
            await file.download_to_drive(pdf_path)
            
        # 2. अगर यूज़र ने PDF का लिंक (Text Message) भेजा है
        elif msg.text and (msg.text.startswith("http://") or msg.text.startswith("https://")):
            pdf_url = msg.text.strip()
            if not download_file(pdf_url, pdf_path):
                await status_msg.edit_text("❌ PDF डाउनलोड करने में समस्या आई।")
                return
        else:
            await status_msg.edit_text("⚠️ कृपया एक PDF फ़ाइल या सही PDF लिंक भेजें।")
            return

        # 3. Analyze PDF
        result_tag = analyze_pdf(pdf_path)

        # 4. Telegram पर सीधा Reply देना
        await status_msg.edit_text(f"🎯 यह फ़ाइल **{result_tag}** है!", parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Error handling message: {e}")
        await status_msg.edit_text("❌ फ़ाइल प्रोसेस करने में कोई गड़बड़ हुई।")

    finally:
        # 5. Auto Delete PDF File
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            logging.info(f"🧹 Temporary file {pdf_path} deleted.")

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN missing in Environment Variables!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # PDF Document या Links को हैंडल करने के लिए
    app.add_handler(MessageHandler(filters.DOCUMENT.MIME('application/pdf') | filters.TEXT, handle_message))

    print("🤖 Telegram Bot Started!")
    app.run_polling()
