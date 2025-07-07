from langchain_core.documents import Document
import logging 


logger = logging.getLogger("ChatbotNDH")


hybrid_search_params = [
    {
        "anns_field": "vector",    # Trường vector dày (dense)
        "metric_type": "COSINE",   # Metric cho vector dày
        "params": {
            "ef": 64,              # Độ chính xác tìm kiếm (càng cao càng chính xác nhưng chậm hơn)
            "nprobe": 16           # Số lượng cluster để tìm kiếm (tương tự nprobe trong IVF)
        }
    },
    {
        "anns_field": "sparse",    # Trường vector thưa (sparse)
        "metric_type": "BM25",     # Metric BM25 cho vector thưa  
        "params": {
            "k1": 1.2,             # Tham số k1 của BM25 (thường từ 1.2-2.0)
            "b": 0.75              # Tham số b của BM25 (thường từ 0.5-0.8)
        }
    }
]
class VecterSearchAgent:
    def __init__(self, vector_store ):
        """Initialize the Retriever with a vector store."""
        self.vector_store = vector_store
        self.search_params = hybrid_search_params
    def retrieve(self, query: str, top_k : int ) -> list[Document]:
        """Retrieve documents from the vector store based on the query."""
        try:
            result = self.vector_store.similarity_search_with_score(
                query=query,
                k = top_k,  # Số lượng tài liệu trả về
                param = self.search_params  # Truyền các tham số tìm kiếm hybrid vào đây
            )
            return result
        except Exception as e:
            logger.info("lỗi: search vector trong vectorstore")
            return []
    
# if __name__ == "__main__":
#     # Example usage
#     from indexer import create_vectorstore
#     from config import API_KEY  # Assuming you have an API_KEY in config.py
#     URI = "http://localhost:19530"

#     vector_store = create_vectorstore(URI, API_KEY=API_KEY)
#     retriever = Retriever(vector_store)
    
#     query = "vcc là gì"
#     results = retriever.retrieve(query, top_k=5)
#     print(results)