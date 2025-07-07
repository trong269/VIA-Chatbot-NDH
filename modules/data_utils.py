# modules/data_utils.py
import json
from typing import List, Optional, Dict, Any


def load_table_metadata(file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        standardized_data = []
        for item in data:
            standardized_item = {
                "table_name": item.get("table", item.get("table_name")),
                "description": item.get("description"),
                "columns": item.get("columns", []),
                "sample_questions": item.get("sample_questions", [])
            }
            # Đảm bảo các cột cũng có tên chuẩn
            standardized_columns = []
            for col in standardized_item["columns"]:
                standardized_columns.append({
                    "column_name": col.get("column", col.get("column_name")),
                    "data_type": col.get("data_type"),
                    "description": col.get("description")
                })
            standardized_item["columns"] = standardized_columns
            if standardized_item["table_name"]: 
                 standardized_data.append(standardized_item)
        return standardized_data
    except FileNotFoundError:
        print(f"Critical error: Metadata file {file_path} not found.")
        raise FileNotFoundError(f"Critical error: Metadata file {file_path} not found.")
    except json.JSONDecodeError:
        print(f"Critical error: Metadata file {file_path} is corrupted.")
        raise json.JSONDecodeError(f"Critical error: Metadata file {file_path} is corrupted.", "", 0)