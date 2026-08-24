import os
import sys
import glob
import io
import threading
import tkinter as tk
import requests
from tkinter import filedialog, messagebox
import pandas as pd
import yfinance as yf


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


class StockDownloaderApp:

    def __init__(self, root):
        self.root = root
        self.root.title("台股歷史資料下載器 v1.0")
        self.root.geometry("500x650")

        # 建立 UI 元件
        self.create_widgets()

        # 執行狀態控制
        self.is_running = False

    def create_widgets(self):
        # 標題
        title_label = tk.Label(
            self.root, text="台股歷史資料下載器 v1.0", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=10)

        # 1. 儲存路徑設定
        path_frame = tk.LabelFrame(self.root, text="儲存路徑設定")
        path_frame.pack(fill="x", padx=15, pady=5)

        self.path_entry = tk.Entry(path_frame)
        self.path_entry.pack(
            side="left", fill="x", expand=True, padx=5, pady=5
        )
        # 預設路徑設為程式所在目錄下的 stockdata 資料夾
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        default_path = os.path.join(base_dir, "stockdata")
        self.path_entry.insert(0, default_path)
        self.setup_context_menu(self.path_entry)

        path_btn = tk.Button(path_frame, text="選擇", command=self.browse_path)
        path_btn.pack(side="right", padx=5, pady=5)

        # 2. 日期範圍設定
        date_frame = tk.LabelFrame(self.root, text="日期範圍設定 (YYYY-MM-DD)")
        date_frame.pack(fill="x", padx=15, pady=5)

        # Allow the second column in the grid to expand
        date_frame.columnconfigure(1, weight=1)

        tk.Label(date_frame, text="起始日期：").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.start_entry = tk.Entry(date_frame)
        self.start_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.start_entry.insert(0, "2020-01-01")
        self.setup_context_menu(self.start_entry)

        tk.Label(date_frame, text="結束日期：").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.end_entry = tk.Entry(date_frame)
        self.end_entry.grid(row=1, column=1, sticky="ew", padx=5)
        self.end_entry.insert(0, pd.Timestamp.now().strftime('%Y-%m-%d'))
        self.setup_context_menu(self.end_entry)

        # 3. 市場選擇
        market_frame = tk.Frame(self.root)
        market_frame.pack(fill="x", padx=15, pady=10)

        self.twse_var = tk.BooleanVar(value=True)
        self.tpex_var = tk.BooleanVar(value=True)

        twse_chk = tk.Checkbutton(
            market_frame, text="上市 TWSE", variable=self.twse_var
        )
        twse_chk.pack(side="left", padx=20)

        tpex_chk = tk.Checkbutton(
            market_frame, text="上櫃 TPEx", variable=self.tpex_var
        )
        tpex_chk.pack(side="left", padx=20)

        # 4. 按鈕控制區
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=15, pady=5)

        self.start_btn = tk.Button(
            btn_frame,
            text="開始下載",
            bg="#D1E8FF",
            command=lambda: self.start_download_thread("all"),
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=3, ipady=5)

        self.update_btn = tk.Button(
            btn_frame,
            text="更新現有資料",
            bg="#E8FFD1",
            command=lambda: self.start_download_thread("update"),
        )
        self.update_btn.pack(side="left", fill="x", expand=True, padx=3, ipady=5)

        self.stop_btn = tk.Button(
            btn_frame,
            text="停止下載",
            state="disabled",
            command=self.stop_download,
        )
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=3, ipady=5)

        # 5. 進度條文字
        self.progress_label = tk.Label(self.root, text="進度：0%", anchor="w")
        self.progress_label.pack(fill="x", padx=15, pady=5)

        # 6. 執行訊息
        msg_frame = tk.LabelFrame(self.root, text="執行訊息：")
        msg_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_text = tk.Text(msg_frame, height=12, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.setup_context_menu(self.log_text)

    def setup_context_menu(self, widget):
        """為元件建立滑鼠右鍵選單 (剪下/複製/貼上/全選)"""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="剪下", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="複製", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="貼上", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        
        def select_all(e=None):
            if isinstance(widget, tk.Text):
                widget.tag_add("sel", "1.0", "end")
            else:
                widget.selection_range(0, tk.END)
                widget.icursor(tk.END)
            return "break"
            
        menu.add_command(label="全選", command=select_all)
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def browse_path(self):
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, selected_dir)

    def log(self, message):
        """向訊息視窗輸出日誌"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def start_download_thread(self, mode="all"):
        """透過執行緒（Thread）啟動下載，避免介面凍結"""
        if self.is_running:
            return
        self.is_running = True
        self.start_btn.config(state="disabled")
        self.update_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        # 啟動背景執行緒
        download_thread = threading.Thread(target=self.download_process, args=(mode,))
        download_thread.daemon = True
        download_thread.start()

    def stop_download(self):
        if self.is_running:
            self.is_running = False
            self.log("🔔 收到停止指令，正在中斷下載...")

    def fetch_symbols(self, market_type):
        """從證交所/櫃買中心獲取所有個股代碼"""
        self.log(f"🔍 正在獲取 {market_type} 全市場股票清單...")
        symbols = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        # 優先方案：使用 TWSE / TPEx 官方 OpenAPI (速度快且不受網頁 HTML 格式改變影響)
        try:
            if market_type == "TWSE":
                url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
                res = requests.get(url, headers=headers, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    for item in data:
                        code = str(item.get("Code", "")).strip()
                        if len(code) == 4 and code.isdigit():
                            symbols.append(code)
            else:
                url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
                res = requests.get(url, headers=headers, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    for item in data:
                        code = str(item.get("SecuritiesCompanyCode", "")).strip()
                        if len(code) == 4 and code.isdigit():
                            symbols.append(code)

            if symbols:
                unique_symbols = sorted(list(set(symbols)))
                self.log(f"✅ 成功透過 OpenAPI 獲取 {market_type} 清單 (共 {len(unique_symbols)} 檔)")
                return unique_symbols
        except Exception as e:
            self.log(f"⚠️ OpenAPI 獲取 {market_type} 清單失敗，切換為備用爬蟲方案: {str(e)}")

        # 備用方案：爬取 ISIN 網頁表格 (使用 io.StringIO 避免 Pandas 3.x 解析異常)
        try:
            mode = "2" if market_type == "TWSE" else "4"
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = "big5"
            dfs = pd.read_html(io.StringIO(response.text))
            df = dfs[0]

            for val in df[0]:
                ticker = str(val).split()[0]
                if len(ticker) == 4 and ticker.isdigit():
                    symbols.append(ticker)
            unique_symbols = sorted(list(set(symbols)))
            self.log(f"✅ 成功透過網頁爬蟲獲取 {market_type} 清單 (共 {len(unique_symbols)} 檔)")
            return unique_symbols
        except Exception as e:
            self.log(f"❌ 無法獲取 {market_type} 清單: {str(e)}")
            return []


    def download_process(self, mode="all"):
        save_path = self.path_entry.get().strip()
        start_date = self.start_entry.get().strip()
        end_date = self.end_entry.get().strip()

        # yfinance 的 end 參數為不包含 (exclusive)，所以需要往後加一天以確保包含使用者指定的結束日
        try:
            yf_end_date = (pd.to_datetime(end_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        except Exception as e:
            self.log(f"❌ 日期格式錯誤: {str(e)}")
            self.reset_ui()
            return

        # 建立資料夾
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
                self.log(f"📁 已建立儲存資料夾: {save_path}")
            except Exception as e:
                self.log(f"❌ 無法建立資料夾: {str(e)}")
                self.reset_ui()
                return

        # 根據 mode 決定目標股票清單
        if mode == "update":
            self.log("🔍 正在掃描儲存路徑下的現有股票 CSV 檔案...")
            existing_csvs = glob.glob(os.path.join(save_path, "*.csv"))
            
            if not existing_csvs:
                self.log("⚠️ 未在儲存路徑中找到任何已下載的股票 CSV 檔案，無法進行更新。")
                self.reset_ui()
                return
            
            stock_last_dates = {}
            stock_files = {}
            stock_orig_starts = {}
            
            for csv_path in existing_csvs:
                filename = os.path.basename(csv_path)
                parts = filename.replace(".csv", "").split("_")
                if len(parts) >= 3:
                    symbol, orig_start, orig_end = parts[0], parts[1], parts[2]
                    if symbol.isdigit():
                        try:
                            # 讀取 CSV
                            df_old = pd.read_csv(csv_path, index_col=0, low_memory=False)
                            valid_dates = pd.to_datetime(df_old.index, errors='coerce').dropna()
                            if not valid_dates.empty:
                                last_date = valid_dates[-1]
                                stock_last_dates[symbol] = last_date
                                stock_files[symbol] = csv_path
                                stock_orig_starts[symbol] = orig_start
                        except Exception as e:
                            self.log(f"⚠️ {symbol} 讀取舊檔失敗: {str(e)}")
            
            if not stock_last_dates:
                self.log("⚠️ 儲存路徑下的 CSV 檔案皆無有效日期，無法進行更新。")
                self.reset_ui()
                return
            
            # 計算需要更新的日期範圍
            target_end_date = pd.to_datetime(end_date)
            # 過濾出真正需要更新的股票 (最後日期早於目標結束日期)
            need_update_stocks = {sym: d for sym, d in stock_last_dates.items() if d < target_end_date}
            
            if not need_update_stocks:
                self.log("⚡ 現有股票資料已是最新，無需更新！")
                messagebox.showinfo("完成", "股票資料已是最新！")
                self.reset_ui()
                return
            
            min_last_date = min(need_update_stocks.values())
            start_download_date = min_last_date + pd.Timedelta(days=1)
            
            # 生成需要下載的日期清單 (排除六日)
            download_dates = pd.date_range(start=start_download_date, end=target_end_date, freq='B')
            
            if download_dates.empty:
                self.log("⚡ 此區間無交易日需要更新！")
                messagebox.showinfo("完成", "此區間無交易日需要更新！")
                self.reset_ui()
                return
            
            day_data = {}
            total_days = len(download_dates)
            self.log(f"📅 預計下載更新的交易日天數: {total_days} 天")
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            
            for d_idx, date_ts in enumerate(download_dates, 1):
                if not self.is_running:
                    break
                date_str = date_ts.strftime('%Y-%m-%d')
                date_param = date_ts.strftime('%Y%m%d')
                
                self.log(f"📥 正在下載 {date_str} 全市場收盤行情 ({d_idx}/{total_days})...")
                day_data[date_str] = {}
                
                # 下載 TWSE (上市)
                try:
                    url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={date_param}&type=ALL"
                    res = requests.get(url, headers=headers, timeout=10)
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
                except Exception as e:
                    self.log(f"⚠️ {date_str} TWSE 下載/解析失敗: {str(e)}")
                
                # 下載 TPEx (上櫃)
                try:
                    tw_year = date_ts.year - 1911
                    tpex_date = f"{tw_year}/{date_ts.strftime('%m/%d')}"
                    url = f"https://www.tpex.org.tw/web/stock/aftertrading/DAILY_CLOSE_quotes/stk_quote_result.php?l=zh-tw&o=json&d={tpex_date}"
                    res = requests.get(url, headers=headers, timeout=10)
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
                except Exception as e:
                    self.log(f"⚠️ {date_str} TPEx 下載/解析失敗: {str(e)}")
                
                # 檢查當天是否真的有下載到資料
                if not day_data[date_str]:
                    self.log(f"ℹ️ {date_str} 證交所與櫃買中心無收盤行情資料 (可能尚未收盤、非交易日或 API 暫時無回應)")
                
                # 禮貌延遲
                if d_idx < total_days and self.is_running:
                    import time
                    time.sleep(1.0)
            
            if not self.is_running:
                self.log("🛑 更新任務已手動停止。")
                self.reset_ui()
                return
            
            # 獲取全市場清單以便比對上市/上櫃
            self.log("🔍 正在獲取市場清單以比對上市/上櫃類別...")
            all_twse = self.fetch_symbols("TWSE")
            all_tpex = self.fetch_symbols("TPEx")
            active_twse = set(all_twse) if self.twse_var.get() else set()
            active_tpex = set(all_tpex) if self.tpex_var.get() else set()
            
            # 找出符合目前勾選市場的股票
            update_symbols = []
            for sym in stock_last_dates:
                if sym in active_twse or sym in active_tpex:
                    update_symbols.append(sym)
            
            total_symbols_count = len(update_symbols)
            self.log(f"✍️ 正在將收盤數據轉檔附加至 {total_symbols_count} 檔個股 CSV...")
            
            for s_idx, symbol in enumerate(update_symbols, 1):
                if not self.is_running:
                    break
                
                last_date = stock_last_dates[symbol]
                orig_start = stock_orig_starts[symbol]
                old_file = stock_files[symbol]
                
                yf_symbol = f"{symbol}.TW" if symbol in active_twse else f"{symbol}.TWO"
                
                new_rows = []
                new_indices = []
                
                for date_ts in download_dates:
                    if date_ts > last_date:
                        date_str = date_ts.strftime('%Y-%m-%d')
                        if date_str in day_data and symbol in day_data[date_str]:
                            s_data = day_data[date_str][symbol]
                            if s_data['Close'] is not None:
                                new_rows.append([
                                    s_data['Close'], # Adj Close
                                    s_data['Close'], # Close
                                    s_data['High'] if s_data['High'] is not None else s_data['Close'],
                                    s_data['Low'] if s_data['Low'] is not None else s_data['Close'],
                                    s_data['Open'] if s_data['Open'] is not None else s_data['Close'],
                                    s_data['Volume']
                                ])
                                new_indices.append(date_str)
                
                if new_rows:
                    cols = pd.MultiIndex.from_tuples([
                        ('Adj Close', yf_symbol),
                        ('Close', yf_symbol),
                        ('High', yf_symbol),
                        ('Low', yf_symbol),
                        ('Open', yf_symbol),
                        ('Volume', yf_symbol)
                    ], names=['Price', 'Ticker'])
                    
                    df_new = pd.DataFrame(new_rows, columns=cols, index=new_indices)
                    try:
                        df_new.to_csv(old_file, mode='a', header=False)
                        self.log(f"✅ {symbol} ({s_idx}/{total_symbols_count}) 附加 {len(new_rows)} 筆資料。")
                    except Exception as e:
                        self.log(f"⚠️ {symbol} 寫入失敗: {str(e)}")
                else:
                    self.log(f"⚡ {symbol} ({s_idx}/{total_symbols_count}) 無新資料需要附加。")
                
                # 更名反映實際最新日期
                actual_last_date = last_date
                if new_rows:
                    actual_last_date = pd.to_datetime(new_indices[-1])
                
                actual_last_date_str = actual_last_date.strftime('%Y-%m-%d')
                new_filename = f"{symbol}_{orig_start}_{actual_last_date_str}.csv"
                new_filepath = os.path.join(save_path, new_filename)
                if old_file != new_filepath:
                    try:
                        if os.path.exists(new_filepath):
                            os.remove(new_filepath)
                        os.rename(old_file, new_filepath)
                        stock_files[symbol] = new_filepath
                    except Exception as e:
                        self.log(f"⚠️ {symbol} 檔案更名失敗: {str(e)}")
                
                # 更新 UI 進度
                progress = int((s_idx / total_symbols_count) * 100)
                self.progress_label.config(text=f"進度：{progress}%")
            
            if self.is_running:
                self.log("🎉 所有股票資料更新完成！")
                messagebox.showinfo("完成", "已完成增量收盤行情更新！")
            else:
                self.log("🛑 更新已手動停止。")
            
            self.reset_ui()
            return
            
        else:
            # 預設：動態獲取全市場清單
            twse_symbols = self.fetch_symbols("TWSE") if self.twse_var.get() else []
            tpex_symbols = self.fetch_symbols("TPEx") if self.tpex_var.get() else []
            target_symbols = twse_symbols + tpex_symbols

        if not target_symbols:
            self.log("⚠️ 未勾選任何市場或無下載目標！")
            self.reset_ui()
            return

        total_count = len(target_symbols)
        self.log(f"🚀 開始下載，總計 {total_count} 檔股票資料...")

        for idx, symbol in enumerate(target_symbols, 1):
            if not self.is_running:
                break

            # 轉換為 yfinance 格式：上市為 .TW，上櫃為 .TWO
            yf_symbol = (
                f"{symbol}.TW" if symbol in twse_symbols else f"{symbol}.TWO"
            )
            
            # 檢查是否已有該檔股票的歷史紀錄檔
            pattern = os.path.join(save_path, f"{symbol}_*.csv")
            existing_files = glob.glob(pattern)
            updated = False
            download_triggered = False

            if existing_files:
                existing_files.sort()
                old_file = existing_files[-1]
                try:
                    # 讀取舊檔案的 index 以確認最後日期
                    df_old = pd.read_csv(old_file, index_col=0, low_memory=False)
                    valid_dates = pd.to_datetime(df_old.index, errors='coerce').dropna()

                    if not valid_dates.empty:
                        basename = os.path.basename(old_file)
                        parts = basename.replace(".csv", "").split("_")
                        orig_start = parts[1] if len(parts) >= 2 else start_date

                        # 如果要求下載的起始日早於舊檔的起始日，則放棄更新，直接重新全量下載
                        if orig_start > start_date:
                            self.log(f"⚠️ {symbol} 現有資料起始日 ({orig_start}) 晚於設定日期 ({start_date})，將重新完整下載。")
                        else:
                            last_date = valid_dates[-1]
                            target_end = pd.to_datetime(end_date)

                            if last_date >= target_end:
                                self.log(f"⚡ {symbol} ({idx}/{total_count}) 已是最新資料，跳過下載。")
                                updated = True
                            else:
                                next_date = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                                self.log(f"正在更新 {symbol} ({idx}/{total_count}) 自 {next_date} 起的新資料...")
                                new_data = yf.download(yf_symbol, start=next_date, end=yf_end_date, progress=False, auto_adjust=False)
                                download_triggered = True

                                if not new_data.empty:
                                    # 以附加模式寫入，不寫入 header，無縫接軌舊資料
                                    new_data.to_csv(old_file, mode='a', header=False)
                                    self.log(f"✅ {symbol} 附加更新成功！")
                                else:
                                    self.log(f"✅ {symbol} 在 {next_date} 後無新資料。")

                                # 將舊檔案更名，以反映新的結束日期
                                new_filename = f"{symbol}_{orig_start}_{end_date}.csv"
                                new_filepath = os.path.join(save_path, new_filename)
                                if old_file != new_filepath:
                                    if os.path.exists(new_filepath):
                                        os.remove(new_filepath)
                                    os.rename(old_file, new_filepath)

                                updated = True
                except Exception as e:
                    self.log(f"⚠️ {symbol} 讀取舊檔失敗，將重新下載: {str(e)}")

            if not updated:
                self.log(f"正在下載 {symbol} ({idx}/{total_count})...")
                try:
                    # 下載完整資料 (明確設定 auto_adjust=False 以符合券商未還原行情)
                    stock_data = yf.download(
                        yf_symbol, start=start_date, end=yf_end_date, progress=False, auto_adjust=False
                    )
                    download_triggered = True

                    if not stock_data.empty:
                        # 自動校正 yfinance 預設股票分割除權因子，還原為台灣券商真實未還原撮合價
                        try:
                            t = yf.Ticker(yf_symbol)
                            splits = t.splits
                            if splits is not None and not splits.empty:
                                if isinstance(stock_data.columns, pd.MultiIndex):
                                    stock_data.columns = stock_data.columns.get_level_values(0)
                                stock_data.index = pd.to_datetime(pd.to_datetime(stock_data.index).date)
                                splits.index = pd.to_datetime(pd.to_datetime(splits.index).date)
                                
                                split_factors = pd.Series(1.0, index=stock_data.index)
                                for s_date, s_val in splits.items():
                                    if s_val > 0 and s_val != 1.0:
                                        # 嚴格大於當前日期（即該交易日在除權日之前）才乘
                                        split_factors[split_factors.index < s_date] *= float(s_val)
                                
                                for col in ['Open', 'High', 'Low', 'Close']:
                                    if col in stock_data.columns:
                                        stock_data[col] = (pd.to_numeric(stock_data[col], errors='coerce') * split_factors).round(2)
                        except Exception:
                            pass

                        # 存成 CSV 檔
                        file_name = f"{symbol}_{start_date}_{end_date}.csv"
                        full_file_path = os.path.join(save_path, file_name)
                        stock_data.to_csv(full_file_path)
                        self.log(f"✅ {symbol} 完整下載成功 -> {file_name}")
                    else:
                        self.log(f"📭 {symbol} 在此區間無資料。")

                except Exception as e:
                    self.log(f"❌ {symbol} 下載失敗: {str(e)}")

            # 更新 UI 進度
            progress = int((idx / total_count) * 100)
            self.progress_label.config(text=f"進度：{progress}%")

            # 隨機延遲，防止被 Yahoo Finance 封鎖
            if download_triggered and idx < total_count and self.is_running:
                import time
                import random
                time.sleep(random.uniform(0.5, 1.5))

        if self.is_running:
            self.log("🎉 所有下載任務已完成！")
            messagebox.showinfo("完成", "股票資料下載完畢！")
        else:
            self.log("🛑 下載已手動停止。")

        self.reset_ui()

    def reset_ui(self):
        self.is_running = False
        self.start_btn.config(state="normal")
        self.update_btn.config(state="normal")
        self.stop_btn.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = StockDownloaderApp(root)
    root.mainloop()
