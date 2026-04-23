import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import minimize
import re

# --- 页面配置 ---
st.set_page_config(page_title="乾坤大乐透·能量守恒推演", layout="wide")

# --- CSS 样式 ---
st.markdown("""
    <style>
    .main { background-color: #0d1117; color: #d1d5db; }
    .status-card { padding: 10px; border-radius: 8px; background: #161b22; border: 1px solid #30363d; text-align: center; margin-bottom: 5px; }
    .instant-box { border: 1px dashed #e5c07b; padding: 15px; border-radius: 10px; background: rgba(229, 192, 123, 0.05); margin: 10px 0; }
    .advice-box { padding: 12px; border-radius: 8px; margin-top: 10px; font-weight: bold; border-left: 5px solid #00ffcc; background: rgba(0, 255, 204, 0.05); }
    .pool-card { border: 1px solid #3e444d; padding: 12px; border-radius: 8px; margin-bottom: 15px; background: #0d1117; border-left: 5px solid #e5c07b; }
    .weight-font { font-family: monospace; color: #00ffcc; }
    </style>
    """, unsafe_allow_html=True)

# --- 逻辑函数 ---
def get_front_status(num):
    if 1 <= num <= 7: return "死", "#6e7681"
    elif 8 <= num <= 14: return "囚", "#f85149"
    elif 15 <= num <= 21: return "休", "#58a6ff"
    elif 22 <= num <= 28: return "相", "#3fb950"
    elif 29 <= num <= 35: return "旺", "#d29922"
    return "无", "#fff"

def get_back_stage(num):
    stages = {
        1: ("胎", "#a371f7"), 2: ("生", "#3fb950"), 3: ("养", "#58a6ff"),
        4: ("沐浴", "#ff7b72"), 5: ("冠戴", "#d29922"), 6: ("临官", "#f0883e"),
        7: ("帝旺", "#f85149"), 8: ("衰", "#6e7681"), 9: ("病", "#484f58"),
        10: ("死", "#21262d"), 11: ("墓", "#161b22"), 12: ("绝", "#0d1117")
    }
    return stages.get(num, ("无", "#fff"))

def get_dynamic_status(nums, method="5x7"):
    status_map = {0: "死", 1: "囚", 2: "休", 3: "相", 4: "旺", 5: "旺"}
    color_map = {"死": "#6e7681", "囚": "#f85149", "休": "#58a6ff", "相": "#3fb950", "旺": "#d29922"}
    zones = [range(1, 8), range(8, 15), range(15, 22), range(22, 29), range(29, 36)] if method == "5x7" else \
            [range(1, 6), range(6, 11), range(11, 16), range(16, 21), range(21, 26), range(26, 31), range(31, 36)]
    return [{"status": status_map.get(sum(1 for n in nums if n in z), "旺"), "color": color_map[status_map.get(sum(1 for n in nums if n in z), "旺")]} for z in zones]

# --- 守恒提示逻辑 ---
def get_balance_advice(score):
    if score > 15:
        return "⚠️ 当前能量【过旺】：建议在剩余位置选择“死”或“囚”态号码进行中和。"
    elif score < -10:
        return "⚠️ 当前能量【过衰】：建议在剩余位置选择“旺”或“相”态号码提升气场。"
    elif -5 <= score <= 5:
        return "✅ 当前能量【接近守恒】：此组合气场平衡，建议保持。"
    else:
        return "💡 能量微偏：可适当通过微调值符/值使状态来微调平衡度。"

# --- 初始化数据与特定权重 ---
if 'weights' not in st.session_state:
    st.session_state.weights = {
        "旺": 7.0, "相": 3.0, "休": 0.0, "囚": -2.0, "死": -5.0,  # 用户指定权重
        "胎": 1.0, "生": 8.0, "养": 4.0, "沐浴": 2.0, "冠戴": 6.0, "临官": 9.0,
        "帝旺": 10.0, "衰": -1.0, "病": -3.0, "死_后": -6.0, "墓": -7.0, "绝": -10.0
    }
if 'compare_pool' not in st.session_state: st.session_state.compare_pool = []
if 'full_db' not in st.session_state: st.session_state.full_db = pd.DataFrame(columns=['期数','前1','前2','前3','前4','前5','后1','后2'])

# --- UI 界面 ---
st.title("⚖️ 乾坤大乐透·能量守恒推演中心")
tab_main, tab_db = st.tabs(["⚖️ 即时推演", "📊 历史仓储"])

