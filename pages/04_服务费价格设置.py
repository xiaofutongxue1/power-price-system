# -*- coding: utf-8 -*-
# pages/04_服务费价格设置.py
import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ===============================
# 页面标题
# ===============================
st.markdown("""
<div class='main-header'>
🏷 超充站服务费价格设置（按电费分时段生成服务费）
</div>
""", unsafe_allow_html=True)


# ===============================
# 操作说明
# ===============================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>🧭</div>
  操作说明
</div>

1. 上传 **站点电价分时段表**（包含电费-1月〜电费-12月字段）。  
2. 上传 **服务费价格表**（包含一口价服务费、尖、峰、平、谷、深）。  
3. 选择月份，系统将根据【当月电费时段划分】生成对应的服务费时段价格。  
4. 若某站点任意月份的电费时段为 **0:00 - 24:00**，则自动使用“一口价服务费”。  

""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


# ===============================
# 上传两张表
# ===============================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>📄</div>
  上传数据文件
</div>
""", unsafe_allow_html=True)

file_station = st.file_uploader(
    "① 上传站点信息（含电费-1月〜电费-12月）",
    type=["xlsx"],
    key="station_fee_structure"
)

file_service = st.file_uploader(
    "② 上传服务费价格表（含一口价服务费 / 尖峰平谷深）",
    type=["xlsx"],
    key="service_price_table"
)

# 选择月份
month = st.number_input("③ 选择月份", min_value=1, max_value=12, value=1)

st.markdown("</div>", unsafe_allow_html=True)


# ===============================
# 工具：解析时段行
# ===============================
pattern = re.compile(r"(\S+)\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")

def parse_line(line):
    """
    输入 "谷 0:00 - 7:00"
    输出 ("谷", "0:00", "7:00")
    """
    m = pattern.search(line)
    if not m:
        return None
    tier, start, end = m.group(1), m.group(2), m.group(3)
    return tier, start, end


# ===============================
# 主逻辑：点击生成服务费
# ===============================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>⚙️</div>
  生成服务费结果
</div>
""", unsafe_allow_html=True)

if st.button("▶ 生成服务费时段", use_container_width=True):

    if file_station is None or file_service is None:
        st.error("❌ 请先上传两张表。")
        st.stop()

    df_station = pd.read_excel(file_station)
    df_service_price = pd.read_excel(file_service)

    # 本月电费字段名
    fee_col = f"电费-{month}月"

    if fee_col not in df_station.columns:
        st.error(f"❌ 未找到字段：{fee_col}")
        st.stop()

    results = []

    for idx, row in df_station.iterrows():

        station = row["站点名称"]
        fee_text = row[fee_col]

        # 找该站点的服务费价格
        matched = df_service_price[df_service_price["站点名称"] == station]

        if matched.empty:
            results.append({
                "站点名称": station,
                "服务费": "未找到服务费价格"
            })
            continue

        price_info = matched.iloc[0]

        # 多行电费时段拆分
        fee_lines = str(fee_text).split("\n")

        # 判断是否含 0:00 - 24:00 → 一口价
        is_flat = any(("0:00" in line and "24:00" in line) for line in fee_lines)

        if is_flat:
            flat_price = price_info.get("一口价服务费")
            if pd.isna(flat_price):
                results.append({
                    "站点名称": station,
                    "服务费": "一口价缺失"
                })
            else:
                results.append({
                    "站点名称": station,
                    "服务费": f"0:00 - 24:00 {flat_price:.2f}元/度"
                })
            continue

        # 否则按分时段生成
        out_lines = []
        for line in fee_lines:
            parsed = parse_line(line)
            if not parsed:
                continue
            tier, start, end = parsed

            service_price = price_info.get(tier)
            if pd.isna(service_price):
                continue

            out_lines.append(f"{tier} {start} - {end} {service_price:.2f}元/度")

        results.append({
            "站点名称": station,
            "服务费": "\n".join(out_lines)
        })

    df_out = pd.DataFrame(results)

    # 显示结果
    st.success("服务费计算完成！")
    st.dataframe(df_out, use_container_width=True)

    # 下载
    buf = BytesIO()
    df_out.to_excel(buf, index=False)
    st.download_button(
        "📥 下载服务费结果 Excel",
        buf.getvalue(),
        f"服务费-第{month}月.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )

    # 保存到 session_state（给 Page5 / Page6 使用）
    st.session_state["service_price_raw"] = df_out

st.markdown("</div>", unsafe_allow_html=True)
