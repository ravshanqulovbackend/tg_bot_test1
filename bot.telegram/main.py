from pathlib import Path
import os
import random
import re

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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


def clean_phone(value):
    return re.sub(r"\D", "", value or "")


def clean_username(value):
    return (value or "").strip().lstrip("@").lower()


def parse_user_line(line):
    if "|" in line:
        parts = (line.split("|") + ["", "", ""])[:4]
        user_id, full_name, username, phone = parts
        if user_id.isdigit():
            return {
                "id": int(user_id),
                "full_name": full_name.strip(),
                "username": clean_username(username),
                "phone": clean_phone(phone),
            }

    if " - " in line:
        user_id, full_name = line.split(" - ", 1)
        if user_id.isdigit():
            return {
                "id": int(user_id),
                "full_name": full_name.strip(),
                "username": "",
                "phone": "",
            }

    return None


def read_users():
    users = {}
    for line in USERS_FILE.read_text(encoding="utf-8").splitlines():
        user = parse_user_line(line.strip())
        if user:
            users[user["id"]] = user
    return users


def write_users(users):
    with USERS_FILE.open("w", encoding="utf-8") as file:
        for user in users.values():
            file.write(
                f"{user['id']}|{user['full_name']}|{user.get('username', '')}|"
                f"{user.get('phone', '')}\n"
            )


def save_user(telegram_user, phone=None, display_name=None):
    users = read_users()
    old_user = users.get(
        telegram_user.id,
        {"id": telegram_user.id, "full_name": "", "username": "", "phone": ""},
    )

    old_user["full_name"] = display_name or telegram_user.full_name or old_user["full_name"]
    old_user["username"] = clean_username(telegram_user.username) or old_user.get("username", "")

    if phone:
        old_user["phone"] = clean_phone(phone)

    users[telegram_user.id] = old_user
    write_users(users)
    return old_user


def user_title(user):
    username = user.get("username")
    phone = user.get("phone")
    if username:
        return f"{user['full_name']} (@{username})"
    if phone:
        return f"{user['full_name']} (+{phone})"
    return user["full_name"]


def find_user(query, current_user_id=None):
    query = query.strip()
    username = clean_username(query)
    phone = clean_phone(query)

    for user in read_users().values():
        if current_user_id and user["id"] == current_user_id:
            continue
        if username and user.get("username") == username:
            return user
        if phone and user.get("phone") == phone:
            return user
    return None


