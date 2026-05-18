from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import admin_kb, main_menu_kb
from config import ADMIN_ID

router = Router()
db = Database()


class AddPromoState(StatesGroup):
    title = State()
    description = State()
    discount = State()
    expires = State()


@router.message(F.text == "🎉 Aksiyalar")
async def show_promotions(message: Message):
    promos = await db.get_active_promotions()

    if not promos:
        await message.answer(
            "😔 Hozircha faol aksiyalar yo'q.\n\nTez orada yangi aksiyalar bo'ladi! 🎉",
            reply_markup=main_menu_kb()
        )
        return

    text = "🎉 <b>Joriy aksiyalar va chegirmalar:</b>\n\n"
    for promo in promos:
        p_id, title, desc, discount, img, is_active, expires = (
            promo[0], promo[1], promo[2], promo[3],
            promo[4], promo[5], promo[6]
        )
        text += (
            f"🔥 <b>{title}</b>\n"
            f"{desc or ''}\n"
            f"{'💸 Chegirma: ' + str(discount) + '%' if discount else ''}\n"
            f"{'📅 Muddati: ' + expires if expires else ''}\n\n"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())


@router.message(F.text == "🎉 Aksiya qo'shish")
async def start_add_promo(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddPromoState.title)
    await message.answer("📝 Aksiya nomini kiriting:")


@router.message(AddPromoState.title)
async def got_promo_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddPromoState.description)
    await message.answer("📄 Aksiya tavsifini kiriting (yoki: Yoq):")


@router.message(AddPromoState.description)
async def got_promo_desc(message: Message, state: FSMContext):
    desc = None if message.text.lower() in ["yoq", "-"] else message.text
    await state.update_data(description=desc)
    await state.set_state(AddPromoState.discount)
    await message.answer("💸 Chegirma foizini kiriting (masalan: 20) yoki: Yoq")


@router.message(AddPromoState.discount)
async def got_discount(message: Message, state: FSMContext):
    if message.text.lower() in ["yoq", "-"]:
        await state.update_data(discount=None)
    else:
        try:
            await state.update_data(discount=int(message.text))
        except:
            await state.update_data(discount=None)
    await state.set_state(AddPromoState.expires)
    await message.answer("📅 Muddatini kiriting (masalan: 31.12.2025) yoki: Yoq")


@router.message(AddPromoState.expires)
async def got_expires(message: Message, state: FSMContext):
    expires = None if message.text.lower() in ["yoq", "-"] else message.text
    data = await state.get_data()
    await db.add_promotion(
        title=data["title"],
        description=data.get("description"),
        discount_percent=data.get("discount"),
        expires_at=expires
    )
    await state.clear()
    await message.answer(
        f"✅ Aksiya qoshildi: <b>{data['title']}</b>",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )


@router.message(F.text == "📞 Bog'lanish")
async def contact_info(message: Message):
    text = (
        "📞 <b>Biz bilan boglanish:</b>\n\n"
        "📱 Tel: +998 88 894 59 00\n"
        "📱 Tel: +998 94 282 62 66\n"
        "📍 Manzil: Samarqand viloyati, Jomboy tuman, Sarichashma qishloq\n"
        "⏰ Ish vaqti: 07:00 - 20:00\n"
        "💬 Telegram: https://t.me/sarichashma_santexnika"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "ℹ️ Haqimizda")
async def about_us(message: Message):
    text = (
        "ℹ️ <b>Sarichashma Santexnika haqida</b>\n\n"
        "Biz santexnika va elektrika mahsulotlari sohasida ishonchli xizmat korsatamiz.\n\n"
        "Bizda mavjud:\n"
        "• Santexnika mahsulotlari\n"
        "• Elektrika mahsulotlari\n\n"
        "Bizning afzalliklarimiz:\n"
        "• Sifatli mahsulotlar\n"
        "• Qulay narxlar\n"
        "• Tez yetkazib berish\n"
        "• Kafolat va xizmat\n\n"
        "📍 Samarqand viloyati, Jomboy tuman, Sarichashma qishloq\n"
        "⏰ Ish vaqti: 07:00 - 20:00\n\n"
        "Bizdan xarid qiling!"
    )
    await message.answer(text, parse_mode="HTML")