with tab_main:
    # 模式选择
    m1, m2 = st.columns(2)
    calc_method = m1.radio("前区逻辑：", ["固定区间法", "动态频率(5区7号)", "动态频率(7区5号)"], horizontal=True)
    scope = m2.radio("转换范围：", ["全案转换", "单前区转换", "单后区转换"], horizontal=True)

    st.divider()

    # 输入控制
    in1, in2 = st.columns([3, 1])
    cur_b = []
    if scope != "单后区转换":
        with in1:
            st.write("**前区号码**")
            cols = st.columns(5)
            cur_b = [cols[i].selectbox(f"位{i+1}", range(1, 36), index=i, key=f"sb{i}") for i in range(5)]
    
    cur_zf, cur_zs = 1, 2
    if scope != "单前区转换":
        with in2:
            st.write("**后区十二长生**")
            cols = st.columns(2)
            cur_zf = cols[0].selectbox("值符", range(1, 13), index=0, key="szf")
            cur_zs = cols[1].selectbox("值使", range(1, 13), index=1, key="szs")

    # 即时转换预览与守恒提示
    st.markdown('<div class="instant-box">', unsafe_allow_html=True)
    st.markdown("#### ✨ 实时转换与能量天平")
    
    p_f_tags, p_b_tags = [], []
    c1, c2 = st.columns([3, 1])
    
    with c1:
        if scope != "单后区转换":
            if "动态" in calc_method:
                res = get_dynamic_status(cur_b, "5x7" if "5区" in calc_method else "7x5")
                d_cols = st.columns(len(res))
                for i, r in enumerate(res):
                    p_f_tags.append(r['status'])
                    d_cols[i].markdown(f"<div class='status-card' style='color:{r['color']};'><b>{r['status']}</b></div>", unsafe_allow_html=True)
            else:
                d_cols = st.columns(5)
                for i, n in enumerate(cur_b):
                    txt, clr = get_front_status(n); p_f_tags.append(txt)
                    d_cols[i].markdown(f"<div class='status-card' style='color:{clr};'><b>{txt}</b></div>", unsafe_allow_html=True)
    
    with c2:
        if scope != "单前区转换":
            h_cols = st.columns(2)
            zft, zfc = get_back_stage(cur_zf); zst, zsc = get_back_stage(cur_zs)
            p_b_tags += [zft if zft != "死" else "死_后", zst if zst != "死" else "死_后"]
            h_cols[0].markdown(f"<div class='status-card' style='border:1px solid {zfc}; color:{zfc};'><b>{zft}</b></div>", unsafe_allow_html=True)
            h_cols[1].markdown(f"<div class='status-card' style='border:1px solid {zsc}; color:{zsc};'><b>{zst}</b></div>", unsafe_allow_html=True)

    # 计算总分与建议
    total_score = sum([st.session_state.weights.get(t, 0) for t in p_f_tags + p_b_tags])
    st.markdown(f"**当前综合得分：** <span style='font-size:24px; color:#e5c07b;'>{total_score:.1f}</span>", unsafe_allow_html=True)
    
    # 核心：能量守恒提示建议
    advice = get_balance_advice(total_score)
    st.markdown(f"<div class='advice-box'>{advice}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button(f"🚀 注入对比池 ({len(st.session_state.compare_pool)}/10)", use_container_width=True):
        if len(st.session_state.compare_pool) < 10:
            st.session_state.compare_pool.append({
                "label": f"组 {len(st.session_state.compare_pool)+1}",
                "score": total_score, "tags": p_f_tags + p_b_tags, "desc": f"{calc_method}"
            })
            st.rerun()

    # 结果对比
    if st.session_state.compare_pool:
        st.divider()
        chart_df = pd.DataFrame([{"组号": r['label'], "能量值": r['score']} for r in st.session_state.compare_pool])
        st.line_chart(chart_df.set_index("组号"), height=250)

# 侧边栏权重监控
with st.sidebar:
    st.header("⚖️ 权重配置")
    st.subheader("前区五态 (指定)")
    for s in ["旺","相","休","囚","死"]:
        st.markdown(f"{s}: <span class='weight-font'>{st.session_state.weights[s]:.1f}</span>", unsafe_allow_html=True)
    st.subheader("后区长生 (驱动)")
    for s in ["胎","生","养","沐浴","冠戴","临官","帝旺","衰","病","死_后","墓","绝"]:
        dn = s.replace("_后", "死")
        st.markdown(f"{dn}: <span class='weight-font'>{st.session_state.weights[s]:.1f}</span>", unsafe_allow_html=True)
