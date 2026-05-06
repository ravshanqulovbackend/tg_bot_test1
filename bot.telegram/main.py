from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

import os
import random

TOKEN = "8607677602:AAFVMc1Bw2iT7aw3RsOA3TaGJtvUAW-O2ko"
ADMIN_ID = 930999333

# Fayl va papkalarni tekshirish
if not os.path.exists("users.txt"):
    open("users.txt", "w", encoding="utf-8").close()
if not os.path.exists("images"):
    os.makedirs("images")
if not os.path.exists("scores.txt"):
    
    open("scores.txt", "w", encoding="utf-8").close()

messages_dict = {}  # Maxfiy chat xabarlari

# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.full_name

    # Foydalanuvchini ro‘yxatga olish
    with open("users.txt", "r", encoding="utf-8") as f:
        users = [line.split(" - ")[0] for line in f.readlines()]
    if str(user_id) not in users:
        with open("users.txt", "a", encoding="utf-8") as f:
            f.write(f"{user_id} - {user_name}\n")

    context.user_data["waiting_for_name"] = True
    await update.message.reply_text("Salom! Avval ismingizni yozing:")

# ===== Ism qabul qilish =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    # Ism qabul qilish
    if context.user_data.get("waiting_for_name", False):
        context.user_data["name"] = text
        context.user_data["waiting_for_name"] = False

        # Telefon raqam tugmasi
        keyboard = [[KeyboardButton("📱 Telefon raqamini yuborish", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"Salom {text}! Telefon raqamingizni yuboring:", reply_markup=reply_markup)

    # Maxfiy chat
    elif context.user_data.get("secret_chat", False):
        messages_dict[user_id] = messages_dict.get(user_id, [])
        messages_dict[user_id].append(text)

        # Adminga yuborish
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"{update.message.from_user.full_name} ({user_id}): {text}")
        await update.message.reply_text("Xabaringiz yuborildi ✅")

# ===== Kontakt qabul qilish =====
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    with open("users.txt", "a", encoding="utf-8") as f:
        f.write(f"{contact.first_name} - {contact.phone_number}\n")

    # Menyu
    keyboard = [
        [InlineKeyboardButton("👑 Bot asoschisi", callback_data='founder')],
        [InlineKeyboardButton("📷 Rasm yuborish", callback_data='upload')],
        [InlineKeyboardButton("💬 Maxfiy chat", callback_data='secret')],
        [InlineKeyboardButton("🎮 Quiz o'ynash", callback_data='quiz')],
        [InlineKeyboardButton("📝 Profilim", callback_data='profile')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Rahmat, {contact.first_name}! Telefon raqamingiz qabul qilindi ✅\nMenyu:", reply_markup=reply_markup)

# ===== Inline tugmalar =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "founder":
        with open("images/image1.jpg", "rb") as photo:
            await query.message.reply_photo(photo=photo, caption="Bot asoschisi: Jonibek 🤖")

    elif query.data == "upload":
        await query.message.reply_text("Rasm yoki fayl yuboring va u avtomatik saqlanadi:")
        context.user_data["waiting_for_photo"] = True

    elif query.data == "secret":
        await query.message.reply_text("Maxfiy chat boshladingiz. Xabar yozing:")
        context.user_data["secret_chat"] = True

    elif query.data == "quiz":
        question, options, correct = random.choice([
            ("Python nima?", ["Til", "Hayvon", "Oziq-ovqat"], "Til"),
            ("2+2=?", ["3", "4", "5"], "4")
        ])
        context.user_data["quiz_answer"] = correct
        buttons = [[InlineKeyboardButton(opt, callback_data="quiz_"+opt)] for opt in options]
        await query.message.reply_text(question, reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("quiz_"):
        answer = query.data[5:]
        if answer == context.user_data.get("quiz_answer"):
            await query.message.reply_text("To'g'ri javob ✅")
            _update_score(user_id, 1)
        else:
            await query.message.reply_text("Noto'g'ri javob ❌")

    elif query.data == "profile":
        name = context.user_data.get("name", "NoName")
        score = _get_score(user_id)
        await query.message.reply_text(f"👤 Profil:\nIsm: {name}\nBall: {score}")

# ===== Rasm yoki fayl qabul qilish =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for_photo", False):
        photo_file = await update.message.photo[-1].get_file()
        file_path = f"images/{update.message.from_user.id}_{photo_file.file_id}.jpg"
        await photo_file.download_to_drive(file_path)
        await update.message.reply_text("Rasm saqlandi ✅")
        context.user_data["waiting_for_photo"] = False

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_path = f"images/{update.message.from_user.id}_{update.message.document.file_name}"
    await file.download_to_drive(file_path)
    await update.message.reply_text("Fayl saqlandi ✅")

# ===== Admin javoblari =====
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    text = update.message.text
    if not text.lower().startswith("/reply "):
        return
    try:
        _, user_id_str, message = text.split(" ", 2)
        user_id = int(user_id_str)
        await context.bot.send_message(chat_id=user_id, text=message)
        await update.message.reply_text(f"Xabar foydalanuvchiga yuborildi ✅")
    except:
        await update.message.reply_text("Xatolik! Format: /reply <user_id> <xabar>")

# ===== Ball tizimi =====
def _update_score(user_id, point):
    scores = {}
    with open("scores.txt", "r", encoding="utf-8") as f:
        for line in f.readlines():
            uid, sc = line.strip().split(" - ")
            scores[int(uid)] = int(sc)
    scores[user_id] = scores.get(user_id, 0) + point
    with open("scores.txt", "w", encoding="utf-8") as f:
        for uid, sc in scores.items():
            f.write(f"{uid} - {sc}\n")

def _get_score(user_id):
    scores = {}
    with open("scores.txt", "r", encoding="utf-8") as f:
        for line in f.readlines():
            uid, sc = line.strip().split(" - ")
            scores[int(uid)] = int(sc)
    return scores.get(user_id, 0)

# ===== Bot ishga tushirish =====
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply))

print("Bot ishga tushdi...")
app.run_polling()
