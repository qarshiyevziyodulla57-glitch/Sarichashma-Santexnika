from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from database import Database
from keyboards import admin_kb, main_menu_kb, order_status_kb, orders_filter_kb
from config import ADMIN_ID
import json

router = Router()
db = Database()


def is_admin(user_id):
    return user_id == ADMIN_ID


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


class BroadcastState(StatesGroup):
    message = State()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Siz admin emassiz!")
        return
    await message.answer(
        "Admin Panel - Xush kelibsiz!",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )


@router.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = await db.get_stats()
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami mijozlar: <b>{stats['users']}</b>\n"
        f"📦 Jami buyurtmalar: <b>{stats['orders']}</b>\n"
        f"🆕 Yangi buyurtmalar: <b>{stats['new_orders']}</b>\n"
        f"💰 Jami daromad: <b>{stats['revenue']:,.0f} so'm</b>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📦 Buyurtmalar")
async def show_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Qaysi buyurtmalarni ko'rmoqchisiz?",
        reply_markup=orders_filter_kb()
    )


@router.callback_query(F.data.startswith("filter_"))
async def filter_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    filter_val = callback.data.split("_")[1]
    status = None if filter_val == "all" else filter_val
    orders = await db.get_all_orders(status)
    if not orders:
        await callback.message.edit_text("Buyurtmalar yo'q.")
        return

    STATUS_EMOJI = {
        "yangi": "🆕", "jarayonda": "⚙️",
        "yetkazilmoqda": "🚚", "yetkazildi": "✅", "bekor": "❌"
    }
    for order in orders[:15]:
        o_id, u_id, items_json, total, address, phone, status_val, note, created, _ = (
            order[0], order[1], order[2], order[3], order[4],
            order[5], order[6], order[7], order[8], order[9]
        )
        try:
            items = json.loads(items_json)
            items_text = "\n".join([f"  - {i['name']} x{i['qty']}" for i in items])
        except:
            items_text = items_json

        emoji = STATUS_EMOJI.get(status_val, "📦")
        text = (
            f"Buyurtma #{o_id}\n"
            f"{emoji} {status_val}\n"
            f"User ID: {u_id}\n"
            f"Mahsulotlar:\n{items_text}\n"
            f"Jami: {total:,.0f} so'm\n"
            f"{address}\n"
            f"{phone}\n"
            f"{'Izoh: ' + note if note else ''}\n"
            f"{created[:16]}"
        )
        await callback.message.answer(
            text,
            reply_markup=order_status_kb(o_id),
            parse_mode="HTML"
        )
    await callback.message.delete()


@router.callback_query(F.data.startswith("setstatus_"))
async def set_order_status(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    order_id = int(parts[1])
    new_status = parts[2]
    await db.update_order_status(order_id, new_status)
    STATUS_EMOJI = {
        "yangi": "🆕", "jarayonda": "⚙️",
        "yetkazilmoqda": "🚚", "yetkazildi": "✅", "bekor": "❌"
    }
    emoji = STATUS_EMOJI.get(new_status, "📦")
    await callback.answer(f"Status yangilandi: {emoji} {new_status}", show_alert=True)
    order = await db.get_order(order_id)
    if order:
        from aiogram import Bot
        from config import BOT_TOKEN
        bot = Bot(token=BOT_TOKEN)
        try:
            notify_text = (
                f"📦 <b>Buyurtma #{order_id} holati yangilandi!</b>\n\n"
                f"{emoji} Yangi holat: <b>{new_status}</b>"
            )
            await bot.send_message(order[1], notify_text, parse_mode="HTML")
        except:
            pass


# ===== MAHSULOT QO'SHISH =====

@router.message(F.text == "➕ Mahsulot qo'shish")
async def start_add_product(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    categories = await db.get_categories()
    text = "📂 <b>Kategoriyani raqami bilan tanlang:</b>\n\n"
    for cat in categories:
        text += f"{cat[0]}. {cat[2]} {cat[1]}\n"
    await state.set_state(AddProductState.category)
    await message.answer(text, parse_mode="HTML")


@router.message(AddProductState.category)
async def got_category(message: Message, state: FSMContext):
    try:
        cat_id = int(message.text)
        await state.update_data(category_id=cat_id)
        await state.set_state(AddProductState.name)
        await message.answer("📝 Mahsulot nomini kiriting:")
    except:
        await message.answer("Raqam kiriting!")


@router.message(AddProductState.name)
async def got_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductState.description)
    await message.answer("📄 Tavsif kiriting (yoki: Yoq):")


@router.message(AddProductState.description)
async def got_description(message: Message, state: FSMContext):
    desc = None if message.text.lower() in ["yoq", "-"] else message.text
    await state.update_data(description=desc)
    await state.set_state(AddProductState.price)
    await message.answer("💰 Narxini kiriting (so'mda):")


@router.message(AddProductState.price)
async def got_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(" ", "").replace(",", ""))
        await state.update_data(price=price)
        await state.set_state(AddProductState.old_price)
        await message.answer("💸 Eski narxini kiriting (chegirma uchun) yoki: Yoq")
    except:
        await message.answer("Narxni to'g'ri kiriting!")


