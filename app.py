# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import re
from io import BytesIO

import requests
import pdfplumber

# ===============================
# 页面配置 + CSS
# ===============================
st.set_page_config(page_title="岚图超充站电费自动计算系统", layout="wide")

st.markdown("""
<style>
    body {
        background-color:#f3f4f6;
    }
    .main-title {
        font-size:38px !important;
        color:white;
        text-align:center;
        padding:22px;
        background:linear-gradient(90deg,#1D4ED8,#0EA5E9);
        border-radius:14px;
        margin-bottom:25px;
        font-weight:700;
    }
    .sub-title {
        font-size:18px;
        color:#374151;
        margin-bottom:18px;
        text-align:center;
    }
    .card {
        background:white;
        padding:20px 24px;
        border-radius:14px;
        box-shadow:0 8px 24px rgba(15,23,42,0.08);
        margin-bottom:24px;
        border:1px solid #e5e7eb;
    }
    .section-title {
        font-size:20px;
        font-weight:600;
        color:#111827;
        margin-bottom:12px;
        display:flex;
        align-items:center;
        gap:8px;
    }
    .section-title span.icon {
        width:26px;
        height:26px;
        border-radius:999px;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        background:#EFF6FF;
        color:#1D4ED8;
        font-size:16px;
    }
</style>
""", unsafe_allow_html=True)

# ===============================
# ---------- 公共工具函数 ----------
# ===============================

def parse_time_rule_line(line):
    line = line.strip()
    if re.match(r"^\d{1,2}:\d{2}", line):
        return "", line
    parts = line.split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1].strip()

def parse_month_rule(text):
    if pd.isna(text):
        return []
    lines = [l for l in str(text).split("\n") if l.strip()]
    out = []
    for l in lines:
        t, tm = parse_time_rule_line(l)
        out.append({"type": t, "time": tm})
    return out

def get_price(tier, row):
    if tier == "":
        return row.get("不分时电价", None)
    return row.get(tier, None)

# ===============================
# 1）超充站电费计算核心函数（保持不变）
# ===============================

def process_station_prices(df_station, df_price, month):
    df_station = df_station.copy()
    df_station["配置"] = df_station["配置"].astype(str).str.strip()
    df_station = df_station[df_station["配置"] != "其他"]

    output = []
    errors = []
    col = f"电费-{month}月"

    for _, r in df_station.iterrows():
        prov = r["所在省份"]
        city = r["所属市区"]
        config = str(r["配置"]).strip()
        fs = str(r["是否分时"]).strip()
        mult = float(r["电费乘子"])
        rule_txt = r.get(col, "")

        match = df_price[(df_price["省份"] == prov) &
                         (df_price["制度"] == config)]

        if match.empty:
            final = "未匹配到价格"
            errors.append((r["序号"], r["站点名称"], prov, city, config))
        else:
            prow = match.iloc[0]

            if fs == "否":
                p = prow["不分时电价"] * mult
                final = f"0:00 - 24:00 {round(p,4)}元/度"
            else:
                rules = parse_month_rule(rule_txt)
                lines = []
                for rr in rules:
                    t = rr["type"]
                    tm = rr["time"]
                    base = get_price(t, prow)
                    if base is None:
                        lines.append(f"{t} {tm} 无对应电价")
                    else:
                        p = round(base * mult, 4)
                        if t == "":
                            lines.append(f"{tm} {p}元/度")
                        else:
                            lines.append(f"{t} {tm} {p}元/度")
                final = "\n".join(lines)

        output.append({
            "序号": r["序号"],
            "站点名称": r["站点名称"],
            "省份": prov,
            "城市": city,
            "配置": config,
            "是否分时": fs,
            "电费乘子": mult,
            "电费": final
        })

    return pd.DataFrame(output), errors

# ===============================
# 2）电价 PDF → 电价表 的所有函数（与你脚本一致）
# ===============================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.95598.cn/",
    "Accept": "application/pdf,application/octet-stream",
}

