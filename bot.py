import os
import logging
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
import firebase_admin
from firebase_admin import credentials, db

# ฤฤ CONFIG ฤฤ
BOT_TOKEN = "8851108752:AAERyC1zOg1v-kH7IZcBodmI5hgUTut9p2s"
ADMIN_ID = 8157078800
FIREBASE_URL = "https://pro-tools-hub1-f4d55-default-rtdb.firebaseio.com"

# ฤฤ FIREBASE INIT ฤฤ
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})

# ฤฤ LOGGING ฤฤ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ฤฤ STATES ฤฤ
WAITING_SCREENSHOT = 1
WAITING_PLAN = 2

# ฤฤ PLANS ฤฤ
PLANS = {
    "7d":   {"name": "7 Days",   "price": 1200, "days": 7},
    "15d":  {"name": "15 Days",  "price": 2200, "days": 15},
    "30d":  {"name": "30 Days",  "price": 3300, "days": 30},
    "life": {"name": "Lifetime", "price": 5500, "days": 0},
}

# ฤฤ KEY GENERATOR ฤฤ
def gen_key():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=4)) for _ in range(3)]
    return '-'.join(parts)

# ฤฤ SAVE KEY TO FIREBASE ฤฤ
def save_key(key, plan_id, user_id, username):
    plan = PLANS[plan_id]
    key_path = key.replace('-', '_')
    expiry = None
    if plan['days'] > 0:
        expiry = (datetime.now() + timedelta(days=plan['days'])).isoformat()
    db.reference(f'keys/{key_path}').set({
        'key': key,
        'type': 'premium',
        'plan': plan['name'],
        'expiry': expiry,
        'active': True,
        'usedBy': {},
        'createdAt': datetime.now().isoformat(),
        'createdFor': f"{username} (ID: {user_id})"
    })
    return key

# ออออออออออออออออออออออออออออ
# /start
# ออออออออออออออออออออออออออออ
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f" * {user.first_name}!*\n\n"
        f" *PRO TOOLS HUB*\n"
        f"Gmail Creator AI  Premium Key System\n\n"
        f"\n"
        f" *Payment :*\n"
        f"ร bKash: `01313267554`\n"
        f"ภ Nagad: `01313267551`\n\n"
        f"\n"
        f" *Plans:*\n"
        f"ร 7 Days     1200\n"
        f"ร 15 Days    2200\n"
        f"ร 30 Days    3300 \n"
        f"ภ Lifetime   5500 \n\n"
        f"\n"
        f" Payment   *screenshot* !",
        parse_mode='Markdown'
    )
    return WAITING_SCREENSHOT

# ออออออออออออออออออออออออออออ
# SCREENSHOT RECEIVED
# ออออออออออออออออออออออออออออ
async def screenshot_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not update.message.photo:
        await update.message.reply_text(
            "   *payment screenshot* !\n\n"
            " /start ",
            parse_mode='Markdown'
        )
        return WAITING_SCREENSHOT

    context.user_data['user_id'] = user.id
    context.user_data['username'] = user.username or user.first_name
    context.user_data['photo_id'] = update.message.photo[-1].file_id

    keyboard = [
        [InlineKeyboardButton("7 Days  1200", callback_data=f"plan_7d_{user.id}")],
        [InlineKeyboardButton("15 Days  2200", callback_data=f"plan_15d_{user.id}")],
        [InlineKeyboardButton("30 Days  3300 ", callback_data=f"plan_30d_{user.id}")],
        [InlineKeyboardButton("Lifetime  5500 ", callback_data=f"plan_life_{user.id}")],
    ]

    await update.message.reply_text(
        " *Screenshot  !*\n\n"
        " *Plan*  ?\n"
        "  select  ",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return WAITING_PLAN

# ออออออออออออออออออออออออออออ
# PLAN SELECTED
# ออออออออออออออออออออออออออออ
async def plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    plan_id = data[1]
    user_id = int(data[2])

    if query.from_user.id != user_id:
        await query.answer("    !", show_alert=True)
        return WAITING_PLAN

    plan = PLANS[plan_id]
    context.user_data['plan_id'] = plan_id

    await query.edit_message_text(
        f" *Plan Selected!*\n\n"
        f" Plan: {plan['name']}\n"
        f" Amount: {plan['price']}\n\n"
        f" Admin verify ...\n"
        f"  ! ",
        parse_mode='Markdown'
    )

    user = query.from_user
    photo_id = context.user_data.get('photo_id')

    admin_keyboard = [
        [
            InlineKeyboardButton(
                " APPROVE",
                callback_data=f"approve_{user.id}_{plan_id}_{user.username or user.first_name}"
            ),
            InlineKeyboardButton(
                " REJECT",
                callback_data=f"reject_{user.id}"
            )
        ]
    ]

    caption = (
        f" * Payment Request!*\n\n"
        f" Name: {user.first_name} {user.last_name or ''}\n"
        f" ID: `{user.id}`\n"
        f" Username: @{user.username or 'N/A'}\n\n"
        f"\n"
        f" Plan: *{plan['name']}*\n"
        f" Amount: {plan['price']}\n\n"
        f"\n"
        f" * bKash/Nagad  !*\n"
        f" bKash: 01313267554\n"
        f" Nagad: 01313267551\n\n"
        f" Approve  Reject  "
    )

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(admin_keyboard),
        parse_mode='Markdown'
    )

