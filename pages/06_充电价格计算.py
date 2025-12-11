# -*- coding: utf-8 -*-
# pages/06_充电价格计算.py

import streamlit as st
import pandas as pd
from io import BytesIO
import re

# ============================================
# 工具函数：时间 & 文本解析
# ============================================

def time_to_min(t: str) -> int:
    """'7:00' -> 420"""
    t = t.strip()
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def min_to_time(m: int) -> str:
    """420 -> '7:00'"""
    h = m // 60
    mm = m % 60
    return f"{h}:{mm:02d}"


def parse_price_text(text):
    """
    解析类似：
      谷 0:00 - 7:00 0.50元/度
      平 7:00 - 10:00 0.75元/度
      0:00 - 24:00 0.5元/度   （没有“谷/峰/平/尖”也可以）

    返回：
      [{"start": "0:00", "end": "7:00", "price": 0.5}, ...]
    """
    rows = []
    if text is None:
        return rows

    for line in str(text).splitlines():
        line = line.strip()
        if not line:
            continue

        # 提取：开始时间 结束时间 价格数字
        m = re.search(
            r"(\d{1,2}:\d{2})\s*[-–~至]\s*(\d{1,2}:\d{2}).*?([0-9]+(?:\.[0-9]+)?)",
            line
        )
        if not m:
            # 有些行可能是备注，直接跳过
            continue

        start, end, price_str = m.groups()
        try:
            price = float(price_str)
        except ValueError:
            continue

        rows.append({
            "start": start.strip(),
            "end": end.strip(),
            "price": price
        })

    return rows


def merge_two_schedules(elec_rows, serv_rows):
    """
    输入：
        elec_rows: [{'start','end','price'}]  电费
        serv_rows: [{'start','end','price'}]  服务费

    逻辑：
        - 把两边所有 start/end 转成分钟，取并集 + 排序
        - 逐段 [t_i, t_{i+1}) 找到对应的电费、服务费，做相加
    返回：
        [{'start','end','electric_price','service_price','total_price'}]
    """
    if not elec_rows or not serv_rows:
        return []

    # 转分钟 & 收集边界
    elec = []
    serv = []
    boundaries = set()

    for r in elec_rows:
        s = time_to_min(r["start"])
        e = time_to_min(r["end"])
        elec.append({"s": s, "e": e, "price": r["price"]})
        boundaries.add(s)
        boundaries.add(e)

    for r in serv_rows:
        s = time_to_min(r["start"])
        e = time_to_min(r["end"])
        serv.append({"s": s, "e": e, "price": r["price"]})
        boundaries.add(s)
        boundaries.add(e)

    points = sorted(boundaries)

    def find_price(segs, t_min):
        for seg in segs:
            if seg["s"] <= t_min < seg["e"]:
                return seg["price"]
        return None  # 理论上不应该出现

    merged = []
    for i in range(len(points) - 1):
        s = points[i]
        e = points[i + 1]
        p_e = find_price(elec, s)
        p_s = find_price(serv, s)

        # 如果其中一个没有覆盖，就跳过（数据不完整）
        if p_e is None or p_s is None:
            continue

        merged.append({
            "start": min_to_time(s),
            "end": min_to_time(e),
            "electric_price": p_e,
            "service_price": p_s,
            "total_price": round(p_e + p_s, 4)
        })

    return merged


# ============================================
# 页面标题
# ============================================
st.markdown("""
<div class='main-header'>💰 超充站总价格设置</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class='sub-title'>
将 Page3 的电费结果 + Page5 的服务费结果，自动按时段合并为【总价】。
</div>
""", unsafe_allow_html=True)

