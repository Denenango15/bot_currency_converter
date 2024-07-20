import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import redis

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from config import TOKEN, redis_port, redis_host

bot = Bot(token=TOKEN)
dp = Dispatcher()

rates = {}
last_update = datetime.min
redis_host = redis_host
redis_port = redis_port
redis = redis.Redis(host=redis_host, port=redis_port, encoding='utf8', db=0)


async def get_exchange_rates():
    global rates, last_update

    rates_key = 'exchange_rates'
    last_update_key = 'last_update'

    rates_in_redis = redis.get(rates_key)
    last_update_in_redis = redis.get(last_update_key)

    if rates_in_redis and last_update_in_redis:
        rates = eval(rates_in_redis)
        last_update_in_redis_str = last_update_in_redis.decode('utf-8')
        last_update = datetime.fromisoformat(last_update_in_redis_str)
        if datetime.now() - last_update > timedelta(hours=12):
            logging.info('Срок хранения данных в Redis превышает 12 часов, обновление...')
            rates, last_update = await fetch_exchange_rates()
            redis.set(rates_key, str(rates))
            redis.set(last_update_key, last_update.isoformat())
    else:
        logging.info('Нет данных в Redis, для извлечения и хранения...')
        rates, last_update = await fetch_exchange_rates()
        redis.set(rates_key, str(rates))
        redis.set(last_update_key, last_update.isoformat())

    rates['RUB'] = 1

    return rates


async def fetch_exchange_rates():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://cbr.ru/scripts/XML_daily.asp') as response:
            if response.status != 200:
                return None, None
            root = ET.fromstring(await response.text())
            rates = {}
            for value in root.findall('.//Valute'):
                char_code = value.find('CharCode').text
                value = float(value.find('Value').text.replace(',', '.'))
                rates[char_code] = value
            last_update = datetime.now()
            return rates, last_update


async def update_exchange_rates():
    while True:
        await asyncio.sleep(12 * 60 * 60)  # ждем 12 часов
        await get_exchange_rates()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer('Привет, я помогу тебе с курсом валют.')
    rates = await get_exchange_rates()
    await message.answer('Текущие курсы валют:\n' + '\n'.join(f'{k}: {v}' for k, v in rates.items()))
    await message.answer('Возможные пути перехода:\n'
                         '/start - начать работу с ботом\n'
                         '/exchange - конвертировать валюту\n'
                         '/rates - получить текущие курсы валют')


@dp.message(Command('exchange'))
async def get_exchange(message: Message):
    args = message.text.split()
    if len(args) < 3 or len(args) > 4:
        await message.answer(
            'Используйте команду в формате: /exchange <валюта 1> <валюта 2> <сумма> (USD RUB 10) или /rates чтобы получить весь список')
        return

    base_currency = args[1].upper()
    target_currency = 'RUB' if len(args) == 3 else args[2].upper()
    amount = float(args[len(args) - 1])

    if datetime.now() - last_update > timedelta(hours=24):
        await get_exchange_rates()

    if base_currency not in rates or target_currency not in rates:
        await message.answer(f'Не удалось найти курсы валют для {base_currency} или {target_currency}')
        return

    result = round(amount * rates[base_currency] / rates[target_currency], 2)

    if len(args) == 3:
        await message.answer(f'{amount} {base_currency} = {result} рублей')
    else:
        await message.answer(f'{amount} {base_currency} = {result} {target_currency}')


@dp.message(Command('rates'))
async def current_course(message: Message):
    if datetime.now() - last_update > timedelta(hours=24):
        await get_exchange_rates()

    await message.answer('Текущие курсы валют:\n' + '\n'.join(f'{k}: {v}' for k, v in rates.items()))


async def main():
    asyncio.create_task(update_exchange_rates())
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Программа завершена')
