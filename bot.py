import logging
import os
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

# ── CONFIG ──
BOT_TOKEN = "8851108752:AAERyC1zOg1v-kH7IZcBodmI5hgUTut9p2s"
ADMIN_ID = 8157078800
FIREBASE_URL = "https://pro-tools-hub1-f4d55-default-rtdb.firebaseio.com"

# ── FIREBASE INIT ──
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})

# ── STATES ──
WAITING_SCREENSHOT = 1
WAITING_PLAN = 2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── PLANS ──
PLANS = {
    "7d": {"name": "7 Days", "price": 1200, "days": 7},
    "15d": {"name": "15 Days", "price": 2200, "days": 15},
    "30d": {"name": "30 Days", "price": 3300, "days": 30},
    "life": {"name": "Lifetime", "price": 5500, "days": 0},
}

# ── KEY GENERATOR ──
def gen_key():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=4)) for _ in range(3)]
    return '-'.join(parts)

def save_key_firebase(key, plan_id, user_id, username):
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

# ── /start ──
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 *স্বাগতম {user.first_name}!*\n\n"
        f"🛡️ *PRO TOOLS HUB* — Premium Key System\n\n"
        f"💳 *Payment করুন:*\n"
        f"├ bKash: `01313267554`\n"
        f"└ Nagad: `01313267551`\n\n"
        f"📸 Payment এর পর screenshot পাঠান\n\n"
        f"📋 *Plans:*\n"
        f"├ 7 Days — ৳1200\n"
        f"├ 15 Days — ৳2200\n"
        f"├ 30 Days — ৳3300\n"
        f"└ Lifetime — ৳5500",
        parse_mode='Markdown'
    )
    return WAITING_SCREENSHOT

