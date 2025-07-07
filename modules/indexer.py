
from typing import Any, Dict, List, Tuple
from langchain_milvus import Milvus, BM25BuiltInFunction
from langchain_openai import OpenAIEmbeddings

from pymilvus import MilvusClient, DataType, Function, FunctionType


from langchain_core.documents import Document

import logging

from modules.parser import convert_html_to_markdown_v3

logger = logging.getLogger("db_sync_nđh")

def create_vectorstore( URI: str ,collection_name: str , API_KEY : str = None ):
  """Create a vector store using Milvus and HuggingFace embeddings."""
  if API_KEY is not None:
    embeddings = OpenAIEmbeddings(
        openai_api_key=API_KEY,
        model="text-embedding-3-large",
        dimensions=1024,
    )
  else:
    logger.error("API_KEY must be provided.")
  vector_store = Milvus(
      auto_id=True,
      embedding_function=embeddings,
      builtin_function= BM25BuiltInFunction(),
      vector_field = ["vector", "sparse"],
      connection_args={"uri": URI},
      collection_name = collection_name
  )
  logger.info(f"connected to Milvus at {URI} - {collection_name}")
  return vector_store

class IndexService:
    def __init__(self, URI: str, collection_name: str , API_KEY: str = None):
        self.uri = URI
        self.collection_name= collection_name
        self.api_key = API_KEY
        self.create_vector_store_if_no_exist()
        self.vector_store = create_vectorstore(URI,collection_name , API_KEY)
    
    def create_vector_store_if_no_exist(self):
        # Khởi tạo client
        client = MilvusClient(uri=self.uri)

        # Kiểm tra xem đã tồn tại collection hay chưa
        if client.has_collection(self.collection_name):
            return

        try:
            # Tạo schema với auto_id=True để Milvus tự động tăng ID
            schema = MilvusClient.create_schema(enable_dynamic_field=True)

            # Các trường cơ bản
            schema.add_field(
                field_name="id",
                datatype=DataType.INT64,
                is_primary=True,
                description="khóa chính"
            )
            schema.add_field(
                field_name="text",
                datatype=DataType.VARCHAR,
                max_length=65535,
                enable_analyzer=True,
                description="văn bản để embedding"
            )
            schema.add_field(
                field_name="sparse",
                datatype=DataType.SPARSE_FLOAT_VECTOR,
                nullable=False,
                description="sparse vector được tự động tạo từ BM25"
            )
            schema.add_field(
                field_name="vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=1024,
                nullable=False,
                description="vector embedding của text"
            )

            # Metadata fields
            schema.add_field(
                field_name="link",
                datatype=DataType.VARCHAR,
                max_length=65535,
                nullable=True,
                description="đường dẫn tới bài viết"
            )
            schema.add_field(
                field_name="category_name",
                datatype=DataType.VARCHAR,
                max_length=65535,
                nullable=True,
                description="chủ đề bài viết"
            )
            schema.add_field(
                field_name="title",
                datatype=DataType.VARCHAR,
                max_length=65535,
                nullable=False,
                description="tiêu đề bài viết"
            )
            schema.add_field(
                field_name="header",
                datatype=DataType.VARCHAR,
                max_length=65535,
                nullable=True,
                description="header của bài viết"
            )
            schema.add_field(
                field_name="author",
                datatype=DataType.VARCHAR,
                max_length=255,
                nullable=True,
                description="tác giả bài viết"
            )
            # Boolean flags as integers
            for flag in [
                "is_comment", "is_active", "is_hot", "is_important", "is_top", "has_video"
            ]:
                schema.add_field(
                    field_name=flag,
                    datatype=DataType.INT32,
                    nullable=True,
                    description=f"cờ {flag}"
                )
            # Counts
            for count in [
                "comment_count", "like_count", "dislike_count", "hit_count"
            ]:
                schema.add_field(
                    field_name=count,
                    datatype=DataType.INT64,
                    nullable=True,
                    description=f"số lượng {count}"
                )
            # Timestamps
            for ts in ["created_at", "updated_at", "published_time"]:
                schema.add_field(
                    field_name=ts,
                    datatype=DataType.VARCHAR,
                    max_length=50,
                    nullable=True,
                    description=f"thời gian {ts} (YYYY-MM-DD HH:MM:SS)"
                )
            # JSON metadata
            schema.add_field(
                field_name="article_json",
                datatype=DataType.VARCHAR,
                max_length=65535,
                nullable=True,
                description="dữ liệu JSON bài viết"
            )

            # Định nghĩa function BM25 cho trường "text" → "sparse"
            bm25_function = Function(
                name="text_bm25_emb",
                input_field_names=["text"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25,
            )
            schema.add_function(bm25_function)

            # Chuẩn bị index
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_name="vector_flat_idx",
                index_type="FLAT",
                metric_type="COSINE",
            )
            index_params.add_index(
                field_name="sparse",
                index_name="sparse_idx",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="BM25",
            )

            # Tạo collection
            client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=index_params
            )
            logger.info(f"✅ collection '{self.collection_name}' chưa tồn tại, đã tạo mới.")
        except Exception as e:
            logger.error(f"⭕ Lỗi: không thể tạo collection '{self.collection_name}': {e}")


    def load_html_to_markdown(self, html_data: str, metadata: dict) -> Document:
        """Load HTML and chunk it into smaller pieces."""
        title = metadata.get("title", "")
        header = metadata.get('header', "")
        author = metadata.get('author', "không xác định")
        markdown_data = f"# {title}\n\n" + f"## {header}\n\n" + f"Tác giả: {author}\n\n" + convert_html_to_markdown_v3(html_data)
        document = Document(
                            page_content=markdown_data,
                            metadata=metadata
                    )
        return document 
    # test
    def get_by_id(self, id: int ) -> Document: 
        try:
            result = self.vector_store._milvus_client.get(  collection_name= self.collection_name,
                                                            ids = id
                                                        )
            if result:
                result = result[ 0 ]
            else:
                return None
            result.pop("vector")
            return Document(   
                        page_content = result.pop("text"),
                        metadata = result
                    )
        except Exception as e:
            logger.info(f"⭕ không thể lấy được bản ghi trong vector store theo ID, lỗi cụ thể: {e}")
        
    def store_chunks(self, chunks: list[Document]):
        """Store chunks in the vector store."""
        self.vector_store.add_documents(chunks)
    