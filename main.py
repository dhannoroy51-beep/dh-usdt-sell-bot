from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters
from telegram.constants import ParseMode
from config import BOT_TOKEN, ADMIN_ID, BYBIT_UID, BEP20_ADDRESS, SUPPORT_USERNAME, CHANNEL_LINK, RATES, MIN_SELL, MAX_SELL, DATA_FILE
import datetime, pytz, json, os, re

BD_TZ = pytz.timezone("Asia/Dhaka")

PENDING_ORDERS = {}
ORDER_HISTORY = {}
ORDER_COUNTER = 1

SELL_NET, SELL_AMOUNT, SELL_PHOTO, USER_PHONE, ADMIN_REJECT_REASON = range(5)

def get_time():
    return datetime.datetime.now(BD_TZ).strftime("%d-%m-%Y %I:%M %p") # BD Time

def get_rate(amount):
    if MIN_SELL <= amount <= 0.99: return RATES["0.1-0.99"]
    elif 1 <= amount <= 1.49: return RATES["1-1.49"]
    elif 1.5 <= amount <= MAX_SELL: return RATES["1.5-10"]
    else: return None

def load_data():
    global PENDING_ORDERS, ORDER_HISTORY, ORDER_COUNTER
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: data = json.load(f)
        PENDING_ORDERS = {int(k):v for k,v in data.get("pending", {}).items()}
        ORDER_HISTORY = {int(k):v for k,v in data.get("history", {}).items()}
        ORDER_COUNTER = data.get("counter", 1)

def save_data():
    with open(DATA_FILE, "w") as f: 
        json.dump({"pending": PENDING_ORDERS, "history": ORDER_HISTORY, "counter": ORDER_COUNTER }, f)

def save_to_history(order_id):
    ORDER_HISTORY[order_id] = PENDING_ORDERS[order_id].copy()
    save_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["i. Support 💬", "ii. History 📜"], ["iii. Rate 💰", "iv. Sell 💵"]]
    msg = f"✨ **স্বাগতম @{update.effective_user.username} Dh USDT Sell Bot এ** ✨\n\n"
    msg += f"💵 **রেঞ্জ:** `{MIN_SELL}$` থেকে `{MAX_SELL}$` পর্যন্ত USDT Sell\n"
    msg += f"📊 অর্ডার করার আগে `iii. Rate` বাটন দিয়ে আজকের রেট দেখে নিন\n"
    msg += f"🔢 **নোট:** শুধুমাত্র Round Figure Amount পেমেন্ট করা হয়\n"
    msg += f"📞 Wallet Number অবশ্যই আপনার Personal 11 Digit হতে হবে\n"
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)

