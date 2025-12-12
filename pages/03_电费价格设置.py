# -*- coding: utf-8 -*-
# pages/03_电费价格设置.py
import streamlit as st
import pandas as pd
from io import BytesIO
import re

# ========== 时间规则解析函数（不动） ==========
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
    """
    tier 可能是：""（不分时）、"尖"、"峰"、"平"、"谷" 等。
    需求：如果 tier == "尖" 但电价表里没有 "尖" 或值为空，就自动用 "峰" 价格。
    """
    if tier == "":
        return row.get("不分时电价", None)

    # 先按原来的 tier 取值
    val = row.get(tier, None)

    # 如果是尖时段，但没有“尖”这一列或是 NaN，则回退到“峰”
    if tier == "尖":
        if val is None or (isinstance(val, (int, float)) and pd.isna(val)):
            # 回退用峰价
            val = row.get("峰", None)

    return val

# ========== 核心计算函数 ==========
def process_station_prices(df_station, df_price, month):
    df_station = df_station.copy()
    df_station["配置"] = df_station["配置"].astype(str).str.strip()

    output = []
    errors = []
    col = f"电费-{month}月"

    for _, r in df_station.iterrows():

        prov = r["所在省份"]
        city = r.get("所属市区", "")
        config = str(r["配置"]).strip()
        fs = str(r["是否分时"]).strip()
        mult = float(r["电费乘子"])
        rule_txt = r.get(col, "")

        # ------- 关键：广东省按城市匹配，其它省按省份匹配 --------
        if "广东" in str(prov):
            # 先按 省份 + 制度 + 城市 精确匹配
            if "城市" in df_price.columns:
                match = df_price[
                    (df_price["省份"] == prov)
                    & (df_price["制度"] == config)
                    & (df_price["城市"] == str(city).strip())
                ]
            else:
                # 万一电价表没有“城市”列，就退回省份 + 制度
                match = df_price[
                    (df_price["省份"] == prov)
                    & (df_price["制度"] == config)
                ]

            # 如果按城市完全没匹配到，再退回 省份 + 制度
            if match.empty:
                match = df_price[
                    (df_price["省份"] == prov)
                    & (df_price["制度"] == config)
                ]
        else:
            # 其他省份：省份 + 制度
            match = df_price[
                (df_price["省份"] == prov)
                & (df_price["制度"] == config)
            ]
        # ----------------------------------------------------

        if match.empty:
            final = "未匹配到价格"
            errors.append((r["序号"], r["站点名称"], prov, city, config))

        else:
            prow = match.iloc[0]

            if fs == "否":
                p = prow["不分时电价"] * mult
                final = f"0:00 - 24:00 {round(p, 4)}元/度"

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


# ========== UI：标题 ==========
st.markdown("""
<div class='main-header'>
⚡ 超充站电费设置（站点信息 × 电价表）
</div>
""", unsafe_allow_html=True)


# ========== 操作流程卡片 ==========
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
    <div class='icon-circle'>🧭</div>
    操作流程
</div>

1. 上传站点信息 Excel。  
2. 选择电价来源（Page2 修正版 / Page1 原始 / 上传 Excel）。  
3. 点击“开始计算电费”，系统生成每站点分时电价文本。  
4. 结果将自动保存，用于 Page6（总价计算）。
""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


# ========== 站点信息 + 电价来源卡片 ==========
st.markdown("<div class='card'>", unsafe_allow_html=True)

st.markdown("""
<div class='card-title'>
    <div class='icon-circle'>📄</div>
    上传文件 & 选择电价表
</div>
""", unsafe_allow_html=True)

# --- 上传站点信息 ---
station_file = st.file_uploader("① 上传站点信息 Excel 文件", type=["xlsx"])

# --- 电价来源 ---
price_src = st.radio(
    "② 选择电价表来源：",
    ["使用 Page2 修正版", "使用 Page1 原始结果", "上传电价 Excel 文件"]
)

df_price = None

if price_src == "使用 Page2 修正版":
    df_price = st.session_state.get("price_fixed")

elif price_src == "使用 Page1 原始结果":
    df_price = st.session_state.get("price_raw")

else:
    up_price = st.file_uploader("上传电价 Excel", type=["xlsx"])
    if up_price:
        df_price = pd.read_excel(up_price)

# --- 月份选择 ---
month = st.number_input("③ 选择月份（月）", 1, 12, 1)

st.markdown("</div>", unsafe_allow_html=True)


# ========== 计算按钮 ==========
st.markdown("<div class='card'>", unsafe_allow_html=True)

st.markdown("""
<div class='card-title'>
    <div class='icon-circle'>⚙️</div>
    电费计算
</div>
""", unsafe_allow_html=True)

if st.button("▶ 开始计算电费", width="stretch"):

    if station_file is None:
        st.error("❌ 请上传站点信息文件！")
        st.stop()

    df_station = pd.read_excel(station_file)

    if df_price is None or df_price.empty:
        st.error("❌ 电价表为空，请检查来源或先完成 Page1/Page2。")
        st.stop()

    with st.spinner("正在为每个站点生成分时电费……"):
        df_out, errors = process_station_prices(df_station, df_price, month)

    st.session_state["station_fee"] = df_out

    st.success(f"电费计算完成，共 {len(df_out)} 条记录。")
    st.dataframe(df_out, width="stretch")

    buf = BytesIO()
    df_out.to_excel(buf, index=False)
    st.download_button(
        f"📥 下载电费计算结果（{month}月）",
        buf.getvalue(),
        f"电费计算_{month}月.xlsx",
        mime="application/vnd.ms-excel",
        width="stretch"
    )

    if errors:
        st.warning("以下站点未匹配到电价：")
        err_df = pd.DataFrame(errors, columns=["序号", "站点名称", "省份", "城市", "配置"])
        st.dataframe(err_df, width="stretch")

st.markdown("</div>", unsafe_allow_html=True)
