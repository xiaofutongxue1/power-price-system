# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from io import BytesIO

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
    ["从 Page1 导入电价表（推荐）", "上传 Excel 文件"]
)

df = None

# ---------------------------
# 来源 1：Page1 自动解析结果
# ---------------------------
if source == "从 Page1 导入电价表（推荐）":
    df = st.session_state.get("price_raw")
    if df is None:
        st.warning("⚠ Page1 尚未解析电价，请先前往 Page1 进行解析，或选择上传 Excel 文件。")

# ---------------------------
# 来源 2：上传 Excel 表
# ---------------------------
else:
    uploaded_file = st.file_uploader("上传电价 Excel 文件", type=["xlsx"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file)


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

    # Editable DataFrame
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",  # 增加/减少行
        use_container_width=True
    )

    # 保存按钮
    if st.button("💾 保存电价修正版", use_container_width=True):
        st.session_state["price_fixed"] = edited_df

        st.success("已保存修正版，可用于 Page3 & Page6。")

        # 允许下载修正版
        buf = BytesIO()
        edited_df.to_excel(buf, index=False)
        st.download_button(
            "📥 下载电价修正版（Excel）",
            buf.getvalue(),
            "电价修正版.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("⬆ 请先选择数据来源并加载电价表。")
