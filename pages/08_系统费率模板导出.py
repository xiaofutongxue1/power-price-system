# -*- coding: utf-8 -*-
# pages/08_费率版本导出.py

import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime
from openpyxl.styles import Font, Alignment

# ==============================
# 页面标题
# ==============================
st.markdown("""
<div class='main-header'>
🧾 费率版本导出（系统审核用）
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class='sub-header'>
将 Page7 的模板结果（或你上传的模板Excel）转为系统审核需要的“费率版本-日期”格式：
<strong>站点名称、站点编号、充电费、服务费</strong>（仅保留必要字段，且费率文本按系统格式清洗）。
</div>
""", unsafe_allow_html=True)

# ==============================
# 文本格式化工具
# ==============================

_TIER_SET = {"尖", "峰", "平", "谷", "深"}

def _parse_line(line: str):
    """
    解析一行：
      谷 0:00 - 7:00 0.5434元/度
      谷0:00-7:00 0.5434元/度
      0:00 - 24:00 0.5元/度
    返回: (tier, start, end, price) or None
    """
    if line is None:
        return None
    s = str(line).strip()
    if not s:
        return None

    # 允许：tier可选 + 各种连接符 + 任意内容 + 数字价格
    m = re.search(
        r"^(?:(尖|峰|平|谷|深)\s*)?"
        r"(\d{1,2}:\d{2})\s*[-–~至]\s*(\d{1,2}:\d{2})"
        r".*?([0-9]+(?:\.[0-9]+)?)",
        s
    )
    if not m:
        return None

    tier, start, end, price = m.groups()
    tier = (tier or "").strip()

    try:
        price = float(price)
    except Exception:
        return None

    return tier, start.strip(), end.strip(), price


def _time_to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _min_to_time(m: int) -> str:
    h = m // 60
    mm = m % 60
    return f"{h}:{mm:02d}"


def _end_minus_one_min_smart(end_t: str) -> str:
    """
    结束时间统一改成 end-1分钟，但要避免“已经是23:59还再减一”的情况：
    - 若 end 分钟为 00 或 30 或 end=24:00：认为是“边界”，执行 -1分钟
    - 若 end 分钟为 59 或 29：认为已是“闭区间结尾”，不再减
    - 其它情况：默认 -1分钟
    """
    end_t = end_t.strip()

    # 24:00 特殊处理
    if end_t == "24:00":
        return "23:59"

    try:
        h, mm = end_t.split(":")
        mm = int(mm)
    except Exception:
        # 异常就尽量不动
        return end_t

    # 已经是 59/29，认为已处理过
    if mm in (59, 29):
        return end_t

    # 典型边界：整点/半点
    end_min = _time_to_min(end_t)
    end_min_adj = max(0, end_min - 1)
    return _min_to_time(end_min_adj)


def normalize_tariff_text(raw_text: str, decimals: int = 4) -> str:
    """
    输出系统格式：
    谷 0:00-6:59,0.5434
    平 7:00-9:59,0.8215

    decimals：价格保留小数位数（电价=4，服务费=2）
    """
    if raw_text is None or (isinstance(raw_text, float) and pd.isna(raw_text)):
        return ""

    lines = [l.strip() for l in str(raw_text).splitlines() if str(l).strip()]
    out_lines = []

    for line in lines:
        parsed = _parse_line(line)
        if not parsed:
            continue

        tier, start, end, price = parsed
        end2 = _end_minus_one_min_smart(end)

        if tier and tier not in _TIER_SET:
            tier = ""

        # 0:00-23:59 强制补 “平”
        if start == "0:00" and end2 == "23:59":
            tier = "平"

        # 按传入的小数位格式化
        price_str = f"{price:.{decimals}f}"

        prefix = f"{tier} " if tier else ""
        out_lines.append(f"{prefix}{start}-{end2},{price_str}")

    return "\n".join(out_lines)


# ==============================
# 数据来源：沿用 Page7 或上传
# ==============================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>📥</div>
  ① 数据来源
