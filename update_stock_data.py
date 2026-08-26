"""
台股歷史資料自動增量更新腳本 (Headless / CLI 模式)
- 採用證交所 (TWSE) 與 櫃買中心 (TPEx) 官方全市場 API 極速下載
- 自動比對現有 CSV 資料最後交易日，增量附加最新數據
- 更新完成後自動更新檔名並徹底刪除舊資料檔
- 適用於 GitHub Actions 定時排程、本地排程或手動一鍵更新
"""

import os
import sys
import glob
import time
import requests
import pandas as pd
import yfinance as yf

# 確保在 Windows 控制台或無介面環境下輸出 UTF-8 編碼
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "stockdata")


def clean_float(val):
    if val is None:
        return None
    val = str(val).strip().replace(",", "")
    if val in ["--", "---", "null", "None", ""]:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def clean_int(val):
    if val is None:
        return 0
    val = str(val).strip().replace(",", "")
    if val in ["--", "---", "null", "None", ""]:
        return 0
    try:
        return int(float(val))
    except ValueError:
        return 0


def fetch_market_symbols(market_type):
    """獲取全市場上市/上櫃代碼清單"""
    url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={2 if market_type == 'TWSE' else 4}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'big5-hkscs'
        df_list = pd.read_html(res.text)
        if df_list:
            df = df_list[0]
            df.columns = df.iloc[0]
            df = df.iloc[1:]
            symbols = []
            for item in df['有價證券代號及名稱'].dropna():
                parts = str(item).strip().split()
                if len(parts) >= 2:
                    code = parts[0]
                    if code.isdigit() and len(code) == 4:
                        symbols.append(code)
            return symbols
    except Exception as e:
        print(f"[!] 獲取 {market_type} 代碼清單失敗: {e}")
    return []


