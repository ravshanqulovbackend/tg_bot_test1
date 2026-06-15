from pathlib import Path
import os
import random

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.txt"
SCORES_FILE = BASE_DIR / "scores.txt"
IMAGES_DIR = BASE_DIR / "images"
ENV_FILE = BASE_DIR / ".env"


def load_env_file():
    if not ENV_FILE.exists():
        return

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. bot.telegram/.env fayliga BOT_TOKEN yozing.")

USERS_FILE.touch(exist_ok=True)
SCORES_FILE.touch(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)


def read_users():
    users = {}
    for line in USERS_FILE.read_text(encoding="utf-8").splitlines():
        if " - " not in line:
            continue

        user_id, user_name = line.split(" - ", 1)
        if user_id.isdigit():
            users[int(user_id)] = user_name.strip()
    return users


def save_user(user_id, user_name):
    users = read_users()
    users[user_id] = user_name

    with USERS_FILE.open("w", encoding="utf-8") as file:
        for saved_user_id, saved_user_name in users.items():
            file.write(f"{saved_user_id} - {saved_user_name}\n")


def main_menu():
    keyboard = [
        [InlineKeyboardButton("👑 Bot asoschisi", callback_data="founder")],
        [InlineKeyboardButton("📷 Rasm yuborish", callback_data="upload")],
        [InlineKeyboardButton("💬 Xabar yuborish", callback_data="message")],
        [InlineKeyboardButton("🎮 Quiz o'ynash", callback_data="quiz")],
        [InlineKeyboardButton("📝 Profilim", callback_data="profile")],
    ]
    return InlineKeyboardMarkup(keyboard)


