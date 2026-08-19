"""
台股歷史資料自動增量更新腳本 (Headless / CLI 模式)
適用於 GitHub Actions 定時排程或背景無介面自動更新。
"""

import os
import glob
import time
import pandas as pd
import yfinance as yf

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

def update_all_stocks():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"建立資料夾: {DATA_DIR}")

    existing_csvs = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not existing_csvs:
        print("未找到現有股票 CSV 檔案。")
        return

    today_str = pd.Timestamp.now().strftime('%Y-%m-%d')
    print(f"=== 開始執行增量更新 (目標最新日期: {today_str}) ===")

    success_count = 0
    skipped_count = 0
    fail_count = 0

    for i, csv_path in enumerate(existing_csvs):
        filename = os.path.basename(csv_path)
        parts = filename.replace(".csv", "").split("_")
        if len(parts) < 3:
            continue

        symbol = parts[0]
        orig_start = parts[1]
        last_date = parts[2]

        if last_date >= today_str:
            skipped_count += 1
            continue

        fetch_start = (pd.to_datetime(last_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        fetch_end = (pd.to_datetime(today_str) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

        if fetch_start >= fetch_end:
            skipped_count += 1
            continue

        print(f"[{i+1}/{len(existing_csvs)}] 更新 {symbol} (從 {fetch_start} 到 {today_str})...")

        # 嘗試下載 (TW -> TWO)
        df_new = None
        for suffix in ['.TW', '.TWO']:
            try:
                ticker_obj = yf.Ticker(f"{symbol}{suffix}")
                df_temp = ticker_obj.history(start=fetch_start, end=fetch_end, auto_adjust=False)
                if not df_temp.empty:
                    df_new = df_temp
                    break
            except Exception:
                pass

        if df_new is None or df_new.empty:
            fail_count += 1
            continue

        try:
            # 讀取舊資料並合併
            df_old = pd.read_csv(csv_path, index_col=0)
            if 'Ticker' in df_old.index:
                df_old = df_old.drop(index=['Ticker', 'Date'], errors='ignore')
            df_old.index = pd.to_datetime(df_old.index)

            df_new.index = pd.to_datetime(df_new.index).tz_localize(None)
            df_combined = pd.concat([df_old, df_new])
            df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
            df_combined.sort_index(inplace=True)

            # 新檔案名稱
            actual_last_date = df_combined.index[-1].strftime('%Y-%m-%d')
            new_filename = f"{symbol}_{orig_start}_{actual_last_date}.csv"
            new_filepath = os.path.join(DATA_DIR, new_filename)

            df_combined.to_csv(new_filepath)
            if new_filepath != csv_path and os.path.exists(csv_path):
                os.remove(csv_path)

            success_count += 1
            time.sleep(0.1)  # 避免過於頻繁觸發 yfinance 限速
        except Exception as e:
            print(f"合併 {symbol} 失敗: {e}")
            fail_count += 1

    print(f"\n=== 更新完成！成功: {success_count}, 已是最新: {skipped_count}, 失敗: {fail_count} ===")

if __name__ == "__main__":
    update_all_stocks()
