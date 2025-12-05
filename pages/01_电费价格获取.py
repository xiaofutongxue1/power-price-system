# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from io import BytesIO
import requests
import pdfplumber
import re

# ===============================
# 页面标题区
# ===============================
st.markdown("""
<div class='main-header'>
📄 电价获取（PDF → 电价表）
</div>
""", unsafe_allow_html=True)


# ===============================
# 顶部红色警告区
# ===============================
st.markdown("""
<div style="
    background:#FEE2E2;
    color:#991B1B;
    padding:18px 22px;
    border-left:6px solid #DC2626;
    border-radius:8px;
    font-size:16px;
    margin-bottom:25px;">
⚠️ <b>以下省份暂不支持自动解析</b> 
 
- <b>国网图片格式</b>：湖北省、山东省、河南省  

- <b>南网数据格式</b>：云南省、广东省、贵州省  

请在 Page2 中手动上传 Excel 进行矫正。
</div>
""", unsafe_allow_html=True)



# ========================================================================
# =============== 以下部分是 PDF 解析函数（可直接运行） ====================
# ========================================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.95598.cn/",
    "Accept": "application/pdf",
}

def safe_float(x):
    try:
        return float(str(x).replace(",", ""))
    except:
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

    # 去掉所有空白，避免“电力\n公司”这种被断行的情况
    text_clean = re.sub(r"\s+", "", text)

    start = text_clean.find("国网")
    if start != -1:
        end = text_clean.find("电力有限公司", start)
        if end == -1:
            end = text_clean.find("电力公司", start)
        if end != -1:
            company = text_clean[start + len("国网") : end]
            province = company.strip()
        else:
            province = "未知省份"
    else:
        province = "未知省份"

    # 小修正：重庆 → 重庆市
    if province == "重庆":
        province = "重庆市"
    if province == "未知省份":
        province = "上海市"
    return province

