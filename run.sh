# run tiến trình đồng bộ dữ liệu mới được thêm
pkill -f -9 "db_ndh_sync.py"
nohup python db_ndh_sync.py >logs/db_ndh_sync.txt 2>&1 & echo $! > logs/db_ndh_sync.pid
# tiến trình đồng bộ với dữ liệu cập nhật
pkill -f -9 "vdb_ndh_sync.py"
nohup python vdb_ndh_sync.py >logs/vdb_ndh_sync.txt 2>&1 & echo $! > logs/vdb_ndh_sync.pid
# run tiến trình backend
pkill -f -9 "retrieval_app.py"
nohup python retrieval_app.py >logs/retrieval_app.txt 2>&1 & echo $! > logs/retrieval_app.pid