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
import aiosqlite
import os
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7151724014"))

# Railway persistent volume yoki oddiy papka
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
DB_PATH = os.path.join(DATA_DIR, "santexnika.db")

MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://qarshiyevziyodulla57-glitch.github.io/Sarichashma-Santexnika/miniapp/")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ===== DATABASE =====
class Database:
    async def create_tables(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE,
                full_name TEXT, username TEXT, phone TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                emoji TEXT DEFAULT '📦', is_active INTEGER DEFAULT 1)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER,
                name TEXT NOT NULL, description TEXT, price REAL NOT NULL,
                old_price REAL, image_url TEXT, stock INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                items TEXT, total_price REAL, address TEXT, phone TEXT,
                status TEXT DEFAULT 'yangi', note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                product_id INTEGER, quantity INTEGER DEFAULT 1)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                description TEXT, discount_percent INTEGER, image_url TEXT,
                is_active INTEGER DEFAULT 1, expires_at TEXT)""")
            await db.commit()
            count = await db.execute("SELECT COUNT(*) FROM categories")
            row = await count.fetchone()
            if row[0] == 0:
                cats = [
                    ("Kranlar va quvurlar","🚰"),("Dushlar va vannalar","🚿"),
                    ("Unitaz va rakovinalar","🚽"),("Nasoslar","💧"),
                    ("Filtrlar va tozalash","🧹"),("Isitish tizimlari","🔥"),
                    ("Kanalizatsiya","🔩"),("Elektrika mahsulotlari","⚡"),
                    ("Boshqa jihozlar","📦"),
                ]
                await db.executemany("INSERT INTO categories (name,emoji) VALUES (?,?)", cats)
                await db.commit()

    async def add_user(self, tid, name, username=None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO users (telegram_id,full_name,username) VALUES (?,?,?)", (tid,name,username))
            await db.commit()

    async def get_all_users(self):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
            return await c.fetchall()

    async def update_user_phone(self, tid, phone):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET phone=? WHERE telegram_id=?", (phone,tid))
            await db.commit()

    async def get_categories(self):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT * FROM categories WHERE is_active=1")
            return await c.fetchall()

    async def get_products_by_category(self, cat_id):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT * FROM products WHERE category_id=? AND is_active=1", (cat_id,))
            return await c.fetchall()

    async def get_product(self, pid):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT * FROM products WHERE id=?", (pid,))
            return await c.fetchone()

    async def get_all_products(self):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT p.*, c.name as cat_name, c.emoji as cat_emoji FROM products p JOIN categories c ON p.category_id=c.id WHERE p.is_active=1")
            return await c.fetchall()

    async def add_product(self, category_id, name, description, price, stock, old_price=None, image_url=None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO products (category_id,name,description,price,old_price,stock,image_url) VALUES (?,?,?,?,?,?,?)",
                (category_id,name,description,price,old_price,stock,image_url))
            await db.commit()

    async def delete_product(self, pid):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE products SET is_active=0 WHERE id=?", (pid,))
            await db.commit()

    async def update_product_field(self, pid, field, value):
        allowed = ["name","description","price","old_price","stock","image_url"]
        if field not in allowed: return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE products SET {field}=? WHERE id=?", (value,pid))
            await db.commit()

    async def add_to_cart(self, uid, pid, qty=1):
        async with aiosqlite.connect(DB_PATH) as db:
            ex = await db.execute("SELECT id,quantity FROM cart WHERE user_id=? AND product_id=?", (uid,pid))
            row = await ex.fetchone()
            if row:
                await db.execute("UPDATE cart SET quantity=? WHERE id=?", (row[1]+qty, row[0]))
            else:
                await db.execute("INSERT INTO cart (user_id,product_id,quantity) VALUES (?,?,?)", (uid,pid,qty))
            await db.commit()

    async def get_cart(self, uid):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("""SELECT c.id,p.name,p.price,c.quantity,(p.price*c.quantity)
                FROM cart c JOIN products p ON c.product_id=p.id WHERE c.user_id=?""", (uid,))
            return await c.fetchall()

    async def remove_from_cart(self, cid):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM cart WHERE id=?", (cid,))
            await db.commit()

    async def clear_cart(self, uid):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM cart WHERE user_id=?", (uid,))
            await db.commit()

    async def create_order(self, user_id, items, total_price, address, phone, note=None):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("INSERT INTO orders (user_id,items,total_price,address,phone,note) VALUES (?,?,?,?,?,?)",
                (user_id, json.dumps(items, ensure_ascii=False), total_price, address, phone, note))
            await db.commit()
            return c.lastrowid

    async def get_orders_by_user(self, uid):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (uid,))
            return await c.fetchall()

    async def get_all_orders(self, status=None):
        async with aiosqlite.connect(DB_PATH) as db:
            if status:
                c = await db.execute("SELECT * FROM orders WHERE status=? ORDER BY created_at DESC", (status,))
            else:
                c = await db.execute("SELECT * FROM orders ORDER BY created_at DESC")
            return await c.fetchall()

    async def update_order_status(self, oid, status):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE orders SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status,oid))
            await db.commit()

    async def get_order(self, oid):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT * FROM orders WHERE id=?", (oid,))
            return await c.fetchone()

    async def get_active_promotions(self):
        async with aiosqlite.connect(DB_PATH) as db:
            c = await db.execute("SELECT * FROM promotions WHERE is_active=1 ORDER BY id DESC")
            return await c.fetchall()

    async def add_promotion(self, title, description, discount_percent, expires_at=None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO promotions (title,description,discount_percent,expires_at) VALUES (?,?,?,?)",
                (title, description, discount_percent, expires_at))
            await db.commit()

    async def get_stats(self):
        async with aiosqlite.connect(DB_PATH) as db:
            users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
            orders = (await (await db.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
            revenue = (await (await db.execute("SELECT SUM(total_price) FROM orders WHERE status='yetkazildi'")).fetchone())[0] or 0
            new_orders = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'")).fetchone())[0]
            return {"users":users,"orders":orders,"revenue":revenue,"new_orders":new_orders}

db = Database()


# ===== API SERVER (Mini App uchun) =====
async def api_products(request):
    """Mini App ga mahsulotlar va kategoriyalarni JSON ko'rinishida beradi"""
    try:
        products = await db.get_all_products()
        categories = await db.get_categories()

        cats_list = [{"id": c[0], "name": c[1], "emoji": c[2]} for c in categories]

        prods_list = []
        for p in products:
            prods_list.append({
                "id": p[0],
                "category_id": p[1],
                "name": p[2],
                "description": p[3] or "",
                "price": p[4],
                "old_price": p[5],
                "image_url": p[6],
                "stock": p[7],
                "cat_name": p[10],   # JOIN natijasi
                "cat_emoji": p[11],  # JOIN natijasi
            })

        data = {"categories": cats_list, "products": prods_list}
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        logger.error(f"API xatosi: {e}")
        return web.Response(
            text=json.dumps({"error": str(e)}),
            content_type="application/json",
            status=500,
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
    b.row(KeyboardButton(
        text="🛒 Do'konni ochish",
        web_app=WebAppInfo(url=MINI_APP_URL)
    ))
    # "🛍 Katalog" tugmasi olib tashlandi
    b.row(KeyboardButton(text="📦 Buyurtmalarim"), KeyboardButton(text="🎉 Aksiyalar"))
    b.row(KeyboardButton(text="📞 Boglanish"), KeyboardButton(text="ℹ️ Haqimizda"))
    return b.as_markup(resize_keyboard=True)

def admin_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📦 Buyurtmalar"))
    b.row(KeyboardButton(text="➕ Mahsulot qoshish"), KeyboardButton(text="🗂 Mahsulotlar"))
    b.row(KeyboardButton(text="🎉 Aksiya qoshish"), KeyboardButton(text="👥 Mijozlar"))
    b.row(KeyboardButton(text="📢 Xabar yuborish"), KeyboardButton(text="🔙 Asosiy menyu"))
    return b.as_markup(resize_keyboard=True)

def categories_kb(categories):
    b = InlineKeyboardBuilder()
    for cat in categories:
        b.button(text=f"{cat[2]} {cat[1]}", callback_data=f"cat_{cat[0]}")
    b.adjust(2)
    return b.as_markup()

def products_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"🔧 {p[2]}", callback_data=f"prod_{p[0]}")
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
        b.button(text=f"❌ {item[1][:25]}", callback_data=f"removecart_{item[0]}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout"),
          InlineKeyboardButton(text="🗑 Tozalash", callback_data="clearcart"))
    return b.as_markup()

