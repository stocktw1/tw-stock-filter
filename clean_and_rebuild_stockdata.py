import os
import glob
import time
import random
import io
import shutil
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

STOCKDATA_DIR = "stockdata"
START_DATE = "2020-01-01"
END_DATE = "2026-08-21"

def get_official_symbols():
    twse_dict = {}
    tpex_dict = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        r2 = requests.get('https://isin.twse.com.tw/isin/C_public.jsp?strMode=2', headers=headers, timeout=15)
        df2 = pd.read_html(io.StringIO(r2.text))[0]
        for idx, row in df2.iterrows():
            val = str(row.iloc[0]).strip()
            parts = val.split()
            if len(parts) >= 2:
                code = parts[0]
                name = parts[1]
                if code.isdigit() and len(code) == 4:
                    twse_dict[code] = name
    except Exception as e:
        print(f"[!] 取得 TWSE 清單失敗: {e}")

    try:
        r4 = requests.get('https://isin.twse.com.tw/isin/C_public.jsp?strMode=4', headers=headers, timeout=15)
        df4 = pd.read_html(io.StringIO(r4.text))[0]
        for idx, row in df4.iterrows():
            val = str(row.iloc[0]).strip()
            parts = val.split()
            if len(parts) >= 2:
                code = parts[0]
                name = parts[1]
                if code.isdigit() and len(code) == 4:
                    tpex_dict[code] = name
    except Exception as e:
        print(f"[!] 取得 TPEx 清單失敗: {e}")

    return twse_dict, tpex_dict

def download_clean_symbol(symbol, suffix, start_date, end_date):
    yf_symbol = f"{symbol}{suffix}"
    csv_filename = f"{symbol}_{start_date}_{end_date}.csv"
    target_path = os.path.join(STOCKDATA_DIR, csv_filename)
    
    # 若檔案已存在且大小正常且不是空檔，可跳過
    if os.path.exists(target_path) and os.path.getsize(target_path) > 10000:
        return True, symbol, "已存在"
        
    for attempt in range(8):
        try:
            ticker = yf.Ticker(yf_symbol)
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
            
            # 每次請求使用全新的獨立 DataFrame 變數
            df = yf.download(yf_symbol, start=start_date, end=end_dt, auto_adjust=False, progress=False)
            
            if df is None or df.empty or len(df) < 5:
                time.sleep(random.uniform(1.2, 3.0))
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df.index = pd.to_datetime(pd.to_datetime(df.index).date)
            
            if 'Close' not in df.columns or df['Close'].dropna().empty:
                time.sleep(random.uniform(1.2, 3.0))
                continue
                
            # 校正除權因子
            try:
                splits = ticker.splits
                if splits is not None and not splits.empty:
                    splits.index = pd.to_datetime(pd.to_datetime(splits.index).date)
                    split_factors = pd.Series(1.0, index=df.index)
                    for s_date, s_val in splits.items():
                        if s_val > 0 and s_val != 1.0:
                            split_factors[split_factors.index < s_date] *= float(s_val)
                    
                    for col in ['Open', 'High', 'Low', 'Close']:
                        if col in df.columns:
                            df[col] = (pd.to_numeric(df[col], errors='coerce') * split_factors).round(2)
            except Exception:
                pass
                
            df.to_csv(target_path)
            return True, symbol, f"成功 ({len(df)} 筆)"
            
        except Exception as e:
            time.sleep(random.uniform(1.5, 3.5))
            
    return False, symbol, "下載失敗"

def rebuild_all():
    print("[*] 正在從證交所/櫃買中心獲取官方清單...")
    twse_dict, tpex_dict = get_official_symbols()
    print(f"[*] 官方上市檔數: {len(twse_dict)}, 上櫃檔數: {len(tpex_dict)}")
    
    # 建立下載任務清單
    tasks = []
    for code in twse_dict:
        tasks.append((code, ".TW"))
    for code in tpex_dict:
        tasks.append((code, ".TWO"))
        
    total = len(tasks)
    print(f"[*] 開始獨立乾淨下載全市場歷史數據 (共 {total} 檔)...")
    
    # 執行多輪下載直到 100% 完成
    for round_num in range(1, 4):
        missing_tasks = []
        for sym, suf in tasks:
            p = os.path.join(STOCKDATA_DIR, f"{sym}_{START_DATE}_{END_DATE}.csv")
            if not os.path.exists(p) or os.path.getsize(p) < 10000:
                missing_tasks.append((sym, suf))
                
        if not missing_tasks:
            print("[*] 全部股票資料已 100% 完整無缺！")
            break
            
        print(f"[*] 第 {round_num} 輪下載：剩餘 {len(missing_tasks)} 檔未完成...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(download_clean_symbol, sym, suf, START_DATE, END_DATE): sym for sym, suf in missing_tasks}
            for idx, fut in enumerate(as_completed(futures), 1):
                pass
        time.sleep(2)
        
    # 清理非官方清單的垃圾 CSV
    all_valid_syms = set(twse_dict.keys()).union(set(tpex_dict.keys()))
    current_csvs = glob.glob(f"{STOCKDATA_DIR}/*.csv")
    cleaned_count = 0
    for c_path in current_csvs:
        c_sym = os.path.basename(c_path).split('_')[0]
        if c_sym not in all_valid_syms:
            try:
                os.remove(c_path)
                cleaned_count += 1
            except Exception:
                pass
                
    final_csvs = glob.glob(f"{STOCKDATA_DIR}/*.csv")
    print("==================================================")
    print(f"[*] 全市場資料庫徹底乾淨建置完成！現存有效 CSV 總數: {len(final_csvs)} 檔 (已清理 {cleaned_count} 檔無效檔案)")
    print("==================================================")

if __name__ == "__main__":
    # 先清空原本所有帶有污染重複的舊 CSV
    if os.path.exists(STOCKDATA_DIR):
        print("[*] 正在清空舊有被污染的資料庫資料夾...")
        shutil.rmtree(STOCKDATA_DIR)
    os.makedirs(STOCKDATA_DIR, exist_ok=True)
    rebuild_all()
