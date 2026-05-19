import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove,
    WebAppInfo
)
import asyncpg
import os
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7151724014"))
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:atENenzEouhYSKnETXSyfNrwPOqNzkuZ@postgres.railway.internal:5432/railway")
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://qarshiyevziyodulla57-glitch.github.io/Sarichashma-Santexnika/miniapp/")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

pool = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL)
    return pool


# ===== DATABASE =====
class Database:
    async def create_tables(self):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    emoji TEXT DEFAULT '📦',
                    is_active INTEGER DEFAULT 1
                )""")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    category_id INTEGER,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    old_price REAL,
                    image_url TEXT,
                    stock INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    items TEXT,
                    total_price REAL,
                    address TEXT,
                    phone TEXT,
                    status TEXT DEFAULT 'yangi',
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cart (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    product_id INTEGER,
                    quantity INTEGER DEFAULT 1
                )""")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promotions (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    discount_percent INTEGER,
                    image_url TEXT,
                    is_active INTEGER DEFAULT 1,
                    expires_at TEXT
                )""")

            count = await db.fetchval("SELECT COUNT(*) FROM categories")
            if count == 0:
                cats = [
                    ("Kranlar va quvurlar", "🚰"),
                    ("Dushlar va vannalar", "🚿"),
                    ("Unitaz va rakovinalar", "🚽"),
                    ("Nasoslar", "💧"),
                    ("Filtrlar va tozalash", "🧹"),
                    ("Isitish tizimlari", "🔥"),
                    ("Kanalizatsiya", "🔩"),
                    ("Elektrika mahsulotlari", "⚡"),
                    ("Boshqa jihozlar", "📦"),
                ]
                await db.executemany(
                    "INSERT INTO categories (name, emoji) VALUES ($1, $2)", cats
                )

    async def add_user(self, tid, name, username=None):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute(
                "INSERT INTO users (telegram_id, full_name, username) VALUES ($1, $2, $3) ON CONFLICT (telegram_id) DO NOTHING",
                tid, name, username
            )

    async def get_all_users(self):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetch("SELECT * FROM users ORDER BY created_at DESC")

    async def update_user_phone(self, tid, phone):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute("UPDATE users SET phone=$1 WHERE telegram_id=$2", phone, tid)

    async def get_categories(self):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetch("SELECT * FROM categories WHERE is_active=1")

    async def get_products_by_category(self, cat_id):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetch("SELECT * FROM products WHERE category_id=$1 AND is_active=1", cat_id)

    async def get_product(self, pid):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetchrow("SELECT * FROM products WHERE id=$1", pid)

    async def get_all_products(self):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetch("""
                SELECT p.*, c.name as cat_name, c.emoji as cat_emoji
                FROM products p
                JOIN categories c ON p.category_id = c.id
                WHERE p.is_active = 1
            """)

    async def add_product(self, category_id, name, description, price, stock, old_price=None, image_url=None):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute(
                "INSERT INTO products (category_id, name, description, price, old_price, stock, image_url) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                category_id, name, description, price, old_price, stock, image_url
            )

    async def delete_product(self, pid):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute("UPDATE products SET is_active=0 WHERE id=$1", pid)

    async def update_product_field(self, pid, field, value):
        allowed = ["name", "description", "price", "old_price", "stock", "image_url"]
        if field not in allowed:
            return
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute(f"UPDATE products SET {field}=$1 WHERE id=$2", value, pid)

    async def add_to_cart(self, uid, pid, qty=1):
        p = await get_pool()
        async with p.acquire() as db:
            row = await db.fetchrow("SELECT id, quantity FROM cart WHERE user_id=$1 AND product_id=$2", uid, pid)
            if row:
                await db.execute("UPDATE cart SET quantity=$1 WHERE id=$2", row['quantity'] + qty, row['id'])
            else:
                await db.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES ($1,$2,$3)", uid, pid, qty)

    async def get_cart(self, uid):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetch("""
                SELECT c.id, p.name, p.price, c.quantity, (p.price * c.quantity) as subtotal
                FROM cart c
                JOIN products p ON c.product_id = p.id
                WHERE c.user_id = $1
            """, uid)

    async def remove_from_cart(self, cid):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute("DELETE FROM cart WHERE id=$1", cid)

    async def clear_cart(self, uid):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute("DELETE FROM cart WHERE user_id=$1", uid)

    async def create_order(self, user_id, items, total_price, address, phone, note=None):
        p = await get_pool()
        async with p.acquire() as db:
            row = await db.fetchrow(
                "INSERT INTO orders (user_id, items, total_price, address, phone, note) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                user_id, json.dumps(items, ensure_ascii=False), total_price, address, phone, note
            )
            return row['id']

    async def get_orders_by_user(self, uid):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetch("SELECT * FROM orders WHERE user_id=$1 ORDER BY created_at DESC", uid)

    async def get_all_orders(self, status=None):
        p = await get_pool()
        async with p.acquire() as db:
            if status:
                return await db.fetch("SELECT * FROM orders WHERE status=$1 ORDER BY created_at DESC", status)
            else:
                return await db.fetch("SELECT * FROM orders ORDER BY created_at DESC")

    async def update_order_status(self, oid, status):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute(
                "UPDATE orders SET status=$1, updated_at=CURRENT_TIMESTAMP WHERE id=$2", status, oid
            )

    async def get_order(self, oid):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetchrow("SELECT * FROM orders WHERE id=$1", oid)

    async def get_active_promotions(self):
        p = await get_pool()
        async with p.acquire() as db:
            return await db.fetch("SELECT * FROM promotions WHERE is_active=1 ORDER BY id DESC")

    async def add_promotion(self, title, description, discount_percent, expires_at=None):
        p = await get_pool()
        async with p.acquire() as db:
            await db.execute(
                "INSERT INTO promotions (title, description, discount_percent, expires_at) VALUES ($1,$2,$3,$4)",
                title, description, discount_percent, expires_at
            )

    async def get_stats(self):
        p = await get_pool()
        async with p.acquire() as db:
            users = await db.fetchval("SELECT COUNT(*) FROM users")
            orders = await db.fetchval("SELECT COUNT(*) FROM orders")
            revenue = await db.fetchval("SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status='yetkazildi'")
            new_orders = await db.fetchval("SELECT COUNT(*) FROM orders WHERE status='yangi'")
            return {"users": users, "orders": orders, "revenue": revenue, "new_orders": new_orders}


db = Database()


# ===== API SERVER =====
async def api_products(request):
    try:
        products = await db.get_all_products()
        categories = await db.get_categories()

        cats_list = [{"id": c['id'], "name": c['name'], "emoji": c['emoji']} for c in categories]
        prods_list = [{
            "id": p['id'], "category_id": p['category_id'],
            "name": p['name'], "description": p['description'] or "",
            "price": p['price'], "old_price": p['old_price'],
            "image_url": p['image_url'], "stock": p['stock'],
            "cat_name": p['cat_name'], "cat_emoji": p['cat_emoji'],
        } for p in products]

        return web.Response(
            text=json.dumps({"categories": cats_list, "products": prods_list}, ensure_ascii=False),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        logger.error(f"API xatosi: {e}")
        return web.Response(
            text=json.dumps({"error": str(e)}),
            content_type="application/json", status=500,
            headers={"Access-Control-Allow-Origin": "*"}
        )

async def api_health(request):
    return web.Response(text="OK")

async def start_api_server():
    app = web.Application()
    app.router.add_get("/api/products", api_products)
    app.router.add_get("/health", api_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"API server started on port {port}")


# ===== KEYBOARDS =====
def main_menu_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=MINI_APP_URL)))
    b.row(KeyboardButton(text="📦 Buyurtmalarim"), KeyboardButton(text="🎉 Aksiyalar"))
    b.row(KeyboardButton(text="📞 Boglanish"), KeyboardButton(text="ℹ️ Haqimizda"))
    return b.as_markup(resize_keyboard=True)

def admin_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📦 Buyurtmalar"))
    b.row(KeyboardButton(text="➕ Mahsulot qoshish"), KeyboardButton(text="🗂 Mahsulotlar"))
    b.row(KeyboardButton(text="🎉 Aksiya qoshish"), KeyboardButton(text="👥 Mijozlar"))
    b.row(KeyboardButton(text="📋 Mijozlar hisoboti"), KeyboardButton(text="📢 Xabar yuborish"))
    b.row(KeyboardButton(text="🔙 Asosiy menyu"))
    return b.as_markup(resize_keyboard=True)

def categories_kb(categories):
    b = InlineKeyboardBuilder()
    for cat in categories:
        b.button(text=f"{cat['emoji']} {cat['name']}", callback_data=f"cat_{cat['id']}")
    b.adjust(2)
    return b.as_markup()

def products_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"🔧 {p['name']}", callback_data=f"prod_{p['id']}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="🔙 Kategoriyalarga", callback_data="back_to_cats"))
    return b.as_markup()

def product_detail_kb(pid):
    b = InlineKeyboardBuilder()
    b.button(text="🛒 Savatga qoshish", callback_data=f"addcart_{pid}")
    b.button(text="🔙 Orqaga", callback_data="back_to_cats")
    b.adjust(1)
    return b.as_markup()

def cart_kb(cart_items):
    b = InlineKeyboardBuilder()
    for item in cart_items:
        b.button(text=f"❌ {item['name'][:25]}", callback_data=f"removecart_{item['id']}")
    b.adjust(1)
    b.row(
        InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout"),
        InlineKeyboardButton(text="🗑 Tozalash", callback_data="clearcart")
    )
    return b.as_markup()

def order_status_kb(oid):
    statuses = [
        ("🆕 Yangi", "yangi"), ("⚙️ Jarayonda", "jarayonda"),
        ("🚚 Yetkazilmoqda", "yetkazilmoqda"), ("✅ Yetkazildi", "yetkazildi"),
        ("❌ Bekor", "bekor")
    ]
    b = InlineKeyboardBuilder()
    for label, status in statuses:
        b.button(text=label, callback_data=f"setstatus_{oid}_{status}")
    b.adjust(2)
    return b.as_markup()

def orders_filter_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🆕 Yangi", callback_data="filter_yangi")
    b.button(text="⚙️ Jarayonda", callback_data="filter_jarayonda")
    b.button(text="🚚 Yetkazilmoqda", callback_data="filter_yetkazilmoqda")
    b.button(text="✅ Barchasi", callback_data="filter_all")
    b.adjust(2)
    return b.as_markup()

def phone_kb():
    b = ReplyKeyboardBuilder()
    b.add(KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True))
    b.add(KeyboardButton(text="🔙 Orqaga"))
    return b.as_markup(resize_keyboard=True)

def products_manage_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Tahrirlash", callback_data="manage_edit")
    b.button(text="🗑 Ochirish", callback_data="manage_delete")
    b.adjust(2)
    return b.as_markup()

def edit_field_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📝 Nom", callback_data="edit_name")
    b.button(text="📄 Tavsif", callback_data="edit_description")
    b.button(text="💰 Narx", callback_data="edit_price")
    b.button(text="💸 Eski narx", callback_data="edit_old_price")
    b.button(text="📦 Ombor", callback_data="edit_stock")
    b.button(text="🖼 Rasm", callback_data="edit_image")
    b.adjust(2)
    return b.as_markup()


# ===== STATES =====
class OrderState(StatesGroup):
    waiting_phone = State()
    waiting_address = State()
    waiting_note = State()

class AddProductState(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    old_price = State()
    stock = State()
    image = State()

class EditProductState(StatesGroup):
    select = State()
    field = State()
    value = State()

class AddPromoState(StatesGroup):
    title = State()
    description = State()
    discount = State()
    expires = State()

class BroadcastState(StatesGroup):
    message = State()


STATUS_EMOJI = {"yangi": "🆕", "jarayonda": "⚙️", "yetkazilmoqda": "🚚", "yetkazildi": "✅", "bekor": "❌"}


# ===== START =====
@dp.message(CommandStart())
async def start(message: Message):
    user = message.from_user
    await db.add_user(user.id, user.full_name, user.username)
    text = (
        f"👋 Assalomu alaykum, <b>{user.first_name}</b>!\n\n"
        f"🔧 <b>Sarichashma Santexnika</b> botiga xush kelibsiz!\n\n"
        f"Bizda mavjud:\n🚿 Santexnika mahsulotlari\n⚡ Elektrika mahsulotlari\n\n"
        f"📍 Samarqand viloyati, Jomboy tuman, Sarichashma qishloq\n"
        f"⏰ Ish vaqti: 07:00 - 20:00\n\nQuyidagi menyudan tanlang:"
    )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


# ===== CATALOG =====
@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(callback: CallbackQuery):
    cats = await db.get_categories()
    await callback.message.edit_text("📂 <b>Kategoriyani tanlang:</b>", reply_markup=categories_kb(cats), parse_mode="HTML")

@dp.callback_query(F.data.startswith("cat_"))
async def show_products(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    products = await db.get_products_by_category(cat_id)
    if not products:
        await callback.answer("Bu kategoriyada mahsulot yoq", show_alert=True)
        return
    await callback.message.edit_text(
        f"🔧 <b>Mahsulotlar ({len(products)} ta):</b>",
        reply_markup=products_kb(products), parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("prod_"))
async def show_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = await db.get_product(pid)
    if not p:
        await callback.answer("Topilmadi", show_alert=True)
        return
    price_text = f"💰 Narxi: <b>{p['price']:,.0f} so'm</b>"
    if p['old_price'] and p['old_price'] > p['price']:
        disc = int((1 - p['price'] / p['old_price']) * 100)
        price_text = f"💰 Narxi: <b>{p['price']:,.0f} so'm</b>\n<s>{p['old_price']:,.0f} so'm</s> 🔴 -{disc}%"
    stock_text = f"✅ Mavjud: {p['stock']} dona" if p['stock'] > 0 else "❌ Mavjud emas"
    text = f"🔧 <b>{p['name']}</b>\n\n{p['description'] or 'Tavsif yoq'}\n\n{price_text}\n{stock_text}"
    if p['image_url']:
        try:
            await callback.message.answer_photo(
                photo=p['image_url'], caption=text,
                reply_markup=product_detail_kb(pid), parse_mode="HTML"
            )
            await callback.message.delete()
            return
        except:
            pass
    await callback.message.edit_text(text, reply_markup=product_detail_kb(pid), parse_mode="HTML")

@dp.callback_query(F.data.startswith("addcart_"))
async def add_to_cart(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = await db.get_product(pid)
    if not p or p['stock'] == 0:
        await callback.answer("Mahsulot mavjud emas!", show_alert=True)
        return
    await db.add_to_cart(callback.from_user.id, pid)
    await callback.answer(f"✅ '{p['name']}' savatga qoshildi!", show_alert=True)


# ===== CART & ORDERS =====
@dp.message(F.text == "🛒 Savatim")
async def show_cart(message: Message):
    cart = await db.get_cart(message.from_user.id)
    if not cart:
        await message.answer("🛒 Savatingiz bosh!\n\nDo'konni ochib mahsulot tanlang.", reply_markup=main_menu_kb())
        return
    total = sum(i['subtotal'] for i in cart)
    text = "🛒 <b>Savatingiz:</b>\n\n"
    for item in cart:
        text += f"• {item['name']} — {item['quantity']} x {item['price']:,.0f} = <b>{item['subtotal']:,.0f} so'm</b>\n"
    text += f"\n💰 <b>Jami: {total:,.0f} so'm</b>"
    await message.answer(text, reply_markup=cart_kb(cart), parse_mode="HTML")

@dp.callback_query(F.data.startswith("removecart_"))
async def remove_from_cart(callback: CallbackQuery):
    await db.remove_from_cart(int(callback.data.split("_")[1]))
    cart = await db.get_cart(callback.from_user.id)
    if not cart:
        await callback.message.edit_text("🛒 Savat bosh!")
        return
    total = sum(i['subtotal'] for i in cart)
    text = "🛒 <b>Savatingiz:</b>\n\n"
    for item in cart:
        text += f"• {item['name']} — {item['quantity']} x {item['price']:,.0f} = <b>{item['subtotal']:,.0f} so'm</b>\n"
    text += f"\n💰 <b>Jami: {total:,.0f} so'm</b>"
    await callback.message.edit_text(text, reply_markup=cart_kb(cart), parse_mode="HTML")

@dp.callback_query(F.data == "clearcart")
async def clear_cart(callback: CallbackQuery):
    await db.clear_cart(callback.from_user.id)
    await callback.message.edit_text("🗑 Savat tozalandi!")

@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery, state: FSMContext):
    cart = await db.get_cart(callback.from_user.id)
    if not cart:
        await callback.answer("Savat bosh!", show_alert=True)
        return
    await state.set_state(OrderState.waiting_phone)
    await callback.message.answer("📱 Telefon raqamingizni yuboring:", reply_markup=phone_kb())

@dp.message(OrderState.waiting_phone, F.contact)
async def got_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await db.update_user_phone(message.from_user.id, message.contact.phone_number)
    await state.set_state(OrderState.waiting_address)
    await message.answer("📍 Yetkazib berish manzilingizni kiriting:", reply_markup=ReplyKeyboardRemove())

@dp.message(OrderState.waiting_phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderState.waiting_address)
    await message.answer("📍 Yetkazib berish manzilingizni kiriting:", reply_markup=ReplyKeyboardRemove())

@dp.message(OrderState.waiting_address)
async def got_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(OrderState.waiting_note)
    await message.answer("📝 Qoshimcha izoh (yoq bolsa: Yoq deb yozing):")

@dp.message(OrderState.waiting_note)
async def got_note(message: Message, state: FSMContext):
    data = await state.get_data()
    note = None if message.text.lower() in ["yoq", "-"] else message.text
    cart = await db.get_cart(message.from_user.id)
    total = sum(i['subtotal'] for i in cart)
    items = [{"name": i['name'], "price": i['price'], "qty": i['quantity']} for i in cart]
    oid = await db.create_order(message.from_user.id, items, total, data["address"], data["phone"], note)
    await db.clear_cart(message.from_user.id)
    await state.clear()
    items_text = "\n".join([f"• {i['name']} x{i['qty']} — {i['price']*i['qty']:,.0f} so'm" for i in items])
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n🔖 Buyurtma #{oid}\n\n{items_text}\n\n"
        f"💰 Jami: <b>{total:,.0f} so'm</b>\n📍 {data['address']}\n📱 {data['phone']}\n\n"
        f"⏳ Tez orada operatorimiz boglanadi!",
        reply_markup=main_menu_kb(), parse_mode="HTML")
    user = message.from_user
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>YANGI BUYURTMA #{oid}</b>\n\n👤 {user.full_name}\n🔗 @{user.username or '-'}\n🆔 {user.id}\n\n"
        f"🛒 {items_text}\n\n💰 {total:,.0f} so'm\n📍 {data['address']}\n📱 {data['phone']}"
        f"{chr(10)+'📝 '+note if note else ''}",
        reply_markup=order_status_kb(oid), parse_mode="HTML")

@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: Message):
    orders = await db.get_orders_by_user(message.from_user.id)
    if not orders:
        await message.answer("📦 Siz hali buyurtma bermagansiz.")
        return
    text = "📦 <b>Buyurtmalaringiz:</b>\n\n"
    for o in orders[:10]:
        emoji = STATUS_EMOJI.get(o['status'], "📦")
        text += f"🔖 <b>Buyurtma #{o['id']}</b>\n{emoji} {o['status']}\n💰 {o['total_price']:,.0f} so'm\n📅 {str(o['created_at'])[:10]}\n\n"
    await message.answer(text, parse_mode="HTML")


# ===== PROMOTIONS =====
@dp.message(F.text == "🎉 Aksiyalar")
async def show_promos(message: Message):
    promos = await db.get_active_promotions()
    if not promos:
        await message.answer("😔 Hozircha faol aksiyalar yoq. Tez orada yangi aksiyalar boladi! 🎉", reply_markup=main_menu_kb())
        return
    text = "🎉 <b>Joriy aksiyalar:</b>\n\n"
    for p in promos:
        text += f"🔥 <b>{p['title']}</b>\n{p['description'] or ''}\n{'💸 Chegirma: '+str(p['discount_percent'])+'%' if p['discount_percent'] else ''}\n{'📅 '+p['expires_at'] if p['expires_at'] else ''}\n\n"
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())

@dp.message(F.text == "📞 Boglanish")
async def contact(message: Message):
    await message.answer(
        "📞 <b>Biz bilan boglanish:</b>\n\n📱 Tel: +998 88 894 59 00\n📱 Tel: +998 94 282 62 66\n"
        "📍 Samarqand viloyati, Jomboy tuman, Sarichashma qishloq\n⏰ 07:00 - 20:00\n"
        "💬 https://t.me/sarichashma_santexnika", parse_mode="HTML")

@dp.message(F.text == "ℹ️ Haqimizda")
async def about(message: Message):
    await message.answer(
        "ℹ️ <b>Sarichashma Santexnika</b>\n\nBiz santexnika va elektrika mahsulotlari sohasida xizmat korsatamiz.\n\n"
        "Bizda mavjud:\n• Santexnika mahsulotlari\n• Elektrika mahsulotlari\n\n"
        "📍 Samarqand viloyati, Jomboy tuman, Sarichashma qishloq\n⏰ 07:00 - 20:00", parse_mode="HTML")


# ===== ADMIN =====
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Siz admin emassiz!")
        return
    await message.answer("🔐 <b>Admin Panel</b>", reply_markup=admin_kb(), parse_mode="HTML")

@dp.message(F.text == "📊 Statistika")
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID: return
    s = await db.get_stats()
    await message.answer(
        f"📊 <b>Statistika</b>\n\n👥 Mijozlar: <b>{s['users']}</b>\n📦 Buyurtmalar: <b>{s['orders']}</b>\n"
        f"🆕 Yangi: <b>{s['new_orders']}</b>\n💰 Daromad: <b>{s['revenue']:,.0f} so'm</b>",
        parse_mode="HTML")

@dp.message(F.text == "📦 Buyurtmalar")
async def admin_orders(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Qaysi buyurtmalar?", reply_markup=orders_filter_kb())

@dp.callback_query(F.data.startswith("filter_"))
async def filter_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    val = callback.data.split("_")[1]
    status = None if val == "all" else val
    orders = await db.get_all_orders(status)
    if not orders:
        await callback.message.edit_text("Buyurtmalar yoq.")
        return
    for o in orders[:15]:
        try: items = json.loads(o['items'])
        except: items = []
        items_text = "\n".join([f"  - {i['name']} x{i['qty']}" for i in items])
        emoji = STATUS_EMOJI.get(o['status'], "📦")
        await callback.message.answer(
            f"Buyurtma #{o['id']}\n{emoji} {o['status']}\nUser: {o['user_id']}\n{items_text}\n{o['total_price']:,.0f} so'm\n{o['address']}\n{o['phone']}",
            reply_markup=order_status_kb(o['id']))
    await callback.message.delete()

@dp.callback_query(F.data.startswith("setstatus_"))
async def set_status(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    parts = callback.data.split("_")
    oid, new_status = int(parts[1]), parts[2]
    await db.update_order_status(oid, new_status)
    emoji = STATUS_EMOJI.get(new_status, "📦")
    await callback.answer(f"Status: {emoji} {new_status}", show_alert=True)
    order = await db.get_order(oid)
    if order:
        try:
            await bot.send_message(
                order['user_id'],
                f"📦 <b>Buyurtma #{oid} holati yangilandi!</b>\n\n{emoji} <b>{new_status}</b>",
                parse_mode="HTML")
        except:
            pass

@dp.message(F.text == "➕ Mahsulot qoshish")
async def add_product_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    cats = await db.get_categories()
    text = "📂 <b>Kategoriya raqamini tanlang:</b>\n\n"
    for c in cats:
        text += f"{c['id']}. {c['emoji']} {c['name']}\n"
    await state.set_state(AddProductState.category)
    await message.answer(text, parse_mode="HTML")

@dp.message(AddProductState.category)
async def ap_category(message: Message, state: FSMContext):
    try:
        await state.update_data(category_id=int(message.text))
        await state.set_state(AddProductState.name)
        await message.answer("📝 Mahsulot nomini kiriting:")
    except:
        await message.answer("Raqam kiriting!")

@dp.message(AddProductState.name)
async def ap_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductState.description)
    await message.answer("📄 Tavsif kiriting (yoq bolsa: Yoq):")

@dp.message(AddProductState.description)
async def ap_desc(message: Message, state: FSMContext):
    await state.update_data(description=None if message.text.lower() in ["yoq", "-"] else message.text)
    await state.set_state(AddProductState.price)
    await message.answer("💰 Narxini kiriting (somda):")

@dp.message(AddProductState.price)
async def ap_price(message: Message, state: FSMContext):
    try:
        await state.update_data(price=float(message.text.replace(" ", "").replace(",", "")))
        await state.set_state(AddProductState.old_price)
        await message.answer("💸 Eski narxini kiriting (yoq bolsa: Yoq):")
    except:
        await message.answer("Togri narx kiriting!")

@dp.message(AddProductState.old_price)
async def ap_old_price(message: Message, state: FSMContext):
    if message.text.lower() in ["yoq", "-"]:
        await state.update_data(old_price=None)
    else:
        try:
            await state.update_data(old_price=float(message.text.replace(" ", "").replace(",", "")))
        except:
            await state.update_data(old_price=None)
    await state.set_state(AddProductState.stock)
    await message.answer("📦 Ombordagi miqdorini kiriting:")

@dp.message(AddProductState.stock)
async def ap_stock(message: Message, state: FSMContext):
    try:
        await state.update_data(stock=int(message.text))
        await state.set_state(AddProductState.image)
        await message.answer("🖼 Rasmini yuboring (yoq bolsa: Yoq):")
    except:
        await message.answer("Raqam kiriting!")

@dp.message(AddProductState.image, F.photo)
async def ap_image_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_product(
        data["category_id"], data["name"], data.get("description"),
        data["price"], data["stock"], data.get("old_price"), message.photo[-1].file_id
    )
    await state.clear()
    await message.answer(f"✅ <b>'{data['name']}'</b> rasmli holda qoshildi!", reply_markup=admin_kb(), parse_mode="HTML")

@dp.message(AddProductState.image, F.text)
async def ap_image_text(message: Message, state: FSMContext):
    data = await state.get_data()
    img = None if message.text.lower() in ["yoq", "-"] else message.text
    await db.add_product(
        data["category_id"], data["name"], data.get("description"),
        data["price"], data["stock"], data.get("old_price"), img
    )
    await state.clear()
    await message.answer(f"✅ <b>'{data['name']}'</b> qoshildi!", reply_markup=admin_kb(), parse_mode="HTML")


# ===== MANAGE PRODUCTS =====
@dp.message(F.text == "🗂 Mahsulotlar")
async def manage_products(message: Message):
    if message.from_user.id != ADMIN_ID: return
    products = await db.get_all_products()
    if not products:
        await message.answer("Mahsulotlar yoq.")
        return
    text = "🗂 <b>Mahsulotlar:</b>\n\n"
    for p in products:
        text += f"🔹 <b>ID:{p['id']}</b> — {p['name']} — {p['price']:,.0f} so'm (ombor: {p['stock']})\n"
    await message.answer(text, parse_mode="HTML", reply_markup=products_manage_kb())

@dp.callback_query(F.data == "manage_edit")
async def manage_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProductState.select)
    await state.update_data(action="edit")
    await callback.message.answer("✏️ Tahrirlash uchun mahsulot ID sini kiriting:")

@dp.callback_query(F.data == "manage_delete")
async def manage_delete(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProductState.select)
    await state.update_data(action="delete")
    await callback.message.answer("🗑 Ochirish uchun mahsulot ID sini kiriting:")

@dp.message(EditProductState.select)
async def ep_select(message: Message, state: FSMContext):
    try:
        pid = int(message.text)
        p = await db.get_product(pid)
        if not p:
            await message.answer("Topilmadi!")
            return
        data = await state.get_data()
        if data.get("action") == "delete":
            await db.delete_product(pid)
            await state.clear()
            await message.answer(f"✅ '{p['name']}' ochirildi!", reply_markup=admin_kb())
        else:
            await state.update_data(product_id=pid)
            await state.set_state(EditProductState.field)
            await message.answer(
                f"✏️ <b>'{p['name']}'</b> — qaysi maydonni ozgartirmoqchisiz?",
                reply_markup=edit_field_kb(), parse_mode="HTML")
    except ValueError:
        await message.answer("Faqat raqam kiriting!")

@dp.callback_query(EditProductState.field, F.data.startswith("edit_"))
async def ep_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")
    await state.update_data(field=field)
    await state.set_state(EditProductState.value)
    prompts = {
        "name": "📝 Yangi nom:", "description": "📄 Yangi tavsif (yoq: Yoq):",
        "price": "💰 Yangi narx:", "old_price": "💸 Yangi eski narx (yoq: Yoq):",
        "stock": "📦 Yangi miqdor:", "image": "🖼 Yangi rasmni yuboring:"
    }
    await callback.message.answer(prompts.get(field, "Yangi qiymat:"))

@dp.message(EditProductState.value, F.photo)
async def ep_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_product_field(data["product_id"], "image_url", message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Rasm yangilandi!", reply_markup=admin_kb())

@dp.message(EditProductState.value, F.text)
async def ep_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field_map = {
        "name": "name", "description": "description", "price": "price",
        "old_price": "old_price", "stock": "stock", "image": "image_url"
    }
    db_field = field_map.get(data["field"])
    value = message.text
    if data["field"] == "price":
        try: value = float(value.replace(" ", "").replace(",", ""))
        except:
            await message.answer("Togri raqam!"); return
    elif data["field"] == "stock":
        try: value = int(value)
        except:
            await message.answer("Togri raqam!"); return
    elif data["field"] in ["description", "old_price", "image"]:
        if value.lower() in ["yoq", "-"]: value = None
        elif data["field"] == "old_price":
            try: value = float(value.replace(" ", "").replace(",", ""))
            except: value = None
    await db.update_product_field(data["product_id"], db_field, value)
    await state.clear()
    await message.answer("✅ Yangilandi!", reply_markup=admin_kb())


# ===== PROMO ADMIN =====
@dp.message(F.text == "🎉 Aksiya qoshish")
async def promo_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.set_state(AddPromoState.title)
    await message.answer("📝 Aksiya nomini kiriting:")

@dp.message(AddPromoState.title)
async def promo_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddPromoState.description)
    await message.answer("📄 Tavsif (yoq: Yoq):")

@dp.message(AddPromoState.description)
async def promo_desc(message: Message, state: FSMContext):
    await state.update_data(description=None if message.text.lower() in ["yoq", "-"] else message.text)
    await state.set_state(AddPromoState.discount)
    await message.answer("💸 Chegirma % (yoq: Yoq):")

@dp.message(AddPromoState.discount)
async def promo_discount(message: Message, state: FSMContext):
    if message.text.lower() in ["yoq", "-"]:
        await state.update_data(discount=None)
    else:
        try: await state.update_data(discount=int(message.text))
        except: await state.update_data(discount=None)
    await state.set_state(AddPromoState.expires)
    await message.answer("📅 Muddat (masalan: 31.12.2025) yoq: Yoq:")

@dp.message(AddPromoState.expires)
async def promo_expires(message: Message, state: FSMContext):
    expires = None if message.text.lower() in ["yoq", "-"] else message.text
    data = await state.get_data()
    await db.add_promotion(data["title"], data.get("description"), data.get("discount"), expires)
    await state.clear()
    await message.answer(f"✅ Aksiya qoshildi: <b>{data['title']}</b>", reply_markup=admin_kb(), parse_mode="HTML")


# ===== USERS & BROADCAST =====
@dp.message(F.text == "👥 Mijozlar")
async def show_users(message: Message):
    if message.from_user.id != ADMIN_ID: return
    users = await db.get_all_users()
    text = f"👥 <b>Mijozlar ro'yxati ({len(users)} ta):</b>\n\n"
    for u in users[:20]:
        text += f"👤 <b>{u['full_name']}</b>\n"
        text += f"   📱 {u['phone'] or '-'} | @{u['username'] or '-'}\n"
        text += f"   🆔 {u['telegram_id']}\n\n"
    if len(users) > 20:
        text += f"<i>...va yana {len(users)-20} ta mijoz</i>"
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "📋 Mijozlar hisoboti")
async def customer_report(message: Message):
    if message.from_user.id != ADMIN_ID: return

    p = await get_pool()
    async with p.acquire() as db_conn:
        # Har bir foydalanuvchi uchun buyurtmalar statistikasi
        rows = await db_conn.fetch("""
            SELECT
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone,
                COUNT(o.id) as order_count,
                COALESCE(SUM(o.total_price), 0) as total_spent,
                MAX(o.created_at) as last_order
            FROM users u
            LEFT JOIN orders o ON u.telegram_id = o.user_id
            GROUP BY u.telegram_id, u.full_name, u.username, u.phone
            ORDER BY total_spent DESC
        """)

    if not rows:
        await message.answer("Hali mijozlar yo'q.")
        return

    # Har bir mijoz uchun alohida xabar (buyurtmali mijozlar)
    active = [r for r in rows if r['order_count'] > 0]
    passive = [r for r in rows if r['order_count'] == 0]

    # Umumiy hisobot
    total_users = len(rows)
    total_revenue = sum(r['total_spent'] for r in rows)
    total_orders = sum(r['order_count'] for r in rows)

    summary = (
        f"📋 <b>MIJOZLAR HISOBOTI</b>\n\n"
        f"👥 Jami foydalanuvchi: <b>{total_users} ta</b>\n"
        f"🛒 Buyurtma berganlar: <b>{len(active)} ta</b>\n"
        f"😴 Faol bo'lmaganlar: <b>{len(passive)} ta</b>\n"
        f"📦 Jami buyurtmalar: <b>{total_orders} ta</b>\n"
        f"💰 Jami tushum: <b>{total_revenue:,.0f} so'm</b>\n"
        f"{'─'*30}\n\n"
        f"🏆 <b>Xaridorlar reytingi:</b>\n\n"
    )
    await message.answer(summary, parse_mode="HTML")

    # Har bir faol mijoz uchun batafsil ma'lumot
    for i, r in enumerate(active[:15], 1):
        # Bu mijozning buyurtmalari va mahsulotlari
        p2 = await get_pool()
        async with p2.acquire() as db_conn2:
            orders = await db_conn2.fetch(
                "SELECT items, total_price, status, created_at FROM orders WHERE user_id=$1 ORDER BY created_at DESC",
                r['telegram_id']
            )

        # Barcha mahsulotlarni yig'ish
        product_counter = {}
        for order in orders:
            try:
                items = json.loads(order['items'])
                for item in items:
                    name = item.get('name', '?')
                    qty = item.get('qty', 1)
                    price = item.get('price', 0)
                    if name in product_counter:
                        product_counter[name]['qty'] += qty
                        product_counter[name]['sum'] += price * qty
                    else:
                        product_counter[name] = {'qty': qty, 'sum': price * qty}
            except:
                pass

        # Xabar matni
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text = (
            f"{medal} <b>{r['full_name']}</b>\n"
            f"📱 {r['phone'] or '-'} | @{r['username'] or '-'}\n"
            f"🛒 Buyurtmalar: <b>{r['order_count']} ta</b>\n"
            f"💰 Jami sarfladi: <b>{r['total_spent']:,.0f} so'm</b>\n"
            f"📅 So'nggi buyurtma: {str(r['last_order'])[:10]}\n"
        )

        if product_counter:
            text += f"\n📦 <b>Sotib olgan mahsulotlari:</b>\n"
            for prod_name, info in sorted(product_counter.items(), key=lambda x: x[1]['sum'], reverse=True):
                text += f"  • {prod_name} — {info['qty']} dona ({info['sum']:,.0f} so'm)\n"

        # Buyurtma holatlari
        status_counts = {}
        for order in orders:
            st = order['status']
            status_counts[st] = status_counts.get(st, 0) + 1
        if status_counts:
            statuses = " | ".join([f"{STATUS_EMOJI.get(k,'📦')}{v}" for k, v in status_counts.items()])
            text += f"\n📊 {statuses}"

        await message.answer(text, parse_mode="HTML")

    if len(active) > 15:
        await message.answer(f"<i>...va yana {len(active)-15} ta faol mijoz</i>", parse_mode="HTML")

    if passive:
        await message.answer(
            f"😴 <b>Hali xarid qilmagan foydalanuvchilar: {len(passive)} ta</b>\n"
            f"Ularga reklama xabar yuborish uchun 📢 Xabar yuborish tugmasidan foydalaning.",
            parse_mode="HTML"
        )

@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.set_state(BroadcastState.message)
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:")

@dp.message(BroadcastState.message)
async def do_broadcast(message: Message, state: FSMContext):
    users = await db.get_all_users()
    sent = 0
    for u in users:
        try:
            await bot.send_message(u['telegram_id'], f"📢 {message.text}")
            sent += 1
        except:
            pass
    await state.clear()
    await message.answer(f"✅ {sent} ta foydalanuvchiga yuborildi!", reply_markup=admin_kb())

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_main(message: Message):
    await message.answer("Asosiy menyu:", reply_markup=main_menu_kb())


# ===== MINI APP HANDLER =====
@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
        name     = data.get("name", "Noma'lum")
        phone    = data.get("phone", "-")
        address  = data.get("address", "-")
        delivery = data.get("delivery", "Kuryer")
        payment  = data.get("payment", "Naqd")
        note     = data.get("note")
        items    = data.get("items", [])
        total    = data.get("total", 0)

        await db.add_user(message.from_user.id, name, message.from_user.username)
        oid = await db.create_order(
            user_id=message.from_user.id, items=items, total_price=total,
            address=address, phone=phone, note=f"To'lov: {payment} | {note or ''}"
        )

        items_text = "\n".join([f"• {i['name']} x{i['qty']} — {i['price']*i['qty']:,.0f} so'm" for i in items])
        await message.answer(
            f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n🔖 Buyurtma #{oid}\n\n{items_text}\n\n"
            f"💰 Jami: <b>{total:,.0f} so'm</b>\n🚚 {delivery}\n💳 {payment}\n📍 {address}\n📱 {phone}\n\n"
            f"⏳ Tez orada operatorimiz bog'lanadi!",
            reply_markup=main_menu_kb(), parse_mode="HTML"
        )
        user = message.from_user
        await bot.send_message(
            ADMIN_ID,
            f"🆕 <b>YANGI BUYURTMA #{oid}</b> (Mini App)\n\n"
            f"👤 {name}\n🔗 @{user.username or '-'} | 🆔 {user.id}\n\n"
            f"🛒 {items_text}\n\n💰 {total:,.0f} so'm\n🚚 {delivery}\n💳 {payment}\n📍 {address}\n📱 {phone}"
            f"{chr(10)+'📝 '+note if note else ''}",
            reply_markup=order_status_kb(oid), parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Mini App data xatosi: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")


# ===== MAIN =====
async def main():
    await db.create_tables()
    await asyncio.gather(
        start_api_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
