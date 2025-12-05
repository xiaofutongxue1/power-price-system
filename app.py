# -*- coding: utf-8 -*-
import streamlit as st

# ================================
# 基础配置
# ================================
st.set_page_config(
    page_title="岚图超充站电价管理系统",
    page_icon="⚡",
    layout="wide"
)

# ================================
# 全局 CSS
# ================================
st.markdown("""
<style>
/* 背景色 */
body {
    background-color: #f3f4f6;
}

/* 主标题栏 */
.main-header {
    font-size: 40px;
    font-weight: 700;
    text-align: center;
    color: white;
    padding: 25px;
    margin-bottom: 30px;
    border-radius: 15px;
    background: linear-gradient(90deg, #1D4ED8, #0EA5E9);
    box-shadow: 0 4px 15px rgba(0,0,0,0.15);
}

/* 次标题 */
.sub-header {
    text-align: center;
    font-size: 18px;
    color: #374151;
    margin-bottom: 25px;
}

/* 卡片样式 */
.card {
    background: white;
    padding: 22px 26px;
    border-radius: 14px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.08);
    border: 1px solid #e5e7eb;
    margin-bottom: 24px;
}

/* 卡片小标题 */
.card-title {
    font-size: 22px;
    font-weight: 600;
    color: #111827;
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 10px;
}

/* 图标背景 */
.icon-circle {
    width: 32px;
    height: 32px;
    border-radius: 999px;
    background: #EFF6FF;
    color: #1D4ED8;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 18px;
}

/* 列表样式 */
.feature-list li {
    margin: 6px 0;
    font-size: 16px;
    color: #374151;
}
</style>
""", unsafe_allow_html=True)


# ================================
# 全局 Session State 初始化
# ================================
def init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

init_state("price_raw", None)
init_state("price_fixed", None)

init_state("station_info", None)
init_state("station_fee", None)

init_state("service_price_raw", None)
init_state("service_price_fixed", None)

init_state("total_price", None)


# ================================
# 页面内容：标题 + 功能介绍卡片
# ================================
st.markdown("<div class='main-header'>岚图超充站电价管理系统</div>", unsafe_allow_html=True)

st.markdown("""
<div class='sub-header'>
本系统提供从电价解析、数据矫正，到电费/服务费/总价自动计算的全流程管理功能。
请选择左侧页面开始操作。
</div>
""", unsafe_allow_html=True)


# ================================
# 功能介绍卡片
# ================================
st.markdown("<div class='card'>", unsafe_allow_html=True)

st.markdown("""
<div class='card-title'>
    <div class='icon-circle'>📌</div>
    系统功能导航
</div>

<ul class='feature-list'>
    <li>① <b>电费价格获取（PDF → 电价表）</b>：自动解析国网电价 PDF，生成标准化 Excel。</li>
    <li>② <b>电费价格矫正</b>：对解析结果进行增删改查，保存为修正版。</li>
    <li>③ <b>电费价格设置</b>：根据站点信息和电价表，自动生成分时电费。</li>
    <li>④ <b>服务费价格设置</b>：上传站点 & 服务费表，生成站点级的分时服务费。</li>
    <li>⑤ <b>服务费价格矫正</b>：编辑服务费时间段，自动校验是否覆盖 0:00–24:00。</li>
    <li>⑥ <b>充电价格计算</b>：自动合并电费 & 服务费，支持不同时间段交集计算。</li>
</ul>
""", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ================================
# 结束提示
# ================================
st.info("请从左侧选择页面开始操作，如需帮助可随时联系开发者。")
