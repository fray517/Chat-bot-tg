import asyncio
import logging
import os
import sqlite3
import random
from typing import Optional

import aiohttp
from aiogram import Bot
from aiogram import Dispatcher
from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.state import State
from aiogram.fsm.state import StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup
from dotenv import load_dotenv

def _get_token() -> str:
    """Возвращает токен бота из окружения."""

    load_dotenv()
    token: Optional[str] = os.getenv("TOKEN")
    if not token:
        raise RuntimeError(
            "Не найден TOKEN. Создайте файл .env рядом с main.py и добавьте "
            "строку TOKEN=ваш_токен_бота"
        )
    return token

bot = Bot(token=_get_token())
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)

button_registr = KeyboardButton(text="Регистрация в телеграм боте")
button_exchange_rates = KeyboardButton(text="Курс валют")
button_tips = KeyboardButton(text="Советы по экономии")
button_finances = KeyboardButton(text="Личные финансы")

keyboard = ReplyKeyboardMarkup(keyboard=[
    [button_registr, button_exchange_rates],
    [button_tips, button_finances]
], resize_keyboard=True)

conn = sqlite3.connect("user.db")
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE,
    name TEXT,
    category1 TEXT,
    category2 TEXT,
    category3 TEXT,
    expenses1 REAL,
    expenses2 REAL,
    expenses3 REAL
    )
''')
conn.commit()

class FinancesForm(StatesGroup):
    category1 = State()
    expenses1 = State()
    category2 = State()
    expenses2 = State()
    category3 = State()
    expenses3 = State()

@dp.message(Command('start'))
async def send_start(message: Message) -> None:
    await message.answer(
        "Привет! Я ваш личный финансовый помощник. "
        "Выберите одну из опций в меню:",
        reply_markup=keyboard,
    )

@dp.message(F.text == "Регистрация в телеграм боте")
async def registration(message: Message) -> None:
    telegram_id = message.from_user.id
    name = message.from_user.full_name
    cursor.execute('''SELECT * FROM users WHERE telegram_id = ?''', (telegram_id,))
    user = cursor.fetchone()
    if user:
        await message.answer("Вы уже зарегистрированы!")
    else:
        cursor.execute('''INSERT INTO users (telegram_id, name) VALUES (?, ?)''', (telegram_id, name))
        conn.commit()
        await message.answer("Вы успешно зарегистрированы!")

@dp.message(F.text == "Курс валют")
async def exchange_rates(message: Message) -> None:
    url = (
        "https://v6.exchangerate-api.com/"
        "v6/5de928c47701b2b5d99ae5df/latest/USD"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    await message.answer(
                        "Не удалось получить данные о курсе валют!",
                    )
                    return
                data = await response.json()

        rates = data["conversion_rates"]
        usd_to_rub = float(rates["RUB"])
        eur_per_usd = float(rates["EUR"])
        eur_to_rub = usd_to_rub / eur_per_usd

        await message.answer(
            f"1 USD - {usd_to_rub:.2f} RUB\n"
            f"1 EUR - {eur_to_rub:.2f} RUB",
        )
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, ValueError):
        await message.answer("Произошла ошибка при получении курса валют.")

@dp.message(F.text == "Советы по экономии")
async def send_tips(message: Message):
    tips = [
        "Совет 1: Ведите бюджет и следите за своими расходами.",
        "Совет 2: Откладывайте часть доходов на сбережения.",
        "Совет 3: Покупайте товары по скидкам и распродажам."
    ]
    tip = random.choice(tips)
    await message.answer(tip)
    
@dp.message(F.text == "Личные финансы")
async def finances(message: Message, state: FSMContext):
    await state.set_state(FinancesForm.category1)
    await message.reply("Введите первую категорию расходов:")

@dp.message(FinancesForm.category1)
async def finances(message: Message, state: FSMContext):
    await state.update_data(category1 = message.text)
    await state.set_state(FinancesForm.expenses1)
    await message.reply("Введите расходы для категории 1:") 
   
@dp.message(FinancesForm.expenses1)
async def finances(message: Message, state: FSMContext):
    await state.update_data(expenses1 = float(message.text))
    await state.set_state(FinancesForm.category2)
    await message.reply("Введите вторую категорию расходов:")
    
@dp.message(FinancesForm.category2)
async def finances(message: Message, state: FSMContext):
    await state.update_data(category2 = message.text)
    await state.set_state(FinancesForm.expenses2)
    await message.reply("Введите расходы для категории 2:")

@dp.message(FinancesForm.expenses2)
async def finances(message: Message, state: FSMContext):
    await state.update_data(expenses2 = float(message.text))
    await state.set_state(FinancesForm.category3)
    await message.reply("Введите третью категорию расходов:")

@dp.message(FinancesForm.category3)
async def finances(message: Message, state: FSMContext):
    await state.update_data(category3 = message.text)
    await state.set_state(FinancesForm.expenses3)
    await message.reply("Введите расходы для категории 3:")
   
@dp.message(FinancesForm.expenses3)
async def finances(message: Message, state: FSMContext):
    data = await state.get_data()
    telegarm_id = message.from_user.id
    cursor.execute('''UPDATE users SET category1 = ?, expenses1 = ?, category2 = ?, expenses2 = ?, category3 = ?, expenses3 = ? WHERE telegram_id = ?''',
                   (data['category1'], data['expenses1'], data['category2'], data['expenses2'], data['category3'], float(message.text), telegarm_id))
    conn.commit()
    await state.clear()

    await message.answer("Категории и расходы сохранены!")

async def main() -> None:
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())