# ── SCREENSHOT RECEIVED ──
async def screenshot_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not update.message.photo:
        await update.message.reply_text(
            "📸 অনুগ্রহ করে *payment screenshot* পাঠান!",
            parse_mode='Markdown'
        )
        return WAITING_SCREENSHOT
    
    # Save user info
    context.user_data['user_id'] = user.id
    context.user_data['username'] = user.username or user.first_name
    context.user_data['photo_id'] = update.message.photo[-1].file_id
    
    # Plan selection keyboard
    keyboard = [
        [InlineKeyboardButton("7 Days — ৳1200", callback_data=f"plan_7d_{user.id}")],
        [InlineKeyboardButton("15 Days — ৳2200", callback_data=f"plan_15d_{user.id}")],
        [InlineKeyboardButton("30 Days — ৳3300 🔥", callback_data=f"plan_30d_{user.id}")],
        [InlineKeyboardButton("Lifetime — ৳5500 👑", callback_data=f"plan_life_{user.id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Screenshot পাওয়া গেছে!\n\n"
        "কোন *Plan* নিতে চান?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return WAITING_PLAN

# ── PLAN SELECTED ──
async def plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    plan_id = data[1]
    user_id = int(data[2])
    
    if query.from_user.id != user_id:
        await query.answer("❌ এটা আপনার জন্য না!", show_alert=True)
        return
    
    plan = PLANS[plan_id]
    context.user_data['plan_id'] = plan_id
    
    await query.edit_message_text(
        f"✅ Plan selected: *{plan['name']}* — ৳{plan['price']}\n\n"
        f"⏳ Admin verify করছেন...\n"
        f"একটু অপেক্ষা করুন!",
        parse_mode='Markdown'
    )
    
    # Forward to admin
    user = query.from_user
    photo_id = context.user_data.get('photo_id')
    
    admin_keyboard = [
        [
            InlineKeyboardButton(
                "✅ APPROVE", 
                callback_data=f"approve_{user.id}_{plan_id}_{user.username or user.first_name}"
            ),
            InlineKeyboardButton(
                "❌ REJECT", 
                callback_data=f"reject_{user.id}"
            )
        ]
    ]
    admin_markup = InlineKeyboardMarkup(admin_keyboard)
    
    caption = (
        f"🔔 *নতুন Payment Request!*\n\n"
        f"👤 User: {user.first_name} {user.last_name or ''}\n"
        f"🆔 ID: `{user.id}`\n"
        f"📛 Username: @{user.username or 'N/A'}\n\n"
        f"💎 Plan: *{plan['name']}*\n"
        f"💰 Amount: ৳{plan['price']}\n\n"
        f"⚠️ *bKash/Nagad চেক করুন তারপর Approve করুন!*\n"
        f"📱 bKash: 01313267554\n"
        f"📱 Nagad: 01313267551"
    )
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=caption,
        reply_markup=admin_markup,
        parse_mode='Markdown'
    )

# ── ADMIN APPROVE ──
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ আপনি Admin না!", show_alert=True)
        return
    
    data = query.data.split('_')
    action = data[0]
    target_user_id = int(data[1])
    
    if action == "approve":
        plan_id = data[2]
        username = data[3] if len(data) > 3 else "User"
        plan = PLANS[plan_id]
        
        # Generate Key
        key = gen_key()
        save_key_firebase(key, plan_id, target_user_id, username)
        
        # Send key to user
        expiry_text = "কখনো Expire হবে না ♾️" if plan['days'] == 0 else f"{plan['days']} দিন পর Expire হবে"
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"🎉 *Payment Approved!*\n\n"
                f"✅ আপনার Premium Key:\n\n"
                f"`{key}`\n\n"
                f"📋 *Key Details:*\n"
                f"├ Plan: {plan['name']}\n"
                f"├ Valid: {expiry_text}\n"
                f"└ Type: Premium\n\n"
                f"📱 *কীভাবে Use করবেন:*\n"
                f"1. App খুলুন\n"
                f"2. Key টা paste করুন\n"
                f"3. Unlock চাপুন\n\n"
                f"⚠️ এই Key শুধু *একটি Device* এ কাজ করবে!\n\n"
                f"🙏 PRO TOOLS HUB ব্যবহার করার জন্য ধন্যবাদ!"
            ),
            parse_mode='Markdown'
        )
        
        # Update admin message
        await query.edit_message_caption(
            caption=(
                f"✅ *APPROVED!*\n\n"
                f"👤 User ID: {target_user_id}\n"
                f"💎 Plan: {plan['name']}\n"
                f"🔑 Key: `{key}`\n\n"
                f"Key পাঠানো হয়েছে!"
            ),
            parse_mode='Markdown'
        )
        
        logger.info(f"Key approved: {key} for user {target_user_id}")
    
    elif action == "reject":
        # Notify user
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                "❌ *Payment Verified হয়নি!*\n\n"
                "আপনার payment আমাদের কাছে পৌঁছায়নি।\n\n"
                "✅ *সঠিক নম্বরে পাঠান:*\n"
                "├ bKash: `01313267554`\n"
                "└ Nagad: `01313267551`\n\n"
                "Payment করার পর আবার screenshot পাঠান।\n\n"
                "সমস্যা হলে: @tarakislam1"
            ),
            parse_mode='Markdown'
        )
        
        # Update admin message
        await query.edit_message_caption(
            caption="❌ *REJECTED!*\n\nUser কে জানানো হয়েছে।",
            parse_mode='Markdown'
        )

# ── TEXT HANDLER ──
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Payment screenshot পাঠান অথবা /start চাপুন।"
    )
    return WAITING_SCREENSHOT

# ── ADMIN COMMANDS ──
async def admin_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    # Generate manual key
    args = context.args
    plan_id = args[0] if args else "30d"
    if plan_id not in PLANS:
        await update.message.reply_text("❌ Plan: 7d, 15d, 30d, life")
        return
    
    key = gen_key()
    save_key_firebase(key, plan_id, 0, "Manual")
    plan = PLANS[plan_id]
    
    await update.message.reply_text(
        f"🔑 *New Key Generated!*\n\n"
        f"`{key}`\n\n"
        f"Plan: {plan['name']}\n"
        f"Price: ৳{plan['price']}",
        parse_mode='Markdown'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    keys_ref = db.reference('keys')
    keys = keys_ref.get() or {}
    
    total = len(keys)
    active = sum(1 for k in keys.values() if k.get('active'))
    
    await update.message.reply_text(
        f"📊 *Stats:*\n\n"
        f"Total Keys: {total}\n"
        f"Active Keys: {active}",
        parse_mode='Markdown'
    )

# ── MAIN ──
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
                MessageHandler(filters.TEXT, text_handler),
            ],
            WAITING_PLAN: [
                CallbackQueryHandler(plan_selected, pattern=r'^plan_'),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
        per_user=True,
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r'^(approve|reject)_'))
    app.add_handler(CommandHandler('genkey', admin_keys))
    app.add_handler(CommandHandler('stats', admin_stats))
    
    print("✅ Bot চালু হয়েছে!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()