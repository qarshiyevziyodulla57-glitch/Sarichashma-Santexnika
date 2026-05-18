from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def main_menu_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🛍 Katalog"),
        KeyboardButton(text="🛒 Savatim")
    )
    builder.row(
        KeyboardButton(text="📦 Buyurtmalarim"),
        KeyboardButton(text="🎉 Aksiyalar")
    )
    builder.row(
        KeyboardButton(text="📞 Bog'lanish"),
        KeyboardButton(text="ℹ️ Haqimizda")
    )
    return builder.as_markup(resize_keyboard=True)


def admin_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Statistika"),
        KeyboardButton(text="📦 Buyurtmalar")
    )
    builder.row(
        KeyboardButton(text="➕ Mahsulot qo'shish"),
        KeyboardButton(text="🗂 Mahsulotlar")
    )
    builder.row(
        KeyboardButton(text="🎉 Aksiya qo'shish"),
        KeyboardButton(text="👥 Mijozlar")
    )
    builder.row(
        KeyboardButton(text="📢 Xabar yuborish"),
        KeyboardButton(text="🔙 Asosiy menyu")
    )
    return builder.as_markup(resize_keyboard=True)


def back_kb():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔙 Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def catalog_kb():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔙 Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def categories_kb(categories):
    builder = InlineKeyboardBuilder()
    for cat in categories:
        cat_id, name, emoji, _ = cat[0], cat[1], cat[2], cat[3]
        builder.button(
            text=f"{emoji} {name}",
            callback_data=f"cat_{cat_id}"
        )
    builder.adjust(2)
    return builder.as_markup()


def products_kb(products, category_id):
    builder = InlineKeyboardBuilder()
    for p in products:
        p_id, _, name = p[0], p[1], p[2]
        builder.button(
            text=f"🔧 {name}",
            callback_data=f"prod_{p_id}"
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="🔙 Kategoriyalarga", callback_data="back_to_cats")
    )
    return builder.as_markup()


def product_detail_kb(product_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Savatga qo'shish", callback_data=f"addcart_{product_id}")
    builder.button(text="🔙 Orqaga", callback_data="back_to_cats")
    builder.adjust(1)
    return builder.as_markup()


def cart_kb(cart_items):
    builder = InlineKeyboardBuilder()
    for item in cart_items:
        cart_id, name = item[0], item[1]
        builder.button(
            text=f"❌ {name[:20]}...",
            callback_data=f"removecart_{cart_id}"
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout"),
        InlineKeyboardButton(text="🗑 Tozalash", callback_data="clearcart")
    )
    return builder.as_markup()


def order_status_kb(order_id):
    statuses = [
        ("🆕 Yangi", "yangi"),
        ("⚙️ Jarayonda", "jarayonda"),
        ("🚚 Yetkazilmoqda", "yetkazilmoqda"),
        ("✅ Yetkazildi", "yetkazildi"),
        ("❌ Bekor qilindi", "bekor")
    ]
    builder = InlineKeyboardBuilder()
    for label, status in statuses:
        builder.button(
            text=label,
            callback_data=f"setstatus_{order_id}_{status}"
        )
    builder.adjust(2)
    return builder.as_markup()


def orders_filter_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Yangi", callback_data="filter_yangi")
    builder.button(text="⚙️ Jarayonda", callback_data="filter_jarayonda")
    builder.button(text="🚚 Yetkazilmoqda", callback_data="filter_yetkazilmoqda")
    builder.button(text="✅ Barchasi", callback_data="filter_all")
    builder.adjust(2)
    return builder.as_markup()


def phone_kb():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True))
    builder.add(KeyboardButton(text="🔙 Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def product_manage_kb(product_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Nomini o'zgartir", callback_data=f"edit_name_{product_id}")
    builder.button(text="💰 Narxini o'zgartir", callback_data=f"edit_price_{product_id}")
    builder.button(text="📦 Miqdorini o'zgartir", callback_data=f"edit_stock_{product_id}")
    builder.button(text="📄 Tavsifni o'zgartir", callback_data=f"edit_desc_{product_id}")
    builder.button(text="🖼 Rasmni o'zgartir", callback_data=f"edit_image_{product_id}")
    builder.button(text="❌ Mahsulotni o'chir", callback_data=f"delete_prod_{product_id}")
    builder.button(text="🔙 Orqaga", callback_data="manage_products")
    builder.adjust(2)
    return builder.as_markup()


def manage_products_kb(products):
    builder = InlineKeyboardBuilder()
    for p in products:
        builder.button(
            text=f"🔧 {p[2][:30]}",
            callback_data=f"manage_prod_{p[0]}"
        )
    builder.adjust(1)
    return builder.as_markup()
