# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from io import BytesIO

PRICE_COLS = ["不分时电价", "尖", "峰", "平", "谷", "深"]  # 你实际有哪些就写哪些

def cast_price_cols(df: pd.DataFrame) -> pd.DataFrame:
    """把所有价钱列统一转成 float，避免 object 混在一起导致奇怪的复制行为。"""
    df = df.copy()
    for col in PRICE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# ================================
# 页面标题区
# ================================
st.markdown("""
<div class='main-header'>
🛠 电价编辑矫正（增删改查）
</div>
""", unsafe_allow_html=True)


# ================================
# 操作流程卡片
# ================================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
    <div class='icon-circle'>🧭</div>
    操作流程
</div>

1. 选择电价表来源（上传 Excel 或使用 Page1 自动解析结果）。  
2. 进入可编辑表格界面，可执行增删改查（支持快捷键）。  
3. 点击“保存修正版”，系统将数据保存到全局，并可下载 Excel 文件。  
4. 修正版将用于 Page3（电费计算）与 Page6（总价计算）。
""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


# ================================
# 选择数据来源卡片
# ================================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
    <div class='icon-circle'>📄</div>
    选择电价表来源
</div>
""", unsafe_allow_html=True)

source = st.radio(
    "请选择电价来源：",
    ["从 Page1 导入电价表（推荐）", "上传 Excel 文件"],
    horizontal=False
)

df: pd.DataFrame | None = None
df_fixed = st.session_state.get("price_fixed")   # 已保存的修正版（如果有）

# ---------------------------
# 情况 1：优先使用已保存的修正版
# ---------------------------
if df_fixed is not None:
    df = cast_price_cols(df_fixed)   # 👈 先把价钱列转 float
    st.info("当前加载的是 **上次保存的电价修正版**。如需重新从 Page1 或 Excel 载入，请先在下方选择来源并重新上传/解析。")

# ---------------------------
# 如果还没有修正版，再按来源取数据
# ---------------------------
if df is None:
    if source == "从 Page1 导入电价表（推荐）":
        df_raw = st.session_state.get("price_raw")
        if df_raw is None:
            st.warning("⚠ Page1 尚未解析电价，请先前往 Page1 进行解析，或选择上传 Excel 文件。")
        else:
            df = cast_price_cols(df_raw)
    else:
        uploaded_file = st.file_uploader("上传电价 Excel 文件", type=["xlsx"])
        if uploaded_file:
            df_up = pd.read_excel(uploaded_file)
            df = cast_price_cols(df_up)

st.markdown("</div>", unsafe_allow_html=True)


# ================================
# 可编辑表格
# ================================
if df is not None:

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("""
    <div class='card-title'>
        <div class='icon-circle'>✏️</div>
        电价表编辑区
    </div>
    """, unsafe_allow_html=True)

    st.info("🔧 提示：在表格中可直接增删改查，并支持快捷键编辑（如 Delete / Ctrl+X）。")

    # 用 df 作为当前可编辑基准（无论是原始数据还是修正版）
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",      # 允许增删行
        use_container_width=True,
        key="price_editor"
    )

    # 保存按钮
    if st.button("💾 保存电价修正版", use_container_width=True):
        cleaned = cast_price_cols(edited_df)   # 再清洗一次，防止复制出的字符串被乱广播
        st.session_state["price_fixed"] = cleaned

        st.success("已保存修正版，可用于 Page3 & Page6。")

    # 下载当前编辑内容（无论是否点击保存）
    buf = BytesIO()
    cast_price_cols(edited_df).to_excel(buf, index=False)
    st.download_button(
        "📥 下载当前电价表（Excel）",
        buf.getvalue(),
        "电价修正版.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("⬆ 请先选择数据来源并加载电价表。")

