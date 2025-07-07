from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from agents.agent_sql_search import SqlAgent
from agents.agent_vector_search import VecterSearchAgent
from modules.indexer import create_vectorstore

from configs.config import load_config
from configs.logging_config import setup_logging

logger = setup_logging(logger_name= 'ChatbotNDH',filename_prefix='ChatbotNDH')
cfg = load_config()

# Pydantic models for request and response wwith vector search
class RetrievalSetting(BaseModel):
    top_k: int = 2
    score_threshold: float = 0

class RetrievalRequest(BaseModel):
    knowledge_id: str
    query: str
    retrieval_setting: RetrievalSetting

class RecordMetadata(BaseModel):
    published_time: str
    category_name: str
    link: str
    author: str
    created_at: str
    updated_at: str

class RetrievalRecord(BaseModel):
    metadata: RecordMetadata
    score: float
    title: str
    header: str
    content: str

class RetrievalResponse(BaseModel):
    records: List[RetrievalRecord]



# # Configuration
# URI = "http://localhost:19530"
# from config import API_KEY  # Assuming
# Initialize the FastAPI app
app = FastAPI(title="Retrieval API")

# Initialize the SqlAgent and VectorSearchAgent

sql_agent = SqlAgent()

try:
    vector_store = create_vectorstore( URI=cfg["vector_db"]["uri"], collection_name= cfg["vector_db"]["collection_name"], API_KEY= cfg["llm"]["openai_api_key"])
    retriever = VecterSearchAgent(vector_store)
except Exception as e:
    vector_store = None
    retriever = None


def verify_api_key(authorization: str = Header(None)) -> bool:
    """Verify the API key from Authorization header"""
    if not authorization:
        return False
    # Extract Bearer token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return False
        # Here you can implement your own API key validation logic
        # For now, we'll accept any non-empty bearer token
        return len(token) > 0
    except ValueError:
        return False

@app.post("/retrieval", response_model=RetrievalResponse)
async def retrieval_endpoint(
    request: RetrievalRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Retrieval API endpoint that searches for documents based on query
    """

    # Verify API key
    if not verify_api_key(authorization):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    
    # Check if retriever is initialized
    if retriever is None:
        logger.info("Lỗi: chưa khởi tạo vector store retrieval")
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        # Perform retrieval
        results = retriever.retrieve(
            query=request.query, 
            top_k=request.retrieval_setting.top_k
        )
        logger.info("============== VECTOR SEARCH RETRIEVAL PROCESS ==============")
        # Filter results by score threshold
        filtered_results = []
        if request.retrieval_setting.score_threshold:
            filtered_results = [
                (doc, score) for doc, score in results 
                if score >= request.retrieval_setting.score_threshold
            ]
        else: 
            filtered_results = [
                (doc, score) for doc, score in results 
            ]
        
        # Convert results to response format
        records = []
        for doc, score in filtered_results:
            # Extract metadata information
            metadata = doc.metadata or {}
            
            # Get title from metadata or generate from path
            title = metadata.get('title', 'Unknown Title')
            header = metadata.get("header", "Unknown Header")
            published_time = metadata.get('published_time', 'Unknown Time')
            category_name = metadata.get('category_name', 'Unknown Category')
            link = metadata.get('link', 'Unknown Link')
            author = metadata.get('author', 'Unknown author')
            created_at = metadata.get('created_at', 'Unknown created_at')
            updated_at = metadata.get('updated_at', 'Unknown updated_at')
            article_json = metadata.get("article_json", "")

            # merge content
            content = f"""
            {doc.page_content}
            \n\nThông tin chi tiết:
            - chủ đề: {category_name}
            - đường dẫn bài viết: {link}
            - created at: {created_at}
            - published time: {published_time}
            - updated at : {updated_at}
            - các bài viết liên quan:
                {article_json}
            """
            record = RetrievalRecord(
                metadata=RecordMetadata(
                    published_time=published_time,
                    category_name=category_name,
                    link=link,
                    author= author,
                    created_at= created_at,
                    updated_at= updated_at
                ),
                score=round(score, 2),
                title=title,
                header= header,
                content= content
            )
            records.append(record)
        
        # logger.info(f"data:\n{records}")
        return RetrievalResponse(records=records)
        
    except Exception as e:
        logger.info(f'Retrieval error: {str(e)}')
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")


# Pydantic models for request and response wwith SQL retrieval
class SqlRetrievalRequest(BaseModel):
    query: str

class SQLRetrievalResponse(BaseModel):
    status: str
    message: str
    sql_result_summary: str
    table_name: str
    table_description: str
    column_descriptions : str

@app.post("/sql_retrieval", response_model=SQLRetrievalResponse)
async def retrieval_endpoint(
    request: SqlRetrievalRequest,
):
    try:
        result = await sql_agent.process(request.query, cfg=cfg)

        return SQLRetrievalResponse(    status= result["status"],
                                        message= result["message"],
                                        sql_result_summary= result["sql_result_summary"], 
                                        table_name= result["table_name"],
                                        table_description= result["table_description"],
                                        column_descriptions= result[ "column_descriptions" ]
                                    )
    except Exception as e:
        logger.info(f'Retrieval error: {str(e)}')
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")
    
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "vector_store_initialized": retriever is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004 )
