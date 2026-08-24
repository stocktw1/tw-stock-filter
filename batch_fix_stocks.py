import os
import glob
import time
import random
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

STOCKDATA_DIR = "stockdata"

def get_market_lists():
    twse = set()
    tpex = set()
    try:
        url_twse = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        res_twse = requests.get(url_twse, timeout=10)
        dfs_twse = pd.read_html(res_twse.text)
        if dfs_twse:
            df = dfs_twse[0]
            for val in df.iloc[:, 0].dropna():
                parts = str(val).split()
                if len(parts) >= 2 and parts[0].isdigit():
                    twse.add(parts[0])
    except Exception as e:
        print(f"[!] 取得 TWSE 清單失敗: {e}")

    try:
        url_tpex = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
        res_tpex = requests.get(url_tpex, timeout=10)
        dfs_tpex = pd.read_html(res_tpex.text)
        if dfs_tpex:
            df = dfs_tpex[0]
            for val in df.iloc[:, 0].dropna():
                parts = str(val).split()
                if len(parts) >= 2 and parts[0].isdigit():
                    tpex.add(parts[0])
    except Exception as e:
        print(f"[!] 取得 TPEx 清單失敗: {e}")

    return twse, tpex

def download_and_clean_single(csv_path, twse_set, tpex_set):
    filename = os.path.basename(csv_path)
    parts = filename.replace(".csv", "").split("_")
    if len(parts) < 3:
        return False, filename, "格式不符"

    symbol = parts[0]
    orig_start = parts[1]
    orig_end = parts[2]

    if symbol in twse_set:
        yf_symbol = f"{symbol}.TW"
    elif symbol in tpex_set:
        yf_symbol = f"{symbol}.TWO"
    else:
        yf_symbol = f"{symbol}.TW"

    # 重試下載機制
    for attempt in range(4):
        try:
            t = yf.Ticker(yf_symbol)
            end_dt = pd.to_datetime(orig_end) + pd.Timedelta(days=1)
            raw_data = yf.download(yf_symbol, start=orig_start, end=end_dt, auto_adjust=False, progress=False)
            
            if not raw_data.empty:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    raw_data.columns = raw_data.columns.get_level_values(0)
                
                raw_data.index = pd.to_datetime(pd.to_datetime(raw_data.index).date)
                
                splits = t.splits
                if splits is not None and not splits.empty:
                    splits.index = pd.to_datetime(pd.to_datetime(splits.index).date)
                    split_factors = pd.Series(1.0, index=raw_data.index)
                    for s_date, s_val in splits.items():
                        if s_val > 0 and s_val != 1.0:
                            # 嚴格大於當前交易日（即除權交易日前）才乘
                            split_factors[split_factors.index < s_date] *= float(s_val)
                    
                    for col in ['Open', 'High', 'Low', 'Close']:
                        if col in raw_data.columns:
                            raw_data[col] = (pd.to_numeric(raw_data[col], errors='coerce') * split_factors).round(2)

                raw_data.to_csv(csv_path)
                return True, symbol, "成功"
            else:
                time.sleep(random.uniform(1.0, 2.5))
        except Exception as e:
            time.sleep(random.uniform(1.5, 3.0))

    return False, symbol, "下載失敗或無資料"

def main():
    print("[*] 正在獲取上市上櫃分類清單...")
    twse_set, tpex_set = get_market_lists()
    print(f"[*] 上市代碼數: {len(twse_set)}, 上櫃代碼數: {len(tpex_set)}")

    csvs = glob.glob(f"{STOCKDATA_DIR}/*.csv")
    total = len(csvs)
    print(f"[*] 開始下載並校正全市場歷史未還原市價資料 (共 {total} 檔)...")

    # 先以單獨優先測試 2542 和 2030
    for test_sym in ['2542', '2030']:
        matches = glob.glob(f"{STOCKDATA_DIR}/*{test_sym}*.csv")
        if matches:
            res, sym, msg = download_and_clean_single(matches[0], twse_set, tpex_set)
            print(f"[*] 優先驗證 {test_sym}: {res} ({msg})")

    success_count = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(download_and_clean_single, p, twse_set, tpex_set): p for p in csvs}
        for idx, fut in enumerate(as_completed(futures), 1):
            try:
                res, sym, msg = fut.result()
                if res:
                    success_count += 1
            except Exception:
                pass
            if idx % 100 == 0 or idx == total:
                print(f"[*] 進度: {idx}/{total} (已成功 {success_count} 檔)")

    print(f"[*] 全部處理完畢！成功更新 {success_count}/{total} 檔。")

if __name__ == "__main__":
    main()
