import re
import os
from typing import List, Dict, Any, AsyncGenerator, Optional
import logging
from datetime import datetime

# Langchain imports
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI # Hoặc LLM bạn dùng

# Import từ các module mới tạo
from modules.data_utils import load_table_metadata
from modules.db_executor import execute_sql_with_retry, format_sql_result_for_llm_analysis
from modules.llm_invoker import invoke_llm_for_full_response

from utils.questions_handle import extract_and_format_from_selected_tables

logger = logging.getLogger("ChatbotNDH")

# Import prompts từ configs
from configs.prompt import (
    SQL_GENERATION_PROMPT,
)

class SqlAgent:
    def __init__(self):
        pass

    async def process( self, message: str, cfg: dict, table_name: str = "data_ndh") -> str:
        start_time = datetime.now()
        logger.info(f"============== SQL RETRIEVAL PROCESS ==============")
        logger.info(f"MESSAGE = '{message}'")
        logger.info(f"TABLE_NAMES = '{table_name}'")

        try:
            # === Init LLM ===
            llm_cfg = cfg['llm']
            if llm_cfg.get('openai_api_key'):
                os.environ['OPENAI_API_KEY'] = llm_cfg['openai_api_key']
            model_4_1 = ChatOpenAI(
                model_name=llm_cfg['model_4_1'],
                temperature=llm_cfg['temperature'],
                streaming=llm_cfg['streaming'],
            )
            result = await self.handle_db_query(model_4_1=model_4_1,
                            original_query=message,
                            target_table_names=[table_name],
                            cfg=cfg
                            )
            return result

        except Exception as e:
            logger.exception(f"Lỗi trong quá trình xử lý pipline: {e})")
            return ""

    async def handle_db_query(self,
        model_4_1: ChatOpenAI,
        original_query: str,
        target_table_names: Optional[List[str]], 
        cfg: Dict[str, Any], 
    ) -> str:


        # try:
        logger.info(f"TARGET_TABLE_FROM_USER = '{target_table_names}'")
        # 1. Load metadata list
        metadata = load_table_metadata(cfg['data']['data_tables_info'])
        if not metadata:
            logger.info("Không thể tải metadata của bảng. Vui lòng kiểm tra cấu hình.")
            return "Unknown"

        # 2. Lấy ra thông tin bảng để truy vấn
        selected_table_info = metadata[ 0 ]

        # 3. Chuẩn bị thông tin cho prompt sinh SQL
        columns_details = "\n".join([
            f"  - {col.get('column_name')} ({col.get('data_type')}): {col.get('description')}"
            for col in selected_table_info.get('columns', [])
        ])

        sql_samples = "".join(extract_and_format_from_selected_tables(metadata,target_table_names,max_questions=4))
        
        # 4. Sinh câu lệnh SQL
        prompt_input_sql = {
            'question': original_query,
            'tables_name': selected_table_info['table_name'],
            'table_description': selected_table_info.get('description', 'N/A'),
            'sql_samples': sql_samples,
            'columns_info': columns_details if columns_details else '  (Không có thông tin cột chi tiết)',
        }
        sql_generation_prompt_str = SQL_GENERATION_PROMPT.format(**prompt_input_sql)

        llm_sql_response = await invoke_llm_for_full_response(model_4_1, [HumanMessage(content=sql_generation_prompt_str)])
        # check sql được sinh ra bằng regex
        sql_match = re.search(r"```sql\s*([\s\S]+?)\s*```", llm_sql_response)
        
        if not sql_match:
            logger.info("câu hỏi đầu vào không thể tạo truy vấn SQL")
            return "Unknown"

        
        generated_sql = sql_match.group(1).strip()
        logger.info(f"SQL = '{generated_sql}'")
        
        # 5. Thực thi câu lệnh SQL
        query_result = await execute_sql_with_retry(model_4_1, 
                                                    original_query,
                                                    selected_table_info['table_name'], 
                                                    generated_sql , 
                                                    prompt_input_sql,
                                                    max_attempts = cfg['bot']['sql_double_check'] )
        
        final_respone = {
            "status": query_result['status'],
            "message": query_result['message'],
            "sql_result_summary": "",
            "table_name": selected_table_info['table_name'],
            "table_description": selected_table_info["description"],
            "column_descriptions" : str(selected_table_info["columns"])
        }
        
        if query_result["status"] not in ["success", "success_no_data"]:
            logger.info(f"Lỗi khi thực thi SQL: {query_result['message']}")
            final_respone['sql_result_summary'] = "N/A"
        else:
            logger.info(f'DATA: {query_result["data"]}')
            final_respone['sql_result_summary'] = format_sql_result_for_llm_analysis(query_result)
        return final_respone
    
# if __name__ == "__main__":
#     from ..configs.config import load_config
#     cfg = load_config()

#     agent = SqlAgent()
#     agent.process("bài viết nào có lượt thích nhiều nhất", cfg=cfg)