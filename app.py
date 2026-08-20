import os
import sys

# 轉發執行主要的篩選器程式
current_dir = os.path.dirname(os.path.abspath(__file__))
web_app_file = os.path.join(current_dir, "股票技術指標篩選器_Web.py")

with open(web_app_file, "r", encoding="utf-8") as f:
    code = f.read()

exec(code)
