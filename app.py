import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ===============================
# CSS（页面美化）
# ===============================
st.set_page_config(page_title="岚图超充站电费自动计算系统", layout="wide")

st.markdown("""
<style>
    .main-title {
        font-size:36px !important;
        color:white;
        text-align:center;
        padding:20px;
        background:#1E3A8A;
        border-radius:8px;
        margin-bottom:20px;
    }
    .sub-title {
        font-size:18px;
        color:#444;
        margin-bottom:10px;
    }
    .card {
        background:white;
        padding:20px;
        border-radius:10px;
        box-shadow:0 2px 6px rgba(0,0,0,0.1);
        margin-bottom:20px;
    }
</style>
""", unsafe_allow_html=True)

# ===============================
# 工具函数
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

# 核心计算函数
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
                         (df_price["城市"] == city) &
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
# 页面标题
# ===============================
st.markdown('<div class="main-title">岚图超充站电费自动计算系统</div>', unsafe_allow_html=True)

st.markdown('<div class="sub-title">上传 Excel → 选择月份 → 自动生成各站点分时电价</div>', unsafe_allow_html=True)


# ===============================
# 左侧栏输入区
# ===============================

with st.sidebar:
    st.header("📥 参数输入")
    station_file = st.file_uploader("上传站点信息 Excel", type=["xlsx"])
    price_file = st.file_uploader("上传电价表 Excel", type=["xlsx"])
    month = st.number_input("选择月份", min_value=1, max_value=12)

    start = st.button("▶ 开始计算")


# ===============================
# 主界面处理
# ===============================
if start:
    if station_file is None or price_file is None:
        st.error("❌ 请上传两个 Excel 文件")
    else:
        df_station = pd.read_excel(station_file)
        df_price = pd.read_excel(price_file)

        with st.spinner("正在处理数据，请稍候..."):
            df_out, errors = process_station_prices(df_station, df_price, month)

        # -------------------------------
        # 结果展示卡片
        # -------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 处理结果预览")
        st.dataframe(df_out)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------
        # 错误显示
        # -------------------------------
        if errors:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("⚠ 未匹配到电价的站点")
            err_df = pd.DataFrame(errors, columns=["序号","站点名称","省份","城市","配置"])
            st.dataframe(err_df)
            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------
        # 文件下载
        # -------------------------------
        out_bytes = BytesIO()
        df_out.to_excel(out_bytes, index=False)
        st.download_button("📥 点击下载结果 Excel", out_bytes.getvalue(),
                           file_name=f"电费计算结果_{month}月.xlsx",
                           mime="application/vnd.ms-excel")
