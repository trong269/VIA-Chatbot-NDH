from __future__ import annotations
import json
import os
import time
import logging
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv
from pathlib import Path
import schedule
import pymysql
import psycopg2
from psycopg2 import sql, extras
from psycopg2.extras import Json, execute_values

from configs.logging_config import setup_logging
from configs.config import load_config
from modules.indexer import IndexService

load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=False)

logger = setup_logging(logger_name="db_sync_ndh", filename_prefix="db_sync_ndh")
cfg = load_config()

indexservice = IndexService(
    cfg["vector_db"].get("uri"),
    collection_name=cfg["vector_db"].get("collection_name"),
    API_KEY=cfg["llm"].get("openai_api_key"),
)


MARIADB_CONFIG = {
    "host": os.environ["NDH_MARIADB_HOST"],
    "port": int(os.getenv("NDH_MARIADB_PORT", 3306)),
    "user": os.environ["NDH_MARIADB_USER"],
    "password": os.environ["NDH_MARIADB_PW"],
    "database": os.environ["NDH_MARIADB_DB"],
    "cursorclass": pymysql.cursors.DictCursor,
    "charset": "utf8mb4",
}

POSTGRES_CONFIG = {
    "host": os.environ["NDH_PG_HOST"],
    "port": int(os.getenv("NDH_PG_PORT", 5432)),
    "user": os.environ["NDH_PG_USER"],
    "password": os.environ["NDH_PG_PW"],
    "dbname": os.environ["NDH_PG_DB"],
    # ví dụ: ép search_path nếu cần
    # "options": "-c search_path=my_schema"
}
SCHEMA_NAME = "via_ndh"
TABLE_NAME = "data_ndh"

# --------------------------------------------------
# Câu lệnh lấy bài viết từ MariaDB
# --------------------------------------------------
ARTICLE_QUERY = """

WITH RECURSIVE related AS (                 
    SELECT DISTINCT related_article_id AS id
    FROM   db_nguoidonghanh.vtp_article_related
),

article_base AS (                           
    SELECT a.id,
           a.slug,
           c.id        AS category_id,
           c.parent_id,
           c.slug      AS cat_slug,
           1           AS level
    FROM   vtp_article  a
    JOIN   vtp_category c  ON a.category_id = c.id
    LEFT JOIN   related      r  ON r.id = a.id
),
category_path AS (                          
    SELECT id          AS article_id,
           category_id,
           parent_id,
           cat_slug     AS slug,
           level
    FROM   article_base
    UNION ALL
    SELECT cp.article_id,
           p.id, p.parent_id, p.slug,
           cp.level + 1
    FROM   vtp_category p
    JOIN   category_path cp ON cp.parent_id = p.id
),
slug_root AS (                              -- slug gốc (không cha)
    SELECT article_id,
           slug AS root_slug
    FROM   category_path
    WHERE  parent_id IS NULL
),
slug_leaf AS (                              -- slug lá (sâu nhất)
    SELECT article_id,
           slug AS leaf_slug
    FROM (
        SELECT article_id,
               slug,
               ROW_NUMBER() OVER (PARTITION BY article_id ORDER BY level ASC) AS rn
        FROM   category_path
    ) t
    WHERE  rn = 1
)

/* ---------- Trả kết quả ---------- */
SELECT
	a.id,
    c.name  AS category_name,
    a.title,
    a.header,
    a.body,
    a.author,
    CONCAT('https://nguoidonghanh.viettel.vn/', sr.root_slug, '/', sl.leaf_slug, '/', a.slug) AS link,
    a.is_comment,
    a.is_active,
    a.is_hot,
    a.is_important,
    a.is_top,
    a.has_video,
    a.comment_count,
    a.like_count,
    a.dislike_count,
    a.hit_count,
    a.created_at,
    a.updated_at,
    a.published_time,

    /* --------- Cột JSON thu gọn --------- */
	JSON_OBJECT(
	    'id',   a.id,
	    'title', a.title,
	    'link', CONCAT('https://nguoidonghanh.viettel.vn/',
	                   sr.root_slug, '/', sl.leaf_slug, '/', a.slug)
	) AS article_json

FROM   vtp_article  a
JOIN   vtp_category c  ON c.id          = a.category_id
JOIN   slug_root    sr ON sr.article_id = a.id
JOIN   slug_leaf    sl ON sl.article_id = a.id
WHERE a.published_time IS NOT NULL AND  a.is_delete = 0;
"""

