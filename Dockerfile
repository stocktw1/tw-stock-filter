# 使用輕量級 Python 3.11 基礎映像檔
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 設定環境變數
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

# 複製依賴套件清單並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案原始碼與靜態資源
COPY . .

# 暴露 Cloud Run 預設連接埠
EXPOSE 8080

# 透過 gunicorn 啟動高性能 Flask 伺服器 (支援平行計算)
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 server:app
