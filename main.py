import os
import zipfile
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import TOKEN, IMAGE_PATH, URL_PATH
from database import init_db, add_image, get_images_by_tags, check_archive_exists, add_archive
from booru import Danbooru, Rule34, Safebooru, Gelbooru, Lolibooru, Yandere, Realbooru
import aiohttp
import orjson

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

boorus = {
    'danbooru': Danbooru,
    'rule34': Rule34,
    'safebooru': Safebooru,
    'lolibooru': Lolibooru,
    'gelbooru': Gelbooru,
    'realbooru': Realbooru,
    'yandere': Yandere
}

# Инициализация базы данных
asyncio.run(init_db())

@dp.message(F.text == "/start")
async def start_handler(message: types.Message):
    await message.reply("Привет! Отправь мне картинку и добавь к ней теги в формате booru.")

@dp.message(F.photo)
async def handle_image(message: types.Message, state: FSMContext):
    await message.reply("Введите теги для этой картинки:")
    await state.update_data(image_id=message.photo[-1].file_id)

@dp.message(F.text.startswith("/fetch"))
async def fetch_from_booru(message: types.Message):
    args = message.text.split()
    if len(args) < 3:
        await message.reply("Используйте: /fetch <booru> <теги>")
        return

    booru_name = args[1]
    tags = args[2]
    
    if booru_name.lower() in boorus.keys():
        booru = boorus[booru_name.lower()]()
    else:
        await message.reply("Поддерживаемые booru: danbooru, rule34, safebooru, gelbooru, lolibooru, realbooru, yandere.")
        return
    
    results = await booru.search(query=tags.split(' -- ')[0], block=tags.split(' -- ')[1])
    resps = orjson.loads(results)
    
    for resp in resps:
        img_url = resp["file_url"]
        file_name = os.path.basename(img_url)
        file_path = os.path.join(IMAGE_PATH, file_name)
        async with aiohttp.ClientSession() as session:
            async with session.get(img_url) as resp:
                with open(file_path, 'wb') as f:
                    f.write(await resp.read())
        await add_image(file_path, tags)
    
    await message.reply(f"Загружено {len(images)} изображений с тегами {tags}.")

@dp.message(F.text)
async def handle_tags(message: types.Message, state: FSMContext):
    tags = message.text
    data = await state.get_data()
    image_id = data.get("image_id")
    
    if not image_id:
        await message.reply("Отправьте картинку, затем укажите теги.")
        return
    
    # Скачивание файла
    file = await bot.get_file(image_id)
    file_path = os.path.join(IMAGE_PATH, f"{image_id}.jpg")
    await bot.download_file(file.file_path, file_path)
    
    await add_image(file_path, tags)
    await message.reply(f"Картинка сохранена с тегами: {tags}")
    await state.clear()

@dp.message(F.text.startswith("/download"))
async def download_images(message: types.Message):
    tags = message.text[len("/download "):]  # Получение аргументов после команды
    images = await get_images_by_tags(tags)
    
    if not images:
        await message.reply("Картинки с указанными тегами не найдены.")
        return
    
    archive_path = os.path.join(IMAGE_PATH, f"{message.chat.id}.zip")
    if await check_archive_exists(tags):
        archive_url = f"{URL_PATH}{message.chat.id}.zip"
        await message.reply(f"Архив уже существует: {archive_url}")
        return
    
    with zipfile.ZipFile(archive_path, 'w') as archive:
        for image_path, in images:
            archive.write(image_path, os.path.basename(image_path))
    
    await add_archive(tags, archive_path)
    archive_url = f"{URL_PATH}{message.chat.id}.zip"
    await message.reply(f"Архив создан: {archive_url}")
    

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