# ============================================
# 1. 数据来源设置
# ============================================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>📥</div> 导入电费 / 服务费数据
</div>
""", unsafe_allow_html=True)

col_a, col_b = st.columns(2)

# ---------- 电费数据 ----------
with col_a:
    st.markdown("#### ⚡ 电费数据（来自 Page3 或 Excel）")

    has_page3 = "station_fee" in st.session_state

    if has_page3:
        st.success("检测到 Page3 生成的电费结果，可直接沿用。")
        src_elec = st.radio(
            "电费数据来源",
            ["沿用 Page3 结果", "上传电费结果 Excel"],
            index=0,
            key="src_elec_radio"
        )
    else:
        st.info("Page3 尚未在 session 中保存结果，请上传电费结果 Excel。")
        src_elec = st.radio(
            "电费数据来源",
            ["上传电费结果 Excel"],
            index=0,
            key="src_elec_radio"
        )

    elec_file = None
    if "上传" in src_elec:
        elec_file = st.file_uploader(
            "电费结果文件（需包含：站点名称 + 电费 文本列）",
            type=["xlsx"],
            key="elec_upload"
        )

# ---------- 服务费数据 ----------
with col_b:
    st.markdown("#### 💵 服务费数据（来自 Page5 或 Excel）")

    # 尝试从 Page5 重建一个「最终服务费表」
    raw_from_state = st.session_state.get("service_price_raw", None)

    # 只有在是非空 DataFrame 时才认为 Page5 有数据
    has_page5_raw = isinstance(raw_from_state, pd.DataFrame) and not raw_from_state.empty

    if has_page5_raw:
        st.success("检测到 Page5 的服务费数据，可直接沿用（自动合并矫正结果）。")
        src_serv = st.radio(
            "服务费数据来源",
            ["沿用 Page5 结果", "上传服务费结果 Excel"],
            index=0,
            key="src_serv_radio"
        )
    else:
        st.info("Page5 尚未在 session 中保存结果，请上传服务费结果 Excel。")
        src_serv = st.radio(
            "服务费数据来源",
            ["上传服务费结果 Excel"],
            index=0,
            key="src_serv_radio"
        )

    serv_file = None
    if "上传" in src_serv:
        serv_file = st.file_uploader(
            "服务费结果文件（需包含：站点名称 + 服务费 文本列）",
            type=["xlsx"],
            key="serv_upload"
        )


st.markdown("</div>", unsafe_allow_html=True)

# ============================================
# 2. 载入 DataFrame
# ============================================

df_elec = None
df_serv = None

# ---- 电费 DF ----
if "沿用" in src_elec:
    # 直接使用 Page3 保存的 station_fee
    if "station_fee" in st.session_state:
        df_elec = st.session_state["station_fee"].copy()
else:
    if elec_file is not None:
        df_elec = pd.read_excel(elec_file)


# ---- 服务费 DF ----
if "沿用" in src_serv and has_page5_raw:
    # 按 Page5 的逻辑，把 raw + corrected 合成为最新服务费表
    raw = st.session_state["service_price_raw"].copy()
    station_list = raw["站点名称"].unique().tolist()
    corrected = st.session_state.get("service_price_corrected", {})

    rows = []
    for name in station_list:
        if name in corrected:
            segs = corrected[name]
            txt = "\n".join(
                [f"{s['start']} - {s['end']} {s['price']}元/度" for s in segs]
            )
        else:
            txt = str(raw[raw["站点名称"] == name]["服务费"].values[0])
        rows.append({"站点名称": name, "服务费": txt})

    df_serv = pd.DataFrame(rows)
else:
    if serv_file is not None:
        df_serv = pd.read_excel(serv_file)

# ============================================
# 3. 基本检查
# ============================================

if df_elec is None or df_serv is None:
    st.warning("请先完成电费 / 服务费数据的导入，再进行总价计算。")
    st.stop()

if ("站点名称" not in df_elec.columns) or ("电费" not in df_elec.columns):
    st.error("电费数据中必须包含列：『站点名称』和『电费』。")
    st.stop()

if ("站点名称" not in df_serv.columns) or ("服务费" not in df_serv.columns):
    st.error("服务费数据中必须包含列：『站点名称』和『服务费』。")
    st.stop()

# 只保留两边都有的站点
set_elec = set(df_elec["站点名称"].unique())
set_serv = set(df_serv["站点名称"].unique())
common_stations = sorted(list(set_elec & set_serv))

if not common_stations:
    st.error("两份数据中【站点名称】没有交集，请检查。")
    st.stop()

if set_elec - set_serv:
    st.info(f"以下站点只有电费没有服务费，将在总价计算中忽略：{', '.join(list(set_elec - set_serv)[:10])} ...")

if set_serv - set_elec:
    st.info(f"以下站点只有服务费没有电费，将在总价计算中忽略：{', '.join(list(set_serv - set_elec)[:10])} ...")

# ============================================
# 4. 计算总价
# ============================================

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("""
<div class='card-title'>
  <div class='icon-circle'>🧮</div> 计算总价
</div>
""", unsafe_allow_html=True)

if st.button("▶ 开始计算总价", use_container_width=True):
    total_rows = []
    detail_dict = {}

    for name in common_stations:
        elec_text = df_elec[df_elec["站点名称"] == name]["电费"].values[0]
        serv_text = df_serv[df_serv["站点名称"] == name]["服务费"].values[0]

        elec_rows = parse_price_text(elec_text)
        serv_rows = parse_price_text(serv_text)

        merged = merge_two_schedules(elec_rows, serv_rows)

        # 保存详情
        detail_dict[name] = merged

        # 汇总文本
        if merged:
            total_txt = "\n".join(
                [f"{m['start']} - {m['end']} {m['total_price']:.4f}元/度" for m in merged]
            )
        else:
            total_txt = "未能成功合并电费与服务费，请检查源数据。"

        total_rows.append({
            "站点名称": name,
            "总价": total_txt
        })

    df_total = pd.DataFrame(total_rows)

    # 存到 session，方便后面页面或重新渲染使用
    st.session_state["total_price_result"] = df_total
    st.session_state["total_price_detail"] = detail_dict

    st.success("✅ 总价计算完成！")

st.markdown("</div>", unsafe_allow_html=True)

# ============================================
# 5. 结果展示 & 下载
# ============================================

if "total_price_result" in st.session_state:
    df_total = st.session_state["total_price_result"]
    detail_dict = st.session_state.get("total_price_detail", {})

    tab_sum, tab_detail = st.tabs(["📊 汇总结果", "🔍 单站点详情"])

    # -------- 汇总表 ----------
    with tab_sum:
        st.markdown("### 各站点总价（文本形式）")
        st.dataframe(df_total, use_container_width=True)

        # 下载按钮
        buf = BytesIO()
        df_total.to_excel(buf, index=False)
        buf.seek(0)
        st.download_button(
            "📥 下载总价结果 Excel",
            data=buf.getvalue(),
            file_name="总价计算结果.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

    # -------- 单站点详情 ----------
    with tab_detail:
        st.markdown("### 单站点时段拆分详情")
        sel = st.selectbox("选择站点：", common_stations)

        records = detail_dict.get(sel, [])
        if not records:
            st.warning("该站点没有可展示的时段数据。")
        else:
            df_detail = pd.DataFrame(records)
            df_detail["时段"] = df_detail["start"] + " - " + df_detail["end"]
            df_detail = df_detail[["时段", "electric_price", "service_price", "total_price"]]
            df_detail.columns = ["时段", "电费(元/度)", "服务费(元/度)", "总价(元/度)"]
            st.dataframe(df_detail, use_container_width=True)

else:
    st.info("尚未计算总价，请点击上方『开始计算总价』按钮。")
