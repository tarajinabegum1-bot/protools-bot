import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ===== CONFIG =====
BOT_TOKEN = "8851108752:AAERyC1zOg1v-kH7IZcBodmI5hgUTut9p2s"
ADMIN_ID = 8157078800

# ===== STATES =====
PHOTO = 1
SELECT_PLAN = 2
WAIT_KEY = 3

# ===== STORAGE =====
pending_payments = {}

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== KEEP ALIVE =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()

# ===== PLANS =====
PLANS = {
    "7d": {"name": "7 Days", "bdt": "1200", "usdt": "11"},
    "15d": {"name": "15 Days", "bdt": "2200", "usdt": "20"},
    "30d": {"name": "30 Days", "bdt": "3300", "usdt": "30"},
    "lifetime": {"name": "Lifetime", "bdt": "5500", "usdt": "50"},
}

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Welcome to PRO TOOLS HUB!\n\n"
        "Send your payment screenshot to get Premium Access.\n\n"
        "Payment Methods:\n"
        "bKash: 01313267551\n"
        "Nagad: 01313267551\n"
        "USDT TRC20: TBf8Mh5DwCCHH4evg4AdVdQ26XLNmpxQts\n\n"
        "Plans:\n"
        "7 Days - 1200 BDT / 11 USDT\n"
        "15 Days - 2200 BDT / 20 USDT\n"
        "30 Days - 3300 BDT / 30 USDT\n"
        "Lifetime - 5500 BDT / 50 USDT\n\n"
        "Send screenshot now!"
    )
    await update.message.reply_text(text)
    return PHOTO

# ===== PHOTO RECEIVED =====
async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["photo_id"] = update.message.photo[-1].file_id
    keyboard = [
        [InlineKeyboardButton("7 Days - 1200 BDT / 11 USDT", callback_data="plan_7d")],
        [InlineKeyboardButton("15 Days - 2200 BDT / 20 USDT", callback_data="plan_15d")],
        [InlineKeyboardButton("30 Days - 3300 BDT / 30 USDT", callback_data="plan_30d")],
        [InlineKeyboardButton("Lifetime - 5500 BDT / 50 USDT", callback_data="plan_lifetime")],
    ]
    await update.message.reply_text(
        "Screenshot received! Now select your plan:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_PLAN

# ===== PLAN SELECTED =====
async def plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.replace("plan_", "")
    plan = PLANS[plan_key]
    user = query.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else user.first_name

    pending_payments[user_id] = {
        "plan": plan_key,
        "plan_name": plan["name"],
        "username": username,
        "photo_id": context.user_data["photo_id"],
    }

    await query.edit_message_text(
        f"Plan selected: {plan['name']}\n"
        "Your payment is being reviewed. Please wait..."
    )

    # Forward to admin with photo
    caption = (
        f"New Payment Request!\n\n"
        f"User: {username}\n"
        f"User ID: {user_id}\n"
        f"Plan: {plan['name']} ({plan['bdt']} BDT / {plan['usdt']} USDT)\n\n"
        f"Reply with key to approve:\n"
        f"/key {user_id} PASTE-KEY-HERE"
    )

    keyboard = [
        [InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{user_id}")],
    ]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=context.user_data["photo_id"],
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Ask admin to send key
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"Payment from {username}\n"
            f"Plan: {plan['name']}\n\n"
            f"Paste key below and send:\n"
            f"Format: /key {user_id} XXXX-XXXX-XXXX"
        )
    )

    return ConversationHandler.END

# ===== ADMIN SEND KEY =====
async def send_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Not admin!")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Format: /key [user_id] [KEY]\n"
            "Example: /key 123456789 ABCD-EFGH-IJKL"
        )
        return

    try:
        user_id = int(args[0])
        key = args[1].upper().strip()
    except:
        await update.message.reply_text("Invalid! Use: /key [user_id] [KEY]")
        return

    if not re.match(r'^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$', key):
        await update.message.reply_text(
            "Invalid key format!\n"
            "Must be: XXXX-XXXX-XXXX\n"
            "Example: ABCD-EFGH-1234"
        )
        return

    payment = pending_payments.get(user_id, {})
    plan_name = payment.get("plan_name", "Unknown")
    username = payment.get("username", "User")

    # Show confirm buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{user_id}_{key}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{user_id}"),
        ]
    ]

    await update.message.reply_text(
        f"Confirm Approval:\n\n"
        f"User: {username}\n"
        f"Plan: {plan_name}\n"
        f"Key: {key}\n\n"
        f"Press APPROVE to send key to user:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== APPROVE CALLBACK =====
async def approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Not admin!")
        return
    await query.answer()

    data = query.data.replace("approve_", "")
    parts = data.split("_", 1)
    user_id = int(parts[0])
    key = parts[1]

    payment = pending_payments.get(user_id, {})
    plan_name = payment.get("plan_name", "Unknown")
    username = payment.get("username", "User")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"Payment Approved!\n\n"
                f"Your Premium Key:\n"
                f"`{key}`\n\n"
                f"Plan: {plan_name}\n\n"
                f"How to use:\n"
                f"1. Open PRO TOOLS HUB\n"
                f"2. Enter the key\n"
                f"3. Click Unlock Access\n\n"
                f"Enjoy Premium!"
            ),
            parse_mode="Markdown"
        )

        await query.edit_message_text(
            f"APPROVED!\n\n"
            f"User: {username}\n"
            f"Plan: {plan_name}\n"
            f"Key: {key}\n"
            f"Key sent successfully!"
        )

        if user_id in pending_payments:
            del pending_payments[user_id]

    except Exception as e:
        await query.edit_message_text(f"Error: {e}")

# ===== REJECT CALLBACK =====
async def reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Not admin!")
        return
    await query.answer()

    user_id = int(query.data.replace("reject_", ""))
    payment = pending_payments.get(user_id, {})
    username = payment.get("username", "User")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "Payment Rejected!\n\n"
                "Your payment was not verified.\n"
                "Please check your payment and try again.\n\n"
                "Contact: @tarakislam1"
            )
        )

        await query.edit_message_text(
            f"REJECTED!\n"
            f"User: {username}\n"
            f"Notification sent."
        )

        if user_id in pending_payments:
            del pending_payments[user_id]

    except Exception as e:
        await query.edit_message_text(f"Error: {e}")

# ===== STATS =====
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Not admin!")
        return
    count = len(pending_payments)
    await update.message.reply_text(
        f"Bot Stats:\n\n"
        f"Pending Payments: {count}\n"
        f"Bot Status: Running"
    )

# ===== CANCEL =====
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# ===== MAIN =====
def main():
    threading.Thread(target=run_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.PHOTO, photo_received),
        ],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo_received)],
            SELECT_PLAN: [CallbackQueryHandler(plan_selected, pattern="^plan_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("key", send_key))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(approve_callback, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(reject_callback, pattern="^reject_"))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