RELATED_QUERY = """
WITH RECURSIVE
/* 1️⃣  Bảng quan hệ gốc, bỏ bản ghi trùng */
related_full AS (
    SELECT DISTINCT               -- MariaDB cho phép DISTINCT
           r.article_id      AS parent_id,
           r.related_article_id AS id
    FROM   vtp_article_related r
),

/* 2️⃣  Thông tin tối thiểu của bài liên quan */
article_base AS (
    SELECT  a.id,
            a.title,
            a.slug,
            c.id        AS category_id,
            c.parent_id,
            c.slug      AS cat_slug,
            1           AS level
    FROM    vtp_article a
    JOIN    vtp_category c ON a.category_id = c.id
    JOIN    related_full  rf ON rf.id = a.id
),

/* 3️⃣  Truy vết cây chuyên mục */
category_path AS (
    -- gốc (level = 1)
    SELECT  id AS article_id,
            category_id,
            parent_id,
            cat_slug AS slug,
            level
    FROM    article_base

    UNION ALL

    -- leo lên cha
    SELECT  cp.article_id,
            p.id           AS category_id,
            p.parent_id,
            p.slug,
            cp.level + 1
    FROM    vtp_category  p
    JOIN    category_path cp ON cp.parent_id = p.id
),

/* 4️⃣  Slug gốc (cha = NULL) – chọn 1 slug duy nhất bằng MIN() */
slug_root AS (
    SELECT  cp.article_id,
            MIN(cp.slug) AS root_slug        -- bảo đảm chỉ 1 hàng/article
    FROM    category_path cp
    WHERE   cp.parent_id IS NULL
    GROUP BY cp.article_id
),

/* 5️⃣  Slug lá sâu nhất – lấy slug ở độ sâu MAX(level) */
slug_leaf AS (
    SELECT  cp.article_id,
            cp.slug AS leaf_slug
    FROM    category_path cp
    JOIN (
        SELECT  article_id, MAX(level) AS max_level
        FROM    category_path
        GROUP BY article_id
    ) mx ON mx.article_id = cp.article_id
        AND mx.max_level  = cp.level
)

/*--------------------------------------------------
 6️⃣  Kết quả cuối – DISTINCT bảo đảm không trùng
--------------------------------------------------*/
SELECT DISTINCT
       rf.parent_id AS article_id,
       a.id         AS related_id,
       a.title      AS related_title,
       CASE
           WHEN sr.root_slug <> sl.leaf_slug THEN
               CONCAT('https://nguoidonghanh.viettel.vn/',
                      sr.root_slug, '/', sl.leaf_slug, '/', a.slug)
           ELSE
               CONCAT('https://nguoidonghanh.viettel.vn/tin-tuc/',
                      sl.leaf_slug, '/', a.slug)
       END AS related_link
FROM   related_full rf
JOIN   vtp_article  a  ON a.id = rf.id
JOIN   slug_root    sr ON sr.article_id = a.id
JOIN   slug_leaf    sl ON sl.article_id = a.id
ORDER BY rf.parent_id DESC
"""

