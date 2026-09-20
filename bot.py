import logging
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8851108752:AAERyC1zOg1v-kH7IZcBodmI5hgUTut9p2s"
ADMIN_ID = 8157078800

PLANS = {
    "7d":   {"name": "7 Days",   "price": "1200 BDT / 11 USDT"},
    "15d":  {"name": "15 Days",  "price": "2200 BDT / 20 USDT"},
    "30d":  {"name": "30 Days",  "price": "3300 BDT / 30 USDT"},
    "life": {"name": "Lifetime", "price": "5500 BDT / 50 USDT"},
}

PLAN_DAYS = {"7d": 7, "15d": 15, "30d": 30, "life": 36500}
PHOTO, SELECT_PLAN = range(2)
pending_payments = {}

def generate_key():
    chars = string.ascii_uppercase + string.digits
    return "-".join("".join(random.choices(chars, k=4)) for _ in range(3))

def save_key_firebase(key, plan, user_id=None):
    try:
        import firebase_admin
        from firebase_admin import credentials, db
        if not firebase_admin._apps:
            cred = credentials.Certificate("firebase_key.json")
            firebase_admin.initialize_app(cred, {"databaseURL": "https://pro-tools-hub1-f4d55-default-rtdb.firebaseio.com"})
        days = PLAN_DAYS.get(plan, 30)
        expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        key_id = key.replace("-", "_")
        db.reference(f"keys/{key_id}").set({
            "key": key, "type": "premium", "plan": plan,
            "expiry": expiry, "active": True,
            "usedBy": user_id or "", "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "createdFor": str(user_id or "admin"),
        })
        return True
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return False

def get_stats_firebase():
    try:
        import firebase_admin
        from firebase_admin import credentials, db
        if not firebase_admin._apps:
            cred = credentials.Certificate("firebase_key.json")
            firebase_admin.initialize_app(cred, {"databaseURL": "https://pro-tools-hub1-f4d55-default-rtdb.firebaseio.com"})
        keys = db.reference("keys").get() or {}
        return len(keys), sum(1 for k in keys.values() if k.get("active"))
    except Exception as e:
        logger.error(f"Firebase stats error: {e}")
        return 0, 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to PRO TOOLS HUB!\n\n"
        "Payment Methods:\n\n"
        "bKash: 01313267554\n"
        "Nagad: 01313267551\n"
        "USDT TRC20:\n"
        "TBf8Mh5DwCCHH4evg4AdVdQ26XLNmpxQts\n\n"
        "Plans:\n"
        "7 Days - 1200 BDT / 11 USDT\n"
        "15 Days - 2200 BDT / 20 USDT\n"
        "30 Days - 3300 BDT / 30 USDT\n"
        "Lifetime - 5500 BDT / 50 USDT\n\n"
        "Send your payment screenshot!"
    )
    return PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data["photo_id"] = photo.file_id
    keyboard = [
        [InlineKeyboardButton("7 Days - 1200 BDT / 11 USDT", callback_data="plan_7d")],
        [InlineKeyboardButton("15 Days - 2200 BDT / 20 USDT", callback_data="plan_15d")],
        [InlineKeyboardButton("30 Days - 3300 BDT / 30 USDT", callback_data="plan_30d")],
        [InlineKeyboardButton("Lifetime - 5500 BDT / 50 USDT", callback_data="plan_life")],
    ]
    await update.message.reply_text("Screenshot received! Select your plan:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_PLAN

async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = query.data.replace("plan_", "")
    plan = PLANS[plan_id]
    user = query.from_user
    photo_id = context.user_data.get("photo_id")
    payment_id = f"{user.id}_{plan_id}"
    pending_payments[payment_id] = {
        "user_id": user.id, "username": user.username or user.first_name,
        "plan_id": plan_id, "plan_name": plan["name"],
        "plan_price": plan["price"], "photo_id": photo_id,
    }
    keyboard = [[
        InlineKeyboardButton("APPROVE", callback_data=f"approve_{payment_id}"),
        InlineKeyboardButton("REJECT", callback_data=f"reject_{payment_id}"),
    ]]
    await context.bot.send_photo(
        chat_id=ADMIN_ID, photo=photo_id,
        caption=(
            f"New Payment Request!\n\n"
            f"User: @{user.username or 'N/A'} ({user.id})\n"
            f"Plan: {plan['name']}\n"
            f"Amount: {plan['price']}\n\n"
            f"Check bKash / Nagad / USDT TRC20 then decide."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.edit_message_text(
        f"Payment sent for verification!\n"
        f"Plan: {plan['name']} ({plan['price']})\n\n"
        f"Wait for admin approval!"
    )
    return ConversationHandler.END

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("You are not admin!", show_alert=True)
        return
    data = query.data
    if data.startswith("approve_"):
        payment_id = data.replace("approve_", "")
        payment = pending_payments.get(payment_id)
        if not payment:
            await query.edit_message_caption("Payment data not found!")
            return
        key = generate_key()
        saved = save_key_firebase(key, payment["plan_id"], payment["user_id"])
        await context.bot.send_message(
            chat_id=payment["user_id"],
            text=(
                f"Payment Approved!\n\n"
                f"Plan: {payment['plan_name']} ({payment['plan_price']})\n\n"
                f"Your Premium Key:\n{key}\n\n"
                f"Use this key in PRO TOOLS HUB!"
            )
        )
        await query.edit_message_caption(
            f"Approved!\n"
            f"User: {payment['user_id']}\n"
            f"Key: {key}\n"
            f"Plan: {payment['plan_name']}\n"
            f"{'Saved to Firebase' if saved else 'Firebase save failed'}"
        )
        pending_payments.pop(payment_id, None)
    elif data.startswith("reject_"):
        payment_id = data.replace("reject_", "")
        payment = pending_payments.get(payment_id)
        if not payment:
            await query.edit_message_caption("Payment data not found!")
            return
        await context.bot.send_message(
            chat_id=payment["user_id"],
            text=(
                "Payment Rejected!\n\n"
                "Payment could not be verified.\n\n"
                "Payment Methods:\n"
                "bKash: 01313267554\n"
                "Nagad: 01313267551\n"
                "USDT TRC20:\n"
                "TBf8Mh5DwCCHH4evg4AdVdQ26XLNmpxQts\n\n"
                "Help: @tarakislam1"
            )
        )
        await query.edit_message_caption(f"Rejected!\nUser: {payment['user_id']}")
        pending_payments.pop(payment_id, None)

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args or args[0] not in PLANS:
        await update.message.reply_text("Usage: /genkey 7d | 15d | 30d | life")
        return
    plan_id = args[0]
    key = generate_key()
    saved = save_key_firebase(key, plan_id)
    await update.message.reply_text(
        f"New Key:\n{key}\n"
        f"Plan: {PLANS[plan_id]['name']}\n"
        f"{'Saved to Firebase' if saved else 'Firebase save failed'}"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total, active = get_stats_firebase()
    await update.message.reply_text(
        f"Stats:\n"
        f"Total Keys: {total}\n"
        f"Active: {active}\n"
        f"Pending: {len(pending_payments)}"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.PHOTO, receive_photo)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, receive_photo)],
            SELECT_PLAN: [CallbackQueryHandler(select_plan, pattern="^plan_")],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(approve|reject)_"))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("stats", stats))
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