@router.message(AddProductState.old_price)
async def got_old_price(message: Message, state: FSMContext):
    if message.text.lower() in ["yoq", "-"]:
        await state.update_data(old_price=None)
    else:
        try:
            old_price = float(message.text.replace(" ", "").replace(",", ""))
            await state.update_data(old_price=old_price)
        except:
            await state.update_data(old_price=None)
    await state.set_state(AddProductState.stock)
    await message.answer("📦 Ombordagi miqdorini kiriting:")


@router.message(AddProductState.stock)
async def got_stock(message: Message, state: FSMContext):
    try:
        stock = int(message.text)
        await state.update_data(stock=stock)
        await state.set_state(AddProductState.image)
        await message.answer(
            "🖼 Mahsulot rasmini yuboring\n\n"
            "Telegramdan rasm fayl yuborishingiz mumkin\n"
            "Rasm bo'lmasa: Yoq deb yozing"
        )
    except:
        await message.answer("Raqam kiriting!")


@router.message(AddProductState.image, F.photo)
async def got_image_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    data = await state.get_data()
    await db.add_product(
        category_id=data["category_id"],
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        old_price=data.get("old_price"),
        stock=data["stock"],
        image_url=file_id
    )
    await state.clear()
    await message.answer(
        f"✅ <b>'{data['name']}'</b> rasmli holda qo'shildi!",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )


@router.message(AddProductState.image, F.text)
async def got_image_text(message: Message, state: FSMContext):
    img = None if message.text.lower() in ["yoq", "-"] else message.text
    data = await state.get_data()
    await db.add_product(
        category_id=data["category_id"],
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        old_price=data.get("old_price"),
        stock=data["stock"],
        image_url=img
    )
    await state.clear()
    await message.answer(
        f"✅ <b>'{data['name']}'</b> qo'shildi!",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )


# ===== MAHSULOTLARNI BOSHQARISH (TAHRIRLASH / O'CHIRISH) =====

@router.message(F.text == "🗂 Mahsulotlar")
async def manage_products(message: Message):
    if not is_admin(message.from_user.id):
        return
    products = await db.get_all_products()
    if not products:
        await message.answer("Mahsulotlar yo'q.")
        return

    text = "🗂 <b>Mahsulotlar ro'yxati:</b>\n\nTahrirlash yoki o'chirish uchun ID ni yozing:\n\n"
    for p in products:
        p_id, cat_id, name, desc, price, old_price, img, stock = (
            p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]
        )
        text += f"🔹 <b>ID:{p_id}</b> — {name} — {price:,.0f} so'm (ombor: {stock})\n"

    await message.answer(text, parse_mode="HTML", reply_markup=products_manage_inline())


def products_manage_inline():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Tahrirlash", callback_data="manage_edit")
    builder.button(text="🗑 O'chirish", callback_data="manage_delete")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data == "manage_edit")
async def start_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProductState.select)
    await state.update_data(action="edit")
    await callback.message.answer("✏️ Tahrirlash uchun mahsulot ID raqamini kiriting:")


@router.callback_query(F.data == "manage_delete")
async def start_delete(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProductState.select)
    await state.update_data(action="delete")
    await callback.message.answer("🗑 O'chirish uchun mahsulot ID raqamini kiriting:")


