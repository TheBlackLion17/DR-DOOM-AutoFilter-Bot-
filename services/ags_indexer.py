import asyncio
import logging

import database as db

log = logging.getLogger("ags-indexer")


async def ensure_tables():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ags_scan_state (
            channel_id BIGINT PRIMARY KEY,
            next_offset_id BIGINT NOT NULL DEFAULT 0,
            stop_before_id BIGINT NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'idle',
            scanned BIGINT NOT NULL DEFAULT 0,
            indexed BIGINT NOT NULL DEFAULT 0,
            skipped BIGINT NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    columns = await db.fetchall(
        "SHOW COLUMNS FROM ags_scan_state"
    )
    names = {row["Field"] for row in columns}

    if "scan_top_id" not in names:
        await db.execute("""
            ALTER TABLE ags_scan_state
            ADD COLUMN scan_top_id BIGINT NOT NULL DEFAULT 0
        """)


async def scan_channel(client, channel_id, index_message):
    await ensure_tables()

    row = await db.fetchone(
        "SELECT * FROM ags_scan_state WHERE channel_id=%s",
        (channel_id,)
    )

    if row and row["status"] in ("running", "paused", "failed"):
        offset = row["next_offset_id"]
        boundary = row["stop_before_id"]
        top = row["scan_top_id"]
    else:
        offset = 0
        boundary = row["scan_top_id"] if row else 0
        top = 0

    scanned = row["scanned"] if row else 0
    indexed = row["indexed"] if row else 0
    skipped = row["skipped"] if row else 0

    await db.execute("""
        INSERT INTO ags_scan_state
        (channel_id, next_offset_id, stop_before_id,
         scan_top_id, status, scanned, indexed, skipped)
        VALUES (%s,%s,%s,%s,'running',%s,%s,%s)
        ON DUPLICATE KEY UPDATE
          next_offset_id=VALUES(next_offset_id),
          stop_before_id=VALUES(stop_before_id),
          scan_top_id=VALUES(scan_top_id),
          status='running'
    """, (
        channel_id, offset, boundary, top,
        scanned, indexed, skipped
    ))

    try:
        while True:
            count = 0
            reached_boundary = False

            # Verify channel access using the history-reader session.
            try:
                chat = await client.get_chat(channel_id)
            except Exception:
                log.exception('History reader cannot access channel %s', channel_id)
                raise

            async for msg in client.get_chat_history(
                channel_id,
                limit=100,
                offset_id=offset
            ):
                if msg.id <= boundary:
                    reached_boundary = True
                    break

                if not top:
                    top = msg.id

                # Only advance checkpoint after successful processing.
                saved = await index_message(msg)

                scanned += 1
                if saved:
                    indexed += 1
                else:
                    skipped += 1

                offset = msg.id
                count += 1

                await db.execute("""
                    UPDATE ags_scan_state
                    SET next_offset_id=%s,
                        scan_top_id=%s,
                        scanned=%s,
                        indexed=%s,
                        skipped=%s,
                        status='running'
                    WHERE channel_id=%s
                """, (
                    offset, top, scanned,
                    indexed, skipped, channel_id
                ))

                if scanned % 100 == 0:
                    log.info(
                        "Channel %s: scanned=%s indexed=%s skipped=%s",
                        channel_id, scanned, indexed, skipped
                    )

            if reached_boundary or count == 0:
                break

            await asyncio.sleep(2)

        await db.execute("""
            UPDATE ags_scan_state
            SET status='completed',
                next_offset_id=0,
                stop_before_id=0
            WHERE channel_id=%s
        """, (channel_id,))

        log.info(
            "Scan completed: channel=%s scanned=%s indexed=%s",
            channel_id, scanned, indexed
        )

    except asyncio.CancelledError:
        await db.execute("""
            UPDATE ags_scan_state
            SET status='paused'
            WHERE channel_id=%s
        """, (channel_id,))
        raise

    except Exception:
        log.exception("Scan failed for channel %s", channel_id)
        await db.execute("""
            UPDATE ags_scan_state
            SET status='failed'
            WHERE channel_id=%s
        """, (channel_id,))
        raise