</div>
""", unsafe_allow_html=True)

df_from_state = st.session_state.get("price_template_df", None)
has_state = isinstance(df_from_state, pd.DataFrame) and not df_from_state.empty

if has_state:
    st.success("检测到 Page7 的模板结果（price_template_df），可直接沿用。")
    src = st.radio("选择数据来源：", ["沿用 Page7 结果", "上传 Page7 导出的模板Excel"], index=0)
else:
    st.info("未检测到 Page7 结果，请上传 Page7 导出的模板Excel。")
    src = st.radio("选择数据来源：", ["上传 Page7 导出的模板Excel"], index=0)

upload_file = None
if "上传" in src:
    upload_file = st.file_uploader("上传模板Excel（来自 Page7 导出）", type=["xlsx"])

st.markdown("</div>", unsafe_allow_html=True)


# ==============================
# 版本日期 & 导出设置
# ==============================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>🗓️</div>
  ② 版本信息与导出设置
</div>
""", unsafe_allow_html=True)

default_date = datetime.now().strftime("%Y%m%d")
version_date = st.text_input("费率版本日期（用于文件名）：", value=default_date)

apply_excel_style = st.checkbox("导出Excel时应用统一样式（微软雅黑 Light、居中、自动换行）", value=True)

st.markdown("</div>", unsafe_allow_html=True)


# ==============================
# 生成费率版本
# ==============================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>🧮</div>
  ③ 生成系统审核用费率版本
</div>
""", unsafe_allow_html=True)

if st.button("▶ 生成费率版本并导出", use_container_width=True):

    # ---- 读取数据 ----
    if "沿用" in src:
        df_src = df_from_state.copy()
    else:
        if upload_file is None:
            st.error("❌ 请先上传 Page7 导出的模板Excel。")
            st.stop()
        df_src = pd.read_excel(upload_file)

    # ---- 必要列检查 ----
    need_cols = {"站点名称", "站点编号", "本次生效价格-电费", "本次生效价格-服务费"}
    miss = need_cols - set(df_src.columns)
    if miss:
        st.error(f"❌ 模板Excel缺少必要列：{miss}")
        st.stop()

    # ---- 仅保留系统需要字段 + 重命名 ----
    df_out = df_src[["站点名称", "站点编号", "本次生效价格-电费", "本次生效价格-服务费"]].copy()
    df_out = df_out.rename(columns={
        "本次生效价格-电费": "充电费",
        "本次生效价格-服务费": "服务费",
    })

    # 站点编号转字符串，避免Excel截断
    df_out["站点编号"] = df_out["站点编号"].apply(lambda x: "" if pd.isna(x) else str(x))

    # ---- 文本格式化（充电费/服务费都要转）----
    df_out["充电费"] = df_out["充电费"].apply(lambda x: normalize_tariff_text(x, decimals=2))
    df_out["服务费"] = df_out["服务费"].apply(lambda x: normalize_tariff_text(x, decimals=2))

    st.success(f"✅ 费率版本生成完成，共 {len(df_out)} 行。")
    st.dataframe(df_out, use_container_width=True)

    # ---- 导出 Excel ----
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="费率版本")

        if apply_excel_style:
            wb = writer.book
            ws = wb["费率版本"]

            header_font = Font(name="微软雅黑 Light", size=10, bold=True)
            body_font = Font(name="微软雅黑 Light", size=10)
            align_center_wrap = Alignment(horizontal="center", vertical="center", wrap_text=True)

            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = align_center_wrap
                    cell.font = header_font if cell.row == 1 else body_font

            # 列宽设置：名称/编号窄一点，费率宽一点
            ws.column_dimensions["A"].width = 40   # 站点名称
            ws.column_dimensions["B"].width = 26   # 站点编号
            ws.column_dimensions["C"].width = 20   # 充电费
            ws.column_dimensions["D"].width = 20   # 服务费

    buf.seek(0)

    filename = f"费率版本-{version_date}.xlsx"
    st.download_button(
        "📥 下载费率版本 Excel（系统审核用）",
        data=buf.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.markdown("</div>", unsafe_allow_html=True)

