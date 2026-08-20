"""
台股技術指標篩選器 - 高性能 Flask 後端伺服器 (支援平行運算)
"""

import os
import sys
import re
import json
import glob
import random
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "stockdata")
FORMULAS_FILE = os.path.join(BASE_DIR, "saved_formulas.json")

app = Flask(__name__, static_folder=STATIC_DIR)

# ----------------------------------------------------
# 常用公式儲存與載入
# ----------------------------------------------------
def load_saved_formulas():
    if os.path.exists(FORMULAS_FILE):
        try:
            with open(FORMULAS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                content_cleaned = re.sub(r',\s*([\]}])', r'\1', content)
                return json.loads(content_cleaned)
        except Exception:
            pass
    return {}

def save_formulas_to_disk(formulas_dict):
    with open(FORMULAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(formulas_dict, f, ensure_ascii=False, indent=4)

# ----------------------------------------------------
# 核心指標計算函式庫
# ----------------------------------------------------
def load_stock_csv(filepath):
    df = pd.read_csv(filepath, index_col=0)
    if 'Ticker' in df.index and 'Date' in df.index:
        df = df.drop(index=['Ticker', 'Date'], errors='ignore')
        df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    if 'Adj Close' in df.columns:
        df = df.drop(columns=['Adj Close'])
    keep_cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
    df = df[keep_cols]
    if 'Volume' in df.columns:
        df['Volume'] = df['Volume'] / 1000
    return df

def convert_to_weekly(df):
    logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    df = df.astype(float)
    df['Actual_Date'] = df.index
    logic['Actual_Date'] = 'last'
    df_weekly = df.resample('W-FRI').agg(logic).dropna()
    df_weekly.index = pd.to_datetime(df_weekly['Actual_Date'])
    df_weekly = df_weekly.drop(columns=['Actual_Date'])
    return df_weekly

def convert_to_monthly(df):
    logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
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
    formula = formula.replace("收盤價", "C").replace("開盤價", "O").replace("最高價", "H").replace("最低價", "L").replace("成交量", "V")
    formula = re.sub(r'(\d+)[日週月]前\s*([a-zA-Z0-9_週月]+)', r'\2_shift_\1', formula)
    formula = re.sub(r'\bAND\b', ' and ', formula, flags=re.IGNORECASE)
    formula = re.sub(r'\bOR\b', ' or ', formula, flags=re.IGNORECASE)
    formula = formula.replace('&', ' and ').replace('|', ' or ')
    formula = formula.replace('=', '==')
    formula = formula.replace('====', '==')

    default_prefix = "W_" if period_type == "週線" else ("M_" if period_type == "月線" else "D_")

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

def process_single_stock(filename, required_inds, py_formula, requested_shifts, period_type):
    symbol = filename.split('_')[0]
    filepath = os.path.join(DATA_DIR, filename)

    try:
        df_raw = load_stock_csv(filepath)
        if len(df_raw) < 50:
            return None

        df_d = df_raw
        df_w = convert_to_weekly(df_raw)
        df_m = convert_to_monthly(df_raw)

        df_d = calculate_dynamic_indicators(df_d, required_inds)
        df_w = calculate_dynamic_indicators(df_w, required_inds)
        df_m = calculate_dynamic_indicators(df_m, required_inds)

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

            return {
                "symbol": symbol,
                "date": date_str,
                "close": f"{df_d['C'].iloc[-1]:.2f}",
                "indicators": data_info_str
            }
    except Exception:
        pass
    return None

# ----------------------------------------------------
# 路由與 API 接口
# ----------------------------------------------------
@app.route('/')
def serve_index():
    if os.path.exists(os.path.join(BASE_DIR, 'index.html')):
        return send_from_directory(BASE_DIR, 'index.html')
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_DIR, path)

@app.route('/api/status', methods=['GET'])
def get_status():
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    latest_date = "未知"
    if csv_files:
        sample_parts = os.path.basename(csv_files[0]).replace(".csv", "").split("_")
        if len(sample_parts) >= 3:
            latest_date = sample_parts[2]
    return jsonify({
        "status": "ok",
        "stock_count": len(csv_files),
        "latest_date": latest_date
    })

@app.route('/api/formulas', methods=['GET'])
def get_formulas():
    return jsonify(load_saved_formulas())

@app.route('/api/formulas', methods=['POST'])
def save_formula():
    data = request.json or {}
    name = data.get('name', '').strip()
    formula = data.get('formula', '').strip()
    if not name or not formula:
        return jsonify({"error": "名稱或公式不能為空"}), 400

    formulas = load_saved_formulas()
    formulas[name] = formula
    save_formulas_to_disk(formulas)
    return jsonify({"success": True, "formulas": formulas})

@app.route('/api/formulas/<name>', methods=['DELETE'])
def delete_formula(name):
    formulas = load_saved_formulas()
    if name in formulas:
        del formulas[name]
        save_formulas_to_disk(formulas)
    return jsonify({"success": True, "formulas": formulas})

@app.route('/api/screen', methods=['POST'])
def run_screen():
    data = request.json or {}
    formula_raw = data.get('formula', '').replace('\n', ' ').strip()
    period_type = data.get('period_type', '日線')
    is_test = bool(data.get('is_test', False))

    if not formula_raw:
        return jsonify({"error": "請先輸入篩選公式"}), 400

    if not os.path.exists(DATA_DIR):
        return jsonify({"error": "找不到股票資料庫目錄 stockdata"}), 500

    csv_files = [os.path.basename(f) for f in glob.glob(os.path.join(DATA_DIR, "*.csv"))]
    if not csv_files:
        return jsonify({"error": "資料庫中沒有可用的 CSV 檔案"}), 400

    try:
        required_inds, formula_with_vars = extract_indicators_from_formula(formula_raw)
        py_formula = parse_formula(formula_with_vars, period_type)
        requested_shifts = [int(s) for s in re.findall(r'_shift_(\d+)', py_formula)]
    except Exception as e:
        return jsonify({"error": f"公式語法解析失敗: {str(e)}"}), 400

    target_files = random.sample(csv_files, min(len(csv_files), 10)) if is_test else csv_files

    # 使用多執行緒平行計算加速
    matches = []
    max_workers = min(32, (os.cpu_count() or 4) * 4)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_stock, f, required_inds, py_formula, requested_shifts, period_type)
            for f in target_files
        ]
        for future in futures:
            res = future.result()
            if res:
                matches.append(res)

    return jsonify({
        "success": True,
        "total_scanned": len(target_files),
        "matches": matches
    })

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    port = int(os.environ.get('PORT', 5000))
    print(f"台股技術指標篩選器 (HTML/Flask 版) 已啟動！正在監聽 http://127.0.0.1:{port}")
    
    # 本機執行時自動開啟瀏覽器
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception:
            pass

    app.run(host='0.0.0.0', port=port, debug=False)