def order_status_kb(oid):
    statuses = [("🆕 Yangi","yangi"),("⚙️ Jarayonda","jarayonda"),
                ("🚚 Yetkazilmoqda","yetkazilmoqda"),("✅ Yetkazildi","yetkazildi"),("❌ Bekor","bekor")]
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


STATUS_EMOJI = {"yangi":"🆕","jarayonda":"⚙️","yetkazilmoqda":"🚚","yetkazildi":"✅","bekor":"❌"}


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


# ===== CATALOG (bot ichida) =====
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
    await callback.message.edit_text(f"🔧 <b>Mahsulotlar ({len(products)} ta):</b>",
        reply_markup=products_kb(products), parse_mode="HTML")

@dp.callback_query(F.data.startswith("prod_"))
async def show_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = await db.get_product(pid)
    if not p:
        await callback.answer("Topilmadi", show_alert=True)
        return
    price_text = f"💰 Narxi: <b>{p[4]:,.0f} so'm</b>"
    if p[5] and p[5] > p[4]:
        disc = int((1 - p[4]/p[5]) * 100)
        price_text = f"💰 Narxi: <b>{p[4]:,.0f} so'm</b>\n<s>{p[5]:,.0f} so'm</s> 🔴 -{disc}%"
    stock_text = f"✅ Mavjud: {p[7]} dona" if p[7] > 0 else "❌ Mavjud emas"
    text = f"🔧 <b>{p[2]}</b>\n\n{p[3] or 'Tavsif yoq'}\n\n{price_text}\n{stock_text}"
    if p[6]:
        try:
            await callback.message.answer_photo(photo=p[6], caption=text,
                reply_markup=product_detail_kb(pid), parse_mode="HTML")
            await callback.message.delete()
            return
        except: pass
    await callback.message.edit_text(text, reply_markup=product_detail_kb(pid), parse_mode="HTML")

