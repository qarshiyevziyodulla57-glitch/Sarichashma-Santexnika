from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import cart_kb, main_menu_kb, phone_kb
from config import ADMIN_ID
from aiogram import Bot
import json

router = Router()
db = Database()


class OrderState(StatesGroup):
    waiting_phone = State()
    waiting_address = State()
    waiting_note = State()


STATUS_EMOJI = {
    "yangi": "🆕",
    "jarayonda": "⚙️",
    "yetkazilmoqda": "🚚",
    "yetkazildi": "✅",
    "bekor": "❌"
}


@router.message(F.text == "🛒 Savatim")
async def show_cart(message: Message):
    cart = await db.get_cart(message.from_user.id)

    if not cart:
        await message.answer(
            "🛒 Savatingiz bo'sh!\n\nKatalogdan mahsulot tanlang.",
            reply_markup=main_menu_kb()
        )
        return

    total = sum(item[4] for item in cart)
    text = "🛒 <b>Savatingiz:</b>\n\n"

    for item in cart:
        _, name, price, qty, item_total = item
        text += f"• {name} — {qty} x {price:,.0f} = <b>{item_total:,.0f} so'm</b>\n"

    text += f"\n💰 <b>Jami: {total:,.0f} so'm</b>"

    await message.answer(text, reply_markup=cart_kb(cart), parse_mode="HTML")


@router.callback_query(F.data.startswith("removecart_"))
async def remove_from_cart(callback: CallbackQuery):
    cart_id = int(callback.data.split("_")[1])
    await db.remove_from_cart(cart_id)

    cart = await db.get_cart(callback.from_user.id)
    if not cart:
        await callback.message.edit_text("🛒 Savat bo'sh!")
        return

    total = sum(item[4] for item in cart)
    text = "🛒 <b>Savatingiz:</b>\n\n"
    for item in cart:
        _, name, price, qty, item_total = item
        text += f"• {name} — {qty} x {price:,.0f} = <b>{item_total:,.0f} so'm</b>\n"
    text += f"\n💰 <b>Jami: {total:,.0f} so'm</b>"

    await callback.message.edit_text(text, reply_markup=cart_kb(cart), parse_mode="HTML")


@router.callback_query(F.data == "clearcart")
async def clear_cart(callback: CallbackQuery):
    await db.clear_cart(callback.from_user.id)
    await callback.message.edit_text("🗑 Savat tozalandi!")


@router.callback_query(F.data == "checkout")
async def checkout_start(callback: CallbackQuery, state: FSMContext):
    cart = await db.get_cart(callback.from_user.id)
    if not cart:
        await callback.answer("Savat bo'sh!", show_alert=True)
        return

    await state.set_state(OrderState.waiting_phone)
    await callback.message.answer(
        "📱 Telefon raqamingizni yuboring yoki kiriting:\n"
        "Misol: +998901234567",
        reply_markup=phone_kb()
    )


@router.message(OrderState.waiting_phone, F.contact)
async def got_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await db.update_user_phone(message.from_user.id, phone)
    await state.set_state(OrderState.waiting_address)
    await message.answer(
        "📍 Yetkazib berish manzilingizni kiriting:\n"
        "Misol: Toshkent, Chilonzor, 5-kvartal, 12-uy",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(OrderState.waiting_phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    phone = message.text
    await state.update_data(phone=phone)
    await db.update_user_phone(message.from_user.id, phone)
    await state.set_state(OrderState.waiting_address)
    await message.answer(
        "📍 Yetkazib berish manzilingizni kiriting:",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(OrderState.waiting_address)
async def got_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(OrderState.waiting_note)
    await message.answer(
        "📝 Qo'shimcha izoh (ixtiyoriy):\n"
        "Misol: 3. qavatga ko'tarib keling\n\n"
        "Yo'q bo'lsa, <b>«Yo'q»</b> deb yozing",
        parse_mode="HTML"
    )


@router.message(OrderState.waiting_note)
async def got_note(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    note = None if message.text.lower() in ["yo'q", "yoq", "-"] else message.text

    cart = await db.get_cart(message.from_user.id)
    total = sum(item[4] for item in cart)

    items = [{"name": item[1], "price": item[2], "qty": item[3]} for item in cart]

    order_id = await db.create_order(
        user_id=message.from_user.id,
        items=items,
        total_price=total,
        address=data["address"],
        phone=data["phone"],
        note=note
    )

    await db.clear_cart(message.from_user.id)
    await state.clear()

    # Mijozga xabar
    items_text = "\n".join([f"• {i['name']} x{i['qty']} — {i['price']*i['qty']:,.0f} so'm" for i in items])
    confirm_text = (
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🔖 Buyurtma №{order_id}\n\n"
        f"{items_text}\n\n"
        f"💰 Jami: <b>{total:,.0f} so'm</b>\n"
        f"📍 Manzil: {data['address']}\n"
        f"📱 Tel: {data['phone']}\n"
        f"{'📝 Izoh: ' + note if note else ''}\n\n"
        f"⏳ Tez orada operatorimiz siz bilan bog'lanadi!"
    )
    await message.answer(confirm_text, reply_markup=main_menu_kb(), parse_mode="HTML")

    # Adminga xabar
    user = message.from_user
    admin_text = (
        f"🆕 <b>YANGI BUYURTMA #{order_id}</b>\n\n"
        f"👤 Mijoz: {user.full_name}\n"
        f"🔗 @{user.username or 'username_yoq'}\n"
        f"🆔 ID: {user.id}\n\n"
        f"🛒 Buyurtma:\n{items_text}\n\n"
        f"💰 Jami: <b>{total:,.0f} so'm</b>\n"
        f"📍 Manzil: {data['address']}\n"
        f"📱 Tel: {data['phone']}\n"
        f"{'📝 Izoh: ' + note if note else ''}"
    )

    from keyboards import order_status_kb
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=order_status_kb(order_id), parse_mode="HTML")


@router.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: Message):
    orders = await db.get_orders_by_user(message.from_user.id)

    if not orders:
        await message.answer("📦 Siz hali buyurtma bermagansiz.")
        return

    text = "📦 <b>Buyurtmalaringiz:</b>\n\n"
    for order in orders[:10]:
        o_id, u_id, items_json, total, address, phone, status, note, created, updated = (
            order[0], order[1], order[2], order[3], order[4],
            order[5], order[6], order[7], order[8], order[9]
        )
        emoji = STATUS_EMOJI.get(status, "📦")
        text += (
            f"🔖 <b>Buyurtma #{o_id}</b>\n"
            f"{emoji} Holat: {status.capitalize()}\n"
            f"💰 Summa: {total:,.0f} so'm\n"
            f"📅 Sana: {created[:10]}\n\n"
        )

    await message.answer(text, parse_mode="HTML")