def safe_float(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None

def download_pdf_to_file(url, idx):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    filename = f"power_price_{idx+1}.pdf"
    with open(filename, "wb") as f:
        f.write(resp.content)
    return filename

def detect_province_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    text_clean = re.sub(r"\s+", "", text)
    start = text_clean.find("国网")
    if start != -1:
        end = text_clean.find("电力有限公司", start)
        if end == -1:
            end = text_clean.find("电力公司", start)
        if end != -1:
            company = text_clean[start + len("国网"): end]
            province = company.strip()
        else:
            province = "未知省份"
    else:
        province = "未知省份"
    if province == "重庆":
        province = "重庆市"
    if province == "未知省份":
        province = "上海市"
    return province

def detect_columns(df):
    period_kw_map = {
        "尖": ["尖峰时段", "尖峰", "尖时段", "尖时"],
        "峰": ["高峰时段", "高峰", "峰时段", "峰时"],
        "平": ["平段", "平时段", "平时"],
        "谷": ["低谷时段", "低谷", "谷段", "谷时段", "谷时"],
        "深": ["深谷时段", "深谷", "深时段", "深时"],
    }
    non_time_kws = [
        "非分时电度电价",
        "非分时电量电价",
        "非分时电价",
    ]
    period_cols = {}
    non_time_col = None
    for _, row in df.iterrows():
        for col_idx, cell in enumerate(row):
            s = str(cell) if cell is not None else ""
            if any(kw in s for kw in non_time_kws):
                non_time_col = col_idx
            if any(w in s for w in ["尖峰时段", "尖峰"]):
                matched_shorts = ["尖"]
            else:
                matched_shorts = []
                for short, kws in period_kw_map.items():
                    if any(kw in s for kw in kws):
                        matched_shorts.append(short)
            if len(matched_shorts) == 1:
                short = matched_shorts[0]
                period_cols[short] = col_idx
    return period_cols, non_time_col

def get_header_time_labels(df):
    raw_to_short = {
        "尖峰时段": "尖", "尖峰": "尖", "尖时段": "尖", "尖时": "尖", "尖": "尖",
        "高峰时段": "峰", "高峰": "峰", "峰段": "峰",
        "峰时段": "峰", "峰时": "峰", "峰": "峰",
        "平段": "平", "平时段": "平", "平时": "平", "平": "平",
        "低谷时段": "谷", "低谷": "谷", "谷段": "谷",
        "谷时段": "谷", "谷时": "谷", "谷": "谷",
        "深谷时段": "深", "深谷": "深", "深时段": "深", "深时": "深", "深": "深",
    }
    header_text = ""
    for _, row in df.iterrows():
        row_text = "".join(str(c) for c in row)
        if "尖峰" in row_text:
            hits = set()
            for raw in raw_to_short.keys():
                if raw in row_text:
                    hits.add(raw_to_short[raw])
            if len(hits) >= 2:
                header_text = row_text
                break
    if not header_text:
        for _, row in df.iterrows():
            row_text = "".join(str(c) for c in row)
            hits = set()
            for raw in raw_to_short.keys():
                if raw in row_text:
                    hits.add(raw_to_short[raw])
            if len(hits) >= 2:
                header_text = row_text
                break
    if not header_text:
        return []
    positions = []
    for raw, short in raw_to_short.items():
        idx = header_text.find(raw)
        if idx != -1:
            positions.append((idx, short))
    positions.sort(key=lambda x: x[0])
    ordered = []
    for _, short in positions:
        if short not in ordered:
            ordered.append(short)
    return ordered

def get_time_cluster_from_row(row):
    values = list(row)
    cluster_rev = []
    started = False
    count = 0
    for cell in reversed(values):
        v = safe_float(cell)
        if v is not None and 0.05 <= v <= 10:
            if not started:
                started = True
            if count < 5:
                cluster_rev.append(v)
                count += 1
            else:
                break
        else:
            if started:
                break
            else:
                continue
    return list(reversed(cluster_rev))

def map_cluster_to_periods(cluster, period_order):
    result = {p: None for p in ["尖", "峰", "平", "谷", "深"]}
    if not period_order or not cluster:
        return result
    n = len(period_order)
    m = len(cluster)
    if m == n:
        for i, p in enumerate(period_order):
            result[p] = cluster[i]
    else:
        offset = n - m
        for i, p in enumerate(period_order):
            j = i - offset
            if 0 <= j < m:
                result[p] = cluster[j]
    return result

def extract_row_prices_with_cluster(row, period_order, non_time_col=None):
    non_time = None
    if non_time_col is not None and non_time_col < len(row):
        non_time = safe_float(row[non_time_col])
    if non_time is None:
        for cell in row:
            v = safe_float(cell)
            if v is not None and 0.1 <= v <= 2:
                non_time = v
                break
    cluster = get_time_cluster_from_row(row)
    period_vals = map_cluster_to_periods(cluster, period_order)
    result = {"non_time": non_time}
    result.update(period_vals)
    return result

def find_voltage_rows_1_10kv(df):
    pattern_1_10 = re.compile(
        r"1\s*[-~～至到]\s*10(?:（\s*20\s*）|\(\s*20\s*\))?\s*(千伏|kV|KV)"
    )
    idxs = []
    for i, row in df.iterrows():
        text = "".join(str(c) for c in row.values)
        if pattern_1_10.search(text):
            idxs.append(i)
    if idxs:
        return idxs
    pattern_10kv = re.compile(r"(^|[^0-9])10\s*千伏(?!安)")
    idxs = []
    for i, row in df.iterrows():
        text = "".join(str(c) for c in row.values)
        if pattern_10kv.search(text):
            idxs.append(i)
    return idxs

def parse_single_pdf(pdf_path):
    province = detect_province_from_pdf(pdf_path)

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    clean = [c.strip() if isinstance(c, str) else c for c in row]
                    if any(clean):
                        rows.append(clean)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.replace("", None, inplace=True)
    df.dropna(how="all", axis=1, inplace=True)
    df.dropna(how="all", axis=0, inplace=True)
    df.reset_index(drop=True, inplace=True)

    period_cols, non_time_col = detect_columns(df)   # non_time_col 主要用来锁“非分时电价”那一列
    period_order = get_header_time_labels(df)

    voltage_label = "1-10（20）千伏"
    row_indices = find_voltage_rows_1_10kv(df)
    if not row_indices:
        return pd.DataFrame()

    if "浙江" in province:
        if len(row_indices) >= 3:
            row_indices = row_indices[1:3]
        else:
            row_indices = row_indices[:2]
    elif "江苏" in province:
        row_indices = row_indices[:2]
        if len(row_indices) == 2:
            row_indices = [row_indices[1], row_indices[0]]
    else:
        row_indices = row_indices[:2]

    rows_out = []
    for pos, idx in enumerate(row_indices):
        row = df.iloc[idx]
        price_info = extract_row_prices_with_cluster(
            row, period_order=period_order, non_time_col=non_time_col
        )
        if pos == 0:
            scheme = "单一制"
        elif pos == 1:
            scheme = "两部制"
        else:
            scheme = f"方案{pos + 1}"
        city = province if province.endswith("市") else ""
        rows_out.append(
            {
                "省份": province,
                "城市": city,
                "制度": scheme,
                "电压等级": voltage_label,
                "不分时电价": price_info["non_time"],
                "尖": price_info["尖"],
                "峰": price_info["峰"],
                "平": price_info["平"],
                "谷": price_info["谷"],
                "深": price_info["深"],
            }
        )
    return pd.DataFrame(rows_out)

def parse_price_from_urls(url_list):
    """输入多个 PDF 链接，返回拼好的电价表 + 错误信息列表"""
    all_results = []
    errors = []
    for i, url in enumerate(url_list):
        if not url:
            continue
        try:
            filename = download_pdf_to_file(url, i)
            df_one = parse_single_pdf(filename)
            if not df_one.empty:
                all_results.append(df_one)
            else:
                errors.append((url, "未提取到电价行"))
        except Exception as e:
            errors.append((url, str(e)))
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
    else:
        final_df = pd.DataFrame()
    return final_df, errors

# ===============================
# 页面标题
# ===============================
st.markdown('<div class="main-title">岚图超充站电费自动计算系统</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">① 电价获取（PDF→Excel） ② 超充站电费设置（Excel→结果）</div>', unsafe_allow_html=True)

# ===============================
# 两个主功能：用 Tab 分开
# ===============================
tab1, tab2 = st.tabs(["⚡ 1. 电价获取（PDF → 电价表）", "🏭 2. 超充站电费设置"])

# -------------------------------------------------------------------
# Tab1：电价获取
# -------------------------------------------------------------------
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span class="icon">⚡</span>电价 PDF 链接解析</div>', unsafe_allow_html=True)
    st.write("在下面的文本框中，每行粘贴一个国网 PDF 电价链接，点击 **解析电价** 即可得到标准化的电价表，并可下载为 Excel。")

    url_text = st.text_area("在此粘贴 PDF 链接（每行一个）", height=180,
                            placeholder="https://www.95598.cn/omg-static/....pdf\nhttps://www.95598.cn/omg-static/....pdf")

    btn_parse = st.button("▶ 解析电价", key="btn_parse_price")

    if btn_parse:
        urls = [u.strip() for u in url_text.splitlines() if u.strip()]
        if not urls:
            st.error("❌ 请至少粘贴一个 PDF 链接。")
        else:
            with st.spinner("正在下载并解析 PDF 电价表..."):
                df_price, pdf_errs = parse_price_from_urls(urls)

            if df_price is None or df_price.empty:
                st.error("⚠ 未解析出任何电价记录，请检查链接或 PDF 内容。")
            else:
                st.success(f"✅ 解析成功，共得到 {len(df_price)} 条电价记录。")
                st.dataframe(df_price)

                # 下载电价表
                buf_price = BytesIO()
                df_price.to_excel(buf_price, index=False)
                st.download_button(
                    "📥 下载电价表 Excel（可用于 Tab2）",
                    buf_price.getvalue(),
                    file_name="电价解析结果_1-10kV_全部省份.xlsx",
                    mime="application/vnd.ms-excel"
                )

            # 显示解析错误
            if pdf_errs:
                st.markdown("----")
                st.markdown("**⚠ 以下链接解析失败或未获取到有效电价：**")
                err_df = pd.DataFrame(pdf_errs, columns=["URL", "错误信息"])
                st.dataframe(err_df)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Tab2：超充站电费设置
# -------------------------------------------------------------------
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span class="icon">🏭</span>超充站电费计算</div>', unsafe_allow_html=True)
    st.write("上传 **站点信息 Excel** 和 **电价表 Excel**，选择月份后点击开始计算，系统会自动生成各站点分时电价设置。")
    st.info("💡 电价表 Excel 列名需包含：`省份`、`城市`、`制度`、`不分时电价`、`尖`、`峰`、`平`、`谷`、`深`。你可以直接使用在 Tab1 中下载的电价表。")

    col_left, col_right = st.columns(2)

    with col_left:
        station_file = st.file_uploader("① 上传站点信息 Excel", type=["xlsx"], key="station_xlsx")

    with col_right:
        price_file = st.file_uploader("② 上传电价表 Excel", type=["xlsx"], key="price_xlsx")

    c1, c2 = st.columns(2)
    with c1:
        month = st.number_input("③ 选择月份", min_value=1, max_value=12, value=1, step=1)
    with c2:
        btn_calc = st.button("▶ 开始计算电费", key="btn_calc_fee")

    if btn_calc:
        if station_file is None or price_file is None:
            st.error("❌ 请同时上传【站点信息 Excel】和【电价表 Excel】。")
        else:
            df_station = pd.read_excel(station_file)
            df_price = pd.read_excel(price_file)

            with st.spinner("正在根据电价表计算各站点电费..."):
                df_out, errors = process_station_prices(df_station, df_price, month)

            st.success(f"✅ 共计算 {len(df_out)} 条站点记录。")
            st.dataframe(df_out)

            # 未匹配到电价的站点
            if errors:
                st.markdown("----")
                st.markdown("**⚠ 以下站点未匹配到电价，请检查省份 / 城市 / 配置 是否与电价表一致：**")
                err_df = pd.DataFrame(errors, columns=["序号","站点名称","省份","城市","配置"])
                st.dataframe(err_df)

            # 下载结果
            out_bytes = BytesIO()
            df_out.to_excel(out_bytes, index=False)
            st.download_button(
                f"📥 下载电费计算结果（{month}月）",
                out_bytes.getvalue(),
                file_name=f"电费计算结果_{month}月.xlsx",
                mime="application/vnd.ms-excel"
            )
    st.markdown('</div>', unsafe_allow_html=True)
