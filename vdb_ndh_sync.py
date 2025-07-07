from __future__ import annotations

from datetime import datetime
import copy
import os
import time
import json
import logging
from typing import Any, Dict, List
from dotenv import load_dotenv
from pathlib import Path
import schedule
import psycopg2
from psycopg2 import sql
from langchain_core.documents import Document

from configs.logging_config import setup_logging
from configs.config import load_config
from modules.indexer import IndexService

load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=False)

logger = setup_logging(logger_name="vdb_sync_ndh", filename_prefix="vdb_sync_ndh")
cfg = load_config()

indexservice = IndexService(
    cfg["vector_db"].get("uri"),
    collection_name=cfg["vector_db"].get("collection_name"),
    API_KEY=cfg["llm"].get("openai_api_key"),
)

POSTGRES_CONFIG = {
    "host": os.environ["NDH_PG_HOST"],
    "port": int(os.getenv("NDH_PG_PORT", 5432)),
    "user": os.environ["NDH_PG_USER"],
    "password": os.environ["NDH_PG_PW"],
    "dbname": os.environ["NDH_PG_DB"],
}
SCHEMA_NAME = "via_ndh"
TABLE_NAME = "data_ndh"

def isupdate(doc_a: Document, doc_b: Document ) -> bool:
    if not doc_a.page_content == doc_b.page_content:
        logger.info(f"nội dung bài viết đã bị thay đổi, đang cập nhật lại nội dung bài viết...")
        return False
    value1 = doc_a.metadata
    value2 = doc_b.metadata
    # value1.pop("article_json")
    value1['article_json'] = json.loads(value1['article_json'])
    value1['created_at'] = datetime.fromisoformat(value1['created_at']).replace(tzinfo=None)
    value1['updated_at'] = datetime.fromisoformat(value1['updated_at']).replace(tzinfo=None)
    value1['published_time'] = datetime.fromisoformat(value1['published_time']).replace(tzinfo=None)
    # value2.pop("article_json")
    value2['article_json'] = json.loads(value2['article_json'])
    value2['created_at'] = datetime.fromisoformat(value2['created_at']).replace(tzinfo=None)
    value2['updated_at'] = datetime.fromisoformat(value2['updated_at']).replace(tzinfo=None)
    value2['published_time'] = datetime.fromisoformat(value2['published_time']).replace(tzinfo=None)

    # So sánh từng key
    for key in value1:
        v1 = value1[key]
        v2 = value2[key]
        if v1 != v2:
            if key != "article_json":
                logger.info(f"Giá trị khác nhau ở key '{key}': {v1} vs {v2}")
            else : 
                logger.info(f"Giá trị khác nhau ở key '{key}'")
            return False
    return True

def vdb_sync():
    """
    Đồng bộ dữ liệu cập nhật từ PostgreSQL sang Milvus.
    """
    # 1. Kết nối PostgreSQL
    with psycopg2.connect(**POSTGRES_CONFIG) as pg_conn, pg_conn.cursor() as pg_cursor:

        # 2. Lấy tất cả bản ghi từ Postgres
        query = f"""
        SELECT id, link, category_name, title, header, body, author,
               is_comment, is_active, is_hot, is_important, is_top, has_video,
               comment_count, like_count, dislike_count, hit_count,
               created_at, updated_at, published_time, article_json
        FROM {SCHEMA_NAME}.{TABLE_NAME};
        """
        pg_cursor.execute(query)
        # lấy tên cột
        cols = [desc[0] for desc in pg_cursor.description]
        # fetch dưới dạng tuple
        rows = pg_cursor.fetchall()
        # chuyển mỗi row tuple thành dict
        records: List[Dict[str, Any]] = [dict(zip(cols, row)) for row in rows]
        # 3. Lấy toàn bộ document trong vectorstore
        all_ids: List[int] = []
        doc_in_db_mapping: Dict[int, Document] = {}
        doc_in_vb_mapping: Dict[int, Document | None] = {}
        
        for r in records:
            id = r['id']
            all_ids.append(id)
            # tạo document với dữ liệu trong PostgreSQL
            document_in_db = indexservice.load_html_to_markdown(
                html_data=r["body"] or "",
                metadata={
                    'id': int(id),
                    'title': r.get('title', ''),
                    'header': r.get('header', ''),
                    'author': r.get('author', ''),
                    'category_name': r.get('category_name', ''),
                    'link': r.get('link', ''),
                    'created_at': r['created_at'].isoformat() if r['created_at'] else '',
                    'updated_at': r['updated_at'].isoformat() if r['updated_at'] else '',
                    'published_time': r['published_time'].isoformat() if r['published_time'] else '',
                    'article_json': json.dumps(r.get('article_json'), ensure_ascii=False, indent= 2 ),
                    **{k: r.get(k) or 0 for k in (
                        'is_comment', 'is_active', 'is_hot', 'is_important',
                        'is_top', 'has_video', 'comment_count', 'like_count',
                        'dislike_count', 'hit_count'
                    )},
                },
            )
            doc_in_db_mapping[id] = document_in_db
            # lấy document từ vectorstore
            vb_docs = indexservice.get_by_id(id)
            doc_in_vb_mapping[id] = vb_docs if vb_docs else None

        # so khớp xem có cần cập nhật hay không
        updated = False
        count = 0
        # copy để không làm mất mát dữ liệu gốc (note phải dùng deepcopy nhé , .copy() ko được đâu )
        doc_in_db_mapping_copy = copy.deepcopy(doc_in_db_mapping)
        doc_in_vb_mapping_copy = copy.deepcopy(doc_in_vb_mapping)
        for id in all_ids:
            a = doc_in_db_mapping_copy.get(id)
            b = doc_in_vb_mapping_copy.get(id)
            if a and b and not isupdate(a, b):
                updated = True
                try:
                    # update dữ liệu vào vector store
                    indexservice.vector_store.upsert(ids = [ id ], documents= [doc_in_db_mapping.get(id)])
                    count += 1
                    logger.info(f"✅ Đã cập nhật bản ghi id={id} trong vector store")
                except Exception as e:
                    logger.exception(f"⭕ Lỗi khi cập nhật dữ liệu Vector Store id={id}: {e}")
        if not updated:
            logger.info("🔔 Không có bản ghi mới nào cần cập nhật vào vector store.")
        else:
            logger.info(f"🎉 Đã cập nhật {count} bản ghi trong vector store")


# schedule.every(1).days.do(vdb_sync)  # hàng ngày
schedule.every(2).days.do(vdb_sync)


if __name__ == "__main__":
    vdb_sync()
    while True:
        schedule.run_pending()
        time.sleep(1)
