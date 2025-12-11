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
# 全局 CSS（亮 / 暗模式自适应）
# ================================
st.markdown("""
<style>
/* =========================
   1. 主题变量（默认：浅色）
   ========================= */
:root {
    --bg-main: #f3f4f6;
    --bg-panel: #e5edff;
    --bg-card: #ffffff;
    --bg-chip: #eff6ff;

    --text-main: #0f172a;
    --text-sub: #4b5563;
    --text-weak: #6b7280;

    --brand-main: #1d4ed8;
    --brand-sub: #0ea5e9;

    --shadow-soft: 0 12px 30px rgba(15, 23, 42, 0.12);
    --shadow-chip: 0 6px 14px rgba(148, 163, 184, 0.4);
}

/* =========================
   2. 深色模式覆盖
   ========================= */
@media (prefers-color-scheme: dark) {
  :root {
      --bg-main: radial-gradient(circle at 10% 0%, #0b1120 0, #020617 45%, #000 100%);
      --bg-panel: radial-gradient(circle at 15% -10%, rgba(56,189,248,0.18) 0, rgba(15,23,42,0.95) 40%, #020617 90%);
      --bg-card: rgba(15,23,42,0.96);
      --bg-chip: rgba(15,23,42,0.9);

      --text-main: #e5e7eb;
      --text-sub: #cbd5f5;
      --text-weak: #9ca3af;

      --brand-main: #38bdf8;
      --brand-sub: #6366f1;

      --shadow-soft: 0 22px 55px rgba(15, 23, 42, 0.75);
      --shadow-chip: 0 10px 24px rgba(15, 23, 42, 0.9);
  }
}

/* 让 Streamlit 主容器用我们的背景 */
[data-testid="stAppViewContainer"] {
    background: var(--bg-main);
}

/* 顶部横幅 */
.main-header {
    font-size: 32px;
    font-weight: 700;
    color: #f9fafb;
    padding: 22px 26px;
    margin-bottom: 28px;
    border-radius: 18px;
    background: linear-gradient(90deg, var(--brand-main), var(--brand-sub));
    box-shadow: var(--shadow-soft);
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* 左侧小徽标 */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(15,23,42,0.6);
    color: #e5e7eb;
    font-size: 12px;
    letter-spacing: 0.03em;
}

/* 副标题 */
.sub-header {
    font-size: 15px;
    color: var(--text-sub);
    margin-top: 6px;
}

/* 卡片容器 */
.card {
    background: var(--bg-card);
    padding: 20px 22px;
    border-radius: 18px;
    box-shadow: var(--shadow-soft);
    border: 1px solid rgba(148,163,184,0.25);
    margin-bottom: 18px;
}

/* 卡片标题行 */
.card-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 8px;
    margin-bottom: 10px;
    border-bottom: 1px solid rgba(148,163,184,0.3);
}

/* 圆形图标背景 */
.icon-circle {
    width: 30px;
    height: 30px;
    border-radius: 999px;
    background: radial-gradient(circle at 30% 30%, #ffffff, #bfdbfe);
    color: #1d4ed8;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}

/* 功能列表 */
.feature-list {
    list-style: none;
    padding-left: 0;
    margin: 0;
}
.feature-list li {
    margin: 6px 0;
    font-size: 15px;
    color: var(--text-sub);
}
.feature-list b {
    color: var(--text-main);
}

/* 右侧状态小圆角标签（基础样式） */
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    background: var(--bg-chip);
    color: var(--text-sub);
    box-shadow: var(--shadow-chip);
    margin: 3px 0;
}

/* 小提示文本 */
.tip-text {
    font-size: 13px;
    color: var(--text-weak);
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

# ================================
# Session State 初始化
# ================================
def init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

# Page1 / Page2
init_state("price_raw", None)            # 电价解析结果
init_state("price_fixed", None)          # 电价修正版

# Page3
init_state("station_info", None)         # 站点基础信息（如果有用）
init_state("station_fee", None)          # 站点分时电费结果

# Page4 / Page5
init_state("service_price_raw", None)    # 服务费原始结果（Page4）
init_state("service_price_corrected", {})# 服务费矫正后的 dict（Page5）

# Page6
init_state("total_price_result", None)   # 充电总价表
init_state("total_price_detail", {})     # 总价拆分详情（可选）

# Page7
init_state("price_template_df", None)    # 模板数据集


# ================================
# 一些小工具：状态徽标
# ================================
def render_status(label: str, ready: bool) -> str:
    """
    根据是否已有数据，在首页右侧显示“已就绪 / 待导入”。
    """
    state_txt = "已就绪" if ready else "待导入"
    if ready:
        color = "#22c55e"
        bg = "rgba(34,197,94,0.12)"
    else:
        color = "#6b7280"
        bg = "var(--bg-chip)"
    return f"<div class='status-badge' style='color:{color};background:{bg};'>{label}：{state_txt}</div>"


# ================================
# 顶部横幅
# ================================
st.markdown("""
<div class='main-header'>
  <div>
    <div class='badge'>⚡ 岚图超充站 · Tariff Engine</div>
    <div style="margin-top:10px;">岚图超充站电价管理系统</div>
    <div class='sub-header'>
      从「国网 PDF 电价解析」到「站点电价 / 服务费 / 充电总价 / 价格模板」的一站式自动化管理工具。
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ================================
# 左右两列布局
# ================================
col_left, col_right = st.columns([2.2, 1.3])

# ---------- 左侧：功能导航 + 操作流程 ----------
with col_left:
    # 功能导航
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("""
    <div class='card-title'>
        <div class='icon-circle'>🧭</div>
        系统功能导航
    </div>
    <ul class='feature-list'>
        <li>① <b>电费价格获取（PDF → 电价表）</b>：自动解析国网电价 PDF，生成标准化 Excel。</li>
        <li>② <b>电费价格矫正</b>：对解析结果进行增删改查，保存为修正版。</li>
        <li>③ <b>电费价格设置</b>：结合站点信息与电价表，生成站点分时电费结构。</li>
        <li>④ <b>服务费价格设置</b>：上传站点 & 服务费表，自动映射生成站点级分时服务费。</li>
        <li>⑤ <b>服务费价格矫正</b>：编辑服务费时间段，自动校验是否覆盖 0:00–24:00。</li>
        <li>⑥ <b>充电价格计算</b>：叠加电费 & 服务费，支持任意时间段交集计费与导出。</li>
        <li>⑦ <b>价格模板数据集生成</b>：整合电费 / 服务费 / 总价与站点信息，输出一键可用的价格执行模板。</li>
    </ul>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # 推荐流程
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("""
    <div class='card-title'>
        <div class='icon-circle'>📋</div>
        推荐操作流程
    </div>
    <ul class='feature-list'>
        <li><b>Step 1 · 获取电价</b>：在「电费价格获取」页粘贴国网 PDF 链接，一键解析生成电价表。</li>
        <li><b>Step 2 · 校正电价</b>：在「电费价格矫正」中检查、增删、调价，将解析结果保存为修正版。</li>
        <li><b>Step 3 · 生成站点电价</b>：在「电费价格设置」中上传站点信息，自动匹配并形成分时电费。</li>
        <li><b>Step 4 · 生成 & 校正服务费</b>：在「服务费价格设置 / 矫正」中配置每个站点的分时服务费策略。</li>
        <li><b>Step 5 · 总价计算</b>：在「充电价格计算」中合并电费 + 服务费，得到站点级充电总价。</li>
        <li><b>Step 6 · 价格模板输出</b>：在「价格模板数据集生成」中整合所有结果，导出正式执行的价格模板。</li>
    </ul>
    <div class='tip-text'>
      提示：如有新的数据字段或电价规则，可在后续版本中继续扩展，目前版本主要服务岚图超充站内部管理使用。
    </div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- 右侧：当前数据状态 + 小贴士 ----------
with col_right:
    # 状态
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("""
    <div class='card-title'>
        <div class='icon-circle'>👁️</div>
        当前数据状态
    </div>
    """, unsafe_allow_html=True)

    html_status = ""
    html_status += render_status("电价解析结果（Page1）", st.session_state["price_raw"] is not None)
    html_status += "<br/>"
    html_status += render_status("电价修正版（Page2）", st.session_state["price_fixed"] is not None)
    html_status += "<br/>"
    html_status += render_status("站点电费结构（Page3）", st.session_state["station_fee"] is not None)
    html_status += "<br/>"

    # 服务费结果：只要原始或矫正里有一个就算“已就绪”
    ready_service = (
        st.session_state["service_price_raw"] is not None
        or bool(st.session_state["service_price_corrected"])
    )
    html_status += render_status("服务费结果（Page4/5）", ready_service)
    html_status += "<br/>"

    html_status += render_status("充电总价表（Page6）", st.session_state["total_price_result"] is not None)
    html_status += "<br/>"

    html_status += render_status("价格模板（Page7）", st.session_state["price_template_df"] is not None)

    st.markdown(html_status, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # 使用小贴士
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("""
    <div class='card-title'>
        <div class='icon-circle'>💡</div>
        使用小贴士
    </div>
    <ul class='feature-list'>
        <li>推荐按照左侧菜单的 ① → ⑦ 顺序依次完成配置。</li>
        <li>部分临时状态只保存在 <code>session_state</code> 中，刷新页面可能会丢失数据。</li>
        <li>如需彻底重置，可在浏览器中刷新首页重新开始本轮配置。</li>
    </ul>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