def update_all_stocks(target_end_date_str=None):
    """執行全市場收盤數據增量更新並刪除舊資料檔"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"[+] 建立資料庫資料夾: {DATA_DIR}")

    existing_csvs = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not existing_csvs:
        print("[!] 未在 stockdata 資料夾中找到任何現有的股票 CSV 檔案。")
        return

    today_str = target_end_date_str or pd.Timestamp.now().strftime('%Y-%m-%d')
    target_end_date = pd.to_datetime(today_str)
    print("==================================================")
    print(f"[*] 開始執行台股盤後數據增量更新 (目標最新日期: {today_str})")
    print("==================================================")

    # 1. 極速掃描現有檔案的最新日期與起始日期 (直接從檔名快速解析)
    stock_last_dates = {}
    stock_files = {}
    stock_orig_starts = {}

    for csv_path in existing_csvs:
        filename = os.path.basename(csv_path)
        parts = filename.replace(".csv", "").split("_")
        if len(parts) >= 3:
            symbol = parts[0]
            orig_start = parts[1]
            orig_end = parts[2]
            if symbol.isdigit():
                try:
                    last_date = pd.to_datetime(orig_end)
                    stock_last_dates[symbol] = last_date
                    stock_files[symbol] = csv_path
                    stock_orig_starts[symbol] = orig_start
                except Exception:
                    try:
                        df_old = pd.read_csv(csv_path, index_col=0, low_memory=False)
                        valid_dates = pd.to_datetime(df_old.index, errors='coerce').dropna()
                        if not valid_dates.empty:
                            last_date = valid_dates[-1]
                            stock_last_dates[symbol] = last_date
                            stock_files[symbol] = csv_path
                            stock_orig_starts[symbol] = orig_start
                    except Exception as e:
                        print(f"[!] {symbol} 讀取舊檔失敗: {e}")

    if not stock_last_dates:
        print("[!] 無有效股票資料檔案可更新。")
        return

    # 2. 過濾需要更新的股票
    need_update_stocks = {sym: d for sym, d in stock_last_dates.items() if d < target_end_date}
    if not need_update_stocks:
        print(f"[*] 所有 {len(stock_last_dates)} 檔股票資料皆已是最新狀態，無需更新！")
        clean_duplicate_old_csvs()
        return

    min_last_date = min(need_update_stocks.values())
    start_download_date = min_last_date + pd.Timedelta(days=1)
    download_dates = pd.date_range(start=start_download_date, end=target_end_date, freq='B')

    if download_dates.empty:
        print("[*] 此區間無交易日需要更新！")
        clean_duplicate_old_csvs()
        return

    total_days = len(download_dates)
    print(f"[*] 預計下載交易日區間: {start_download_date.strftime('%Y-%m-%d')} ~ {today_str} (共 {total_days} 天)")

    # 3. 透過證交所 / 櫃買中心 API 下載全市場盤後收盤資料 (含重試機制)
    day_data = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for d_idx, date_ts in enumerate(download_dates, 1):
        date_str = date_ts.strftime('%Y-%m-%d')
        date_param = date_ts.strftime('%Y%m%d')
        print(f"[*] [{d_idx}/{total_days}] 下載 {date_str} 全市場收盤行情...")
        day_data[date_str] = {}

        # 下載 TWSE (上市) - 最多重試 3 次
        for attempt in range(3):
            try:
                url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={date_param}&type=ALL"
                res = requests.get(url, headers=headers, timeout=15)
                if res.status_code == 200:
                    r_json = res.json()
                    if r_json.get("stat") == "OK" and "tables" in r_json:
                        for tbl in r_json["tables"]:
                            fields = tbl.get("fields", [])
                            if "證券代號" in fields:
                                idx_code = fields.index("證券代號")
                                idx_open = fields.index("開盤價") if "開盤價" in fields else 5
                                idx_high = fields.index("最高價") if "最高價" in fields else 6
                                idx_low = fields.index("最低價") if "最低價" in fields else 7
                                idx_close = fields.index("收盤價") if "收盤價" in fields else 8
                                idx_vol = fields.index("成交股數") if "成交股數" in fields else 2

                                for row in tbl.get("data", []):
                                    code = str(row[idx_code]).strip()
                                    day_data[date_str][code] = {
                                        'Open': clean_float(row[idx_open]),
                                        'High': clean_float(row[idx_high]),
                                        'Low': clean_float(row[idx_low]),
                                        'Close': clean_float(row[idx_close]),
                                        'Volume': clean_int(row[idx_vol])
                                    }
                                break
                    break
            except Exception as e:
                if attempt == 2:
                    print(f"[!] {date_str} TWSE 下載/解析異常: {e}")
                time.sleep(2.0)

        # 下載 TPEx (上櫃) - 最多重試 3 次
        for attempt in range(3):
            try:
                tw_year = date_ts.year - 1911
                tpex_date = f"{tw_year}/{date_ts.strftime('%m/%d')}"
                url = f"https://www.tpex.org.tw/web/stock/aftertrading/DAILY_CLOSE_quotes/stk_quote_result.php?l=zh-tw&o=json&d={tpex_date}"
                res = requests.get(url, headers=headers, timeout=15)
                if res.status_code == 200:
                    r_json = res.json()
                    if "tables" in r_json:
                        for tbl in r_json["tables"]:
                            fields = tbl.get("fields", [])
                            if "代號" in fields or "證券代號" in fields:
                                idx_code = fields.index("代號") if "代號" in fields else fields.index("證券代號")
                                idx_open = fields.index("開盤") if "開盤" in fields else 4
                                idx_high = fields.index("最高") if "最高" in fields else 5
                                idx_low = fields.index("最低") if "最低" in fields else 6
                                idx_close = fields.index("收盤") if "收盤" in fields else 2
                                idx_vol = fields.index("成交股數") if "成交股數" in fields else 8

                                for row in tbl.get("data", []):
                                    code = str(row[idx_code]).strip()
                                    day_data[date_str][code] = {
                                        'Open': clean_float(row[idx_open]),
                                        'High': clean_float(row[idx_high]),
                                        'Low': clean_float(row[idx_low]),
                                        'Close': clean_float(row[idx_close]),
                                        'Volume': clean_int(row[idx_vol])
                                    }
                                break
                    break
            except Exception as e:
                if attempt == 2:
                    print(f"[!] {date_str} TPEx 下載/解析異常: {e}")
                time.sleep(2.0)

        if not day_data[date_str]:
            print(f"[-] {date_str} 無收盤資料 (非交易日或證交所未開盤)")

        if d_idx < total_days:
            time.sleep(1.0)

    # 4. 附加新數據至 CSV，並自動更名與刪除舊檔 (極速檔案寫入模式)
    update_symbols = list(need_update_stocks.keys())
    total_symbols = len(update_symbols)
    print(f"[*] 正在增量更新並清理舊檔 (共 {total_symbols} 檔個股)...")

    success_count = 0
    updated_files_count = 0

    for s_idx, symbol in enumerate(update_symbols, 1):
        last_date = stock_last_dates[symbol]
        orig_start = stock_orig_starts[symbol]
        old_file = stock_files[symbol]

        new_lines = []
        new_indices = []

        for date_ts in download_dates:
            if date_ts > last_date:
                date_str = date_ts.strftime('%Y-%m-%d')
                if date_str in day_data and symbol in day_data[date_str]:
                    s_data = day_data[date_str][symbol]
                    if s_data['Close'] is not None:
                        c = s_data['Close']
                        h = s_data['High'] if s_data['High'] is not None else c
                        l = s_data['Low'] if s_data['Low'] is not None else c
                        o = s_data['Open'] if s_data['Open'] is not None else c
                        v = s_data['Volume']
                        new_lines.append(f"{date_str},{c},{c},{h},{l},{o},{v}\n")
                        new_indices.append(date_str)

        # 若有新資料，直接寫入檔案尾部
        if new_lines:
            try:
                with open(old_file, "a", encoding="utf-8") as f:
                    f.writelines(new_lines)
                updated_files_count += 1
            except Exception as e:
                print(f"[!] {symbol} 寫入附加資料失敗: {e}")

        # 確定實際最新日期
        actual_last_date = last_date
        if new_indices:
            actual_last_date = pd.to_datetime(new_indices[-1])

        actual_last_date_str = actual_last_date.strftime('%Y-%m-%d')
        new_filename = f"{symbol}_{orig_start}_{actual_last_date_str}.csv"
        new_filepath = os.path.join(DATA_DIR, new_filename)

        # 檔案更名與刪除舊檔
        if old_file != new_filepath:
            try:
                if os.path.exists(new_filepath):
                    os.remove(new_filepath)
                os.rename(old_file, new_filepath)
                stock_files[symbol] = new_filepath
                success_count += 1
            except Exception as e:
                print(f"[!] {symbol} 檔案更名/刪除舊檔失敗: {e}")
        else:
            success_count += 1

    # 5. 最後全面清理：防止任何同一股票有多個不同日期舊檔案的情況
    clean_duplicate_old_csvs()

    print("\n==================================================")
    print("[*] 盤後資料更新完成！")
    print(f"[*] 總計處理: {total_symbols} 檔股票")
    print(f"[*] 寫入最新行情: {updated_files_count} 檔")
    print("[*] 舊資料檔已全數自動刪除/更名完成！")
    print("==================================================")


def clean_duplicate_old_csvs():
    """全面掃描 stockdata 資料夾，確保每個股票代碼僅保留最新日期的一個 CSV，刪除所有舊檔"""
    all_csvs = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    stocks_map = {}

    for path in all_csvs:
        filename = os.path.basename(path)
        parts = filename.replace(".csv", "").split("_")
        if len(parts) >= 3 and parts[0].isdigit():
            symbol = parts[0]
            orig_start = parts[1]
            end_date = parts[2]
            if symbol not in stocks_map:
                stocks_map[symbol] = []
            stocks_map[symbol].append((end_date, path))

    deleted_count = 0
    for symbol, file_list in stocks_map.items():
        if len(file_list) > 1:
            # 依據結束日期排序，保留最新的一個
            file_list.sort(key=lambda x: x[0], reverse=True)
            newest_file = file_list[0][1]
            for _, old_file_path in file_list[1:]:
                try:
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                        deleted_count += 1
                except Exception as e:
                    print(f"[!] 清理舊檔案 {old_file_path} 失敗: {e}")

    if deleted_count > 0:
        print(f"[*] 已額外清理並刪除 {deleted_count} 個歷史重複/舊版本 CSV 檔案。")


if __name__ == "__main__":
    update_all_stocks()

