import os
import asyncio
import aiosqlite
import datetime
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ===== ENV থেকে সব নিবে =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME") # @dhannoRoy51
BEP20_ADDRESS = os.getenv("BEP20_ADDRESS")
BYBIT_UID = os.getenv("BYBIT_UID")
CHANNEL_LINK = os.getenv("CHANNEL_LINK") # https://t.me/tomar_channel

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
DB_NAME = "orders.db"
BD_TZ = pytz.timezone('Asia/Dhaka')

class Form(StatesGroup):
    amount = State()
    network = State()
    wallet_address = State()
    wallet_type = State()
    wallet_number = State()
    screenshot = State()
    reject_reason = State()

def get_rate(amount):
    if 0.15 <= amount <= 0.99: return 122
    elif 1.0 <= amount <= 3.99: return 125
    elif 4.0 <= amount <= 10.0: return 127.5
    else: return 0

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS orders
            (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
            amount REAL, bdt REAL, rate REAL, status TEXT, payment_status TEXT, date TEXT, time TEXT,
            network TEXT, wallet_address TEXT, wallet_type TEXT, wallet_number TEXT, screenshot TEXT, reject_reason TEXT)''')
        await db.commit()

def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("i. Support 💬"), KeyboardButton("ii. History 📁"))
    kb.add(KeyboardButton("iii. Rate 💰"), KeyboardButton("iv. Sell 💵"))
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("1. Pending Order"))
    kb.add(KeyboardButton("2. History"), KeyboardButton("3. Pending Payment"))
    return kb

# ===== USER PANEL =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    text = f"""✨ স্বাগতম @{message.from_user.username} Dh USDT Sell Bot এ ✨
💰 রেঞ্জ: 0.15 $ থেকে 10 $ পর্যন্ত USDT Sell
📊 অর্ডার করার আগে iii. Rate বাটন দিয়ে আজকের রেট দেখে নিন"""
    await message.answer(text, reply_markup=main_kb())

@dp.message_handler(text="i. Support 💬")
async def support(message: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👨‍💼 Admin কে Message দিন", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}"))
    kb.add(InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK))
    await message.answer("📞 যেকোনো সমস্যায় নিচের বাটনে ক্লিক করুন:", reply_markup=kb)

@dp.message_handler(text="ii. History 📁")
async def history(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, amount, bdt, rate, status, date, time, wallet_type, reject_reason FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15", (message.from_user.id,)) as cursor:
            rows = await cursor.fetchall()
    if not rows: await message.answer("📜 আপনার কোনো Order History নাই"); return
    text = "📜 আপনার Last 15 টা Order:\n\n"
    for row in rows:
        status_emoji = "✅" if row[4]=="Approved" else "❌" if row[4]=="Rejected" else "⏳"
        text += f"{status_emoji} #{row[0]} | {row[5]} {row[6]} BD\n@{message.from_user.username}\n{row[1]}$ x {row[3]}৳ = {row[2]} BDT\nWallet: {row[7]}\n"
        if row[4] == "Rejected": text += f"কারণ: {row[8]}\n"
        text += "\n"
    await message.answer(text)

@dp.message_handler(text="iii. Rate 💰")
async def rate(message: types.Message):
    text = f"""📊 আজকের Rate Chart:
💵 0.15$ - 0.99$ = 122৳
💵 1.00$ - 3.99$ = 125৳
💵 4.00$ - 10.0$ = 127.5৳"""
    await message.answer(text)

@dp.message_handler(text="iv. Sell 💵")
async def sell_start(message: types.Message):
    await message.answer("💵 কত USDT Sell করবেন? \nMin: 0.15$ - Max: 10$\nশুধু সংখ্যা লিখুন।")
    await Form.amount.set()

@dp.message_handler(state=Form.amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        rate = get_rate(amount)
        if rate == 0: await message.answer("❌ Amount 0.15 থেকে 10 এর মধ্যে হতে হবে"); return
        bdt = round(amount * rate)
        await state.update_data(amount=amount, bdt=bdt, rate=rate)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("BEP-20", callback_data="BEP-20")).add(InlineKeyboardButton("Bybit UID", callback_data="Bybit"))
        await message.answer(f"আপনি {amount}$ Sell করবেন\nRate: {rate}৳\nমোট পাবেন: {bdt} BDT\n🌐 কোন Network এ পাঠাবেন?", reply_markup=kb)
        await Form.network.set()
    except: await message.answer("❌ সঠিক সংখ্যা লিখুন।")

@dp.callback_query_handler(state=Form.network)
async def process_network(call: types.CallbackQuery, state: FSMContext):
    await call.answer(); network = call.data; await state.update_data(network=network)
    if network == "BEP-20": await call.message.answer(f"📩 আমাদের BEP-20 Address:\n`{BEP20_ADDRESS}`\n\nUSDT পাঠিয়ে Screenshot দিন", parse_mode="Markdown")
    else: await call.message.answer(f"📩 আমাদের Bybit UID:\n`{BYBIT_UID}`\n\nUSDT পাঠিয়ে Screenshot দিন", parse_mode="Markdown")
    await Form.wallet_address.set()

@dp.message_handler(state=Form.wallet_address)
async def process_wallet(message: types.Message, state: FSMContext):
    await state.update_data(wallet_address=message.text)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add("Bkash", "Nagad", "Rocket")
    await message.answer("💳 কোন Wallet এ টাকা নিবেন?", reply_markup=kb)
    await Form.wallet_type.set()

@dp.message_handler(state=Form.wallet_type)
async def process_wallet_type(message: types.Message, state: FSMContext):
    if message.text not in ["Bkash", "Nagad", "Rocket"]: await message.answer("শুধু Bkash / Nagad / Rocket লিখুন"); return
    await state.update_data(wallet_type=message.text)
    await message.answer("📱 11 Digit Mobile Number দিন", reply_markup=types.ReplyKeyboardRemove())
    await Form.wallet_number.set()

@dp.message_handler(state=Form.wallet_number)
async def process_number(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or len(message.text)!= 11: await message.answer("❌ 11 Digit নাম্বার দিন।"); return
    await state.update_data(wallet_number=message.text)
    await message.answer("📸 এখন Payment এর Screenshot পাঠান")
    await Form.screenshot.set()

@dp.message_handler(content_types=['photo'], state=Form.screenshot)
async def process_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data(); now = datetime.datetime.now(BD_TZ); date = now.strftime("%Y-%m-%d"); time = now.strftime("%H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO orders VALUES (NULL,?,?,?,?,?, 'Pending','Unpaid',?,?,?,?,?,?,?,?,?)",
            (message.from_user.id, message.from_user.username, data['amount'], data['bdt'], data['rate'], date, time,
             data['network'], data['wallet_address'], data['wallet_type'], data['wallet_number'], message.photo[-1].file_id, None))
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor: order_id = (await cursor.fetchone())[0]
    await message.answer("✅ Order Submit হয়েছে। 15 মিনিটের মধ্যে টাকা পেয়ে যাবেন।", reply_markup=main_kb())
    text = f"🆕 নতুন Order #{order_id}\n👤 @{message.from_user.username}\nID: {message.from_user.id}\n💵 {data['amount']}$ x {data['rate']}৳ = {data['bdt']} BDT\n🌐 {data['network']}\n💳 {data['wallet_type']}: {data['wallet_number']}\n📅 {date} {time} BD"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Approve ✅", callback_data=f"approve_{order_id}")).add(InlineKeyboardButton("Reject ❌", callback_data=f"reject_{order_id}"))
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=text, reply_markup=kb)
    await state.finish()

# ===== ADMIN PANEL =====
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID: await message.answer("Admin Panel", reply_markup=admin_kb())

@dp.message_handler(text="1. Pending Order")
async def pending_orders(message: types.Message):
    if message.from_user.id!= ADMIN_ID: return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, username, amount, bdt, rate, date, time, network, wallet_type, wallet_number FROM orders WHERE status='Pending' ORDER BY id DESC") as cursor: rows = await cursor.fetchall()
    if not rows: await message.answer("📭 কোনো Pending Order নাই"); return
    for row in rows:
        text = f"🆕 Order #{row[0]}\n👤 @{row[1]}\n💵 {row[2]}$ x {row[4]}৳ = {row[3]} BDT\n🌐 {row[7]}\n💳 {row[8]}: {row[9]}\n📅 {row[5]} {row[6]} BD"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Approve ✅", callback_data=f"approve_{row[0]}")).add(InlineKeyboardButton("Reject ❌", callback_data=f"reject_{row[0]}"))
        await message.answer(text, reply_markup=kb)

@dp.message_handler(text="2. History")
async def admin_history(message: types.Message):
    if message.from_user.id!= ADMIN_ID: return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, username, amount, bdt, rate, status, payment_status, date, time, wallet_type, wallet_number, reject_reason FROM orders ORDER BY id DESC LIMIT 20") as cursor: rows = await cursor.fetchall()
    if not rows: await message.answer("কোনো History নাই"); return
    text = "📜 Admin History - Last 20 Orders:\n\n"
    for row in rows:
        status_emoji = "✅" if row[5]=="Approved" else "❌" if row[5]=="Rejected" else "⏳"
        pay_emoji = "💰" if row[6]=="Paid" else "⏳"
        text += f"{status_emoji}{pay_emoji} #{row[0]} | {row[7]} {row[8]} BD\n@{row[1]} | {row[2]}$ x {row[4]}৳ = {row[3]} BDT\n"
        if row[5]=="Approved": text += f"Wallet: {row[9]} {row[10]}\n"
        if row[5]=="Rejected": text += f"কারণ: {row[11]}\n"
        text += "\n"
    await message.answer(text)

@dp.message_handler(text="3. Pending Payment")
async def pending_payment(message: types.Message):
    if message.from_user.id!= ADMIN_ID: return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, username, amount, bdt, date, time, wallet_type, wallet_number FROM orders WHERE status='Approved' AND payment_status='Unpaid' ORDER BY id DESC") as cursor: rows = await cursor.fetchall()
    if not rows: await message.answer("💰 সব Payment Done"); return
    for row in rows:
        text = f"💰 Payment Pending #{row[0]}\n👤 @{row[1]}\n💵 {row[2]}$ = {row[3]} BDT\n💳 {row[6]}: {row[7]}\n📅 {row[4]} {row[5]} BD"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Payment Sent ✅", callback_data=f"paid_{row[0]}"))
        await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def approve(call: types.CallbackQuery):
    if call.from_user.id!= ADMIN_ID: return
    order_id = call.data.split('_')[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status='Approved' WHERE id=?", (order_id,))
        await db.commit()
        async with db.execute("SELECT user_id, wallet_type FROM orders WHERE id=?", (order_id,)) as cursor: user_id, wallet_type = await cursor.fetchone()
    await bot.send_message(user_id, f"✅ Order #{order_id} Approved!\n15 মিনিটের মধ্যে {wallet_type} এ টাকা পেয়ে যাবেন।")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.edit_text(call.message.text + "\n\n✅ Approved")

@dp.callback_query_handler(lambda c: c.data.startswith('reject_'))
async def reject(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id!= ADMIN_ID: return
    order_id = call.data.split('_')[1]
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("Reject এর কারণ লিখুন:")
    await Form.reject_reason.set()
    await state.update_data(order_id=order_id, msg_id=call.message.message_id)

@dp.message_handler(state=Form.reject_reason)
async def process_reject(message: types.Message, state: FSMContext):
    data = await state.get_data(); order_id = data['order_id']
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status='Rejected', reject_reason=? WHERE id=?", (message.text, order_id))
        await db.commit()
        async with db.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)) as cursor: user_id = (await cursor.fetchone())[0]
    await bot.send_message(user_id, f"❌ Order #{order_id} Rejected\nকারণ: {message.text}")
    await bot.edit_message_text(f"{(await bot.get_message(ADMIN_ID, data['msg_id'])).text}\n\n❌ Rejected: {message.text}", ADMIN_ID, data['msg_id'])
    await message.answer("Reject করা হয়েছে")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('paid_'))
async def payment_done(call: types.CallbackQuery):
    if call.from_user.id!= ADMIN_ID: return
    order_id = call.data.split('_')[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET payment_status='Paid' WHERE id=?", (order_id,))
        await db.commit()
        async with db.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)) as cursor: user_id = (await cursor.fetchone())[0]
    await bot.send_message(user_id, f"💰 Order #{order_id} এর Payment Sent করা হয়েছে। Check করুন।")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.edit_text(call.message.text + "\n\n✅ Payment Sent")

async def on_startup(_): await init_db()

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
