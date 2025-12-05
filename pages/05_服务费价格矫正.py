# -*- coding: utf-8 -*-
# pages/05_服务费价格矫正.py

import streamlit as st
import pandas as pd
from io import BytesIO
import re

# ============================================
# 页面标题
# ============================================
st.markdown("""
<div class='main-header'>🛠️ 超充站服务费价格矫正</div>
""", unsafe_allow_html=True)

# ============================================
# 读取数据：沿用 or 上传（类似 Page2）
# ============================================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>📥</div> 数据来源（沿用或上传）
</div>
""", unsafe_allow_html=True)

df_source = None

# 判断 Page4 是否真的有可用数据
has_page4_data = (
    "service_price_raw" in st.session_state
    and isinstance(st.session_state["service_price_raw"], pd.DataFrame)
    and not st.session_state["service_price_raw"].empty
    and ("站点名称" in st.session_state["service_price_raw"].columns)
    and ("服务费" in st.session_state["service_price_raw"].columns)
)

# 选择数据来源
source_option = st.radio(
    "请选择服务费数据来源：",
    ("从 Page4 导入服务费表（推荐）", "上传 Excel 文件"),
    index=0 if has_page4_data else 1,
    horizontal=False,
)

if has_page4_data:
    st.success("✅ 检测到 Page4 生成的服务费数据，可直接沿用。")
else:
    st.info("ℹ 当前会话中尚未检测到 Page4 生成的服务费结果，如有需要请先前往 Page4 计算，或上传 Excel 文件。")

# 上传文件控件（无论选择哪种来源，都允许上传，以防覆盖）
uploaded_file = st.file_uploader("或上传服务费数据（需包含『站点名称』和『服务费』两列）", type=["xlsx"])

st.markdown("</div>", unsafe_allow_html=True)

# ============================================
# 数据载入逻辑
# ============================================
if source_option == "从 Page4 导入服务费表（推荐）" and has_page4_data:
    df_source = st.session_state["service_price_raw"].copy()
elif uploaded_file is not None:
    df_source = pd.read_excel(uploaded_file)

if df_source is None:
    st.warning("请先从 Page4 导入服务费结果，或上传包含『站点名称 + 服务费』列的 Excel 文件。")
    st.stop()

if "站点名称" not in df_source.columns or "服务费" not in df_source.columns:
    st.error("❌ 数据缺少必要字段：站点名称 / 服务费")
    st.stop()

# ============================================
# 文本解析函数：服务费文本 → (start, end, price)
# ============================================
def parse_fee_text(text):
    """
    输入示例（支持有/没有“谷/峰/平/尖”等前缀）：
        谷 0:00 - 7:00 0.50元/度
        平 7:00 - 10:00 0.50元/度
        0:00 - 24:00 0.50元/度
    输出 DataFrame:
        start | end | price
    """
    rows = []

    if text is None:
        return pd.DataFrame(columns=["start", "end", "price"])

    for line in str(text).splitlines():
        line = line.strip()
        if not line:
            continue

        m = re.search(
            r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2}).*?([0-9]+(?:\.[0-9]+)?)",
            line
        )
        if not m:
            continue

        start, end, price_str = m.groups()
        try:
            price = float(price_str)
        except ValueError:
            continue

        rows.append([start, end, price])

    return pd.DataFrame(rows, columns=["start", "end", "price"])


# ============================================
# 初始化 session_state 用于保存矫正结果
# ============================================
if "service_price_corrected" not in st.session_state:
    st.session_state["service_price_corrected"] = {}

# ============================================
# TAB：编辑模式 & 演示模式
# ============================================
tab_edit, tab_view = st.tabs(["🔧 编辑模式", "📄 演示模式"])

# ============================================================
# 🔧 TAB 1：编辑模式
# ============================================================
with tab_edit:

    station_list = df_source["站点名称"].unique().tolist()
    station = st.selectbox("选择需要矫正的站点：", station_list)

    # 获取当前站点原始结构或矫正后的结构
    if station in st.session_state["service_price_corrected"]:
        df_current = pd.DataFrame(st.session_state["service_price_corrected"][station])
    else:
        raw_text = df_source[df_source["站点名称"] == station]["服务费"].values[0]
        df_current = parse_fee_text(raw_text)

    st.markdown("### 当前服务费时段")
    st.dataframe(df_current, use_container_width=True)

    st.info("👇 进行服务费矫正：仅需填写【结束时间 + 服务费】，开始时间系统自动生成。")

    # 构建可编辑表（只编辑 end / price）
    editable_df = pd.DataFrame({
        "结束时间": df_current["end"].tolist(),
        "服务费": df_current["price"].tolist()
    })

    editable_df = st.data_editor(
        editable_df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_fee_rows"
    )

    # === 点击保存 ===
    if st.button("💾 保存矫正结果", use_container_width=True):

        # 直接用 data_editor 返回值
        if isinstance(editable_df, pd.DataFrame):
            new_df = editable_df.copy()
        else:
            new_df = pd.DataFrame(editable_df)

        # 1. 检查列名
        if ("结束时间" not in new_df.columns) or ("服务费" not in new_df.columns):
            st.error("❌ 表格缺少『结束时间』或『服务费』列，请不要修改列名。")
            st.stop()

        # 2. 丢掉空行
        new_df["结束时间"] = new_df["结束时间"].astype(str).str.strip()
        new_df = new_df[new_df["结束时间"] != ""]
        new_df = new_df[~new_df["服务费"].isna()]

        if new_df.empty:
            st.error("❌ 请至少保留一行有效的时间段（结束时间 + 服务费）。")
            st.stop()

        # 3. 取出干净的列表
        ends = new_df["结束时间"].tolist()
        prices = new_df["服务费"].astype(float).tolist()

        try:
            # 必须以 24:00 结束
            if ends[-1] != "24:00":
                st.error("❌ 最后一段必须以 24:00 结束")
                st.stop()

            # 生成新的 start/end 结构
            reconstructed = []
            current_start = "0:00"

            for end, price in zip(ends, prices):
                reconstructed.append({
                    "start": current_start,
                    "end": end,
                    "price": float(price)
                })
                current_start = end

            # 校验起点
            if reconstructed[0]["start"] != "0:00":
                st.error("❌ 第一段必须从 0:00 开始")
                st.stop()

            # 校验连续性
            for i in range(1, len(reconstructed)):
                if reconstructed[i]["start"] != reconstructed[i - 1]["end"]:
                    st.error(f"❌ 时间段不连续：{reconstructed[i-1]['end']} → {reconstructed[i]['start']}")
                    st.stop()

            # 保存
            st.session_state["service_price_corrected"][station] = reconstructed
            st.success("✔ 已保存矫正服务费！")

            # 关键：立即刷新页面，让上面的“当前服务费时段”也使用新结果
            st.rerun()

        except Exception as e:
            st.error(f"❌ 保存失败，请检查输入格式：{e}")

# ============================================================
# 📄 TAB 2：演示模式
# ============================================================
with tab_view:

    st.markdown("### 全部站点的最新服务费时段结构")

    rows_out = []

    for st_name in df_source["站点名称"].unique():

        # 优先使用矫正结果
        if st_name in st.session_state["service_price_corrected"]:
            df_final = st.session_state["service_price_corrected"][st_name]
        else:
            raw_text = df_source[df_source["站点名称"] == st_name]["服务费"].values[0]
            df_final = parse_fee_text(raw_text).to_dict("records")

        txt = "\n".join(
            [f"{r['start']} - {r['end']}  {r['price']}元/度" for r in df_final]
        ) if df_final else "-"

        rows_out.append([st_name, txt])

    df_show = pd.DataFrame(rows_out, columns=["站点名称", "服务费"])
    st.dataframe(df_show, use_container_width=True)

    # === 新增：下载矫正后的服务费表 ===
    out_buf = BytesIO()
    df_show.to_excel(out_buf, index=False)
    out_buf.seek(0)

    st.download_button(
        "📥 下载矫正后的服务费表 Excel",
        data=out_buf.getvalue(),
        file_name="服务费_矫正结果.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True,
    )