# ออออออออออออออออออออออออออออ
# ADMIN CALLBACK
# ออออออออออออออออออออออออออออ
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("  Admin !", show_alert=True)
        return

    data = query.data.split('_')
    action = data[0]
    target_user_id = int(data[1])

    if action == "approve":
        plan_id = data[2]
        username = data[3] if len(data) > 3 else "User"
        plan = PLANS[plan_id]

        key = gen_key()
        save_key(key, plan_id, target_user_id, username)

        expiry_text = (
            " Expire   "
            if plan['days'] == 0
            else f"{plan['days']}   Expire "
        )

        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f" *Payment Approved!*\n\n"
                f"\n"
                f" * Premium Key:*\n\n"
                f"`{key}`\n\n"
                f"\n"
                f" *Key Details:*\n"
                f"ร Plan: {plan['name']}\n"
                f"ร Valid: {expiry_text}\n"
                f"ภ Type: Premium \n\n"
                f"\n"
                f" * Use :*\n"
                f"1 App \n"
                f"2 Key  copy \n"
                f"3 Paste \n"
                f"4 Unlock  \n\n"
                f"  Key  * Device*   !\n\n"
                f" PRO TOOLS HUB    !\n"
                f" : @tarakislam1"
            ),
            parse_mode='Markdown'
        )

        await query.edit_message_caption(
            caption=(
                f" *APPROVED!*\n\n"
                f" User: {target_user_id}\n"
                f" Plan: {plan['name']}\n"
                f" Key: `{key}`\n\n"
                f" Key  !"
            ),
            parse_mode='Markdown'
        )

    elif action == "reject":
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f" *Payment Verified !*\n\n"
                f" payment   \n\n"
                f"\n"
                f" *  :*\n"
                f"ร bKash: `01313267554`\n"
                f"ภ Nagad: `01313267551`\n\n"
                f"\n"
                f"Payment   \n"
                f"screenshot \n\n"
                f" : @tarakislam1"
            ),
            parse_mode='Markdown'
        )

        await query.edit_message_caption(
            caption=(
                f" *REJECTED!*\n\n"
                f"User   "
            ),
            parse_mode='Markdown'
        )

# ออออออออออออออออออออออออออออ
# TEXT HANDLER
# ออออออออออออออออออออออออออออ
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " Payment  *screenshot* !\n\n"
        " /start ",
        parse_mode='Markdown'
    )
    return WAITING_SCREENSHOT

# ออออออออออออออออออออออออออออ
# ADMIN COMMANDS
# ออออออออออออออออออออออออออออ
async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    args = context.args
    plan_id = args[0] if args else "30d"

    if plan_id not in PLANS:
        await update.message.reply_text(
            " Plan  !\n\n"
            "  format:\n"
            "/genkey 7d\n"
            "/genkey 15d\n"
            "/genkey 30d\n"
            "/genkey life"
        )
        return

    key = gen_key()
    save_key(key, plan_id, 0, "Manual-Admin")
    plan = PLANS[plan_id]

    await update.message.reply_text(
        f" *New Key Generated!*\n\n"
        f"`{key}`\n\n"
        f"\n"
        f"Plan: {plan['name']}\n"
        f"Price: {plan['price']}\n"
        f"Type: Premium ",
        parse_mode='Markdown'
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        keys = db.reference('keys').get() or {}
        total = len(keys)
        active = sum(1 for k in keys.values() if k.get('active'))
        trial = sum(1 for k in keys.values() if k.get('type') == 'trial')
        premium = sum(1 for k in keys.values() if k.get('type') == 'premium')

        await update.message.reply_text(
            f" *PRO TOOLS HUB Stats*\n\n"
            f"\n"
            f" Total Keys: {total}\n"
            f" Active: {active}\n"
            f" Premium: {premium}\n"
            f" Trial: {trial}\n"
            f"",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f" Error: {e}")

# ออออออออออออออออออออออออออออ
# MAIN
# ออออออออออออออออออออออออออออ
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.PHOTO, screenshot_received),
        ],
        states={
            WAITING_SCREENSHOT: [
                MessageHandler(filters.PHOTO, screenshot_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
            ],
            WAITING_PLAN: [
                CallbackQueryHandler(plan_selected, pattern=r'^plan_'),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r'^(approve|reject)_'))
    app.add_handler(CommandHandler('genkey', genkey))
    app.add_handler(CommandHandler('stats', stats))

    print(" Bot  !")
    logger.info("Bot started successfully!")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()