@dp.callback_query(F.data.startswith("addcart_"))
async def add_to_cart(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = await db.get_product(pid)
    if not p or p[7] == 0:
        await callback.answer("Mahsulot mavjud emas!", show_alert=True)
        return
    await db.add_to_cart(callback.from_user.id, pid)
    await callback.answer(f"✅ '{p[2]}' savatga qoshildi!", show_alert=True)


# ===== CART & ORDERS =====
@dp.message(F.text == "🛒 Savatim")
async def show_cart(message: Message):
    cart = await db.get_cart(message.from_user.id)
    if not cart:
        await message.answer("🛒 Savatingiz bosh!\n\nDo'konni ochib mahsulot tanlang.", reply_markup=main_menu_kb())
        return
    total = sum(i[4] for i in cart)
    text = "🛒 <b>Savatingiz:</b>\n\n"
    for item in cart:
        text += f"• {item[1]} — {item[3]} x {item[2]:,.0f} = <b>{item[4]:,.0f} so'm</b>\n"
    text += f"\n💰 <b>Jami: {total:,.0f} so'm</b>"
    await message.answer(text, reply_markup=cart_kb(cart), parse_mode="HTML")

@dp.callback_query(F.data.startswith("removecart_"))
async def remove_from_cart(callback: CallbackQuery):
    await db.remove_from_cart(int(callback.data.split("_")[1]))
    cart = await db.get_cart(callback.from_user.id)
    if not cart:
        await callback.message.edit_text("🛒 Savat bosh!")
        return
    total = sum(i[4] for i in cart)
    text = "🛒 <b>Savatingiz:</b>\n\n"
    for item in cart:
        text += f"• {item[1]} — {item[3]} x {item[2]:,.0f} = <b>{item[4]:,.0f} so'm</b>\n"
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
    note = None if message.text.lower() in ["yoq","-"] else message.text
    cart = await db.get_cart(message.from_user.id)
    total = sum(i[4] for i in cart)
    items = [{"name":i[1],"price":i[2],"qty":i[3]} for i in cart]
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
    await bot.send_message(ADMIN_ID,
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
        emoji = STATUS_EMOJI.get(o[6], "📦")
        text += f"🔖 <b>Buyurtma #{o[0]}</b>\n{emoji} {o[6]}\n💰 {o[3]:,.0f} so'm\n📅 {o[8][:10]}\n\n"
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
        text += f"🔥 <b>{p[1]}</b>\n{p[2] or ''}\n{'💸 Chegirma: '+str(p[3])+'%' if p[3] else ''}\n{'📅 '+p[6] if p[6] else ''}\n\n"
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
    await message.answer(f"📊 <b>Statistika</b>\n\n👥 Mijozlar: <b>{s['users']}</b>\n📦 Buyurtmalar: <b>{s['orders']}</b>\n🆕 Yangi: <b>{s['new_orders']}</b>\n💰 Daromad: <b>{s['revenue']:,.0f} so'm</b>", parse_mode="HTML")

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
        try: items = json.loads(o[2])
        except: items = []
        items_text = "\n".join([f"  - {i['name']} x{i['qty']}" for i in items])
        emoji = STATUS_EMOJI.get(o[6], "📦")
        await callback.message.answer(
            f"Buyurtma #{o[0]}\n{emoji} {o[6]}\nUser: {o[1]}\n{items_text}\n{o[3]:,.0f} so'm\n{o[4]}\n{o[5]}",
            reply_markup=order_status_kb(o[0]))
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
            await bot.send_message(order[1], f"📦 <b>Buyurtma #{oid} holati yangilandi!</b>\n\n{emoji} <b>{new_status}</b>", parse_mode="HTML")
        except: pass

@dp.message(F.text == "➕ Mahsulot qoshish")
async def add_product_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    cats = await db.get_categories()
    text = "📂 <b>Kategoriya raqamini tanlang:</b>\n\n"
    for c in cats: text += f"{c[0]}. {c[2]} {c[1]}\n"
    await state.set_state(AddProductState.category)
    await message.answer(text, parse_mode="HTML")

@dp.message(AddProductState.category)
async def ap_category(message: Message, state: FSMContext):
    try:
        await state.update_data(category_id=int(message.text))
        await state.set_state(AddProductState.name)
        await message.answer("📝 Mahsulot nomini kiriting:")
    except: await message.answer("Raqam kiriting!")

@dp.message(AddProductState.name)
async def ap_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductState.description)
    await message.answer("📄 Tavsif kiriting (yoq bolsa: Yoq):")

@dp.message(AddProductState.description)
async def ap_desc(message: Message, state: FSMContext):
    await state.update_data(description=None if message.text.lower() in ["yoq","-"] else message.text)
    await state.set_state(AddProductState.price)
    await message.answer("💰 Narxini kiriting (somda):")

@dp.message(AddProductState.price)
async def ap_price(message: Message, state: FSMContext):
    try:
        await state.update_data(price=float(message.text.replace(" ","").replace(",","")))
        await state.set_state(AddProductState.old_price)
        await message.answer("💸 Eski narxini kiriting (yoq bolsa: Yoq):")
    except: await message.answer("Togri narx kiriting!")

@dp.message(AddProductState.old_price)
async def ap_old_price(message: Message, state: FSMContext):
    if message.text.lower() in ["yoq","-"]: await state.update_data(old_price=None)
    else:
        try: await state.update_data(old_price=float(message.text.replace(" ","").replace(",","")))
        except: await state.update_data(old_price=None)
    await state.set_state(AddProductState.stock)
    await message.answer("📦 Ombordagi miqdorini kiriting:")

@dp.message(AddProductState.stock)
async def ap_stock(message: Message, state: FSMContext):
    try:
        await state.update_data(stock=int(message.text))
        await state.set_state(AddProductState.image)
        await message.answer("🖼 Rasmini yuboring (yoq bolsa: Yoq):")
    except: await message.answer("Raqam kiriting!")

@dp.message(AddProductState.image, F.photo)
async def ap_image_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_product(data["category_id"], data["name"], data.get("description"),
        data["price"], data["stock"], data.get("old_price"), message.photo[-1].file_id)
    await state.clear()
    await message.answer(f"✅ <b>'{data['name']}'</b> rasmli holda qoshildi!", reply_markup=admin_kb(), parse_mode="HTML")

@dp.message(AddProductState.image, F.text)
async def ap_image_text(message: Message, state: FSMContext):
    data = await state.get_data()
    img = None if message.text.lower() in ["yoq","-"] else message.text
    await db.add_product(data["category_id"], data["name"], data.get("description"),
        data["price"], data["stock"], data.get("old_price"), img)
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
        text += f"🔹 <b>ID:{p[0]}</b> — {p[2]} — {p[4]:,.0f} so'm (ombor: {p[7]})\n"
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
            await message.answer(f"✅ '{p[2]}' ochirildi!", reply_markup=admin_kb())
        else:
            await state.update_data(product_id=pid)
            await state.set_state(EditProductState.field)
            await message.answer(f"✏️ <b>'{p[2]}'</b> — qaysi maydonni ozgartirmoqchisiz?",
                reply_markup=edit_field_kb(), parse_mode="HTML")
    except ValueError: await message.answer("Faqat raqam kiriting!")

@dp.callback_query(EditProductState.field, F.data.startswith("edit_"))
async def ep_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_","")
    await state.update_data(field=field)
    await state.set_state(EditProductState.value)
    prompts = {"name":"📝 Yangi nom:","description":"📄 Yangi tavsif (yoq: Yoq):","price":"💰 Yangi narx:",
               "old_price":"💸 Yangi eski narx (yoq: Yoq):","stock":"📦 Yangi miqdor:","image":"🖼 Yangi rasmni yuboring:"}
    await callback.message.answer(prompts.get(field,"Yangi qiymat:"))

@dp.message(EditProductState.value, F.photo)
async def ep_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_product_field(data["product_id"], "image_url", message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Rasm yangilandi!", reply_markup=admin_kb())

@dp.message(EditProductState.value, F.text)
async def ep_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field_map = {"name":"name","description":"description","price":"price","old_price":"old_price","stock":"stock","image":"image_url"}
    db_field = field_map.get(data["field"])
    value = message.text
    if data["field"] == "price":
        try: value = float(value.replace(" ","").replace(",",""))
        except: await message.answer("Togri raqam!"); return
    elif data["field"] == "stock":
        try: value = int(value)
        except: await message.answer("Togri raqam!"); return
    elif data["field"] in ["description","old_price","image"]:
        if value.lower() in ["yoq","-"]: value = None
        elif data["field"] == "old_price":
            try: value = float(value.replace(" ","").replace(",",""))
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
    await state.update_data(description=None if message.text.lower() in ["yoq","-"] else message.text)
    await state.set_state(AddPromoState.discount)
    await message.answer("💸 Chegirma % (yoq: Yoq):")

@dp.message(AddPromoState.discount)
async def promo_discount(message: Message, state: FSMContext):
    if message.text.lower() in ["yoq","-"]: await state.update_data(discount=None)
    else:
        try: await state.update_data(discount=int(message.text))
        except: await state.update_data(discount=None)
    await state.set_state(AddPromoState.expires)
    await message.answer("📅 Muddat (masalan: 31.12.2025) yoq: Yoq:")

@dp.message(AddPromoState.expires)
async def promo_expires(message: Message, state: FSMContext):
    expires = None if message.text.lower() in ["yoq","-"] else message.text
    data = await state.get_data()
    await db.add_promotion(data["title"], data.get("description"), data.get("discount"), expires)
    await state.clear()
    await message.answer(f"✅ Aksiya qoshildi: <b>{data['title']}</b>", reply_markup=admin_kb(), parse_mode="HTML")


# ===== USERS & BROADCAST =====
@dp.message(F.text == "👥 Mijozlar")
async def show_users(message: Message):
    if message.from_user.id != ADMIN_ID: return
    users = await db.get_all_users()
    text = f"👥 <b>Mijozlar ({len(users)} ta):</b>\n\n"
    for u in users[:20]:
        text += f"- {u[2]} | @{u[3] or '-'} | {u[4] or '-'}\n"
    await message.answer(text, parse_mode="HTML")

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
            await bot.send_message(u[1], f"📢 {message.text}")
            sent += 1
        except: pass
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
            user_id=message.from_user.id,
            items=items,
            total_price=total,
            address=address,
            phone=phone,
            note=f"To'lov: {payment} | {note or ''}"
        )

        items_text = "\n".join([f"• {i['name']} x{i['qty']} — {i['price']*i['qty']:,.0f} so'm" for i in items])
        await message.answer(
            f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"🔖 Buyurtma #{oid}\n\n"
            f"{items_text}\n\n"
            f"💰 Jami: <b>{total:,.0f} so'm</b>\n"
            f"🚚 Yetkazib berish: {delivery}\n"
            f"💳 To'lov: {payment}\n"
            f"📍 {address}\n"
            f"📱 {phone}\n\n"
            f"⏳ Tez orada operatorimiz bog'lanadi!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )

        user = message.from_user
        await bot.send_message(
            ADMIN_ID,
            f"🆕 <b>YANGI BUYURTMA #{oid}</b> (Mini App)\n\n"
            f"👤 {name}\n"
            f"🔗 @{user.username or '-'} | 🆔 {user.id}\n\n"
            f"🛒 {items_text}\n\n"
            f"💰 {total:,.0f} so'm\n"
            f"🚚 {delivery}\n"
            f"💳 {payment}\n"
            f"📍 {address}\n"
            f"📱 {phone}"
            f"{chr(10)+'📝 '+note if note else ''}",
            reply_markup=order_status_kb(oid),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Mini App data xatosi: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")


# ===== MAIN =====
async def main():
    await db.create_tables()
    # API server va botni parallel ishlatish
    await asyncio.gather(
        start_api_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
