import os
import glob
import time
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

STOCKDATA_DIR = "stockdata"

def fix_single_csv(csv_path):
    filename = os.path.basename(csv_path)
    symbol = filename.split('_')[0]
    if not symbol.isdigit():
        return False, symbol, "Non-digit symbol"

    try:
        df = pd.read_csv(csv_path, index_col=0, low_memory=False)
        is_multi_header = 'Ticker' in df.index
        if is_multi_header:
            header_rows = df.loc[['Ticker', 'Date']]
            df_data = df.drop(index=['Ticker', 'Date']).copy()
        else:
            df_data = df.copy()

        df_data.index = pd.to_datetime(df_data.index, errors='coerce')
        df_data = df_data.dropna(subset=['Close']) if 'Close' in df_data.columns else df_data

        if df_data.empty:
            return False, symbol, "Empty data"

        start_date = df_data.index.min()
        end_date = df_data.index.max()

        for suffix in ['.TW', '.TWO']:
            yf_symbol = f"{symbol}{suffix}"
            t = yf.Ticker(yf_symbol)
            try:
                splits = t.splits
                if splits is not None and not splits.empty:
                    splits.index = pd.to_datetime(splits.index.date)
                    valid_splits = splits[(splits.index > start_date) & (splits.index <= end_date) & (splits != 1.0) & (splits > 0)]
                    if not valid_splits.empty:
                        split_factors = pd.Series(1.0, index=df_data.index)
                        for s_date, s_val in valid_splits.items():
                            split_factors[split_factors.index < s_date] *= float(s_val)

                        for col in ['Open', 'High', 'Low', 'Close']:
                            if col in df_data.columns:
                                df_data[col] = (pd.to_numeric(df_data[col], errors='coerce') * split_factors).round(2)

                        if is_multi_header:
                            df_final = pd.concat([header_rows, df_data])
                        else:
                            df_final = df_data

                        df_final.to_csv(csv_path)
                        return True, symbol, f"修復 {len(valid_splits)} 次除權配股"
            except Exception:
                pass

        return False, symbol, "無需修復"
    except Exception as e:
        return False, symbol, f"錯誤: {e}"

def fix_all_stocks(max_workers=8):
    csvs = glob.glob(f"{STOCKDATA_DIR}/*.csv")
    print(f"[*] 開始掃描與修復全市場歷史 CSV 除權因子 (共 {len(csvs)} 檔)...")
    
    fixed_count = 0
    total = len(csvs)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(fix_single_csv, csv_path): csv_path for csv_path in csvs}
        for idx, future in enumerate(as_completed(future_to_file), 1):
            try:
                is_fixed, symbol, msg = future.result()
                if is_fixed:
                    fixed_count += 1
                    print(f"[{idx}/{total}] ✅ {symbol}: {msg}")
            except Exception as e:
                pass
            
            if idx % 100 == 0:
                print(f"[*] 進度: {idx}/{total} (已修復 {fixed_count} 檔)")

    print("==================================================")
    print(f"[*] 全市場除權因子修正完成！共修復 {fixed_count} 檔包含股票股利/分割的個股。")
    print("==================================================")

if __name__ == "__main__":
    fix_all_stocks(max_workers=10)