@router.message(EditProductState.select)
async def select_product(message: Message, state: FSMContext):
    try:
        product_id = int(message.text)
        product = await db.get_product(product_id)
        if not product:
            await message.answer("Mahsulot topilmadi! ID ni to'g'ri kiriting.")
            return

        data = await state.get_data()
        action = data.get("action")

        if action == "delete":
            await db.delete_product(product_id)
            await state.clear()
            await message.answer(
                f"✅ <b>'{product[2]}'</b> o'chirildi!",
                reply_markup=admin_kb(),
                parse_mode="HTML"
            )

        elif action == "edit":
            await state.update_data(product_id=product_id)
            await state.set_state(EditProductState.field)

            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="📝 Nom", callback_data="edit_name")
            builder.button(text="📄 Tavsif", callback_data="edit_description")
            builder.button(text="💰 Narx", callback_data="edit_price")
            builder.button(text="💸 Eski narx", callback_data="edit_old_price")
            builder.button(text="📦 Ombor", callback_data="edit_stock")
            builder.button(text="🖼 Rasm", callback_data="edit_image")
            builder.adjust(2)

            await message.answer(
                f"✏️ <b>'{product[2]}'</b> — qaysi maydonni o'zgartirmoqchisiz?",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer("Faqat raqam kiriting!")


@router.callback_query(EditProductState.field, F.data.startswith("edit_"))
async def select_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")
    await state.update_data(field=field)
    await state.set_state(EditProductState.value)

    prompts = {
        "name": "📝 Yangi nomni kiriting:",
        "description": "📄 Yangi tavsifni kiriting (yoki: Yoq):",
        "price": "💰 Yangi narxni kiriting (so'mda):",
        "old_price": "💸 Yangi eski narxni kiriting (yoki: Yoq):",
        "stock": "📦 Yangi miqdorni kiriting:",
        "image": "🖼 Yangi rasmni yuboring yoki: Yoq",
    }
    await callback.message.answer(prompts.get(field, "Yangi qiymatni kiriting:"))


@router.message(EditProductState.value, F.photo)
async def got_edit_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    await db.update_product_field(data["product_id"], "image_url", file_id)
    await state.clear()
    await message.answer("✅ Rasm yangilandi!", reply_markup=admin_kb())


@router.message(EditProductState.value, F.text)
async def got_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    field = data["field"]
    value = message.text

    field_map = {
        "name": "name",
        "description": "description",
        "price": "price",
        "old_price": "old_price",
        "stock": "stock",
        "image": "image_url",
    }

    db_field = field_map.get(field)

    if field in ["price", "stock"]:
        try:
            value = float(value.replace(" ", "").replace(",", "")) if field == "price" else int(value)
        except:
            await message.answer("To'g'ri raqam kiriting!")
            return
    elif field in ["description", "old_price", "image"]:
        if value.lower() in ["yoq", "-"]:
            value = None
        elif field == "old_price":
            try:
                value = float(value.replace(" ", "").replace(",", ""))
            except:
                value = None

    await db.update_product_field(product_id, db_field, value)
    await state.clear()
    await message.answer(
        f"✅ Mahsulot yangilandi!",
        reply_markup=admin_kb()
    )


# ===== MIJOZLAR =====

@router.message(F.text == "👥 Mijozlar")
async def show_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    users = await db.get_all_users()
    text = f"👥 <b>Mijozlar ({len(users)} ta):</b>\n\n"
    for u in users[:20]:
        u_id, tg_id, name, username, phone, created = (
            u[0], u[1], u[2], u[3], u[4], u[5]
        )
        text += f"- {name} | @{username or '-'} | {phone or '-'}\n"
    await message.answer(text, parse_mode="HTML")


# ===== AKSIYA QO'SHISH =====

@router.message(F.text == "🎉 Aksiya qo'shish")
async def redirect_to_promo(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Aksiya qo'shish uchun discounts handlerda...")


# ===== BROADCAST =====

@router.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastState.message)
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:")


@router.message(BroadcastState.message)
async def do_broadcast(message: Message, state: FSMContext):
    from aiogram import Bot
    from config import BOT_TOKEN
    users = await db.get_all_users()
    bot = Bot(token=BOT_TOKEN)
    sent = 0
    for user in users:
        try:
            await bot.send_message(user[1], f"📢 {message.text}")
            sent += 1
        except:
            pass
    await state.clear()
    await message.answer(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi!", reply_markup=admin_kb())


@router.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message):
    await message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
