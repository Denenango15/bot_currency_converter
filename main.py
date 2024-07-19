import asyncio
import logging
import requests
import xml.etree.ElementTree as ET

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        'Привет, я помогу тебе с курсом валют.\n'
        'Используйте команду в формате: /exchange <валюта_источник> <валюта_целевая> <сумма>')


@dp.message(Command('exchange'))
async def get_exchange(message: Message):
    args = message.text.split()
    if len(args) != 4:
        await message.answer('Используйте команду в формате: /exchange <валюта_источник> <валюта_целевая> <сумма>')
        return

    base_currency = args[1].upper()
    target_currency = args[2].upper()
    amount = float(args[3])

    response = requests.get('https://cbr.ru/scripts/XML_daily.asp')
    root = ET.fromstring(response.content)

    base_rate = None
    target_rate = None

    for value in root.findall('.//Valute'):
        char_code = value.find('CharCode').text
        value = float(value.find('Value').text.replace(',', '.'))

        if char_code == base_currency:
            base_rate = value
        elif char_code == target_currency:
            target_rate = value

    if base_rate is None or target_rate is None:
        await message.answer(f'Не удалось найти курсы валют для {base_currency} или {target_currency}')
        return

    result = amount * base_rate / target_rate
    await message.answer(f'{amount} {base_currency} = {result} {target_currency}')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Программа завершена')
