import os
import glob
import time
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

STOCKDATA_DIR = "stockdata"

def fix_single_stock(csv_path):
    filename = os.path.basename(csv_path)
    parts = filename.replace(".csv", "").split("_")
    if len(parts) < 3:
        return False, filename, "格式不符"
    
    symbol = parts[0]
    orig_start = parts[1]
    orig_end = parts[2]
    
    if not symbol.isdigit():
        return False, symbol, "非數字代碼"

    try:
        # 下載完整歷史未還原數據
        for suffix in ['.TW', '.TWO']:
            yf_symbol = f"{symbol}{suffix}"
            t = yf.Ticker(yf_symbol)
            splits = t.splits
            
            # 若無 splits 或下載成功
            raw_data = yf.download(yf_symbol, start=orig_start, end=pd.to_datetime(orig_end) + pd.Timedelta(days=1), auto_adjust=False, progress=False)
            if not raw_data.empty:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    raw_data.columns = raw_data.columns.get_level_values(0)
                
                raw_data.index = pd.to_datetime(raw_data.index.date)
                
                if splits is not None and not splits.empty:
                    splits.index = pd.to_datetime(splits.index.date)
                    split_factors = pd.Series(1.0, index=raw_data.index)
                    for s_date, s_val in splits.items():
                        if s_val > 0 and s_val != 1.0:
                            # 嚴格大於當前日期（即該交易日在除權日之前）才乘
                            split_factors[split_factors.index < s_date] *= float(s_val)
                    
                    for col in ['Open', 'High', 'Low', 'Close']:
                        if col in raw_data.columns:
                            raw_data[col] = (raw_data[col] * split_factors).round(2)
                
                # 重新儲存乾淨標準 CSV (保留 yfinance 格式結構)
                raw_data.to_csv(csv_path)
                num_splits = len(splits[(splits > 0) & (splits != 1.0)]) if splits is not None and not splits.empty else 0
                return True, symbol, f"成功校正 ({num_splits} 次除權)"
                
        return False, symbol, "無數據"
    except Exception as e:
        return False, symbol, f"錯誤: {e}"

def fix_all_stocks(max_workers=10):
    csvs = glob.glob(f"{STOCKDATA_DIR}/*.csv")
    total = len(csvs)
    print(f"[*] 開始重新下載並精確校正全市場歷史數據 (共 {total} 檔)...")
    
    fixed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(fix_single_stock, csv_path): csv_path for csv_path in csvs}
        for idx, future in enumerate(as_completed(future_to_file), 1):
            try:
                is_fixed, symbol, msg = future.result()
                if is_fixed:
                    fixed_count += 1
            except Exception:
                pass
            
            if idx % 100 == 0 or idx == total:
                print(f"[*] 進度: {idx}/{total} (已完成 {fixed_count} 檔)")

    print("==================================================")
    print(f"[*] 全市場歷史數據精確校正完成！共完成 {fixed_count} 檔。")
    print("==================================================")

if __name__ == "__main__":
    fix_all_stocks(max_workers=12)
