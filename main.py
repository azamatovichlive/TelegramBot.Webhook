import os
from telegram import Update, ReplyKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, InlineQueryHandler, ContextTypes, filters
from translator import is_kiril, kiril_to_lotin, lotin_to_kiril
from utils import add_user_stat, load_stats
from dotenv import load_dotenv
from uuid import uuid4
from docx import Document
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas
from openai import OpenAI

# 🔐 .env dan ma’lumotlarni olish
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# 🧠 OpenAI client
client = OpenAI(api_key=OPENAI_KEY)

# 📱 Asosiy menyu
menu = ReplyKeyboardMarkup([
    ["🔤 Matn tarjima", "📄 Fayl tarjima"],
    ["🤖 AI tarjima", "📊 Statistikalar"],
    ["ℹ️ Yordam"]
], resize_keyboard=True)

# 🔒 Limitlarni saqlash
user_limits = {}

def check_limit(user_id, key, max_count):
    """Foydalanuvchi uchun kunlik limitni tekshirish"""
    if user_id not in user_limits:
        user_limits[user_id] = {"texts": 0, "files": 0, "ai": 0}
    if user_limits[user_id][key] >= max_count:
        return False
    user_limits[user_id][key] += 1
    return True

# 💬 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "👋 Assalomu alaykum!\nMen Kiril ↔ Lotin tarjima botiman.\nQuyidagilardan birini tanlang:",
            reply_markup=menu
        )
    except Exception as e:
        print(f"[Xato] start: {e}")

# ℹ️ /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ <b>Yordam:</b>\n\n"
        "🔤 Matn tarjima — matn yuboring.\n"
        "📄 Fayl tarjima — .docx, .pdf yoki .txt fayl yuboring.\n"
        "🤖 AI tarjima — /ai yoki menyu orqali AI bilan tarjima.\n"
        "📊 Statistikalar — foydalanish soni.\n\n"
        "📢 Kanal: @AsadbekAzamatovich",
        parse_mode="HTML"
    )

# 📊 Statistika
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    stats = user_limits.get(user_id, {"texts": 0, "files": 0, "ai": 0})
    await update.message.reply_text(
        f"📊 Foydalanish statistikasi:\n\n"
        f"🔤 Matn: {stats['texts']}/5\n"
        f"📄 Fayl: {stats['files']}/2\n"
        f"🤖 AI: {stats['ai']}/2"
    )

# 🔘 Tugmalarni boshqarish
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔤 Matn tarjima":
        await update.message.reply_text("✍️ Oddiy matn yuboring, men tarjima qilaman.")
    elif text == "📄 Fayl tarjima":
        await update.message.reply_text("📎 Word (.docx), PDF yoki TXT fayl yuboring.")
    elif text == "🤖 AI tarjima":
        await update.message.reply_text("🧠 AI rejim yoqildi. Matn yuboring (kuniga 2 marta).")
        context.user_data["ai_mode"] = True
    elif text == "📊 Statistikalar":
        await stats(update, context)
    elif text == "ℹ️ Yordam":
        await help_command(update, context)

# 🧠 Matn tarjimasi (AI + oddiy)
async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        text = update.message.text

        # AI rejimi yoqilgan bo‘lsa
        if context.user_data.get("ai_mode"):
            if not check_limit(user_id, "ai", 2):
                await update.message.reply_text("❌ AI limit tugagan (kuniga 2 marta).")
                return

            await update.message.reply_text("⏳ AI tarjima jarayoni...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Siz o‘zbek tilidagi matnlarni lotin ↔ kiril yozuviga tarjima qiluvchi yordamchisiz."},
                    {"role": "user", "content": f"Tarjima qil: {text}"}
                ]
            )

            translated = response.choices[0].message.content
            await update.message.reply_text(f"🤖 AI tarjima:\n\n{translated}")
            context.user_data["ai_mode"] = False
            return

        # Oddiy tarjima (limit bilan)
        if not check_limit(user_id, "texts", 5):
            await update.message.reply_text("⚠️ Bugun uchun matn tarjima limiti tugagan (5/5).")
            return

        translated = kiril_to_lotin(text) if is_kiril(text) else lotin_to_kiril(text)
        await update.message.reply_text(translated)

    except Exception as e:
        print(f"[Xato] translate_text: {e}")

# 📄 Fayl tarjimasi
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        if not check_limit(user_id, "files", 2):
            await update.message.reply_text("❌ Kunlik fayl limit tugagan (2/2).")
            return

        file = await update.message.document.get_file()
        filename = update.message.document.file_name
        ext = filename.split('.')[-1].lower()
        local_path = f"temp_input.{ext}"
        await file.download_to_drive(local_path)

        text = ""
        if ext == "txt":
            text = open(local_path, 'r', encoding='utf-8', errors='ignore').read()
        elif ext == "docx":
            doc = Document(local_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif ext == "pdf":
            reader = PdfReader(local_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        else:
            await update.message.reply_text("❌ Faqat .txt, .docx yoki .pdf fayl yuboring.")
            return

        translated = kiril_to_lotin(text) if is_kiril(text) else lotin_to_kiril(text)
        out_path = f"translated_{filename.split('.')[0]}.txt"
        open(out_path, "w", encoding="utf-8").write(translated)

        await update.message.reply_document(open(out_path, "rb"))
        os.remove(local_path)
        os.remove(out_path)
    except Exception as e:
        print(f"[Xato] handle_file: {e}")

# 🚀 Ishga tushurish
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Regex("^(🔤 Matn tarjima|📄 Fayl tarjima|🤖 AI tarjima|📊 Statistikalar|ℹ️ Yordam)$"), menu_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_text))

    print("✅ Bot ishga tushdi (AI + Limit versiyasi)...")
    app.run_polling()
