import logging
from typing import Dict, Any, List, Optional
from modules.db import Database_data
from modules.llm_invoker import invoke_llm_for_full_response
from configs.config import load_config
from configs.prompt import SQL_GENERATION_DOUBLE_CHECK
from langchain_core.messages import HumanMessage
import json
import re


config = load_config()
logger = logging.getLogger("ChatbotNDH")

FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE",
    "ALTER", "CREATE USER", "GRANT", "REVOKE", "SET ROLE"
]

DB = Database_data()

async def sql_double_check(llm, previous_sql: str, sql_error: str, attempt: int, prompt_input_sql: str) -> str:

    # Enhanced prompt with previous attempt information
    prompt_input = {
        'question': prompt_input_sql['question'],
        'tables_name': prompt_input_sql['tables_name'],
        'table_description': prompt_input_sql['table_description'],
        'columns_info': prompt_input_sql['columns_info'],
        'sql_error': sql_error,
        'previous_sql': previous_sql,
    }
    sql_generation_prompt = SQL_GENERATION_DOUBLE_CHECK.format(**prompt_input)
    
    try:
        llm_sql_response = await invoke_llm_for_full_response(llm, [HumanMessage(content=sql_generation_prompt)])
        return llm_sql_response
    except Exception as e:
        logger.error(f"LLM invocation failed: {str(e)}")
        return f"Lỗi khi gọi LLM: {str(e)}"

def execute_sql_query(sql_query: str) -> Dict[str, Any]:
    result = {
        "status": "error",
        "data": None,
        "message": "",
        "columns": None,
        "row_count": 0
    }

    # Normalize SQL
    normalized_sql = ' '.join(sql_query.upper().split())
    for keyword in FORBIDDEN_KEYWORDS:
        if f" {keyword} " in f" {normalized_sql} " or normalized_sql.startswith(keyword + " "):
            result["message"] = f"Lỗi: Câu lệnh SQL chứa từ khóa không được phép: {keyword}. Chỉ cho phép SELECT."
            # return result

    if not normalized_sql.startswith("SELECT"):
        result["message"] = "Lỗi: Chỉ cho phép thực thi câu lệnh SELECT."
        # return result

    try:
        conn, cur = DB.connect()
        if conn is None or cur is None:
            result["message"] = "Không thể kết nối database!"
            logger.error('Không thể kết nối database!')
            # return result

        # Execute query
        cur.execute(sql_query)
        rows = cur.fetchall() if cur.description else None
        
        if rows is None:
            result["message"] = "Câu lệnh đã được thực thi nhưng không trả về dữ liệu."
            result["status"] = "success_no_data"
        elif all(cell is None for row in rows for cell in row):
            result["message"] = "Câu lệnh đã được thực thi nhưng không trả về dữ liệu."
            result["status"] = "success_no_data"
        else:
            result["row_count"] = len(rows)
            result["data"] = rows[:20]  # Limit to 20 rows
            result["columns"] = [desc[0] for desc in cur.description]

            if result["row_count"] > 20:
                result["message"] = f"Thành công. Hiển thị 20 dòng đầu tiên trong tổng số {result['row_count']} dòng."
            else:
                result["message"] = f"Thành công. Lấy được {result['row_count']} dòng."
            result["status"] = "success"

    except Exception as e:
        result["message"] = f"Lỗi thực thi SQL: {str(e)}"
        result["status"] = "db_error"
        logger.error(f"SQL execution error: {str(e)}")

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

    return result

async def execute_sql_with_retry(llm, query: str, tables: List[str], initial_sql: str, prompt_input_sql: str, max_attempts: int = 3) -> Dict[str, Any]:
    result = {
        "status": "error",
        "data": None,
        "message": "",
        "columns": None,
        "row_count": 0,
        "attempts_made": 0
    }
    
    current_sql = initial_sql
    for attempt in range(1, max_attempts + 1):
        result = execute_sql_query(current_sql)
        result["attempts_made"] = attempt
        
        if result["status"] == "success":
            return result
            
        if result["status"] in ["success_no_data", "db_error"]:
            error_message = result["message"]
            logger.info(f"Attempt {attempt} failed: {error_message}. Generating new SQL...")
            
            new_sql = await sql_double_check(llm, current_sql, error_message, attempt, prompt_input_sql)
            new_sql = re.search(r"```sql\s*([\s\S]+?)\s*```", new_sql)
            new_sql = new_sql.group(1).strip()
            
            logger.info(f"NEW SQL {attempt}: {new_sql}")
            
            if isinstance(new_sql, str) and new_sql.startswith("Lỗi"):
                result["message"] = f"Không thể tạo câu SQL mới: {new_sql}"
                return result
                
            current_sql = new_sql
        else:
            return result
            
        if attempt == max_attempts:
            result["message"] = f"Đã thử {max_attempts} lần nhưng không lấy được dữ liệu. Lỗi cuối cùng: {result['message']}"
            return result

    return result

def format_sql_result_for_llm_analysis( query_result: Dict[str, Any], max_rows: int = 20, max_cols: int = 20) -> str:
    
    status = query_result.get("status")
    if status == "success" and query_result["data"]:
        cols = query_result["columns"][:max_cols]
        rows = query_result["data"][:max_rows]

        # lines = [f"Các cột: {', '.join(cols)}", "Các hàng dữ liệu:"]
        lines = [f"{', '.join(cols)}"]
        for row in rows:
            line = ", ".join(
                str(cell) for cell in row[:max_cols]
            )
            lines.append(f"{line}")

        more_rows = query_result["row_count"] - len(rows)
        if more_rows > 0:
            lines.append("...")
            lines.append(f"phía trên là {len(rows)} dòng dữ liệu và còn {more_rows} dòng dữ liệu chưa hiển thị.")
        return "\n".join(lines)
    elif status == "success_no_data":
        return "Truy vấn không trả về dòng dữ liệu nào."
    else:
        return f"Lỗi: {query_result.get('message', 'Không rõ')}"