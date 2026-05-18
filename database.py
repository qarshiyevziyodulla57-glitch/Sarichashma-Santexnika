import aiosqlite
import json
from datetime import datetime

DB_PATH = "santexnika.db"


class Database:
    async def create_tables(self):
        async with aiosqlite.connect(DB_PATH) as db:
            # Foydalanuvchilar
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Kategoriyalar
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    emoji TEXT DEFAULT '📦',
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Mahsulotlar
            await db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    old_price REAL,
                    image_url TEXT,
                    stock INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            """)

            # Buyurtmalar
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    items TEXT,
                    total_price REAL,
                    address TEXT,
                    phone TEXT,
                    status TEXT DEFAULT 'yangi',
                    note TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            """)

            # Savat (korzinka)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cart (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_id INTEGER,
                    quantity INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)

            # Aksiyalar
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promotions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    discount_percent INTEGER,
                    image_url TEXT,
                    is_active INTEGER DEFAULT 1,
                    expires_at TEXT
                )
            """)

            await db.commit()

            # Default kategoriyalar qo'shish
            await self._add_default_categories(db)

    async def _add_default_categories(self, db):
        count = await db.execute("SELECT COUNT(*) FROM categories")
        row = await count.fetchone()
        if row[0] == 0:
            categories = [
                ("Kranlar va quvurlar", "🚰"),
                ("Dushlar va vannalar", "🚿"),
                ("Unitaz va rakovinalar", "🚽"),
                ("Quvurlar va fitinglar", "🔧"),
                ("Nasoslar", "💧"),
                ("Filtrlar va tozalash", "🧹"),
                ("Isitish tizimlari", "🔥"),
                ("Kanalizatsiya", "🔩"),
                ("Elektrika mahsulotlari", "⚡"),
                ("Boshqa jihozlar", "📦"),
            ]
            await db.executemany(
                "INSERT INTO categories (name, emoji) VALUES (?, ?)",
                categories
            )
            await db.commit()

    # ===== USERS =====
    async def add_user(self, telegram_id, full_name, username=None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (telegram_id, full_name, username)
                VALUES (?, ?, ?)
            """, (telegram_id, full_name, username))
            await db.commit()

    async def get_all_users(self):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
            return await cursor.fetchall()

    async def update_user_phone(self, telegram_id, phone):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET phone=? WHERE telegram_id=?",
                (phone, telegram_id)
            )
            await db.commit()

    # ===== CATEGORIES =====
    async def get_categories(self):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM categories WHERE is_active=1"
            )
            return await cursor.fetchall()

    async def add_category(self, name, emoji="📦"):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO categories (name, emoji) VALUES (?, ?)",
                (name, emoji)
            )
            await db.commit()

    # ===== PRODUCTS =====
    async def get_products_by_category(self, category_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT p.*, c.name as cat_name
                FROM products p
                JOIN categories c ON p.category_id = c.id
                WHERE p.category_id=? AND p.is_active=1
            """, (category_id,))
            return await cursor.fetchall()

    async def get_product(self, product_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM products WHERE id=?", (product_id,)
            )
            return await cursor.fetchone()

    async def add_product(self, category_id, name, description, price, stock, old_price=None, image_url=None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO products (category_id, name, description, price, old_price, stock, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (category_id, name, description, price, old_price, stock, image_url))
            await db.commit()

    async def delete_product(self, product_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE products SET is_active=0 WHERE id=?", (product_id,))
            await db.commit()

    async def update_product(self, product_id, name=None, description=None, price=None, old_price=None, stock=None):
        async with aiosqlite.connect(DB_PATH) as db:
            if name:
                await db.execute("UPDATE products SET name=? WHERE id=?", (name, product_id))
            if description is not None:
                await db.execute("UPDATE products SET description=? WHERE id=?", (description, product_id))
            if price:
                await db.execute("UPDATE products SET price=? WHERE id=?", (price, product_id))
            if old_price is not None:
                await db.execute("UPDATE products SET old_price=? WHERE id=?", (old_price, product_id))
            if stock is not None:
                await db.execute("UPDATE products SET stock=? WHERE id=?", (stock, product_id))
            await db.commit()

    async def update_product_field(self, product_id, field, value):
        allowed = ["name", "description", "price", "old_price", "stock", "image_url"]
        if field not in allowed:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE products SET {field}=? WHERE id=?", (value, product_id))
            await db.commit()

    async def update_product_image(self, product_id, image_url):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE products SET image_url=? WHERE id=?", (image_url, product_id))
            await db.commit()

    async def get_all_products(self):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT p.*, c.name as cat_name FROM products p
                JOIN categories c ON p.category_id = c.id
                WHERE p.is_active=1
            """)
            return await cursor.fetchall()

    # ===== CART =====
    async def add_to_cart(self, user_id, product_id, quantity=1):
        async with aiosqlite.connect(DB_PATH) as db:
            existing = await db.execute(
                "SELECT id, quantity FROM cart WHERE user_id=? AND product_id=?",
                (user_id, product_id)
            )
            row = await existing.fetchone()
            if row:
                await db.execute(
                    "UPDATE cart SET quantity=? WHERE id=?",
                    (row[1] + quantity, row[0])
                )
            else:
                await db.execute(
                    "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
                    (user_id, product_id, quantity)
                )
            await db.commit()

    async def get_cart(self, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT c.id, p.name, p.price, c.quantity, (p.price * c.quantity) as total
                FROM cart c
                JOIN products p ON c.product_id = p.id
                WHERE c.user_id=?
            """, (user_id,))
            return await cursor.fetchall()

    async def remove_from_cart(self, cart_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM cart WHERE id=?", (cart_id,))
            await db.commit()

    async def clear_cart(self, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
            await db.commit()

    # ===== ORDERS =====
    async def create_order(self, user_id, items, total_price, address, phone, note=None):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                INSERT INTO orders (user_id, items, total_price, address, phone, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, json.dumps(items, ensure_ascii=False), total_price, address, phone, note))
            await db.commit()
            return cursor.lastrowid

    async def get_orders_by_user(self, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",
                (user_id,)
            )
            return await cursor.fetchall()

    async def get_all_orders(self, status=None):
        async with aiosqlite.connect(DB_PATH) as db:
            if status:
                cursor = await db.execute(
                    "SELECT * FROM orders WHERE status=? ORDER BY created_at DESC", (status,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM orders ORDER BY created_at DESC"
                )
            return await cursor.fetchall()

    async def update_order_status(self, order_id, status):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, order_id)
            )
            await db.commit()

    async def get_order(self, order_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
            return await cursor.fetchone()

    # ===== PROMOTIONS =====
    async def get_active_promotions(self):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM promotions WHERE is_active=1 ORDER BY id DESC"
            )
            return await cursor.fetchall()

    async def add_promotion(self, title, description, discount_percent, expires_at=None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO promotions (title, description, discount_percent, expires_at)
                VALUES (?, ?, ?, ?)
            """, (title, description, discount_percent, expires_at))
            await db.commit()

    # ===== STATS =====
    async def get_stats(self):
        async with aiosqlite.connect(DB_PATH) as db:
            users = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
            orders = await (await db.execute("SELECT COUNT(*) FROM orders")).fetchone()
            revenue = await (await db.execute(
                "SELECT SUM(total_price) FROM orders WHERE status='yetkazildi'"
            )).fetchone()
            new_orders = await (await db.execute(
                "SELECT COUNT(*) FROM orders WHERE status='yangi'"
            )).fetchone()
            return {
                "users": users[0],
                "orders": orders[0],
                "revenue": revenue[0] or 0,
                "new_orders": new_orders[0]
            }
