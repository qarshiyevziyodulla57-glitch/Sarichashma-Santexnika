from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database import Database
from keyboards import categories_kb, products_kb, product_detail_kb, main_menu_kb

router = Router()
db = Database()


@router.message(F.text == "🛍 Katalog")
async def show_catalog(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Hozircha kategoriyalar yo'q.")
        return

    await message.answer(
        "📂 <b>Kategoriyani tanlang:</b>",
        reply_markup=categories_kb(categories),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_cats")
async def back_to_categories(callback: CallbackQuery):
    categories = await db.get_categories()
    await callback.message.edit_text(
        "📂 <b>Kategoriyani tanlang:</b>",
        reply_markup=categories_kb(categories),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("cat_"))
async def show_products(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    products = await db.get_products_by_category(category_id)

    if not products:
        await callback.answer("Bu kategoriyada mahsulot yo'q", show_alert=True)
        return

    await callback.message.edit_text(
        f"🔧 <b>Mahsulotlar ({len(products)} ta):</b>",
        reply_markup=products_kb(products, category_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("prod_"))
async def show_product_detail(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = await db.get_product(product_id)

    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    # product: id, cat_id, name, description, price, old_price, image_url, stock, is_active, created_at
    p_id, cat_id, name, desc, price, old_price, img, stock = (
        product[0], product[1], product[2], product[3],
        product[4], product[5], product[6], product[7]
    )

    price_text = f"💰 Narxi: <b>{price:,.0f} so'm</b>"
    if old_price and old_price > price:
        discount = int((1 - price / old_price) * 100)
        price_text = (
            f"💰 Narxi: <b>{price:,.0f} so'm</b>\n"
            f"~~{old_price:,.0f} so'm~~ 🔴 -{discount}% chegirma"
        )

    stock_text = f"✅ Mavjud: {stock} dona" if stock > 0 else "❌ Mavjud emas"

    text = (
        f"🔧 <b>{name}</b>\n\n"
        f"{desc or 'Tavsif yo\'q'}\n\n"
        f"{price_text}\n"
        f"{stock_text}"
    )

    if img:
        try:
            await callback.message.answer_photo(
                photo=img,
                caption=text,
                reply_markup=product_detail_kb(p_id),
                parse_mode="HTML"
            )
            await callback.message.delete()
        except:
            await callback.message.edit_text(
                text,
                reply_markup=product_detail_kb(p_id),
                parse_mode="HTML"
            )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=product_detail_kb(p_id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("addcart_"))
async def add_to_cart(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = await db.get_product(product_id)

    if not product or product[7] == 0:
        await callback.answer("❌ Mahsulot mavjud emas!", show_alert=True)
        return

    await db.add_to_cart(callback.from_user.id, product_id)
    await callback.answer(f"✅ '{product[2]}' savatga qo'shildi!", show_alert=True)