def users_keyboard(current_user_id):
    buttons = []
    users = read_users()

    for user_id, user_name in users.items():
        if user_id == current_user_id:
            continue
        buttons.append([InlineKeyboardButton(user_name, callback_data=f"chat_{user_id}")])

    buttons.append([InlineKeyboardButton("⬅️ Menyu", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.full_name)

    context.user_data["waiting_for_name"] = True
    await update.message.reply_text("Salom! Avval ismingizni yozing:")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id, update.effective_user.full_name)

    users = read_users()
    if len(users) <= 1:
        await update.message.reply_text("Hozircha boshqa foydalanuvchilar yo'q.")
        return

    await update.message.reply_text(
        "Kimga xabar yubormoqchisiz?",
        reply_markup=users_keyboard(user_id),
    )


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /reply <user_id> <xabar>")
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID faqat raqam bo'lishi kerak.")
        return

    message = " ".join(context.args[1:]).strip()
    if not message:
        await update.message.reply_text("Xabar matnini ham yozing.")
        return

    await send_user_message(update, context, target_user_id, message)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    save_user(user.id, user.full_name)

    if context.user_data.get("waiting_for_name"):
        context.user_data["name"] = text
        context.user_data["waiting_for_name"] = False

        keyboard = [[KeyboardButton("📱 Telefon raqamini yuborish", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            one_time_keyboard=True,
            resize_keyboard=True,
        )
        await update.message.reply_text(
            f"Salom {text}! Telefon raqamingizni yuboring:",
            reply_markup=reply_markup,
        )
        return

    target_user_id = context.user_data.get("chat_with")
    if target_user_id:
        await send_user_message(update, context, target_user_id, text)
        return

    await update.message.reply_text("Menyu:", reply_markup=main_menu())


async def send_user_message(update, context, target_user_id, message):
    sender = update.effective_user
    save_user(sender.id, sender.full_name)

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"📩 Sizga {sender.full_name} dan xabar:\n\n"
                f"{message}\n\n"
                f"Javob berish uchun /reply {sender.id} <xabar>"
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ Javob yozish", callback_data=f"chat_{sender.id}")]]
            ),
        )
    except TelegramError:
        await update.message.reply_text(
            "Xabar yuborilmadi. U odam avval botga /start bosgan bo'lishi kerak."
        )
        return

    await update.message.reply_text("Xabaringiz yuborildi ✅")


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.effective_user
    save_user(user.id, user.full_name)

    await update.message.reply_text(
        f"Rahmat, {contact.first_name}! Telefon raqamingiz qabul qilindi ✅\nMenyu:",
        reply_markup=main_menu(),
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    save_user(user_id, query.from_user.full_name)

    if query.data == "menu":
        context.user_data.pop("chat_with", None)
        await query.message.reply_text("Menyu:", reply_markup=main_menu())

    elif query.data == "founder":
        image_path = IMAGES_DIR / "image1.jpg"
        if image_path.exists():
            with image_path.open("rb") as photo:
                await query.message.reply_photo(photo=photo, caption="Bot asoschisi: Jonibek 🤖")
        else:
            await query.message.reply_text("Founder rasmi topilmadi.")

    elif query.data == "upload":
        await query.message.reply_text("Rasm yoki fayl yuboring va u avtomatik saqlanadi:")
        context.user_data["waiting_for_photo"] = True

    elif query.data == "message":
        users = read_users()
        if len(users) <= 1:
            await query.message.reply_text("Hozircha boshqa foydalanuvchilar yo'q.")
            return

        await query.message.reply_text(
            "Kimga xabar yubormoqchisiz?",
            reply_markup=users_keyboard(user_id),
        )

    elif query.data.startswith("chat_"):
        target_user_id = int(query.data.removeprefix("chat_"))
        target_name = read_users().get(target_user_id, "foydalanuvchi")

        context.user_data["chat_with"] = target_user_id
        await query.message.reply_text(
            f"{target_name} ga xabar yozing. Tugatish uchun /menu bosing."
        )

    elif query.data == "quiz":
        question, options, correct = random.choice(
            [
                ("Python nima?", ["Til", "Hayvon", "Oziq-ovqat"], "Til"),
                ("2+2=?", ["3", "4", "5"], "4"),
            ]
        )
        context.user_data["quiz_answer"] = correct
        buttons = [[InlineKeyboardButton(opt, callback_data="quiz_" + opt)] for opt in options]
        await query.message.reply_text(question, reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("quiz_"):
        answer = query.data[5:]
        if answer == context.user_data.get("quiz_answer"):
            await query.message.reply_text("To'g'ri javob ✅")
            update_score(user_id, 1)
        else:
            await query.message.reply_text("Noto'g'ri javob ❌")

    elif query.data == "profile":
        name = context.user_data.get("name", query.from_user.full_name)
        score = get_score(user_id)
        await query.message.reply_text(f"👤 Profil:\nIsm: {name}\nBall: {score}")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("chat_with", None)
    await update.message.reply_text("Menyu:", reply_markup=main_menu())


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_photo"):
        return

    photo_file = await update.message.photo[-1].get_file()
    file_path = IMAGES_DIR / f"{update.message.from_user.id}_{photo_file.file_id}.jpg"
    await photo_file.download_to_drive(file_path)
    await update.message.reply_text("Rasm saqlandi ✅")
    context.user_data["waiting_for_photo"] = False


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_path = IMAGES_DIR / f"{update.message.from_user.id}_{update.message.document.file_name}"
    await file.download_to_drive(file_path)
    await update.message.reply_text("Fayl saqlandi ✅")


def update_score(user_id, point):
    scores = {}
    for line in SCORES_FILE.read_text(encoding="utf-8").splitlines():
        if " - " not in line:
            continue
        uid, score = line.strip().split(" - ", 1)
        if uid.isdigit() and score.isdigit():
            scores[int(uid)] = int(score)

    scores[user_id] = scores.get(user_id, 0) + point

    with SCORES_FILE.open("w", encoding="utf-8") as file:
        for uid, score in scores.items():
            file.write(f"{uid} - {score}\n")


def get_score(user_id):
    for line in SCORES_FILE.read_text(encoding="utf-8").splitlines():
        if " - " not in line:
            continue
        uid, score = line.strip().split(" - ", 1)
        if uid.isdigit() and int(uid) == user_id and score.isdigit():
            return int(score)
    return 0


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu_command))
app.add_handler(CommandHandler("users", users_command))
app.add_handler(CommandHandler("reply", reply_command))
app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CallbackQueryHandler(button))

print("Bot ishga tushdi...")
app.run_polling()
