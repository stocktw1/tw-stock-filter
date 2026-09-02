import os
import sys
import glob
import time
import json
import pandas as pd
import numpy as np

# 確保在 Windows 控制台輸出正常
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = r"D:\csv資料庫\01_金融市場_台股每日行情\daily_records"
OUTPUT_PATH = os.path.join(BASE_DIR, "stockdata")
STOCK_NAMES_PATH = os.path.join(BASE_DIR, "stock_names.json")

def clean_num(val, is_float=True):
    if val is None or pd.isna(val):
        return None if is_float else 0
    val_str = str(val).strip().replace(",", "").replace('"', '').replace("+", "")
    if val_str in ["--", "---", "-", "null", "None", "", "NaN", "nan", "除權", "除息"]:
        return None if is_float else 0
    try:
        f = float(val_str)
        return f if is_float else int(f)
    except ValueError:
        return None if is_float else 0

def execute_clean_assembly():
    print("==================================================")
    print("🚀 開始執行全市場歷史資料全量清空重組作業 (D 槽嚴格唯讀)")
    print(f"📂 資料來源: {DB_PATH}")
    print(f"💾 輸出目錄: {OUTPUT_PATH}")
    print("==================================================")

    if not os.path.exists(DB_PATH):
        print(f"❌ 錯誤：找不到資料庫路徑 {DB_PATH}")
        return False

    csv_files = sorted(glob.glob(os.path.join(DB_PATH, "*.csv")))
    if not csv_files:
        print("❌ 錯誤：daily_records 中找不到任何每日行情 CSV 檔案！")
        return False

    total_files = len(csv_files)
    print(f"📊 共發現 {total_files} 個每日交易記錄檔案。")

    # 1. 清空本地 stockdata 資料夾
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    old_files = glob.glob(os.path.join(OUTPUT_PATH, "*.csv"))
    print(f"🧹 正在清空 stockdata/ 資料夾 (共移除 {len(old_files)} 個舊檔案)...")
    for f in old_files:
        try:
            os.remove(f)
        except Exception:
            pass
    print("✅ stockdata/ 資料夾已完全清空！")

    # 2. 唯讀載入每日行情資料庫
    print("⚡ 正在高速載入與分組每日收盤行情 (純記憶體處理)...")
    t0 = time.time()
    stock_records = {}
    stock_names = {}
    processed_dates = []

    for idx, fpath in enumerate(csv_files, 1):
        # 1. 快速檔案大小過濾（休市假檔案固定約 73KB，真實全市場交易日 > 90KB）
        try:
            if os.path.getsize(fpath) < 85 * 1024:
                continue
        except Exception:
            pass

        fname = os.path.basename(fpath).replace(".csv", "")
        date_raw = fname.replace("-", "")
        if len(date_raw) == 8 and date_raw.isdigit():
            file_date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        else:
            file_date_str = fname

        try:
            try:
                df_day = pd.read_csv(fpath, encoding='utf-8-sig', dtype=str)
            except Exception:
                df_day = pd.read_csv(fpath, encoding='cp950', dtype=str)

            cols = {c.strip(): c for c in df_day.columns}
            c_code = cols.get('證券代號') or cols.get('代號')
            c_name = cols.get('證券名稱') or cols.get('名稱')
            c_open = cols.get('開盤價') or cols.get('開盤')
            c_high = cols.get('最高價') or cols.get('最高')
            c_low = cols.get('最低價') or cols.get('最低')
            c_close = cols.get('收盤價') or cols.get('收盤')
            c_vol = cols.get('成交股數') or cols.get('成交量')

            if not (c_code and c_close):
                continue

            # 2. 核心真偽校驗：真實全市場交易日至少有 1200 檔以上，且權值股 2330 必須在其中撮合交易
            codes_series = df_day[c_code].astype(str).str.strip()
            if len(df_day) < 1200 or not (codes_series == '2330').any():
                continue

            for row in df_day.itertuples(index=False):
                row_dict = row._asdict()
                code = str(row_dict.get(c_code, '')).strip()
                if not code or code in ["--", "---", "nan", "None"]:
                    continue
                if len(code) not in (4, 5):
                    continue

                name = str(row_dict.get(c_name, '')).strip() if c_name else ""
                if name and code not in stock_names:
                    stock_names[code] = name

                c_val = clean_num(row_dict.get(c_close))
                if c_val is None:
                    continue

                o_val = clean_num(row_dict.get(c_open)) if c_open else c_val
                h_val = clean_num(row_dict.get(c_high)) if c_high else c_val
                l_val = clean_num(row_dict.get(c_low)) if c_low else c_val
                v_val = clean_num(row_dict.get(c_vol), is_float=False) if c_vol else 0

                o_val = o_val if o_val is not None else c_val
                h_val = h_val if h_val is not None else c_val
                l_val = l_val if l_val is not None else c_val

                if code not in stock_records:
                    stock_records[code] = []
                stock_records[code].append((file_date_str, c_val, c_val, h_val, l_val, o_val, v_val))

            processed_dates.append(file_date_str)
        except Exception as e:
            print(f"⚠️ 讀取 {fname} 異常: {e}")

        if idx % 300 == 0 or idx == total_files:
            print(f"[*] 載入進度: {idx}/{total_files} 日 ({idx/total_files*100:.1f}%) - 已累計 {len(stock_records)} 檔個股")

    actual_start_date = min(processed_dates) if processed_dates else "2021-08-09"
    actual_end_date = max(processed_dates) if processed_dates else "2026-08-24"
    print(f"✅ 資料庫載入完成！有效交易日共 {len(processed_dates)} 天 ({actual_start_date} ~ {actual_end_date})，涵蓋 {len(stock_records)} 檔股票。耗時: {time.time()-t0:.2f} 秒")

    # 3. 輸出個股 CSV
    print(f"💾 開始將 {len(stock_records)} 檔個股寫入 stockdata/ ...")
    cols = ['Adj Close', 'Close', 'High', 'Low', 'Open', 'Volume']
    saved_count = 0
    t1 = time.time()

    for s_idx, (code, rows) in enumerate(stock_records.items(), 1):
        rows.sort(key=lambda x: x[0])
        dates = [r[0] for r in rows]
        data_matrix = [[r[1], r[2], r[3], r[4], r[5], r[6]] for r in rows]

        df_out = pd.DataFrame(data_matrix, index=dates, columns=cols)
        df_out.index.name = 'Date'
        out_filename = f"{code}_{actual_start_date}_{actual_end_date}.csv"
        out_filepath = os.path.join(OUTPUT_PATH, out_filename)

        try:
            df_out.to_csv(out_filepath)
            saved_count += 1
        except Exception as e:
            print(f"⚠️ 寫入 {code} 失敗: {e}")

        if s_idx % 500 == 0 or s_idx == len(stock_records):
            print(f"[*] 寫入進度: {s_idx}/{len(stock_records)} 檔 ({s_idx/len(stock_records)*100:.1f}%)")

    # 4. 更新 stock_names.json
    if stock_names:
        try:
            if os.path.exists(STOCK_NAMES_PATH):
                try:
                    with open(STOCK_NAMES_PATH, 'r', encoding='utf-8') as f:
                        curr_names = json.load(f)
                    curr_names.update(stock_names)
                    stock_names = curr_names
                except Exception:
                    pass
            with open(STOCK_NAMES_PATH, 'w', encoding='utf-8') as f:
                json.dump(stock_names, f, ensure_ascii=False, indent=2)
            print(f"📝 成功更新 stock_names.json (共 {len(stock_names)} 檔個股)")
        except Exception as e:
            print(f"⚠️ 更新 stock_names.json 失敗: {e}")

    print("==================================================")
    print(f"🎉 全量組裝大功告成！共成功產出 {saved_count} 檔個股 CSV，總耗時 {time.time()-t0:.2f} 秒。")
    print("==================================================")
    return True

if __name__ == "__main__":
    execute_clean_assembly()
