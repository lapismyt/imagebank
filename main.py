import os
import zipfile
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from config import TOKEN, IMAGE_PATH, URL_PATH
from database import init_db, add_image, get_images_by_tags, check_archive_exists, add_archive
from booru import Danbooru, Rule34

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инициализация базы данных
asyncio.run(init_db())

@dp.message(commands=["start"])
async def start_handler(message: types.Message):
    await message.reply("Привет! Отправь мне картинку и добавь к ней теги в формате booru.")

@dp.message(content_types=types.ContentType.PHOTO)
async def handle_image(message: types.Message):
    await message.reply("Введите теги для этой картинки:")
    await dp.storage.set_data(chat=message.chat.id, data={"image_id": message.photo[-1].file_id})

@dp.message(F.text)
async def handle_tags(message: types.Message):
    tags = message.text
    data = await dp.storage.get_data(chat=message.chat.id)
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
    await dp.storage.delete_data(chat=message.chat.id)

@dp.message(commands=["download"])
async def download_images(message: types.Message):
    tags = message.get_args()
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

@dp.message(commands=["fetch"])
async def fetch_from_booru(message: types.Message):
    args = message.get_args().split()
    booru_name = args[0]
    tags = args[1]
    
    if booru_name.lower() == "danbooru":
        booru = Danbooru()
    elif booru_name.lower() == "rule34":
        booru = Rule34()
    else:
        await message.reply("Поддерживаемые booru: danbooru, rule34.")
        return
    
    results = await booru.search(query=tags)
    images = booru.resolve(results)
    
    for img_url in images:
        file_name = os.path.basename(img_url)
        file_path = os.path.join(IMAGE_PATH, file_name)
        async with aiohttp.ClientSession() as session:
            async with session.get(img_url) as resp:
                with open(file_path, 'wb') as f:
                    f.write(await resp.read())
        await add_image(file_path, tags)
    
    await message.reply(f"Загружено {len(images)} изображений с тегами {tags}.")

if __name__ == "__main__":
    dp.run_polling(bot)
