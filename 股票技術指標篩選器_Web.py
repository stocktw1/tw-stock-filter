import os
import sys

# 若直接透過 Python (例如 IDE 播放鍵) 執行，自動轉接為 Streamlit 網頁服務
if __name__ == '__main__':
    from streamlit.runtime import exists as runtime_exists
    if not runtime_exists():
        from streamlit.web import cli as stcli
        sys.argv = ["streamlit", "run", os.path.abspath(__file__)]
        sys.exit(stcli.main())

import random
import re
import json
import pandas as pd
import numpy as np
import streamlit as st

# ------------------ 系統與版面設定 ------------------
st.set_page_config(page_title="台股技術指標篩選器 - Web 版", layout="wide", page_icon="📈")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "stockdata")
FORMULAS_FILE = os.path.join(BASE_DIR, "saved_formulas.json")
STOCK_NAMES_FILE = os.path.join(BASE_DIR, "stock_names.json")

def get_stock_name(symbol):
    """取得股票名稱"""
    if not hasattr(get_stock_name, "_cache"):
        names = {}
        if os.path.exists(STOCK_NAMES_FILE):
            try:
                with open(STOCK_NAMES_FILE, 'r', encoding='utf-8') as f:
                    names = json.load(f)
            except Exception:
                pass
        get_stock_name._cache = names
    return get_stock_name._cache.get(str(symbol), "")

# 初始化網頁的暫存狀態 (Session State)
if "formula" not in st.session_state:
    st.session_state.formula = ""

