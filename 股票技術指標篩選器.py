import os
import sys
import random
import re
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import pandas as pd
import numpy as np

class TechnicalFilterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("台股技術指標篩選器 v1.1 - 參數自訂版")
        self.root.geometry("700x850")
        
        # 資料存放路徑 (與下載器預設路徑一致，預設為程式同目錄下的 stockdata)
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.data_dir = os.path.join(base_dir, "stockdata")
        self.loaded_data = {}  # 暫存讀取的 DataFrame

        self.setup_ui()

    def setup_ui(self):
        # 區塊 A：指標與欄位按鍵區
        frame_a = tk.LabelFrame(self.root, text="區塊 A：指標與欄位 (點擊輸入，可自行修改括號內數字)", padx=10, pady=10)
        frame_a.pack(fill="x", padx=10, pady=5)

        # 週期選擇
        period_frame = tk.Frame(frame_a)
        period_frame.grid(row=0, column=0, columnspan=5, sticky="w", padx=5, pady=(0, 5))
        self.period_var = tk.StringVar(value="日線")
        tk.Label(period_frame, text="週期：").pack(side="left")
        tk.Radiobutton(period_frame, text="日線", variable=self.period_var, value="日線").pack(side="left")
        tk.Radiobutton(period_frame, text="週線", variable=self.period_var, value="週線").pack(side="left")
        tk.Radiobutton(period_frame, text="月線", variable=self.period_var, value="月線").pack(side="left")

        indicators = [
            ("收盤價", "C"), ("開盤價", "O"), ("最高價", "H"), ("最低價", "L"), ("成交量", "V"),
            ("K值", "K(9)"), ("D值", "D(9)"), ("RSI", "RSI(14)"), ("MACD", "MACD(12,26,9)"), ("DIFF", "DIFF(12,26)"),
            ("均價", "MA(5)"), ("均量", "VMA(5)"), ("+DI", "+DI(14)"), ("-DI", "-DI(14)"), ("ADX", "ADX(14)"),
            ("Osc", "OSC(12,26,9)"), ("Bias", "BIAS(5)"), ("Wms", "WMS(14)"), ("順勢指標", "CCI(22)"), ("Adxr", "ADXR(14)")
        ]
        
        for i, (name, code) in enumerate(indicators):
            btn = tk.Button(frame_a, text=name, width=12, command=lambda n=name, c=code: self.add_indicator(n, c))
            btn.grid(row=(i // 5) + 1, column=i % 5, padx=5, pady=5)

        # 區塊 B：運算符號與邏輯按鍵區
        frame_b = tk.LabelFrame(self.root, text="區塊 B：運算與邏輯", padx=10, pady=10)
        frame_b.pack(fill="x", padx=10, pady=5)

        operators = ["+", "-", "*", "/", ">", "<", "=", "AND", "OR"]
        for i, op in enumerate(operators):
            btn = tk.Button(frame_b, text=op, width=5, command=lambda o=op: self.add_to_formula(f"{o} "))
            btn.pack(side="left", padx=3)

        # 時間控制元件
        time_frame = tk.Frame(frame_b)
        time_frame.pack(side="left", padx=15)
        
        tk.Label(time_frame, text="n=").pack(side="left")
        self.n_days_spin = tk.Spinbox(time_frame, from_=1, to=250, width=5)
        self.n_days_spin.delete(0, "end")
        self.n_days_spin.insert(0, "1")
        self.n_days_spin.pack(side="left")
        self.setup_context_menu(self.n_days_spin)
        
        self.n_btn = tk.Button(frame_b, text="n日前", bg="#FFECB3", command=self.add_n_days)
        self.n_btn.pack(side="left", padx=5)
        
        # 當週期改變時，自動更新 n期前 按鈕文字
        self.period_var.trace_add("write", self.update_period_ui)
        self.update_period_ui()

        # 區塊 C：公式顯示與編輯區
        frame_c = tk.LabelFrame(self.root, text="區塊 C：篩選公式編輯", padx=10, pady=10)
        frame_c.pack(fill="x", padx=10, pady=5)

        # 常用公式管理列
        fav_frame = tk.Frame(frame_c)
        fav_frame.pack(fill="x", side="top", pady=(0, 5))
        
        tk.Label(fav_frame, text="常用公式：").pack(side="left")
        self.formula_combo = ttk.Combobox(fav_frame, state="readonly", width=30)
        self.formula_combo.pack(side="left", padx=5)
        
        tk.Button(fav_frame, text="載入", command=self.load_favorite_formula).pack(side="left", padx=2)
        tk.Button(fav_frame, text="儲存當前公式", command=self.save_favorite_formula).pack(side="left", padx=2)
        tk.Button(fav_frame, text="刪除", command=self.delete_favorite_formula).pack(side="left", padx=2)

        editor_frame = tk.Frame(frame_c)
        editor_frame.pack(fill="x", side="top", expand=True)

        self.formula_entry = tk.Text(editor_frame, font=("Consolas", 12), height=4, wrap=tk.WORD)
        self.formula_entry.pack(fill="x", side="left", expand=True, padx=5)
        self.setup_context_menu(self.formula_entry)
        
        clear_btn = tk.Button(editor_frame, text="清除", command=lambda: self.formula_entry.delete("1.0", tk.END))
        clear_btn.pack(side="right", padx=5)
        
        # 載入儲存的公式資料
        self.load_formulas_data()

        # 區塊 D：執行與結果顯示區
        frame_d = tk.LabelFrame(self.root, text="區塊 D：執行結果", padx=10, pady=10)
        frame_d.pack(fill="both", expand=True, padx=10, pady=5)

        btn_box = tk.Frame(frame_d)
        btn_box.pack(fill="x", pady=5)

        self.test_btn = tk.Button(btn_box, text="🎯 隨機抽樣測試 (10檔)", command=self.random_test)
        self.test_btn.pack(side="left", expand=True, fill="x", padx=5)

        self.run_btn = tk.Button(btn_box, text="🚀 開始全量篩選", bg="#D1E8FF", command=self.run_search)
        self.run_btn.pack(side="left", expand=True, fill="x", padx=5)

        self.result_text = scrolledtext.ScrolledText(frame_d, height=15, font=("Microsoft JhengHei", 10))
        self.result_text.pack(fill="both", expand=True, pady=5)
        self.setup_context_menu(self.result_text)

    def setup_context_menu(self, widget):
        """為元件建立滑鼠右鍵選單 (剪下/複製/貼上/全選)"""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="剪下", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="複製", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="貼上", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        
        def select_all(e=None):
            if isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                widget.tag_add("sel", "1.0", "end")
            else:
                widget.selection_range(0, tk.END)
                widget.icursor(tk.END)
            return "break"
            
        menu.add_command(label="全選", command=select_all)
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def add_to_formula(self, text):
        self.formula_entry.insert(tk.END, text)

    def add_indicator(self, name, code):
        period_type = self.period_var.get()
        if period_type == "週線":
            prefix = "週"
        elif period_type == "月線":
            prefix = "月"
        else:
            prefix = ""
        # 解析參數 (如果有括號)，讓所有指標都能套用「中文名稱(參數)」與「週」或「月」前綴的直覺格式
        if "(" in code:
            params = code[code.find("("):]
            self.add_to_formula(f"{prefix}{name}{params} ")
        else:
            self.add_to_formula(f"{prefix}{name} ")
            
    def update_period_ui(self, *args):
        if hasattr(self, 'n_btn'):
            period_type = self.period_var.get()
            if period_type == "月線":
                unit = "月"
            elif period_type == "週線":
                unit = "週"
            else:
                unit = "日"
            self.n_btn.config(text=f"n{unit}前")

    def add_n_days(self):
        n = self.n_days_spin.get()
        period_type = self.period_var.get()
        if period_type == "月線":
            unit = "月"
        elif period_type == "週線":
            unit = "週"
        else:
            unit = "日"
        self.add_to_formula(f"{n}{unit}前 ")

    def log(self, msg):
        self.result_text.insert(tk.END, msg + "\n")
        self.result_text.see(tk.END)

    def load_formulas_data(self):
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.formulas_file = os.path.join(base_dir, "saved_formulas.json")
        self.saved_formulas = {}
        if os.path.exists(self.formulas_file):
            try:
                with open(self.formulas_file, 'r', encoding='utf-8') as f:
                    self.saved_formulas = json.load(f)
            except Exception:
                pass
        self.update_formula_combo()

    def update_formula_combo(self):
        self.formula_combo['values'] = list(self.saved_formulas.keys())
        if self.saved_formulas:
            self.formula_combo.current(0)
        else:
            self.formula_combo.set('')

    def save_favorite_formula(self):
        formula_raw = self.formula_entry.get("1.0", tk.END).strip()
        if not formula_raw:
            messagebox.showwarning("警告", "公式為空，無法儲存！")
            return
            
        name = simpledialog.askstring("儲存公式", "請輸入公式名稱：", parent=self.root)
        if name:
            name = name.strip()
            if not name: return
            self.saved_formulas[name] = formula_raw
            self.save_formulas_to_disk()
            self.update_formula_combo()
            self.formula_combo.set(name)
            messagebox.showinfo("成功", f"公式「{name}」已儲存！")

    def load_favorite_formula(self):
        name = self.formula_combo.get()
        if not name or name not in self.saved_formulas:
            return
        formula = self.saved_formulas[name]
        self.formula_entry.insert(tk.END, formula)

    def delete_favorite_formula(self):
        name = self.formula_combo.get()
        if not name or name not in self.saved_formulas:
            return
        if messagebox.askyesno("確認", f"確定要刪除公式「{name}」嗎？"):
            del self.saved_formulas[name]
            self.save_formulas_to_disk()
            self.update_formula_combo()

    def save_formulas_to_disk(self):
        try:
            with open(self.formulas_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_formulas, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存公式失敗: {e}")

    def calculate_dynamic_indicators(self, df, required_indicators):
        """根據公式中實際使用到的指標和參數，動態計算並加入 DataFrame"""
        df = df.rename(columns={'Open': 'O', 'High': 'H', 'Low': 'L', 'Close': 'C', 'Volume': 'V'})
        
        for item in required_indicators:
            ind_type = item[0]
            
            if ind_type == 'RSI':
                period = int(item[1])
                col_name = f"RSI_{period}"
                if col_name not in df.columns:
                    delta = df['C'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                    rs = gain / loss
                    df[col_name] = 100 - (100 / (1 + rs))
                    
            elif ind_type in ['K', 'D']:
                period = int(item[1])
                k_col = f"K_{period}"
                d_col = f"D_{period}"
                if k_col not in df.columns or d_col not in df.columns:
                    low_p = df['L'].rolling(window=period).min()
                    high_p = df['H'].rolling(window=period).max()
                    rsv = (df['C'] - low_p) / (high_p - low_p) * 100
                    df[k_col] = rsv.ewm(com=2, adjust=False).mean()
                    df[d_col] = df[k_col].ewm(com=2, adjust=False).mean()

            elif ind_type in ['MACD', 'DIFF', 'OSC']:
                fast = int(item[1])
                slow = int(item[2])
                signal_period = int(item[3]) if ind_type in ['MACD', 'OSC'] else 9
                
                diff_col = f"DIFF_{fast}_{slow}"
                if diff_col not in df.columns:
                    ema_fast = df['C'].ewm(span=fast, adjust=False).mean()
                    ema_slow = df['C'].ewm(span=slow, adjust=False).mean()
                    df[diff_col] = ema_fast - ema_slow
                
                if ind_type in ['MACD', 'OSC']:
                    macd_col = f"MACD_{fast}_{slow}_{signal_period}"
                    if macd_col not in df.columns:
                        df[macd_col] = df[diff_col].ewm(span=signal_period, adjust=False).mean()
                        
                if ind_type == 'OSC':
                    osc_col = f"OSC_{fast}_{slow}_{signal_period}"
                    if osc_col not in df.columns:
                        df[osc_col] = df[diff_col] - df[macd_col]

            elif ind_type == 'MA':
                period = int(item[1])
                col_name = f"MA_{period}"
                if col_name not in df.columns:
                    df[col_name] = df['C'].rolling(window=period).mean()

            elif ind_type == 'VMA':
                period = int(item[1])
                col_name = f"VMA_{period}"
                if col_name not in df.columns:
                    df[col_name] = df['V'].rolling(window=period).mean()

            elif ind_type in ['PDI', 'MDI', 'ADX', 'ADXR']:
                period = int(item[1])
                pdi_col = f"PDI_{period}"
                mdi_col = f"MDI_{period}"
                adx_col = f"ADX_{period}"
                adxr_col = f"ADXR_{period}"
                if pdi_col not in df.columns or mdi_col not in df.columns:
                    high_diff = df['H'].diff()
                    low_diff = -df['L'].diff()
                    pos_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
                    neg_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)
                    tr1 = df['H'] - df['L']
                    tr2 = (df['H'] - df['C'].shift(1)).abs()
                    tr3 = (df['L'] - df['C'].shift(1)).abs()
                    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
                    alpha = 1 / period
                    atr = tr.ewm(alpha=alpha, adjust=False).mean()
                    pos_dm_smooth = pd.Series(pos_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
                    neg_dm_smooth = pd.Series(neg_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
                    df[pdi_col] = 100 * (pos_dm_smooth / atr)
                    df[mdi_col] = 100 * (neg_dm_smooth / atr)
                    
                if ind_type in ['ADX', 'ADXR'] and adx_col not in df.columns:
                    alpha = 1 / period
                    dx = 100 * (df[pdi_col] - df[mdi_col]).abs() / (df[pdi_col] + df[mdi_col])
                    df[adx_col] = dx.ewm(alpha=alpha, adjust=False).mean()

                if ind_type == 'ADXR' and adxr_col not in df.columns:
                    df[adxr_col] = (df[adx_col] + df[adx_col].shift(period)) / 2
                    
            elif ind_type == 'BIAS':
                period = int(item[1])
                col_name = f"BIAS_{period}"
                if col_name not in df.columns:
                    ma = df['C'].rolling(window=period).mean()
                    df[col_name] = (df['C'] - ma) / ma * 100

            elif ind_type == 'WMS':
                period = int(item[1])
                col_name = f"WMS_{period}"
                if col_name not in df.columns:
                    high_p = df['H'].rolling(window=period).max()
                    low_p = df['L'].rolling(window=period).min()
                    df[col_name] = (high_p - df['C']) / (high_p - low_p) * -100

            elif ind_type == 'CCI':
                period = int(item[1])
                col_name = f"CCI_{period}"
                if col_name not in df.columns:
                    tp = (df['H'] + df['L'] + df['C']) / 3
                    sma_tp = tp.rolling(window=period).mean()
                    mad = (tp - sma_tp).abs().rolling(window=period).mean()
                    df[col_name] = (tp - sma_tp) / (0.015 * mad)
                        
        return df

    def extract_indicators_from_formula(self, formula_str):
        """解析公式，找出所有帶參數的指標並替換為內部變數名稱"""
        required = []
        
        # 將中文顯示名稱轉回內部指標代號，以便正則表達式能正確辨識與計算
        formula_str = formula_str.replace("K值", "K").replace("D值", "D")
        formula_str = formula_str.replace("均價", "MA").replace("均量", "VMA")
        formula_str = formula_str.replace("Osc", "OSC").replace("Bias", "BIAS").replace("Wms", "WMS")
        formula_str = formula_str.replace("順勢指標", "CCI").replace("CCI順勢", "CCI")
        
        parsed_formula = formula_str
        
        for m in re.finditer(r'RSI\((\d+)\)', formula_str):
            required.append(('RSI', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"RSI_{m.group(1)}")
            
        for m in re.finditer(r'K\((\d+)\)', formula_str):
            required.append(('K', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"K_{m.group(1)}")
            
        for m in re.finditer(r'D\((\d+)\)', formula_str):
            required.append(('D', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"D_{m.group(1)}")
            
        for m in re.finditer(r'MACD\((\d+),(\d+),(\d+)\)', formula_str):
            required.append(('MACD', m.group(1), m.group(2), m.group(3)))
            parsed_formula = parsed_formula.replace(m.group(0), f"MACD_{m.group(1)}_{m.group(2)}_{m.group(3)}")
            
        for m in re.finditer(r'DIFF\((\d+),(\d+)\)', formula_str):
            required.append(('DIFF', m.group(1), m.group(2)))
            parsed_formula = parsed_formula.replace(m.group(0), f"DIFF_{m.group(1)}_{m.group(2)}")
            
        for m in re.finditer(r'MA\((\d+)\)', formula_str):
            required.append(('MA', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"MA_{m.group(1)}")
            
        for m in re.finditer(r'VMA\((\d+)\)', formula_str):
            required.append(('VMA', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"VMA_{m.group(1)}")
            
        for m in re.finditer(r'\+DI\((\d+)\)', formula_str, re.IGNORECASE):
            required.append(('PDI', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"PDI_{m.group(1)}")
            
        for m in re.finditer(r'-DI\((\d+)\)', formula_str, re.IGNORECASE):
            required.append(('MDI', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"MDI_{m.group(1)}")
            
        for m in re.finditer(r'ADX\((\d+)\)', formula_str, re.IGNORECASE):
            required.append(('ADX', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"ADX_{m.group(1)}")
            
        for m in re.finditer(r'ADXR\((\d+)\)', formula_str, re.IGNORECASE):
            required.append(('ADXR', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"ADXR_{m.group(1)}")
            
        for m in re.finditer(r'OSC\((\d+),(\d+),(\d+)\)', formula_str):
            required.append(('OSC', m.group(1), m.group(2), m.group(3)))
            parsed_formula = parsed_formula.replace(m.group(0), f"OSC_{m.group(1)}_{m.group(2)}_{m.group(3)}")
            
        for m in re.finditer(r'BIAS\((\d+)\)', formula_str, re.IGNORECASE):
            required.append(('BIAS', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"BIAS_{m.group(1)}")
            
        for m in re.finditer(r'WMS\((\d+)\)', formula_str, re.IGNORECASE):
            required.append(('WMS', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"WMS_{m.group(1)}")
            
        for m in re.finditer(r'CCI\((\d+)\)', formula_str, re.IGNORECASE):
            required.append(('CCI', m.group(1)))
            parsed_formula = parsed_formula.replace(m.group(0), f"CCI_{m.group(1)}")
            
        return required, parsed_formula

    def parse_formula(self, formula_str):
        """將使用者介面的公式轉換為 Python eval 語法，支援多週期與自訂 shift"""
        formula = formula_str
        
        # 1. 將中文基本欄位轉回內部代號
        formula = formula.replace("收盤價", "C").replace("開盤價", "O").replace("最高價", "H").replace("最低價", "L").replace("成交量", "V")
        
        # 2. 處理 n日前/n週前/n月前 的 shift 邏輯，轉成 _shift_n 尾碼
        formula = re.sub(r'(\d+)[日週月]前\s*([a-zA-Z0-9_週月]+)', r'\2_shift_\1', formula)
        
        # 3. 統一將邏輯運算子轉為 Python 標準的 and / or / ==
        formula = re.sub(r'\bAND\b', ' and ', formula, flags=re.IGNORECASE)
        formula = re.sub(r'\bOR\b', ' or ', formula, flags=re.IGNORECASE)
        formula = formula.replace('&', ' and ').replace('|', ' or ')
        formula = formula.replace('=', '==')
        formula = formula.replace('====', '==')
        
        # 4. 將變數加上週期的前綴 (W_, M_, D_)
        base_period = self.period_var.get()
        if base_period == "週線":
            default_prefix = "W_"
        elif base_period == "月線":
            default_prefix = "M_"
        else:
            default_prefix = "D_"
            
        def repl(match):
            prefix = match.group(1)
            name = match.group(2)
            if name.lower() in ['and', 'or']:
                return match.group(0)
            
            if prefix == '週':
                return f"W_{name}"
            elif prefix == '月':
                return f"M_{name}"
            else:
                return f"{default_prefix}{name}"
                
        # 匹配 (週|月)? 加上變數名
        formula = re.sub(r'\b(週|月)?([a-zA-Z_][a-zA-Z0-9_]*)\b', repl, formula)
        
        return formula

    def load_stock_files(self):
        if not os.path.exists(self.data_dir):
            messagebox.showerror("錯誤", f"找不到資料夾: {self.data_dir}")
            return []
        return [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]

    def load_stock_csv(self, filepath):
        df = pd.read_csv(filepath, index_col=0)
        if 'Ticker' in df.index and 'Date' in df.index:
            df = df.drop(index=['Ticker', 'Date'])
            df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        
        # 移除 Adj Close 欄位，只保留 Open/High/Low/Close/Volume (未還原行情)
        if 'Adj Close' in df.columns:
            df = df.drop(columns=['Adj Close'])
        
        # 只保留標準 OHLCV 欄位
        keep_cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
        df = df[keep_cols]
        
        # 將成交量從「股」轉換為「張」
        if 'Volume' in df.columns:
            df['Volume'] = df['Volume'] / 1000
            
        return df

    def convert_to_weekly(self, df):
        """將日線 DataFrame 轉換為週線"""
        logic = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        # 確保資料為浮點數
        df = df.astype(float)
        
        # 記錄原始日期，避免 resample 後被統一標記為未來的週五
        df['Actual_Date'] = df.index
        logic['Actual_Date'] = 'last'
        
        df_weekly = df.resample('W-FRI').agg(logic).dropna()
        
        # 將索引還原為該週最後一個實際交易日
        df_weekly.index = pd.to_datetime(df_weekly['Actual_Date'])
        df_weekly = df_weekly.drop(columns=['Actual_Date'])
        
        return df_weekly

    def convert_to_monthly(self, df):
        """將日線 DataFrame 轉換為月線"""
        logic = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        # 確保資料為浮點數
        df = df.astype(float)
        
        # 記錄原始日期，避免 resample 後被統一標記為月底最後一天（如週日或假日）
        df['Actual_Date'] = df.index
        logic['Actual_Date'] = 'last'
        
        df_monthly = df.resample('ME').agg(logic).dropna()
        
        # 將索引還原為該月最後一個實際交易日
        df_monthly.index = pd.to_datetime(df_monthly['Actual_Date'])
        df_monthly = df_monthly.drop(columns=['Actual_Date'])
        
        return df_monthly

    def random_test(self):
        formula_raw = self.formula_entry.get("1.0", tk.END).replace('\n', ' ').strip()
        if not formula_raw:
            messagebox.showwarning("警告", "請先輸入篩選公式！")
            return

        required_inds, formula_with_vars = self.extract_indicators_from_formula(formula_raw)
        
        try:
            py_formula = self.parse_formula(formula_with_vars)
        except Exception as e:
            messagebox.showerror("語法解析錯誤", f"公式格式不正確: {e}")
            return

        files = self.load_stock_files()
        if not files: return
        
        sample_size = min(len(files), 10)
        test_files = random.sample(files, sample_size)
        
        self.result_text.delete(1.0, tk.END)
        period_type = self.period_var.get()
        
        self.log(f"🧪 隨機抽取 {sample_size} 檔進行測試 (基準週期: {period_type})...\n內部轉換語法: {py_formula}\n" + "-"*30)
        
        self.loaded_data = {}
        matches = []
        for f in test_files:
            symbol = f.split('_')[0]
            try:
                # 載入日線，並轉換為週線、月線
                df_d = self.load_stock_csv(os.path.join(self.data_dir, f))
                if len(df_d) < 50: continue
                
                df_w = self.convert_to_weekly(df_d)
                df_m = self.convert_to_monthly(df_d)
                
                # 計算指標
                df_d = self.calculate_dynamic_indicators(df_d, required_inds)
                df_w = self.calculate_dynamic_indicators(df_w, required_inds)
                df_m = self.calculate_dynamic_indicators(df_m, required_inds)
                
                # 緩存
                self.loaded_data[(symbol, 'D')] = df_d
                self.loaded_data[(symbol, 'W')] = df_w
                self.loaded_data[(symbol, 'M')] = df_m
                
                # 提取公式中要求的所有 shift 數值
                requested_shifts = [int(s) for s in re.findall(r'_shift_(\d+)', py_formula)]
                
                # 建立標量字典
                scalar_dict = {}
                
                # 日線
                for col in df_d.columns:
                    if len(df_d) > 0:
                        scalar_dict[f"D_{col}"] = df_d[col].iloc[-1]
                        for s in requested_shifts:
                            if len(df_d) > s:
                                scalar_dict[f"D_{col}_shift_{s}"] = df_d[col].iloc[-1 - s]
                                
                # 週線
                for col in df_w.columns:
                    if len(df_w) > 0:
                        scalar_dict[f"W_{col}"] = df_w[col].iloc[-1]
                        for s in requested_shifts:
                            if len(df_w) > s:
                                scalar_dict[f"W_{col}_shift_{s}"] = df_w[col].iloc[-1 - s]
                                
                # 月線
                for col in df_m.columns:
                    if len(df_m) > 0:
                        scalar_dict[f"M_{col}"] = df_m[col].iloc[-1]
                        for s in requested_shifts:
                            if len(df_m) > s:
                                scalar_dict[f"M_{col}_shift_{s}"] = df_m[col].iloc[-1 - s]
                
                # 動態提取公式中涉及的變數與對應數值，以供使用者校對
                terms = re.findall(r'\b[DWM]_[a-zA-Z0-9_]+\b', py_formula)
                valid_terms = set(terms)
                
                data_info_list = []
                for term in valid_terms:
                    val = scalar_dict.get(term)
                    if val is None:
                        continue
                    val_str = f"{val:.2f}" if isinstance(val, (float, np.floating)) else str(val)
                    
                    parts = term.split('_')
                    prefix_char = "週" if parts[0] == 'W' else ("月" if parts[0] == 'M' else "日")
                    
                    if 'shift' in parts:
                        shift_idx = parts.index('shift')
                        shift_num = parts[shift_idx + 1]
                        var_name = "_".join(parts[1:shift_idx])
                        display_name = f"{shift_num}{prefix_char}前{prefix_char}{var_name}"
                    else:
                        var_name = "_".join(parts[1:])
                        display_name = f"{prefix_char}{var_name}"
                    
                    display_name = display_name.replace('PDI', '+DI').replace('MDI', '-DI').replace('CCI', '順勢指標')
                    display_name = display_name.replace('C', '收盤價').replace('O', '開盤價').replace('H', '最高價').replace('L', '最低價').replace('V', '成交量')
                    data_info_list.append(f"{display_name}={val_str}")
                    
                data_info_str = ", ".join(sorted(data_info_list))
                
                # 評估條件
                is_match = eval(py_formula, {"__builtins__": None}, scalar_dict)
                
                # 取得基準週期的日期
                if period_type == "週線":
                    date_str = df_w.index[-1].strftime('%Y-%m-%d')
                elif period_type == "月線":
                    date_str = df_m.index[-1].strftime('%Y-%m-%d')
                else:
                    date_str = df_d.index[-1].strftime('%Y-%m-%d')
                
                if is_match:
                    matches.append((symbol, date_str, df_d['C'].iloc[-1]))
                    self.log(f"✨ 發現符合: {symbol} (日期: {date_str}, 收盤: {df_d['C'].iloc[-1]:.2f})")
                    if data_info_str: self.log(f"   ↳ 數據: {data_info_str}")
                else:
                    self.log(f"✅ {symbol} 載入成功，但不符合條件")
                    if data_info_str: self.log(f"   ↳ 數據: {data_info_str}")
            except Exception as e:
                self.log(f"❌ {symbol} 載入失敗或運算錯誤: {e}")
                
        self.log("-"*30)
        if not matches:
            self.log("結果：隨機抽樣中沒有找到符合條件的股票。")
        else:
            self.log(f"🎉 測試完成！隨機 {sample_size} 檔中共找到 {len(matches)} 檔符合條件。")

    def run_search(self):
        formula_raw = self.formula_entry.get("1.0", tk.END).replace('\n', ' ').strip()
        if not formula_raw:
            messagebox.showwarning("警告", "請先輸入篩選公式！")
            return

        required_inds, formula_with_vars = self.extract_indicators_from_formula(formula_raw)
        
        try:
            py_formula = self.parse_formula(formula_with_vars)
        except Exception as e:
            messagebox.showerror("語法解析錯誤", f"公式格式不正確: {e}")
            return

        all_files = self.load_stock_files()
        if not all_files: return

        self.result_text.delete(1.0, tk.END)
        period_type = self.period_var.get()
        
        self.log(f"🔍 執行全量篩選中 (基準週期: {period_type})...\n內部轉換語法: {py_formula}\n" + "-"*30)

        matches = []
        
        for f in all_files:
            symbol = f.split('_')[0]
            try:
                # 檢查快取
                if (symbol, 'D') in self.loaded_data and (symbol, 'W') in self.loaded_data and (symbol, 'M') in self.loaded_data:
                    df_d = self.loaded_data[(symbol, 'D')]
                    df_w = self.loaded_data[(symbol, 'W')]
                    df_m = self.loaded_data[(symbol, 'M')]
                else:
                    df_raw = self.load_stock_csv(os.path.join(self.data_dir, f))
                    if len(df_raw) < 50: continue
                    
                    df_d = df_raw
                    df_w = self.convert_to_weekly(df_raw)
                    df_m = self.convert_to_monthly(df_raw)
                    
                    self.loaded_data[(symbol, 'D')] = df_d
                    self.loaded_data[(symbol, 'W')] = df_w
                    self.loaded_data[(symbol, 'M')] = df_m
                
                # 不論是否命中快取，皆動態計算公式中實際使用到的指標 (已計算者會自動跳過)
                df_d = self.calculate_dynamic_indicators(df_d, required_inds)
                df_w = self.calculate_dynamic_indicators(df_w, required_inds)
                df_m = self.calculate_dynamic_indicators(df_m, required_inds)
                
                # 提取公式中要求的所有 shift 數值
                requested_shifts = [int(s) for s in re.findall(r'_shift_(\d+)', py_formula)]
                
                # 建立標量字典
                scalar_dict = {}
                
                # 日線
                for col in df_d.columns:
                    if len(df_d) > 0:
                        scalar_dict[f"D_{col}"] = df_d[col].iloc[-1]
                        for s in requested_shifts:
                            if len(df_d) > s:
                                scalar_dict[f"D_{col}_shift_{s}"] = df_d[col].iloc[-1 - s]
                                
                # 週線
                for col in df_w.columns:
                    if len(df_w) > 0:
                        scalar_dict[f"W_{col}"] = df_w[col].iloc[-1]
                        for s in requested_shifts:
                            if len(df_w) > s:
                                scalar_dict[f"W_{col}_shift_{s}"] = df_w[col].iloc[-1 - s]
                                
                # 月線
                for col in df_m.columns:
                    if len(df_m) > 0:
                        scalar_dict[f"M_{col}"] = df_m[col].iloc[-1]
                        for s in requested_shifts:
                            if len(df_m) > s:
                                scalar_dict[f"M_{col}_shift_{s}"] = df_m[col].iloc[-1 - s]
                
                # 評估條件
                is_match = eval(py_formula, {"__builtins__": None}, scalar_dict)
                
                if is_match:
                    # 取得基準週期的日期
                    if period_type == "週線":
                        date_str = df_w.index[-1].strftime('%Y-%m-%d')
                    elif period_type == "月線":
                        date_str = df_m.index[-1].strftime('%Y-%m-%d')
                    else:
                        date_str = df_d.index[-1].strftime('%Y-%m-%d')
                    matches.append((symbol, date_str, df_d['C'].iloc[-1]))
                    self.log(f"✨ 發現符合: {symbol} (日期: {date_str}, 收盤: {df_d['C'].iloc[-1]:.2f})")
            
            except Exception as e:
                continue

        self.log("-"*30)
        if not matches:
            self.log("結果：沒有找到符合條件的股票。")
        else:
            self.log(f"🎉 篩選完成！共找到 {len(matches)} 檔符合條件。")
            
if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    app = TechnicalFilterApp(root)
    root.mainloop()

"""
使用說明範例公式 (可自訂括號內參數)：
1. 股價突破昨日最高： C > 1日前 H
2. KD(9) 黃金交叉： K(9) > D(9) AND 1日前 K(9) < 1日前 D(9)
3. RSI(14) 強勢且量增： RSI(14) > 70 AND V > 1日前 V
4. 尋找 RSI 背離： RSI(6) < RSI(14) AND C > 1日前 C
5. MACD 金叉： DIFF(12,26) > MACD(12,26,9) AND 1日前 DIFF(12,26) < 1日前 MACD(12,26,9)
"""
