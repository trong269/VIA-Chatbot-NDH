
def format_question_sql_string(question_text, sql_query):
    if not sql_query:
        return f"Câu hỏi: \"{question_text}\"\nTruy vấn SQL:\nKhông có truy vấn SQL.\n"

    formatted_string = f"Câu hỏi: \"{question_text}\"\n"
    formatted_string += "Truy vấn SQL:\n"
    formatted_string += "```sql\n"
    for line in sql_query.strip().split('\n'):
        formatted_string += f"{line}\n"
    formatted_string += "```\n"
    return formatted_string

def extract_and_format_from_selected_tables(all_metadata, target_table_names_list, max_questions=3):
    if not all_metadata:
        return ["Thông báo: Dữ liệu 'all_metadata' rỗng hoặc chưa được nạp.\n"]
    
    if not target_table_names_list:
        return ["Thông báo: Danh sách 'target_table_names_list' rỗng. Sẽ không có bảng nào được xử lý.\n"]

    formatted_results = []
    printed_count = 0

    for table_entry in all_metadata:
        if printed_count >= max_questions:
            break

        current_table_name = table_entry.get("table_name")
        if current_table_name and current_table_name in target_table_names_list:
            sample_questions_list = table_entry.get("sample_questions", [])
            if not isinstance(sample_questions_list, list):
                continue

            for qa_pair in sample_questions_list:
                if printed_count >= max_questions:
                    break

                if isinstance(qa_pair, dict):
                    question = qa_pair.get("question")
                    sql = qa_pair.get("sql")
                    if question and sql:
                        formatted_string = format_question_sql_string(question, sql)
                        formatted_results.append(formatted_string.strip() + "\n" + "-" * 40 + "\n")
                        printed_count += 1

    if not formatted_results:
        return ["Không tìm thấy cặp câu hỏi-SQL nào có đủ thông tin trong các bảng mục tiêu đã chỉ định.\n"]
    
    return formatted_results