def check_password():
    """檢查登入密碼 (支援 st.secrets, 環境變數, 預設密碼)"""
    target_password = os.environ.get("APP_PASSWORD", "8888")
    try:
        if hasattr(st, "secrets") and "PASSWORD" in st.secrets:
            target_password = str(st.secrets["PASSWORD"])
    except Exception:
        pass
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("<h2 style='text-align: center;'>🔒 台股技術指標篩選器 - 登入</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        pwd = st.text_input("請輸入系統密碼：", type="password", key="login_pwd")
        if st.button("登入系統", type="primary", use_container_width=True):
            if pwd == target_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ 密碼不正確，請重新輸入！")
        st.caption("💡 預設測試密碼為：`8888`（可於 Streamlit Cloud Secrets 中修改）")
    return False

if not check_password():
    st.stop()

def append_to_formula(text):
    """將文字加入公式編輯區"""
    st.session_state.formula += text

def add_indicator(name, code, period):
    """處理指標按鈕的點擊"""
    if period == "週線":
        prefix = "週"
    elif period == "月線":
        prefix = "月"
    else:
        prefix = ""
    if "(" in code:
        params = code[code.find("("):]
        append_to_formula(f"{prefix}{name}{params} ")
    else:
        append_to_formula(f"{prefix}{name} ")

def load_saved_formulas():
    """載入儲存的常用公式 (支援容錯處理)"""
    if os.path.exists(FORMULAS_FILE):
        try:
            with open(FORMULAS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                # 容錯：移除結尾多餘逗號 (Trailing Commas)
                content_cleaned = re.sub(r',\s*([\]}])', r'\1', content)
                return json.loads(content_cleaned)
        except Exception as e:
            print(f"載入公式失敗: {e}")
    return {}

def save_formulas_to_disk(formulas_dict):
    """將常用公式存回磁碟"""
    with open(FORMULAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(formulas_dict, f, ensure_ascii=False, indent=4)

# ------------------ 核心運算邏輯 (繼承自原版) ------------------
@st.cache_data(show_spinner=False)
def load_stock_csv(filepath):
    df = pd.read_csv(filepath, index_col=0)
    if 'Ticker' in df.index and 'Date' in df.index:
        df = df.drop(index=['Ticker', 'Date'])
        df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    # 移除 Adj Close 欄位，只保留 Open/High/Low/Close/Volume (未還原行情)
    if 'Adj Close' in df.columns:
        df = df.drop(columns=['Adj Close'])
    keep_cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
    df = df[keep_cols]
    if 'Volume' in df.columns:
        df['Volume'] = df['Volume'] / 1000
    return df

def convert_to_weekly(df):
    logic = {
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }
    df = df.astype(float)
    df['Actual_Date'] = df.index
    logic['Actual_Date'] = 'last'
    df_weekly = df.resample('W-FRI').agg(logic).dropna()
    df_weekly.index = pd.to_datetime(df_weekly['Actual_Date'])
    df_weekly = df_weekly.drop(columns=['Actual_Date'])
    return df_weekly

def convert_to_monthly(df):
    logic = {
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }
    df = df.astype(float)
    df['Actual_Date'] = df.index
    logic['Actual_Date'] = 'last'
    df_monthly = df.resample('ME').agg(logic).dropna()
    df_monthly.index = pd.to_datetime(df_monthly['Actual_Date'])
    df_monthly = df_monthly.drop(columns=['Actual_Date'])
    return df_monthly

def extract_indicators_from_formula(formula_str):
    required = []
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

def parse_formula(formula_str, period_type="日線"):
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
    if period_type == "週線":
        default_prefix = "W_"
    elif period_type == "月線":
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

def calculate_dynamic_indicators(df, required_indicators):
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
            if k_col not in df.columns:
                low_p = df['L'].rolling(window=period).min()
                high_p = df['H'].rolling(window=period).max()
                rsv = (df['C'] - low_p) / (high_p - low_p) * 100
                df[k_col] = rsv.ewm(com=2, adjust=False).mean()
                df[d_col] = df[k_col].ewm(com=2, adjust=False).mean()
        elif ind_type in ['MACD', 'DIFF', 'OSC']:
            fast, slow = int(item[1]), int(item[2])
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
        elif ind_type in ['PDI', 'MDI', 'ADX']:
            period = int(item[1])
            pdi_col, mdi_col, adx_col = f"PDI_{period}", f"MDI_{period}", f"ADX_{period}"
            if pdi_col not in df.columns:
                high_diff, low_diff = df['H'].diff(), -df['L'].diff()
                pos_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
                neg_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)
                tr = pd.DataFrame({'tr1': df['H'] - df['L'], 'tr2': (df['H'] - df['C'].shift(1)).abs(), 'tr3': (df['L'] - df['C'].shift(1)).abs()}).max(axis=1)
                alpha = 1 / period
                atr = tr.ewm(alpha=alpha, adjust=False).mean()
                pos_dm_smooth = pd.Series(pos_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
                neg_dm_smooth = pd.Series(neg_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
                df[pdi_col] = 100 * (pos_dm_smooth / atr)
                df[mdi_col] = 100 * (neg_dm_smooth / atr)
            if ind_type == 'ADX' and adx_col not in df.columns:
                dx = 100 * (df[pdi_col] - df[mdi_col]).abs() / (df[pdi_col] + df[mdi_col])
                df[adx_col] = dx.ewm(alpha=1/period, adjust=False).mean()
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

# ------------------ 介面呈現 ------------------
with st.sidebar:
    st.markdown("### 👤 帳號管理")
    st.success("✅ 已通過身分驗證")
    if st.button("🔒 登出系統", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()
    st.info("💡 資料庫更新時間將依據 GitHub Actions 每日盤後自動排程。")

st.title("📈 台股技術指標篩選器 - 網頁版")
st.markdown("將複雜的技術指標篩選條件，轉換為直覺的中文介面！無縫相容舊版自訂公式。")

col1, col2 = st.columns([2, 1])

with col1:
    st.header("1. 指標與條件設定")
    period_type = st.radio("🔄 選擇週期：", ["日線", "週線", "月線"], horizontal=True)
    
    st.subheader("點擊加入指標")
    indicators = [
        ("收盤價", "C"), ("開盤價", "O"), ("最高價", "H"), ("最低價", "L"), ("成交量", "V"),
        ("K值", "K(9)"), ("D值", "D(9)"), ("RSI", "RSI(14)"), ("MACD", "MACD(12,26,9)"), ("DIFF", "DIFF(12,26)"),
        ("均價", "MA(5)"), ("均量", "VMA(5)"), ("+DI", "+DI(14)"), ("-DI", "-DI(14)"), ("ADX", "ADX(14)"),
        ("Osc", "OSC(12,26,9)"), ("Bias", "BIAS(5)"), ("Wms", "WMS(14)"), ("順勢指標", "CCI(22)")
    ]
    
    # 排列按鈕
    cols = st.columns(5)
    for i, (name, code) in enumerate(indicators):
        cols[i % 5].button(name, key=f"ind_{name}", on_click=add_indicator, args=(name, code, period_type), use_container_width=True)

    st.subheader("運算符號與邏輯")
    op_cols = st.columns(10)
    operators = ["+", "-", "*", "/", ">", "<", "=", "AND", "OR"]
    for i, op in enumerate(operators):
        op_cols[i].button(op, key=f"op_{i}", on_click=append_to_formula, args=(f"{op} ",))
        
    with op_cols[9]:
        n_val = st.number_input("n=", value=1, min_value=1, max_value=250, label_visibility="collapsed")
        if period_type == "月線":
            unit = "月"
        elif period_type == "週線":
            unit = "週"
        else:
            unit = "日"
        st.button(f"n{unit}前", on_click=append_to_formula, args=(f"{n_val}{unit}前 ",), type="secondary")

with col2:
    st.header("2. 常用公式管理")
    saved_formulas = load_saved_formulas()
    formula_names = list(saved_formulas.keys())
    
    if formula_names:
        st.caption("⚡ 點擊快速載入公式：")
        for f_name in formula_names:
            if st.button(f"📌 {f_name}", key=f"quick_btn_{f_name}", use_container_width=True):
                st.session_state.formula = saved_formulas[f_name]
                st.rerun()
    else:
        st.info("尚無儲存的自訂公式。")
        
    st.divider()
    new_formula_name = st.text_input("儲存當前公式命名：")
    if st.button("儲存公式", type="primary", use_container_width=True):
        if new_formula_name and st.session_state.formula.strip():
            saved_formulas[new_formula_name] = st.session_state.formula.strip()
            save_formulas_to_disk(saved_formulas)
            st.success(f"公式 `{new_formula_name}` 已儲存！")
            st.rerun()

st.divider()

# ------------------ 篩選公式編輯區 ------------------
st.header("3. 篩選公式編輯")

st.text_area("請在此輸入或修改篩選條件：", key="formula", height=100)

def clear_formula():
    st.session_state.formula = ""

st.button("清除公式", on_click=clear_formula, type="secondary")

st.divider()

# ------------------ 執行結果 ------------------
st.header("4. 執行與結果")

if not os.path.exists(DATA_DIR):
    st.error(f"找不到資料夾: {DATA_DIR}，請先下載股票資料！")
    st.stop()
    
csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]

col_run1, col_run2 = st.columns(2)

from concurrent.futures import ThreadPoolExecutor

def process_single_stock_web(f, required_inds, py_formula, requested_shifts, period_type):
    symbol = f.split('_')[0]
    try:
        df_raw = load_stock_csv(os.path.join(DATA_DIR, f))
        if len(df_raw) < 50: 
            return None
        
        df_d = df_raw
        df_w = convert_to_weekly(df_raw)
        df_m = convert_to_monthly(df_raw)
        
        df_d = calculate_dynamic_indicators(df_d, required_inds)
        df_w = calculate_dynamic_indicators(df_w, required_inds)
        df_m = calculate_dynamic_indicators(df_m, required_inds)
        
        scalar_dict = {}
        for col in df_d.columns:
            if len(df_d) > 0:
                scalar_dict[f"D_{col}"] = df_d[col].iloc[-1]
                for s in requested_shifts:
                    if len(df_d) > s:
                        scalar_dict[f"D_{col}_shift_{s}"] = df_d[col].iloc[-1 - s]
        for col in df_w.columns:
            if len(df_w) > 0:
                scalar_dict[f"W_{col}"] = df_w[col].iloc[-1]
                for s in requested_shifts:
                    if len(df_w) > s:
                        scalar_dict[f"W_{col}_shift_{s}"] = df_w[col].iloc[-1 - s]
        for col in df_m.columns:
            if len(df_m) > 0:
                scalar_dict[f"M_{col}"] = df_m[col].iloc[-1]
                for s in requested_shifts:
                    if len(df_m) > s:
                        scalar_dict[f"M_{col}_shift_{s}"] = df_m[col].iloc[-1 - s]
        
        is_match = eval(py_formula, {"__builtins__": None}, scalar_dict)
        if is_match:
            if period_type == "週線":
                date_str = df_w.index[-1].strftime('%Y-%m-%d')
            elif period_type == "月線":
                date_str = df_m.index[-1].strftime('%Y-%m-%d')
            else:
                date_str = df_d.index[-1].strftime('%Y-%m-%d')
            
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

            last_close = float(df_d['C'].iloc[-1])
            last_vol = float(df_d['V'].iloc[-1]) if 'V' in df_d.columns else 0.0
            trade_value_raw = last_close * last_vol * 1000  # 元
            trade_value_yi = trade_value_raw / 100_000_000  # 億元

            return {
                "代碼": symbol, 
                "股名": get_stock_name(symbol),
                "日期": date_str, 
                "收盤價": f"{last_close:.2f}",
                "成交量(張)": f"{int(last_vol):,}",
                "成交值(億)": f"{trade_value_yi:.2f}",
                "_sort_val": trade_value_raw
            }
    except Exception:
        pass
    return None

def run_screener(is_test=False):
    formula_raw = st.session_state.formula.replace('\n', ' ').strip()
    if not formula_raw:
        st.warning("請先輸入篩選公式！")
        return
        
    try:
        required_inds, formula_with_vars = extract_indicators_from_formula(formula_raw)
        py_formula = parse_formula(formula_with_vars, period_type)
        requested_shifts = [int(s) for s in re.findall(r'_shift_(\d+)', py_formula)]
    except Exception as e:
        st.error(f"語法解析錯誤: {e}")
        return
        
    target_files = random.sample(csv_files, min(len(csv_files), 10)) if is_test else csv_files
    
    st.info(f"內部轉換語法: `{py_formula}` （共掃描 {len(target_files)} 檔股票）")
    
    with st.spinner("⚡ 正在極速平行比對全市場資料庫..."):
        matches = []
        max_workers = min(32, (os.cpu_count() or 4) * 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_single_stock_web, f, required_inds, py_formula, requested_shifts, period_type)
                for f in target_files
            ]
            for future in futures:
                res = future.result()
                if res:
                    matches.append(res)
        
    if matches:
        # 按照當日成交值由大到小排序 (降序)
        matches.sort(key=lambda x: x["_sort_val"], reverse=True)
        for item in matches:
            item.pop("_sort_val", None)

        df_results = pd.DataFrame(matches)
        
        st.success(f"🎉 篩選完成！全市場共掃描 {len(target_files)} 檔，找到 **{len(matches)}** 檔符合條件（已按當日成交值由大到小排序）。")
        st.dataframe(df_results, use_container_width=True)
        
        # 匯出排列整齊、無亂碼的 CSV 檔案 (包含 utf-8-sig BOM 標籤)
        csv_bytes = df_results.to_csv(index=False).encode('utf-8-sig')
        current_time_str = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        st.download_button(
            label="📥 下載篩選結果為 CSV 檔案",
            data=csv_bytes,
            file_name=f"台股選股結果_{current_time_str}.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )
    else:
        if is_test:
            st.info("💡 隨機抽樣 10 檔中未命中此條件，請點擊右側 **【🚀 開始全量篩選】** 掃描全市場 1,120+ 檔股票！")
        else:
            st.warning(f"結果：全市場共掃描 {len(target_files)} 檔股票，未找到完全符合所有條件的標的。")

with col_run1:
    if st.button("🎯 隨機抽樣測試 (10檔)", use_container_width=True):
        run_screener(is_test=True)

with col_run2:
    if st.button("🚀 開始全量篩選", type="primary", use_container_width=True):
        run_screener(is_test=False)