# ==========================
# 基础小函数
# ==========================
def safe_float(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None

def detect_columns(df):
    """
    返回：
        period_cols: {'尖': col_idx, '峰': col_idx, ...} （只包含存在的档位）
        non_time_col: 非分时电度电价所在列号（找不到则为 None）
    """
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

    # ⚠ 不要再提前 break，整张表都扫一遍，后面的行可以覆盖前面的误判
    for _, row in df.iterrows():
        for col_idx, cell in enumerate(row):
            s = str(cell) if cell is not None else ""

            # 1）非分时电价列
            if any(kw in s for kw in non_time_kws):
                non_time_col = col_idx

            # 2）分时档位列
            # 🔹 先专门处理“尖峰时段 / 尖峰” —— 强制认为只有“尖”
            if any(w in s for w in ["尖峰时段", "尖峰"]):
                matched_shorts = ["尖"]
            else:
                matched_shorts = []
                for short, kws in period_kw_map.items():
                    if any(kw in s for kw in kws):
                        matched_shorts.append(short)

            # 只在“只命中一个档位”的单元格里认列号
            if len(matched_shorts) == 1:
                short = matched_shorts[0]
                period_cols[short] = col_idx
            else:
                continue
    return period_cols, non_time_col
# ---------- 修复四川：更稳健地识别表头 ----------
def get_header_time_labels(df):
    """
    在整张表里扫描，找到包含分时档关键字的一行，用这行判断分时档位的顺序，
    映射为 ['尖','峰','平','谷','深'] 中的一部分。
    优先选择「包含尖峰」的行，若没有再退而求其次。
    """
    raw_to_short = {
        # 尖 / 尖峰
        "尖峰时段": "尖", "尖峰": "尖", "尖时段": "尖", "尖时": "尖", "尖": "尖",
        # 峰（高峰、峰段、峰时等）
        "高峰时段": "峰", "高峰": "峰", "峰段": "峰",
        "峰时段": "峰", "峰时": "峰", "峰": "峰",
        # 平
        "平段": "平", "平时段": "平", "平时": "平", "平": "平",
        # 谷
        "低谷时段": "谷", "低谷": "谷", "谷段": "谷",
        "谷时段": "谷", "谷时": "谷", "谷": "谷",
        # 深谷 / 深
        "深谷时段": "深", "深谷": "深", "深时段": "深", "深时": "深", "深": "深",
    }

    # ---------- 第 1 轮：优先找包含“尖峰”的表头行 ----------
    header_text = ""
    # 优先找包含“尖峰”的行
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

    # ---------- 第 2 轮：如果没有尖峰，再退而求其次 ----------
    if not header_text:
        # 再找任意包含两个以上时段关键字的行
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
        # 没识别到，说明这个省可能完全没有分时电价
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

    # 从右向左，最多抓 5 个“像电价的数字”
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
    """
    将分时电价簇（cluster）右对齐映射到 period_order 里。
    返回：{'尖':None,'峰':x,'平':y,'谷':z,'深':None}
    """
    result = {p: None for p in ["尖", "峰", "平", "谷", "深"]}
    if not period_order or not cluster:
        return result

    n = len(period_order)
    m = len(cluster)

    if m == n:
        # 1 对 1 对齐
        for i, p in enumerate(period_order):
            result[p] = cluster[i]
    else:
        # 默认右对齐（缺尖时），兼容福建这类情况
        offset = n - m
        for i, p in enumerate(period_order):
            j = i - offset
            if 0 <= j < m:
                result[p] = cluster[j]

    return result


def extract_row_prices(row, period_order):
    """
    从一行中抽取：非分时电价 + 分时电价（按 period_order 映射）
    """
    # 非分时电价 = 这一行第一个 0.1~2 之间的数
    non_time = None
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

# ---------- 修复上海：更通用的电压匹配 ----------
def find_voltage_rows_1_10kv(df):
    """
    在整张表中找到“1-10（20）千伏 / 1-10千伏 / 10千伏”等行。
    优先匹配 1-10（20）千伏，如果没有，再匹配 10千伏。
    """
    # 1) 先找 1-10（20）千伏 / 1-10千伏 / 1~10千伏
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

    # 2) 如果完全没有 1-10 这种写法，退化为找 “10千伏”
    pattern_10kv = re.compile(r"(^|[^0-9])10\s*千伏(?!安)")
    idxs = []
    for i, row in df.iterrows():
        text = "".join(str(c) for c in row.values)
        if pattern_10kv.search(text):
            idxs.append(i)

    return idxs
def extract_row_prices_fallback(row, period_order):
    # 非分时电价：这一行第一个 0.1~2 的数字
    non_time = None
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

# ==========================
# 解析单个 PDF → 返回该省的 1-10kV 结果
# ==========================
def parse_single_pdf(pdf_path):
    province = detect_province_from_pdf(pdf_path)
    city = ""  # 目前国网表里没有城市这一层，就先留空

    # 1. PDF → DataFrame
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    clean = [c.strip() if isinstance(c, str) else c for c in row]
                    if any(clean):
                        rows.append(clean)

    if not rows:
        print(f"[{province}] 没有解析到任何表格。")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.replace("", None, inplace=True)
    df.dropna(how="all", axis=1, inplace=True)
    df.dropna(how="all", axis=0, inplace=True)
    df.reset_index(drop=True, inplace=True)

    # 2. 识别分时档顺序
    period_cols, non_time_col = detect_columns(df)
    print(f"[{province}] 检测到列：", period_cols, " 非分时列 =", non_time_col)


    voltage_label = "1-10（20）千伏"  # 只是最终输出的展示文字
    row_indices = find_voltage_rows_1_10kv(df)

    if not row_indices:
        print(f"[{province}] 未找到 1-10（20）千伏 / 10千伏 行，跳过。")
        return pd.DataFrame()

    if "浙江" in province:
        # 浙江取第 2、3 条
        if len(row_indices) >= 3:
            row_indices = row_indices[1:3]
        else:
            row_indices = row_indices[:2]

    elif "江苏" in province:
        # 江苏 PDF 里是 先两部制 后单一制，需要反过来
        row_indices = row_indices[:2]
        if len(row_indices) == 2:
            row_indices = [row_indices[1], row_indices[0]]

    else:
        # 其他省份：默认取前两条（单一制 + 两部制）
        row_indices = row_indices[:2]
    rows_out = []

    for pos, idx in enumerate(row_indices):
        row = df.iloc[idx]

        # 5. 读取价格（你原来的逻辑）
        if period_cols:
            price_info = {"non_time": None, "尖": None, "峰": None, "平": None, "谷": None, "深": None}

            # 非分时电价
            if non_time_col is not None and non_time_col < len(row):
                price_info["non_time"] = safe_float(row[non_time_col])
            # 兜底再扫一遍
            if price_info["non_time"] is None:
                for cell in row:
                    v = safe_float(cell)
                    if v is not None and 0.1 <= v <= 2:
                        price_info["non_time"] = v
                        break

            # 各分时段
            for p, col_idx in period_cols.items():
                if col_idx < len(row):
                    price_info[p] = safe_float(row[col_idx])

        else:
            period_order = get_header_time_labels(df)
            price_info = extract_row_prices_fallback(row, period_order)

        # ------------------------------------------------------------------
        # 【新增】浙江省专用修正：去掉“政府性基金”那一列，只保留 尖/峰/平/谷
        # ------------------------------------------------------------------
        if "浙江" in province:
            cluster = get_time_cluster_from_row(row)  # 例如 [0.0292, 1.3162, 1.0969, 0.6648, 0.2526]

            # 如果前面有一个很小的数（通常是政府性基金），把它丢掉，只保留后 4 个
            while len(cluster) > 4 and cluster[0] is not None and cluster[0] < 0.1:
                cluster = cluster[1:]

            if len(cluster) == 4:
                # 保留原来算出来的 non_time（不分时电价）
                non_time_val = price_info.get("non_time")

                price_info = {
                    "non_time": non_time_val,
                    "尖": cluster[0],
                    "峰": cluster[1],
                    "平": cluster[2],
                    "谷": cluster[3],
                    "深": None,  # 浙江没有深谷
                }
        # ------------------------------------------------------------------

        # 6. 行标签：单一制 / 两部制 / 方案3...
        if pos == 0:
            scheme = "单一制"
        elif pos == 1:
            scheme = "两部制"
        else:
            scheme = f"方案{pos + 1}"

        rows_out.append(
            {
                "省份": province,
                "城市": city if province != "重庆市" else "重庆市",
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
    results = []
    errors = []

    for i, url in enumerate(url_list):
        try:
            file = download_pdf_to_file(url, i)
            df_one = parse_single_pdf(file)
            if df_one.empty:
                errors.append((url, "未能识别有效电价行"))
            else:
                results.append(df_one)

        except Exception as e:
            errors.append((url, str(e)))

    if results:
        df_final = pd.concat(results, ignore_index=True)
    else:
        df_final = pd.DataFrame()

    return df_final, errors
# ========================================================================
# =============================== UI 部分 ================================
# ========================================================================


# 输入区卡片
st.markdown("<div class='card'>", unsafe_allow_html=True)

st.markdown("""
<div class='card-title'>
    <div class='icon-circle'>🔗</div>
    输入 PDF 链接
</div>
""", unsafe_allow_html=True)

url_text = st.text_area(
    "每行一个 PDF 链接",
    height=200,
    placeholder="https://www.95598.cn/...pdf\nhttps://www.95598.cn/...pdf"
)


if st.button("▶ 解析电价", use_container_width=True):

    urls = [u
            for u in url_text.splitlines()
            if u.strip()]

    if not urls:
        st.error("❌ 请至少粘贴一个链接")
        st.stop()

    df_price, errors = parse_price_from_urls(urls)

    st.session_state["price_raw"] = df_price

    st.markdown("</div>", unsafe_allow_html=True)

    # 输出卡片
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("""
    <div class='card-title'>
        <div class='icon-circle'>📊</div>
        解析结果
    </div>
    """, unsafe_allow_html=True)

    if df_price is not None and not df_price.empty:
        st.success(f"解析完成：共 {len(df_price)} 条记录")
        st.dataframe(df_price)

        buf = BytesIO()
        df_price.to_excel(buf, index=False)
        st.download_button(
            "📥 下载电价表（Excel）",
            buf.getvalue(),
            "电价解析结果.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )
    else:
        st.warning("⚠ 未能解析任何电价")

    st.markdown("</div>", unsafe_allow_html=True)

    # 错误卡片
    if errors:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("""
        <div class='card-title'>
            <div class='icon-circle'>⚠️</div>
            解析失败列表
        </div>
        """, unsafe_allow_html=True)
        err_df = pd.DataFrame(errors, columns=["URL", "错误信息"])
        st.dataframe(err_df)
        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.markdown("</div>", unsafe_allow_html=True)