COLS: Tuple[str, ...] = (
    "id",
    "link",
    "category_name",
    "title",
    "header",
    "body",
    "author",
    "is_comment",
    "is_active",
    "is_hot",
    "is_important",
    "is_top",
    "has_video",
    "comment_count",
    "like_count",
    "dislike_count",
    "hit_count",
    "created_at",
    "updated_at",
    "published_time",
    "article_json",  # list[dict]
)
# --------------------------------------------------
# Hàm đồng bộ
# --------------------------------------------------
def sync_articles() -> None:
    """Main scheduled job."""

    logger.info("🔄  Bắt đầu đồng bộ …")

    # 1️⃣  Read main articles + related links from MariaDB
    with pymysql.connect(**MARIADB_CONFIG) as mariadb_conn, mariadb_conn.cursor() as cur:
        cur.execute(ARTICLE_QUERY)
        articles: List[Dict[str, Any]] = cur.fetchall()

        if not articles:
            logger.info("⏭️  Không có bản ghi bài viết nào được trả về, bỏ qua.")
            return

        cur.execute(RELATED_QUERY)
        related_rows: List[Dict[str, Any]] = cur.fetchall()

    # Build map {article_id: [ {title, link}, … ] }
    related_map: Dict[int, List[Dict[str, str]]] = {}
    for r in related_rows:
        related_map.setdefault(r["article_id"], []).append(
            {"title": r["related_title"], "link": r["related_link"]}
        )

    # Merge JSON + collect records for PG insert
    records: List[Tuple[Any, ...]] = []
    for art in articles:
        art["article_json"] = Json(related_map.get(art["id"], []))
        records.append(tuple(art[col] for col in COLS))

    incoming_ids = [rec[0] for rec in records]  # list[int]

    # 2️⃣  Upsert into PostgreSQL
    with psycopg2.connect(**POSTGRES_CONFIG) as pg_conn, pg_conn.cursor() as cur:
        # 2.1 – ensure schema / table
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {};").format(sql.Identifier(SCHEMA_NAME)))
        cur.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {}.{} (
                    id              INTEGER      PRIMARY KEY,
                    link            TEXT,
                    category_name   TEXT,
                    title           TEXT,
                    header          TEXT,
                    body            TEXT,
                    author          TEXT,
                    is_comment      INTEGER,
                    is_active       INTEGER,
                    is_hot          INTEGER,
                    is_important    INTEGER,
                    is_top          INTEGER,
                    has_video       INTEGER,
                    comment_count   INTEGER,
                    like_count      INTEGER,
                    dislike_count   INTEGER,
                    hit_count       INTEGER,
                    created_at      TIMESTAMPTZ,
                    updated_at      TIMESTAMPTZ,
                    published_time  TIMESTAMPTZ,
                    article_json    JSONB
                );
                """
            ).format(sql.Identifier(SCHEMA_NAME), sql.Identifier(TABLE_NAME))
        )

        # 2.2 – fetch existing ids
        cur.execute(
            sql.SQL("SELECT id FROM {}.{} WHERE id = ANY(%s);").format(
                sql.Identifier(SCHEMA_NAME), sql.Identifier(TABLE_NAME)
            ),
            (incoming_ids,),
        )
        existing: set[int] = {row[0] for row in cur.fetchall()}

        new_articles = [a for a in articles if a["id"] not in existing]

        logger.info(f"🆕 Đang đồng bộ {len(records)} bài viết, trong đó có {len(new_articles)} bài viết mới!", )

        insert_query = sql.SQL(
            """
            INSERT INTO {}.{} (
                id, link, category_name, title, header, body, author,
                is_comment, is_active, is_hot, is_important, is_top, has_video,
                comment_count, like_count, dislike_count, hit_count,
                created_at, updated_at, published_time, article_json
            ) VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                link           = EXCLUDED.link,
                category_name  = EXCLUDED.category_name,
                title          = EXCLUDED.title,
                header         = EXCLUDED.header,
                body           = EXCLUDED.body,
                author         = EXCLUDED.author,
                is_comment     = EXCLUDED.is_comment,
                is_active      = EXCLUDED.is_active,
                is_hot         = EXCLUDED.is_hot,
                is_important   = EXCLUDED.is_important,
                is_top         = EXCLUDED.is_top,
                has_video      = EXCLUDED.has_video,
                comment_count  = EXCLUDED.comment_count,
                like_count     = EXCLUDED.like_count,
                dislike_count  = EXCLUDED.dislike_count,
                hit_count      = EXCLUDED.hit_count,
                created_at     = EXCLUDED.created_at,
                updated_at     = EXCLUDED.updated_at,
                published_time = EXCLUDED.published_time,
                article_json   = EXCLUDED.article_json;
            """
        ).format(sql.Identifier(SCHEMA_NAME), sql.Identifier(TABLE_NAME))

        try:
            execute_values(cur, insert_query.as_string(pg_conn), records, page_size=1000)
            logger.info("✅ Đồng bộ xong %d bản ghi vào PostgreSQL.", len(records))
        except Exception:
            logger.info("⭕ Lỗi khi UPSERT vào PostgreSQL")
            return  # skip vector‑store step if DB failed

    # 3️⃣  Push new rows to the vector store
    try:
        for idx, art in enumerate(new_articles, start=1):
            chunk = indexservice.load_html_to_markdown(
                html_data=art["body"] or "",
                metadata={
                    'id': int(art['id']),
                    "title": art.get("title", ""),
                    "header": art.get("header", ""),
                    "author": art.get("author", ""),
                    "category_name": art.get("category_name", ""),
                    "link": art.get("link", ""),
                    "created_at": art["created_at"].isoformat() if art["created_at"] else "",
                    "updated_at": art["updated_at"].isoformat() if art["updated_at"] else "",
                    "published_time": art["published_time"].isoformat() if art["published_time"] else "",
                    'article_json': json.dumps(art.get("article_json").adapted, ensure_ascii=False, indent=2 ),
                    **{k: art.get(k) or 0  for k in (
                        "is_comment",
                        "is_active",
                        "is_hot",
                        "is_important",
                        "is_top",
                        "has_video",
                        "comment_count",
                        "like_count",
                        "dislike_count",
                        "hit_count",
                    )},
                },
            )
            indexservice.store_chunks([chunk])
            logger.info("📥  VectorStore %d/%d", idx, len(new_articles))                
        if len(new_articles):
            logger.info("✅ Đã đồng bộ %d bản ghi mới vào Vector Store.", len(new_articles))
        else : 
            logger.info("🔔 Không có bản ghi mới nào cần đồng bộ vào vector store.")
    except Exception as e:
        logger.info(f"⭕ Lỗi khi đẩy dữ liệu vào Vector Store , lỗi cụ thể: {e}")

##############################
# Schedule: every 1 minute
##############################

schedule.every(1).minutes.do(sync_articles)

if __name__ == "__main__":
    sync_articles()  # run once immediately
    while True:
        schedule.run_pending()
        time.sleep(1)