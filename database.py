import aiosqlite
import os

DB_NAME = "images.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                tags TEXT NOT NULL
            );
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tags TEXT NOT NULL,
                file_path TEXT NOT NULL
            );
            """
        )
        await db.commit()

async def add_image(file_path, tags):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO images (file_path, tags) VALUES (?, ?)", (file_path, tags))
        await db.commit()

async def get_images_by_tags(tags):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT file_path FROM images WHERE tags LIKE ?", (f"%{tags}%",))
        return await cursor.fetchall()

async def check_archive_exists(tags):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT file_path FROM archives WHERE tags = ?", (tags,))
        return await cursor.fetchone()

async def add_archive(tags, file_path):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO archives (tags, file_path) VALUES (?, ?)", (tags, file_path))
        await db.commit()
