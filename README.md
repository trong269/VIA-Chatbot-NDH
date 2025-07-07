# VIA Chatbot NDH - Backend API

![VIA Chatbot NDH](https://img.shields.io/badge/VIA%20Chatbot-NDH-blue)
![Version](https://img.shields.io/badge/version-1.0.0-green)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![Status](https://img.shields.io/badge/status-production-green)

## 📚 Giới thiệu

VIA Chatbot NDH là hệ thống chatbot thông minh được phát triển cho dữ liệu bài viết (> 10.000 bài viết) trên trang web Người Đồng Hành (NDH) của Viettel Construction Joint Stock Corporation, kết hợp giữa tìm kiếm vector và SQL để tối ưu hóa khả năng truy vấn dữ liệu. Dự án sử dụng công nghệ AI tiên tiến để cung cấp khả năng tìm kiếm và trích xuất thông tin chính xác từ cơ sở dữ liệu.

Dự án này là phần backend API, với giao diện người dùng được xây dựng trên nền tảng mã nguồn mở [Dify](https://github.com/langgenius/dify).

## 🌟 Tính năng chính

- **Tìm kiếm vector thông minh**: Sử dụng Milvus làm cơ sở dữ liệu vector để tìm kiếm ngữ nghĩa
- **Truy vấn SQL động**: Chuyển đổi câu hỏi tự nhiên thành truy vấn SQL cho dữ liệu có cấu trúc
- **Đồng bộ hóa dữ liệu tự động**: Hỗ trợ đồng bộ dữ liệu từ MariaDB sang PostgreSQL và Vector DB
- **Xử lý đa ngôn ngữ**: Hỗ trợ tiếng Việt và tiếng Anh
- **Tích hợp với LLM**: Kết hợp với mô hình ngôn ngữ lớn GPT-4.1 để phân tích và xử lý câu hỏi
- **API RESTful**: Cung cấp các endpoint API dễ tích hợp với các hệ thống frontend khác nhau

## 🛠️ Kiến trúc hệ thống

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  MariaDB    │────▶│ PostgreSQL  │────▶│  Vector DB      │
│  (Source)   │     │ (Processed) │     │  (Milvus)       │
└─────────────┘     └─────────────┘     └─────────────────┘
        ───────────────────│                       │
        │                                          │
        ▼                                          ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  SQL Agent  │◀───▶│ FastAPI     │◀───▶│  Vector Search│
│             │     │ Backend     │     │  Agent          │
└─────────────┘     └─────────────┘     └─────────────────┘
        ▲                 │
        │                 ▼
        │          ┌─────────────┐
        └──────────│  Dify UI    │
                   │  Frontend   │
                   └─────────────┘
```

## 🚀 Cài đặt

### Yêu cầu hệ thống

- Python 3.12+
- PostgreSQL 13+ 
- Milvus 2.0+
- MariaDB (cở sở dữ liệu gốc)

### Cài đặt môi trường

```bash
# Clone repository
git clone https://github.com/trong269/VIA-Chatbot-NDH.git
cd VIA_Chatbot_NDH

# Tạo môi trường với conda
conda env create -f environment.yml

# Kích hoạt môi trường
conda activate via_ndh_env
```

### Cấu hình

1. Tạo file `.env` trong thư mục gốc dự án:

```
NDH_MARIADB_HOST=your_mariadb_host
NDH_MARIADB_PORT=your_mariadb_port
NDH_MARIADB_USER=your_mariadb_user
NDH_MARIADB_PW=your_mariadb_password
NDH_MARIADB_DB=your_mariadb_database

NDH_PG_HOST=your_postgres_host
NDH_PG_PORT=your_postgres_port
NDH_PG_USER=your_postgres_user
NDH_PG_PW=your_postgres_password
NDH_PG_DB=your_postgres_database
```

2. Cập nhật file `configs/config.yaml` nếu cần thay đổi cấu hình:
   - API keys
   - Thông tin kết nối cơ sở dữ liệu
   - Cấu hình vector database
   - Các tham số hệ thống khác

## 🏃‍♂️ Chạy dự án

### Khởi động API Server

```bash
# Khởi động API server
python retrieval_app.py
```

### Chạy đồng bộ hóa dữ liệu

```bash
# Đồng bộ từ MariaDB sang PostgreSQL
python db_ndh_sync.py

# Đồng bộ từ PostgreSQL sang Vector DB
python vdb_ndh_sync.py
```

### Sử dụng script khởi động tự động

```bash
# Khởi động tất cả các dịch vụ
bash run.sh
```

## 📖 API Reference

### Endpoint: /retrieval

**Method:** POST

**Description:** Tìm kiếm và trả về các tài liệu liên quan đến truy vấn.

**Request Body:**
```json
{
  "knowledge_id": "string",
  "query": "string",
  "retrieval_setting": {
    "top_k": 2,
    "score_threshold": 0
  }
}
```

**Response Body:**
```json
{
  "records": [
    {
      "metadata": {
        "published_time": "string",
        "category_name": "string",
        "link": "string",
        "author": "string",
        "created_at": "string",
        "updated_at": "string"
      },
      "score": 0.95,
      "title": "string",
      "header": "string",
      "content": "string"
    }
  ]
}
```

### Authentication

API sử dụng Bearer token authentication:

```
Authorization: Bearer <your_token>
```

## 🧩 Tích hợp với Dify

VIA Chatbot NDH sử dụng [Dify github](https://github.com/langgenius/dify) làm giao diện người dùng, một nền tảng mã nguồn mở để xây dựng các ứng dụng AI.

### Thiết lập External Knowledge Base trong  Dify để Sử dụng Milvus làm cơ sở dữ liệu vector để tìm kiếm ngữ nghĩa :

1. Cài đặt và cấu hình Dify theo hướng dẫn tại [trang chủ Dify](https://docs.dify.ai/getting-started/install-self-hosted)
2. Trong Dify, tạo một ứng dụng mới và chọn "External API" làm nguồn dữ liệu
3. Cấu hình endpoint API để trỏ đến `/retrieval` của VIA Chatbot NDH API
4. Thiết lập xác thực API với Bearer token

### Thiết lập Truy vấn SQL (Text to SQL) trong Dify:

1. Tạo một Flow trong ứng dụng Dify với nút "HTTP Request"
2. Cấu hình HTTP Request với các thông số sau:
   - Method: POST
   - URL: http://<your server>:8004/sql_retrieval (endpoint của SQL Agent)
   - Headers: 
     ```
     accept: application/json
     Content-Type: application/json
     ```

#### Request Body:
```json
{
  "query": "{{input}}",
}
```

| Tham số | Kiểu | Mô tả |
|---------|------|-------|
| query | string | Câu hỏi bằng ngôn ngữ tự nhiên để chuyển đổi sang SQL |


#### Response Body:
```json
{
  "status": "string",
  "message": "string",
  "sql_result_summary": "string",
  "table_name": "string",
  "table_description": "string",
  "column_descriptions": "string"
}
```

3. Kết nối nút HTTP Request với các nút xử lý kết quả để hiển thị dữ liệu SQL truy vấn được
4. Thiết lập prompt trong Dify để hướng dẫn người dùng nhập câu hỏi dưới dạng ngôn ngữ tự nhiên, ví dụ: "Cho tôi 5 bài viết mới nhất về chủ đề đời sống"

## 🔍 Cấu trúc dự án

```
.
├── agents/                 # Các agent xử lý truy vấn
│   ├── agent_sql_search.py # Agent xử lý truy vấn SQL
│   └── agent_vector_search.py # Agent xử lý tìm kiếm vector
├── configs/                # Cấu hình
│   ├── config.py           # Loader cấu hình
│   ├── config.yaml         # File cấu hình chính
│   ├── logging_config.py   # Cấu hình logging
│   └── prompt.py           # Các prompt cho LLM
├── data/                   # Dữ liệu
│   └── metadata.json       # Metadata của các bảng
├── logs/                   # Log files
├── modules/                # Các module chức năng
│   ├── data_utils.py       # Tiện ích xử lý dữ liệu
│   ├── db.py               # Kết nối cơ sở dữ liệu
│   ├── db_executor.py      # Thực thi SQL
│   ├── indexer.py          # Xử lý vector indexing
│   ├── llm_invoker.py      # Gọi LLM
│   └── parser.py           # Xử lý parsing
├── utils/                  # Tiện ích
│   └── questions_handle.py # Xử lý câu hỏi
├── db_ndh_sync.py          # Đồng bộ từ MariaDB sang PostgreSQL
├── retrieval_app.py        # FastAPI application
├── run.sh                  # Script khởi động
├── vdb_ndh_sync.py         # Đồng bộ PostgreSQL sang Vector DB
└── environment.yml         # Cấu hình môi trường conda
```

## 🔄 Quy trình làm việc

1. Dữ liệu được đồng bộ từ MariaDB sang PostgreSQL qua `db_ndh_sync.py`
2. Dữ liệu từ PostgreSQL được xử lý và đồng bộ vào Vector DB thông qua `vdb_ndh_sync.py`
3. API server (`retrieval_app.py`) xử lý các yêu cầu từ frontend
4. Các agent (`agent_sql_search.py` và `agent_vector_search.py`) xử lý truy vấn và trả về kết quả

## 📊 Hiệu suất và Mở rộng

- Dự án hỗ trợ mở rộng theo chiều ngang bằng cách triển khai nhiều instance API
- Vector DB có thể được mở rộng để xử lý hàng triệu tài liệu
- Cấu trúc module hóa cho phép dễ dàng thay thế các thành phần như LLM hoặc Vector DB

## 👥 Đóng góp

Mọi đóng góp cho dự án đều được hoan nghênh. Vui lòng tuân theo quy trình sau:

1. Fork repository
2. Tạo nhánh tính năng (`git checkout -b feature/amazing-feature`)
3. Commit các thay đổi (`git commit -m 'Add some amazing feature'`)
4. Push lên nhánh (`git push origin feature/amazing-feature`)
5. Mở Pull Request


## 📞 Liên hệ

Để biết thêm thông tin, vui lòng liên hệ team phát triển qua email: [trongbg2692004@gmail.com](mailto:trongbg2692004@gmail.com)
