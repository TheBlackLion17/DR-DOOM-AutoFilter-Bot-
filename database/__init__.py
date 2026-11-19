import aiomysql
from config import CFG

pool = None

async def init_db():
    global pool
    pool = await aiomysql.create_pool(host=CFG['DB_HOST'], port=int(CFG['DB_PORT']), user=CFG['DB_USER'], password=CFG['DB_PASSWORD'], db=CFG['DB_NAME'], autocommit=True, minsize=1, maxsize=8, charset='utf8mb4')
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute('''CREATE TABLE IF NOT EXISTS files (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                file_unique_id VARCHAR(255) NOT NULL,
                file_id TEXT NOT NULL,
                source_channel BIGINT NOT NULL,
                source_message BIGINT NOT NULL,
                file_name VARCHAR(1024) NOT NULL DEFAULT '',
                title VARCHAR(512) NOT NULL DEFAULT '',
                kind VARCHAR(16) NOT NULL DEFAULT 'movie',
                season INT NULL, episode INT NULL,
                quality VARCHAR(20) NULL, language VARCHAR(80) NULL,
                file_size BIGINT NOT NULL DEFAULT 0,
                media_type VARCHAR(16) NOT NULL,
                caption TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_source (source_channel, source_message),
                KEY idx_unique (file_unique_id),
                KEY idx_title (title(191)),
                KEY idx_kind (kind),
                KEY idx_season (season,episode)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci''')
            await cur.execute('''CREATE TABLE IF NOT EXISTS scan_progress (
                channel_id BIGINT PRIMARY KEY,
                last_message_id BIGINT NOT NULL DEFAULT 0,
                scanned BIGINT NOT NULL DEFAULT 0,
                indexed BIGINT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )''')

async def execute(sql, args=()):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, args)
            return cur.rowcount

async def fetchall(sql, args=()):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchall()

async def fetchone(sql, args=()):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchone()

async def close_db():
    if pool:
        pool.close()
        await pool.wait_closed()

async def insert_id(sql, args=()):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql,args)
            return cur.lastrowid