def main_menu():
    keyboard = [
        [InlineKeyboardButton("💬 Xabar yuborish", callback_data="message")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
        [InlineKeyboardButton("👑 Bot asoschisi", callback_data="founder")],
        [InlineKeyboardButton("📷 Rasm saqlash", callback_data="upload")],
        [InlineKeyboardButton("🎮 Quiz o'ynash", callback_data="quiz")],
        [InlineKeyboardButton("📝 Profilim", callback_data="profile")],
    ]
    return InlineKeyboardMarkup(keyboard)


def users_keyboard(current_user_id):
    buttons = []
    for user in read_users().values():
        if user["id"] == current_user_id:
            continue
        buttons.append([InlineKeyboardButton(user_title(user), callback_data=f"chat_{user['id']}")])

    buttons.append([InlineKeyboardButton("⬅️ Menyu", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


def chat_keyboard(sender_id):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ Javob yozish", callback_data=f"chat_{sender_id}")]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    context.user_data["waiting_for_name"] = True

    await update.message.reply_text("Salom! Avval ismingizni yozing:")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("chat_with", None)
    context.user_data.pop("searching_user", None)
    await update.message.reply_text("Menyu:", reply_markup=main_menu())


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)

    if len(read_users()) <= 1:
        await update.message.reply_text("Hozircha boshqa foydalanuvchilar yo'q.")
        return

    await update.message.reply_text(
        "Kimga xabar yubormoqchisiz?",
        reply_markup=users_keyboard(update.effective_user.id),
    )


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)

    if len(context.args) < 2:
        await update.message.reply_text("Format: /reply <user_id> <xabar>")
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID faqat raqam bo'lishi kerak.")
        return

    message = " ".join(context.args[1:]).strip()
    await send_text_message(update, context, target_user_id, message)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    save_user(
        update.effective_user,
        phone=contact.phone_number,
        display_name=update.effective_user.full_name,
    )

    await update.message.reply_text(
        f"Rahmat, {contact.first_name}! Telefon raqamingiz qabul qilindi ✅\nMenyu:",
        reply_markup=main_menu(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    text = update.message.text.strip()

    if context.user_data.get("waiting_for_name"):
        context.user_data["name"] = text
        context.user_data["waiting_for_name"] = False

        keyboard = [[KeyboardButton("📱 Telefon raqamini yuborish", request_contact=True)]]
        await update.message.reply_text(
            f"Salom {text}! Telefon raqamingizni yuboring:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return

    if context.user_data.get("searching_user"):
        target = find_user(text, current_user_id=update.effective_user.id)
        if not target:
            await update.message.reply_text(
                "Bunday foydalanuvchi topilmadi. U avval botga /start bosgan va "
                "username yoki telefonini botga bergan bo'lishi kerak."
            )
            return

        context.user_data["searching_user"] = False
        context.user_data["chat_with"] = target["id"]
        await update.message.reply_text(
            f"{user_title(target)} topildi. Endi yubormoqchi bo'lgan xabaringizni, "
            "rasm/video/faylingizni yuboring. Tugatish uchun /menu bosing.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    target_user_id = context.user_data.get("chat_with")
    if target_user_id:
        await send_text_message(update, context, target_user_id, text)
        return

    await update.message.reply_text("Menyu:", reply_markup=main_menu())


async def send_text_message(update, context, target_user_id, message):
    sender = save_user(update.effective_user)
    if not message:
        await update.message.reply_text("Xabar matnini yozing.")
        return

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"📩 Sizga {user_title(sender)} dan xabar keldi:\n\n"
                f"{message}\n\n"
                f"Javob berish: /reply {sender['id']} <xabar>"
            ),
            reply_markup=chat_keyboard(sender["id"]),
        )
    except TelegramError:
        await update.message.reply_text(
            "Xabar yuborilmadi. U odam avval botga /start bosgan bo'lishi kerak."
        )
        return

    await update.message.reply_text("Xabaringiz yuborildi ✅")


async def send_copied_message(update, context, target_user_id):
    sender = save_user(update.effective_user)

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📩 Sizga {user_title(sender)} dan xabar keldi:",
            reply_markup=chat_keyboard(sender["id"]),
        )
        await context.bot.copy_message(
            chat_id=target_user_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
        )
    except TelegramError:
        await update.effective_message.reply_text(
            "Xabar yuborilmadi. U odam avval botga /start bosgan bo'lishi kerak."
        )
        return

    await update.effective_message.reply_text("Xabaringiz yuborildi ✅")


async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)

    target_user_id = context.user_data.get("chat_with")
    if target_user_id:
        await send_copied_message(update, context, target_user_id)
        return

    await update.effective_message.reply_text(
        "Avval kimga yuborishni tanlang.",
        reply_markup=main_menu(),
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    save_user(query.from_user)

    if query.data == "menu":
        context.user_data.pop("chat_with", None)
        context.user_data.pop("searching_user", None)
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
        context.user_data["searching_user"] = True
        context.user_data.pop("chat_with", None)
        await query.message.reply_text(
            "Qabul qiluvchi username yoki telefon raqamini yozing.\n"
            "Masalan: @username yoki +998901234567"
        )

    elif query.data == "users":
        if len(read_users()) <= 1:
            await query.message.reply_text("Hozircha boshqa foydalanuvchilar yo'q.")
            return

        await query.message.reply_text(
            "Kimga xabar yubormoqchisiz?",
            reply_markup=users_keyboard(query.from_user.id),
        )

    elif query.data.startswith("chat_"):
        target_user_id = int(query.data.removeprefix("chat_"))
        target = read_users().get(target_user_id)

        context.user_data["chat_with"] = target_user_id
        context.user_data["searching_user"] = False
        await query.message.reply_text(
            f"{user_title(target) if target else 'foydalanuvchi'} ga xabar yozing. "
            "Text, rasm, video yoki fayl yuborishingiz mumkin. Tugatish uchun /menu bosing."
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
            update_score(query.from_user.id, 1)
        else:
            await query.message.reply_text("Noto'g'ri javob ❌")

    elif query.data == "profile":
        user = read_users().get(query.from_user.id, save_user(query.from_user))
        score = get_score(query.from_user.id)
        await query.message.reply_text(
            f"👤 Profil:\n"
            f"Ism: {user['full_name']}\n"
            f"Username: @{user['username'] or 'yoq'}\n"
            f"Telefon: +{user['phone'] or 'yoq'}\n"
            f"Ball: {score}"
        )


async def handle_photo_for_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_photo"):
        await handle_media_message(update, context)
        return

    photo_file = await update.message.photo[-1].get_file()
    file_path = IMAGES_DIR / f"{update.message.from_user.id}_{photo_file.file_id}.jpg"
    await photo_file.download_to_drive(file_path)
    await update.message.reply_text("Rasm saqlandi ✅")
    context.user_data["waiting_for_photo"] = False


async def handle_document_for_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_photo"):
        await handle_media_message(update, context)
        return

    file = await update.message.document.get_file()
    file_path = IMAGES_DIR / f"{update.message.from_user.id}_{update.message.document.file_name}"
    await file.download_to_drive(file_path)
    await update.message.reply_text("Fayl saqlandi ✅")
    context.user_data["waiting_for_photo"] = False


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
app.add_handler(MessageHandler(filters.PHOTO, handle_photo_for_storage))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document_for_storage))
app.add_handler(
    MessageHandler(
        filters.VIDEO | filters.AUDIO | filters.VOICE | filters.VIDEO_NOTE | filters.Sticker.ALL,
        handle_media_message,
    )
)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CallbackQueryHandler(button))

print("Bot ishga tushdi...")
app.run_polling()
