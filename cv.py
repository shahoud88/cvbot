# cv.py - مع دعم Google Drive للصورة + خدمة مدفوعة مباشرة

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from PyPDF2 import PdfReader
from docx import Document
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME")
MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "@sameer_shahoud")
QR_CODE_URL = os.getenv("QR_CODE_URL")

if not all([TELEGRAM_TOKEN, HF_TOKEN, MODEL_NAME, QR_CODE_URL]):
    raise ValueError("تأكد من وجود جميع المتغيرات في ملف .env!")

from huggingface_hub import InferenceClient
client = InferenceClient(token=HF_TOKEN)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📄 تحليل سيرة موجودة", callback_data="analyze")],
        [InlineKeyboardButton("✍️ إنشاء سيرة ذاتية جديدة", callback_data="create_new")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "مرحبًا بك! 🌟\n"
        "• إذا كنت تملك سيرة ذاتية → اختر 'تحليل سيرة موجودة' للحصول على تحليل مجاني.\n"
        "• إذا كنت تريد سيرة احترافية من الصفر → اختر 'إنشاء سيرة ذاتية جديدة'.",
        reply_markup=reply_markup
    )

async def analyze_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("✅ أرسل سيرتك الذاتية (PDF أو DOCX) للتحليل.")

async def create_new_cv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_payment_info(query.message)

def extract_text_from_pdf(path):
    text = ""
    for page in PdfReader(path).pages:
        t = page.extract_text()
        if t: text += t + "\n"
    return text

def extract_text_from_docx(path):
    return "\n".join(para.text for para in Document(path).paragraphs if para.text.strip())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    name = doc.file_name
    await update.message.reply_text(f"✅ جاري تحليل {name}...")

    tmp_dir = "/data/data/com.termux/files/home/bots/cvbot/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    fp = os.path.join(tmp_dir, name)
    await (await doc.get_file()).download_to_drive(fp)

    try:
        if name.lower().endswith(".pdf"):
            text = extract_text_from_pdf(fp)
        elif name.lower().endswith(".docx"):
            text = extract_text_from_docx(fp)
        else:
            await update.message.reply_text("❌ يُرجى إرسال PDF أو DOCX فقط.")
            return

        if not text.strip():
            await update.message.reply_text("❌ الملف فارغ أو غير قابل للقراءة.")
            return

        prompt = f"""أنت خبير موارد بشرية في السوق العربي. حلّل السيرة الذاتية التالية:

{text}

قدّم:
- نقاط القوة
- نقاط الضعف
- توصيات عملية
- ملاحظة ختامية احترافية

اكتب بالعربية الفصحى."""

        response = client.chat_completion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.7
        )
        analysis = response.choices[0].message.content
        await update.message.reply_text(f"✅ تحليل السيرة:\n\n{analysis[:4000]}")

        keyboard = [[InlineKeyboardButton("طلب الحصول على CV احترافي", callback_data="premium_cv")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "هل ترغب بسيرة ذاتية احترافية جاهزة؟\n"
            "تصمم من قبل اختصاصي موارد بشرية\n"
            "اضغط على الزر أدناه",
            reply_markup=reply_markup
        )

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        if os.path.exists(fp):
            os.remove(fp)

async def send_payment_info(message):
    await message.reply_photo(
        photo=QR_CODE_URL,
        caption=(
            "💳 **طريقة الدفع**:\n"
            "1. ادفع 25,000 ل.س عبر شام كاش باستخدام رمز QR أعلاه.\n"
            "2. أرسل لي **رقم العملية** أو لقطة شاشة للتأكيد مع اسمك الثلاثي.\n\n"
            "📞 أو تواصل مباشرة مع المدير:\n"
            "**تلغرام**: @sameer_shahoud\n\n"
            "ستحصل على سيرتك خلال 24 ساعة بعد تأكيد الدفع و تزويدنا بالمعلومات التي سيتم طلبها! 🚀"
        )
    )

async def premium_cv_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_payment_info(query.message)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(analyze_choice, pattern="^analyze$"))
    app.add_handler(CallbackQueryHandler(create_new_cv, pattern="^create_new$"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(premium_cv_handler, pattern="^premium_cv$"))

    print("✅ البوت يعمل مع صورة QR من Google Drive!")
    app.run_polling()

if __name__ == "__main__":
    main()