async def user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text; user_id = update.effective_user.id
    if text == "i. Support 💬":
        keyboard = [[InlineKeyboardButton("💬 Admin কে মেসেজ করুন", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}")], [InlineKeyboardButton("📢 আমাদের Channel", url=CHANNEL_LINK)]]
        await update.message.reply_text("**সাপোর্ট প্রয়োজন? নিচের বাটনে ক্লিক করুন:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    elif text == "ii. History 📜":
        user_orders = {k:v for k,v in ORDER_HISTORY.items() if v['user_id'] == user_id}
        if not user_orders: return await update.message.reply_text("📜 **আপনার এখনো কোনো Order নাই।**", parse_mode=ParseMode.MARKDOWN)
        history_text = "📜 **আপনার Last 10 টি Order:**\n\n"; count = 0
        for order_id, data in sorted(user_orders.items(), reverse=True):
            if count >= 10: break
            emoji = "✅" if data['status'] == "COMPLETED" else "❌" if data['status'] == "REJECTED" else "⏳"
            reason = f"\n**কারণ:** {data.get('reason', '-')}" if data['status'] == "REJECTED" else ""
            history_text += f"{emoji} **Order #{order_id}**\n**Date:** `{data['time']}`\n**Amount:** `{data['amount']}$` = `{data['bdt']} BDT`\n**Status:** **{data['status']}**{reason}\n\n"; count += 1
        await update.message.reply_text(history_text, parse_mode=ParseMode.MARKDOWN)
    elif text == "iii. Rate 💰":
        msg = f"💰 **আজকের রেট:**\n`0.1$ - 0.99$` = **{RATES['0.1-0.99']} BDT**\n`1$ - 1.49$` = **{RATES['1-1.49']} BDT**\n`1.5$ - 10$` = **{RATES['1.5-10']} BDT**\n*Min: {MIN_SELL} USDT | Max: {MAX_SELL} USDT*"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    elif text == "iv. Sell 💵":
        keyboard = [[InlineKeyboardButton("BEP-20", callback_data="net_BEP20")], [InlineKeyboardButton("Bybit", callback_data="net_Bybit")], [InlineKeyboardButton("❌ Cancel", callback_data="cancel_sell")]]
        msg = await update.message.reply_text("**আপনি যে মাধ্যমে পেমেন্ট করবেন, তা নির্বাচন করুন ।**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        context.user_data["last_msg_id"] = msg.message_id; return SELL_NET

async def sell_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "cancel_sell": await query.edit_message_text("❌ **Sell বাতিল করা হয়েছে।**", parse_mode=ParseMode.MARKDOWN); return ConversationHandler.END
    context.user_data["network"] = query.data.split("_")[1]
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_sell")]]
    await query.edit_message_text(f"আপনি সিলেক্ট করেছেন: **{context.user_data['network']}**\n\n**কত $ Sell করবেন?** শুধু নাম্বার দিন।\n*Min: {MIN_SELL} | Max: {MAX_SELL}*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return SELL_AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: amount = float(update.message.text)
    except: return await update.message.reply_text("❌ **শুধু নাম্বার দিন। যেমন:** `5.5`", parse_mode=ParseMode.MARKDOWN)
    if amount < MIN_SELL or amount > MAX_SELL: return await update.message.reply_text(f"❌ **Amount {MIN_SELL} থেকে {MAX_SELL} USDT এর মধ্যে হতে হবে।**", parse_mode=ParseMode.MARKDOWN)
    rate = get_rate(amount)
    if not rate: return await update.message.reply_text("❌ **এই Amount এর জন্য Rate নাই।**", parse_mode=ParseMode.MARKDOWN)
    context.user_data["amount"] = amount; context.user_data["rate"] = rate; bdt = int(amount * rate); network = context.user_data["network"]
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_sell")]]
    if network == "BEP20": text = f"📍 **BEP-20 Address:** `{BEP20_ADDRESS}`\n\n⚠️ **শুধু BEP-20 Network**\n💰 **Amount:** `{amount}$` USDT\n💵 **Rate:** `{rate}` BDT\n💸 **Total:** `{bdt}` BDT\n📸 পেমেন্ট Screenshot আপলোড করুন"
    else: text = f"📍 **Bybit UID:** `{BYBIT_UID}`\n\n⚠️ **Memo লাগবে না**\n💰 **Amount:** `{amount}$` USDT\n💵 **Rate:** `{rate}` BDT\n💸 **Total:** `{bdt}` BDT\n📸 পেমেন্ট Screenshot আপলোড করুন"
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=context.user_data["last_msg_id"], text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return SELL_PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ORDER_COUNTER; order_id = ORDER_COUNTER; ORDER_COUNTER += 1
    context.user_data["photo_id"] = update.message.photo[-1].file_id
    PENDING_ORDERS[order_id] = {"user_id": update.effective_user.id, "username": update.effective_user.username, "network": context.user_data["network"], "amount": context.user_data["amount"], "rate": context.user_data["rate"], "bdt": int(context.user_data["amount"] * context.user_data["rate"]), "photo_id": context.user_data["photo_id"], "status": "PENDING", "time": get_time()} # BD Time Save
    save_data()
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=context.user_data["last_msg_id"], text=f"✅ **Order Admin এর কাছে পাঠানো হয়েছে**\n\n`30 মিনিট থেকে 24 ঘন্টার` মধ্যে Admin যাচাই করবে", parse_mode=ParseMode.MARKDOWN)
    admin_text = f"🆕 **নতুন Order #{order_id}**\n👤 **User:** @{PENDING_ORDERS[order_id]['username']}\n🆔 **ID:** `{PENDING_ORDERS[order_id]['user_id']}`\n🌐 **Network:** {PENDING_ORDERS[order_id]['network']}\n💰 **Amount:** `{PENDING_ORDERS[order_id]['amount']}` USDT\n💵 **Rate:** `{PENDING_ORDERS[order_id]['rate']}` BDT\n💸 **Total:** `{PENDING_ORDERS[order_id]['bdt']}` BDT\n⏰ **Time:** {PENDING_ORDERS[order_id]['time']}"
    keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{order_id}")], [InlineKeyboardButton("❌ Reject", callback_data=f"rej_{order_id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=PENDING_ORDERS[order_id]['photo_id'], caption=admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("❌ **Sell বাতিল করা হয়েছে।**", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    keyboard = [["Pending 📝", "History 📜"]]
    await update.message.reply_text("👑 **Admin Panel**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    text = update.message.text
    if text == "Pending 📝":
        pending = [f"**#{k}:** @{v['username']} - `{v['amount']}$` - `{v['time']}`" for k,v in PENDING_ORDERS.items() if v['status']=='PENDING'] # Time Add
        msg = "📝 **Pending Orders:**\n" + ("\n".join(pending) if pending else "কোনো Pending Order নাই")
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    elif text == "History 📜":
        if not ORDER_HISTORY: return await update.message.reply_text("📜 **History নাই।**", parse_mode=ParseMode.MARKDOWN)
        history_text = "📜 **Last 10 Orders:**\n\n"; count = 0
        for order_id, data in sorted(ORDER_HISTORY.items(), reverse=True):
            if count >= 10: break
            if data['status'] == "COMPLETED": 
                history_text += f"✅ **#{order_id}**\n👤 @{data['username']}\n⏰ `{data['time']}`\n`{data['amount']}$` = `{data['bdt']} BDT`\n💳 {data.get('wallet_type', '-')}: `{data.get('phone', '-')}`\n\n" # Time Added
            elif data['status'] == "REJECTED": 
                history_text += f"❌ **#{order_id}**\n👤 @{data['username']}\n⏰ `{data['time']}`\n`{data['amount']}$`\nকারণ: {data.get('reason', '-')}\n\n" # Time Added
            count += 1
        await update.message.reply_text(history_text, parse_mode=ParseMode.MARKDOWN)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); data = query.data
    if data.startswith("app_"):
        order_id = int(data.split("_")[1]); PENDING_ORDERS[order_id]["status"] = "APPROVED"; save_to_history(order_id)
        bdt_amount = PENDING_ORDERS[order_id]['bdt']
        keyboard = [[InlineKeyboardButton("Bkash", callback_data=f"wall_Bkash_{order_id}")]]
        if bdt_amount >= 50: keyboard.append([InlineKeyboardButton("Nagad", callback_data=f"wall_Nagad_{order_id}")])
        keyboard.append([InlineKeyboardButton("Rocket", callback_data=f"wall_Rocket_{order_id}")])
        msg = await context.bot.send_message(chat_id=PENDING_ORDERS[order_id]['user_id'], text="✅ **Order Approved!**\n\n**টাকা নেওয়ার জন্য Mobile Wallet সিলেক্ট করুন:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        PENDING_ORDERS[order_id]["wallet_msg_id"] = msg.message_id
        
        admin_pay_text = f"💰 **Payment Waiting #{order_id}**\n👤 **User:** @{PENDING_ORDERS[order_id]['username']}\n⏰ **Time:** {PENDING_ORDERS[order_id]['time']}\n💵 **Amount:** `{PENDING_ORDERS[order_id]['bdt']} BDT`\n📱 **Number:** `Pending...`\n\nUser Wallet সিলেক্ট করার পর এখানে দেখাবে" # Time Add
        pay_keyboard = [[InlineKeyboardButton("✏️ Number Update", callback_data=f"num_{order_id}")]]
        await query.edit_message_caption(caption=admin_pay_text, reply_markup=InlineKeyboardMarkup(pay_keyboard), parse_mode=ParseMode.MARKDOWN); save_data()

    elif data.startswith("rej_"):
        context.user_data["reject_id"] = int(data.split("_")[1]); await query.message.reply_text("❌ **Reject এর কারণ লিখুন:**", parse_mode=ParseMode.MARKDOWN); return ADMIN_REJECT_REASON
    
    elif data.startswith("wall_"): 
        parts = data.split("_"); wallet = parts[1]; order_id = int(parts[2])
        PENDING_ORDERS[order_id]["wallet_type"] = wallet; save_data()
        msg_id = PENDING_ORDERS[order_id]["wallet_msg_id"]
        await context.bot.edit_message_text(
            chat_id=PENDING_ORDERS[order_id]['user_id'], 
            message_id=msg_id, 
            text=f"✅ **Order Approved!**\n\nআপনি **{wallet}** সিলেক্ট করেছেন।\n\n**এখন 11 Digit Mobile Number দিন:**\nউদাহরণ: `017XXXXXXXXX`", 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=None
        )
        return USER_PHONE

    elif data.startswith("num_"):
        context.user_data["update_num_order"] = int(data.split("_")[1])
        await query.message.reply_text(f"**Order #{context.user_data['update_num_order']} এর জন্য সঠিক 11 Digit নাম্বার লিখুন:**", parse_mode=ParseMode.MARKDOWN)
        return ADMIN_REJECT_REASON
    
    elif data.startswith("paid_"):
        order_id = int(data.split("_")[1]); PENDING_ORDERS[order_id]["status"] = "COMPLETED"; save_to_history(order_id)
        await context.bot.send_message(chat_id=PENDING_ORDERS[order_id]['user_id'], text=f"✅ **Payment Completed #{order_id}**\nআপনার `{PENDING_ORDERS[order_id]['bdt']} BDT` পাঠানো হয়েছে।\nধন্যবাদ ❤️", parse_mode=ParseMode.MARKDOWN)
        await query.edit_message_text(f"✅ **Payment Sent**\n**Order:** #{order_id}\n**User:** @{PENDING_ORDERS[order_id]['username']}\n⏰ **Time:** {PENDING_ORDERS[order_id]['time']}\n**Amount:** `{PENDING_ORDERS[order_id]['bdt']} BDT`\n**Wallet:** {PENDING_ORDERS[order_id]['wallet_type']} `{PENDING_ORDERS[order_id]['phone']}`\n**Status:** COMPLETED", parse_mode=ParseMode.MARKDOWN); save_data() # Time Add

async def get_wallet_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip().replace(" ", "")
    if not re.match(r"^01[3-9]\d{8}$", phone):
        return await update.message.reply_text("❌ **ভুল নাম্বার!**\nঅবশ্যই 11 Digit হতে হবে এবং `01` দিয়ে শুরু হতে হবে।\nউদাহরণ: `017XXXXXXXXX`\n\n**আবার সঠিক নাম্বার দিন:**", parse_mode=ParseMode.MARKDOWN)
    user_id = update.effective_user.id
    order_id = None
    for k, v in PENDING_ORDERS.items():
        if v['user_id'] == user_id and v['status'] == 'APPROVED': order_id = k; break
    if not order_id: return await update.message.reply_text("❌ **Order পাওয়া যায়নি। আবার /start দিন।**")
    PENDING_ORDERS[order_id]["phone"] = phone; PENDING_ORDERS[order_id]["status"] = "WAITING_PAYMENT"; save_data()
    o = PENDING_ORDERS[order_id]
    keyboard = [[InlineKeyboardButton("💰 Payment Sent", callback_data=f"paid_{order_id}")]]
    admin_text = f"💰 **Payment Request #{order_id}**\n👤 **User:** @{o['username']}\n⏰ **Time:** {o['time']}\n💳 **Wallet:** {o['wallet_type']}\n📱 **Number:** `{o['phone']}`\n💵 **Amount:** `{o['amount']}` USDT x `{o['rate']}` BDT = **`{o['bdt']} BDT`**\n\nটাকা পাঠিয়ে নিচের বাটনে চাপ দিন।" # Time Add
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("✅ **Admin `15 মিনিট থেকে 30 মিনিটের` মধ্যে Payment Complete করবে ।**\nদয়া করে অপেক্ষা করুন ।", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "update_num_order" in context.user_data:
        order_id = context.user_data["update_num_order"]
        phone = text.strip().replace(" ", "")
        if not re.match(r"^01[3-9]\d{8}$", phone): return await update.message.reply_text("❌ 11 Digit নাম্বার দিন।")
        PENDING_ORDERS[order_id]["phone"] = phone; PENDING_ORDERS[order_id]["status"] = "WAITING_PAYMENT"; save_data()
        del context.user_data["update_num_order"]
        o = PENDING_ORDERS[order_id]
        keyboard = [[InlineKeyboardButton("💰 Payment Sent", callback_data=f"paid_{order_id}")]]
        admin_text = f"💰 **Payment Request #{order_id}**\n👤 **User:** @{o['username']}\n⏰ **Time:** {o['time']}\n💳 **Wallet:** {o['wallet_type']}\n📱 **Number:** `{o['phone']}`\n💵 **Amount:** `{o['amount']}` USDT x `{o['rate']}` BDT = **`{o['bdt']} BDT`**\n\nটাকা পাঠিয়ে নিচের বাটনে চাপ দিন।" # Time Add
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ **নাম্বার Update হয়েছে। এখন Payment করতে পারবেন।**")
        return ConversationHandler.END
    else:
        order_id = context.user_data["reject_id"]; reason = text
        PENDING_ORDERS[order_id]["status"] = "REJECTED"; PENDING_ORDERS[order_id]["reason"] = reason; save_to_history(order_id)
        await context.bot.send_message(chat_id=PENDING_ORDERS[order_id]['user_id'], text=f"❌ **Order #{order_id} Reject হয়েছে।**\n**কারণ:** {reason}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ **Reject করা হয়েছে।**", parse_mode=ParseMode.MARKDOWN); save_data()
        return ConversationHandler.END

def main():
    load_data(); print(f"✅ {len(ORDER_HISTORY)} টি পুরাতন Order Load হয়েছে")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    sell_conv = ConversationHandler(entry_points=[CallbackQueryHandler(sell_network, pattern="^(net_|cancel_sell)")], states={ SELL_NET:[], SELL_AMOUNT:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount), CallbackQueryHandler(cancel, pattern="^cancel_sell")], SELL_PHOTO:[MessageHandler(filters.PHOTO, get_photo), CallbackQueryHandler(cancel, pattern="^cancel_sell")] }, fallbacks=[])
    phone_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_callback, pattern="^wall_")], states={USER_PHONE:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet_phone)]}, fallbacks=[])
    reject_conv = ConversationHandler(entry_points=[CallbackQueryHandler(admin_callback, pattern="^(rej_|num_)")], states={ADMIN_REJECT_REASON:[MessageHandler(filters.TEXT & ~filters.COMMAND, reject_reason)]}, fallbacks=[])
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin))
    app.add_handler(sell_conv); app.add_handler(phone_conv); app.add_handler(reject_conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(app_|rej_|wall_|paid_|num_)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_ID), admin_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_menu))
    print("🤖 Bot Running v15.2 - Admin History BD Time Added")
    app.run_polling()

if __name__ == "__main__": main()
