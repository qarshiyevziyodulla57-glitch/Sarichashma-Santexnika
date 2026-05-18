# 🔧 SanTex Do'kon Telegram Boti

## 📁 Fayl tuzilmasi
```
santexnika_bot/
├── bot.py              # Asosiy fayl
├── config.py           # Token va Admin ID
├── database.py         # Ma'lumotlar bazasi
├── keyboards.py        # Tugmalar
├── requirements.txt    # Kutubxonalar
└── handlers/
    ├── catalog.py      # Katalog
    ├── orders.py       # Buyurtmalar
    ├── admin.py        # Admin panel
    └── discounts.py    # Aksiyalar
```

## 🚀 O'rnatish va ishga tushirish

### 1. Python o'rnatish
Python 3.10+ versiyasi kerak: https://python.org

### 2. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 3. Token sozlash
`config.py` faylini oching va:
```python
BOT_TOKEN = "BU YERGA BOT TOKENINGIZNI YOZING"
ADMIN_ID = 7151724014  # Sizning ID (o'zgarmaydi)
```

### 4. Botni ishga tushirish
```bash
python bot.py
```

---

## 👤 Foydalanuvchi imkoniyatlari
- 🛍 Katalogni ko'rish (kategoriyalar bo'yicha)
- 🛒 Savatga qo'shish va buyurtma berish
- 📦 Buyurtmalar holatini kuzatish
- 🎉 Aksiyalar va chegirmalarni ko'rish
- 📞 Bog'lanish ma'lumotlari

## 🔐 Admin imkoniyatlari
`/admin` buyrug'i bilan kirish:
- 📊 Statistika (mijozlar, buyurtmalar, daromad)
- 📦 Buyurtmalarni boshqarish va status o'zgartirish
- ➕ Yangi mahsulot qo'shish
- 🎉 Aksiya qo'shish
- 👥 Mijozlar ro'yxati
- 📢 Barcha foydalanuvchilarga xabar yuborish

## 🌐 Hosting (bepul)
**Railway.app** da joylashtirish:
1. https://railway.app ga kiring
2. GitHub repoga yuklang
3. Deploy qiling

**Yoki VPS server** da:
```bash
# Screen yoki systemd bilan
screen -S santexbot
python bot.py
```
