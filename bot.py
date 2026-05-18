import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID
from database import Database
from keyboards import main_menu_kb
from handlers import catalog, orders, admin, discounts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()


async def main():
    await db.create_tables()

    dp.include_router(catalog.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)
    dp.include_router(discounts.router)

    @dp.message(CommandStart())
    async def start(message: Message):
        user = message.from_user
        await db.add_user(user.id, user.full_name, user.username)

        welcome_text = (
            f"👋 Assalomu alaykum, <b>{user.first_name}</b>!\n\n"
            f"🔧 <b>Sarichashma Santexnika</b> botiga xush kelibsiz!\n\n"
            f"Bizda siz topasiz:\n"
            f"🚿 Santexnika mahsulotlari\n"
            f"⚡ Elektrika mahsulotlari\n\n"
            f"📍 Samarqand viloyati, Jomboy tuman, Sarichashma qishloq\n"
            f"⏰ Ish vaqti: 07:00 - 20:00\n\n"
            f"Quyidagi menyudan tanlang:"
        )
        await message.answer(welcome_text, reply_markup=main_menu_kb(), parse_mode="HTML")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
