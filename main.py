import os
import shutil
import zipfile
import tarfile
import aiohttp
import aiosqlite
import booru
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from pathlib import Path

# Загрузка переменных окружения
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
IMAGE_FOLDER = 'images'
ARCHIVE_FOLDER = '/var/www/lapismyt.lol'
DB_PATH = "database.db"

os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Состояния для FSM
class AddImage(StatesGroup):
    waiting_for_tags = State()

# Функция для создания базы данных
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS images (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            file_path TEXT NOT NULL)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS tags (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS image_tags (
                            image_id INTEGER,
                            tag_id INTEGER,
                            FOREIGN KEY (image_id) REFERENCES images (id),
                            FOREIGN KEY (tag_id) REFERENCES tags (id))""")
        await db.commit()

# Функция для сохранения изображения в базу данных и папку
async def save_image(file_path, tags):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO images (file_path) VALUES (?)", (file_path,))
        image_id = (await db.execute("SELECT last_insert_rowid()")).fetchone()[0]
        for tag in tags:
            await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            tag_id = (await db.execute("SELECT id FROM tags WHERE name = ?", (tag,))).fetchone()[0]
            await db.execute("INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)", (image_id, tag_id))
        await db.commit()

# Хэндлер для добавления изображения
@dp.message(Command("add_image"), F.photo)
async def add_image(message: types.Message, state: FSMContext):
    await message.answer("Введите теги для изображения в формате booru (через пробел):")
    await AddImage.waiting_for_tags.set()
    await message.photo[-1].download(f"{IMAGE_FOLDER}/{message.photo[-1].file_id}.jpg")
    await state.update_data(file_path=f"{IMAGE_FOLDER}/{message.photo[-1].file_id}.jpg")

# Хэндлер для получения тегов и сохранения изображения
@dp.message(AddImage.waiting_for_tags)
async def get_tags(message: types.Message, state: FSMContext):
    tags = message.text.split()
    data = await state.get_data()
    await save_image(data["file_path"], tags)
    await message.answer("Изображение сохранено.")
    await state.clear()

# Функция для создания архива
async def create_archive(tags, format='zip'):
    async with aiosqlite.connect(DB_PATH) as db:
        images_to_archive = await db.execute_fetchall(
            """SELECT file_path FROM images
               JOIN image_tags ON images.id = image_tags.image_id
               JOIN tags ON image_tags.tag_id = tags.id
               WHERE tags.name IN (?)""",
            (tags,))
        archive_path = f"{ARCHIVE_FOLDER}/{hash(tuple(tags))}.{format}"
        if not os.path.exists(archive_path):
            with zipfile.ZipFile(archive_path, "w") if format == 'zip' else tarfile.open(archive_path, "w:gz") as archive:
                for image_path in images_to_archive:
                    archive.write(image_path)
        return archive_path

# Хэндлер для создания архива по тегам
@dp.message(Command("get_archive"))
async def get_archive(message: types.Message):
    tags = message.get_args().split()
    archive_path = await create_archive(tags)
    link = f"http://lapismyt.lol/local/{os.path.basename(archive_path)}"
    await message.answer(f"Ваш архив доступен по ссылке: {link}")

# Функция для загрузки изображений с booru
async def fetch_from_booru(tag, site='danbooru'):
    booru_client = booru.Danbooru() if site == 'danbooru' else booru.Booru(site)
    response = await booru_client.search(query=tag)
    posts = booru.resolve(response)
    
    for post in posts:
        file_url = post.get('file_url')
        if file_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        file_name = os.path.join(IMAGE_FOLDER, f"{tag}_{post['id']}.jpg")
                        with open(file_name, 'wb') as f:
                            f.write(await response.read())
                        await save_image(file_name, [tag])

@dp.message(Command("fetch_booru"))
async def fetch_booru_images(message: types.Message):
    args = message.get_args().split()
    tag = args[0]
    site = args[1] if len(args) > 1 else 'danbooru'
    await fetch_from_booru(tag, site)
    await message.answer(f"Изображения с {site} по тегу {tag} добавлены в базу.")

if __name__ == '__main__':
    import asyncio
    asyncio.run(init_db())
    dp.start_polling(bot)
