"""τ Lab — Streamlit 版交互式仿真（完整复用 tau_sim，含 SimPy DES）。

用法: streamlit run app.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from tau_sim import layer2_circuit as L2
from tau_sim import params as P
from tau_sim import style
from tau_sim import thermal as TH
from tau_sim.cascade import (SystemConfig, alpha_decomposition, amdahl_scan,
                             bottleneck_migration, decade_trajectories,
                             iteration_tau)
from tau_sim.layer2_circuit import fold
from tau_sim.layer3_chip import evaluate
from tau_sim.layer4_system import (moe_decode_step, simpy_alltoall,
                                   train_iteration)

st.set_page_config(page_title="τ Lab", page_icon="🎛️", layout="wide")
style.apply_style()
C = style.SERIES

st.title("τ Lab — τ Scaling 交互式仿真")
st.caption("模型与图表复用仓库 tau_sim/（论文验证所用的文献校准参数即默认值）。"
           "浏览器免安装版见 tau_lab.html。")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["① 折叠 + 热约束", "② 封装 N²-vs-N", "③ 集群通信（含 DES）",
     "④ 级联实验 A-D", "⑤ 参数与出处", "⑥ 敏感性扫描"])

# ================= Tab 1 折叠 + 热约束 =================
with tab1:
    c1, c2 = st.columns([1, 3])
    with c1:
        tiers = st.slider("折叠层数", 2, 4, 2)
        pitch = st.slider("混合键合 pitch (μm)", 0.5, 6.0, 1.5, 0.1)
        rent = st.slider("Rent 指数 p", 0.50, 0.75, P.RENT_P, 0.01)
        eff = st.slider("折叠布局效率", 0.60, 1.00, P.FOLD_EFFICIENCY, 0.05)
        fstyle = st.selectbox("折叠形态", ["logic-on-memory", "logic-on-logic"],
                              format_func=lambda s: "逻辑+存储 (Kirin 形态)"
                              if s == "logic-on-memory" else "逻辑+逻辑 (全功率)")
        cool = st.selectbox("散热场景", ["mobile", "ai"],
                            format_func=lambda s: "移动·无源" if s == "mobile"
                            else "AI·液冷")
    with c2:
        old_p, old_e = P.RENT_P, P.FOLD_EFFICIENCY
        P.RENT_P, P.FOLD_EFFICIENCY = rent, eff
        try:
            r = fold("7nm", tiers, pitch)
            th = TH.sustained(tiers, fstyle, cool)
            m = st.columns(5)
            m[0].metric("线长降幅", f"−{r.wl_reduction*100:.1f}%")
            m[1].metric("频率增益 (burst)", f"{r.freq_gain*100:+.1f}%")
            m[2].metric("密度 MTr/mm²", f"{r.density_mtr_mm2:.0f}")
            m[3].metric("可持续频率", f"{th.f_sustained:.2f}×")
            m[4].metric("判据 τ_B > τ_P",
                        "成立" if r.tau_benefit_ps > r.tau_penalty_ps else "反转",
                        f"gear {r.gear_ratio:.1f}")

            pitches = np.linspace(0.5, 6.0, 40)
            rs = [fold("7nm", tiers, p_) for p_ in pitches]
            fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 3.8))
            ax.plot(pitches, [x.tau_benefit_ps for x in rs], color=C[1],
                    label="τ_Benefit")
            ax.plot(pitches, [x.tau_penalty_ps for x in rs], color=C[5],
                    label="τ_Penalty")
            ax.axvline(pitch, color=style.MUTED, ls=":", lw=1)
            ax.set_xlabel("混合键合 pitch (μm)"); ax.set_ylabel("ps")
            ax.set_title("折叠判据"); ax.legend()

            ks = [1, 2, 3, 4]
            burst = [1.0] + [1 + fold("7nm", k, pitch).freq_gain for k in ks[1:]]
            sust = [TH.sustained(k, fstyle, cool).f_sustained for k in ks]
            ax2.plot(ks, burst, "--o", color=style.MUTED, label="电路极限 burst")
            ax2.plot(ks, sust, "-o", color=C[0], label="可持续 (热约束)")
            ax2.axhline(1.0, color=style.BASELINE, lw=0.8)
            ax2.set_xticks(ks); ax2.set_xlabel("折叠层数")
            ax2.set_ylabel("相对频率"); ax2.set_title("burst vs 可持续")
            ax2.legend()
            st.pyplot(fig); plt.close(fig)
        finally:
            P.RENT_P, P.FOLD_EFFICIENCY = old_p, old_e

# ================= Tab 2 封装 =================
with tab2:
    c1, c2 = st.columns([1, 3])
    with c1:
        inten = st.select_slider("负载运算强度 (FLOP/B)",
                                 [1, 2, 5, 10, 30, 100, 300, 1000], 2)
        surf = st.slider("3D 表面带宽密度 (TB/s/mm²)", 0.01, 0.10,
                         P.SURFACE_BW_TBS_MM2, 0.005)
        hbm = st.slider("HBM 每栈带宽 (TB/s)", 0.8, 2.4, P.HBM_STACK_BW_TBS, 0.1)
    with c2:
        oldS, oldH = P.SURFACE_BW_TBS_MM2, P.HBM_STACK_BW_TBS
        P.SURFACE_BW_TBS_MM2, P.HBM_STACK_BW_TBS = surf, hbm
        try:
            sides = np.linspace(8, 64, 50)
            pts = [evaluate(s) for s in sides]
            peak = np.array([p.peak_tflops for p in pts])
            ach_e = np.minimum(peak, inten * np.array([p.bw_edge_tbs for p in pts]))
            ach_s = np.minimum(peak, inten * np.array([p.bw_surf_tbs for p in pts]))
            fig, ax = plt.subplots(figsize=(9, 3.8))
            ax.plot(sides, peak, "--", color=style.MUTED, label="峰值 ∝N²")
            ax.plot(sides, ach_e, color=C[5], label="2.5D 边缘供带宽")
            ax.plot(sides, ach_s, color=C[1], label="3D Folding 表面")
            ax.set_xscale("log"); ax.set_yscale("log")
            ax.set_xticks([8, 16, 32, 64], ["8", "16", "32", "64"])
            ax.set_xlabel("边长 N (mm)"); ax.set_ylabel("可达算力 (TFLOPS)")
            ax.set_title(f"可达算力（强度 {inten} FLOP/B）"); ax.legend()
            st.pyplot(fig); plt.close(fig)
        finally:
            P.SURFACE_BW_TBS_MM2, P.HBM_STACK_BW_TBS = oldS, oldH

# ================= Tab 3 集群通信 =================
with tab3:
    c1, c2 = st.columns([1, 3])
    with c1:
        wl = st.radio("负载", ["训练 AllReduce (大消息)", "MoE all-to-all (小消息)"])
        run_des = st.button("运行 SimPy DES 验证点（约 10s）")
    with c2:
        if wl.startswith("训练"):
            ns = [2 ** e for e in range(3, 15)]
            fig, ax = plt.subplots(figsize=(9, 3.8))
            for fab, lab, col in [("legacy_tcp", "TCP/IP 栈", C[5]),
                                  ("legacy_rdma", "RDMA/IB", C[2]),
                                  ("ub_hione", "UB+HiONE", C[1])]:
                ax.plot(ns, [train_iteration(n, fab).scaling_eff * 100
                             for n in ns], "-o", ms=4, color=col, label=lab)
            ax.set_xscale("log", base=2); ax.set_xlabel("GPU/NPU 数")
            ax.set_ylabel("扩展效率 (%)"); ax.legend()
            st.pyplot(fig); plt.close(fig)
        else:
            eps = [2 ** e for e in range(3, 9)]
            fig, ax = plt.subplots(figsize=(9, 3.8))
            for fab, lab, col in [("legacy_tcp", "TCP/IP 栈", C[5]),
                                  ("legacy_rdma", "RDMA/IB", C[2]),
                                  ("ub_protocol", "UB 协议 (同 400G 线)", C[0])]:
                ax.plot(eps, [moe_decode_step(n, fab, n).t_iter * 1e3
                              for n in eps], "-o", ms=4, color=col, label=lab)
                if run_des:
                    des = []
                    for n in [8, 32, 128]:
                        msg = P.MOE_TOKENS_PER_GPU_DECODE * P.MOE_HIDDEN * 2 / n
                        t = simpy_alltoall(n, msg, P.FABRICS[fab])
                        des.append((P.MOE_LAYERS * 2 * t + P.MOE_LAYERS * 8e-6) * 1e3)
                    ax.plot([8, 32, 128], des, "s", ms=8, mfc="none",
                            mec=col, mew=1.6)
            if run_des:
                ax.plot([], [], "s", ms=8, mfc="none", mec=style.INK2,
                        mew=1.6, label="SimPy DES 验证点")
            ax.set_xscale("log", base=2); ax.set_yscale("log")
            ax.set_xlabel("专家并行规模"); ax.set_ylabel("每步时间 (ms)")
            ax.legend()
            st.pyplot(fig); plt.close(fig)

# ================= Tab 4 级联 =================
with tab4:
    c1, c2 = st.columns([1, 3])
    with c1:
        ub = st.checkbox("UB 内存语义协议")
        hione = st.checkbox("Hi-ONE 光互连带宽")
        d3f = st.checkbox("3D Folding 供内存 (×2.5)")
        lf = st.checkbox("LogicFolding 提算力 (×1.6)")
        ngpu = st.select_slider("集群规模", [512, 1024, 2048, 4096, 8192, 16384],
                                4096)
        show = st.radio("视图", ["瓶颈迁移 (5 阶段)", "当前配置 Amdahl",
                                 "十年轨迹 (实验 B)", "α 口径分解 (实验 D)"])
    with c2:
        fabname = "ub_hione" if hione else ("ub_protocol" if ub else "legacy_tcp")
        cfg = SystemConfig(n_gpus=ngpu, fabric=fabname,
                           k_memory=2.5 if d3f else 1.0,
                           k_compute=1.6 if lf else 1.0)
        parts = iteration_tau(cfg)
        names = {"compute": "计算", "memory": "访存", "comm": "通信",
                 "other": "其他"}
        dom = max(parts, key=parts.get)
        m = st.columns(3)
        m[0].metric("当前迭代 τ", f"{sum(parts.values()):.2f}s")
        m[1].metric("主导 τ 层", names[dom])
        m[2].metric("主导层占比", f"{parts[dom]/sum(parts.values())*100:.0f}%")

        if show.startswith("瓶颈"):
            stages = bottleneck_migration(ngpu)
            keys = ["compute", "memory", "comm", "other"]
            cols = {"compute": C[0], "memory": C[2], "comm": C[5],
                    "other": style.MUTED}
            fig, ax = plt.subplots(figsize=(9, 4))
            bottom = np.zeros(len(stages))
            x = np.arange(len(stages))
            for k in keys:
                vals = np.array([s[1][k] for s in stages])
                ax.bar(x, vals, 0.6, bottom=bottom, color=cols[k],
                       label=names[k], edgecolor=style.SURFACE, linewidth=2)
                bottom += vals
            ax.set_xticks(x, [s[0] for s in stages], fontsize=8)
            ax.set_ylabel("迭代 τ (秒)"); ax.legend()
            st.pyplot(fig); plt.close(fig)
        elif show.startswith("当前"):
            res = amdahl_scan(cfg)
            fig, ax = plt.subplots(figsize=(9, 4))
            cols = {"compute": C[0], "memory": C[2], "comm": C[5],
                    "other": style.MUTED}
            for k in ["comm", "compute", "memory", "other"]:
                ax.plot(res["k"], res[k], color=cols[k],
                        label=f"只加速{names[k]}（占比 {res['fractions'][k]*100:.0f}%）")
            ax.set_xscale("log"); ax.set_xlabel("单层 τ 压缩倍数")
            ax.set_ylabel("系统加速"); ax.legend()
            st.pyplot(fig); plt.close(fig)
        elif show.startswith("十年"):
            traj = decade_trajectories(n_gpus=ngpu)
            fig, ax = plt.subplots(figsize=(9, 4))
            cols = [C[5], C[2], C[1]]
            for (name, t), col in zip(traj.items(), cols):
                years = np.arange(len(t))
                a = (1 / t[-1]) ** (1 / (len(t) - 1))
                ax.plot(years, t, "-o", ms=4, color=col,
                        label=f"{name} (α≈{a:.2f}/年)")
            ax.set_yscale("log"); ax.set_xlabel("年")
            ax.set_ylabel("系统 τ (归一化)"); ax.legend()
            st.pyplot(fig); plt.close(fig)
        else:
            d = alpha_decomposition()
            fig, ax = plt.subplots(figsize=(9, 4))
            for strat, lab, col in [("legacy", "legacy fabric 固定", C[5]),
                                    ("tau_first", "τ-first 协同演进", C[1])]:
                r = d[strat]
                ax.plot(d["years"], r["capability"], "-o", ms=4, color=col,
                        label=f"{lab} (α≈{r['alpha_total']:.2f}/年)")
            ax.set_yscale("log"); ax.set_xlabel("年")
            ax.set_ylabel("系统有效算力 (相对第 0 年)"); ax.legend()
            st.pyplot(fig); plt.close(fig)

# ================= Tab 6 敏感性扫描 =================

def _attr_param(mod, attr):
    return (lambda: getattr(mod, attr)), (lambda v: setattr(mod, attr, v))


def _ub_o():
    return (lambda: P.FABRICS["ub_protocol"]["o"],
            lambda v: (P.FABRICS["ub_protocol"].__setitem__("o", v),
                       P.FABRICS["ub_hione"].__setitem__("o", v)))


def _ub_a():
    return (lambda: P.FABRICS["ub_protocol"]["alpha_inter"],
            lambda v: (P.FABRICS["ub_protocol"].__setitem__("alpha_inter", v),
                       P.FABRICS["ub_hione"].__setitem__("alpha_inter", v)))


def _tcp_o():
    return (lambda: P.FABRICS["legacy_tcp"]["o"],
            lambda v: P.FABRICS["legacy_tcp"].__setitem__("o", v))


SENS_PARAMS = [
    ("Rent 指数 p", *_attr_param(P, "RENT_P")),
    ("折叠布局效率", *_attr_param(P, "FOLD_EFFICIENCY")),
    ("时钟裕量占比", *_attr_param(L2, "SKEW_FRACTION")),
    ("绕线系数", *_attr_param(L2, "CROSS_DETOUR_COEF")),
    ("键合电容/焊盘", *_attr_param(P, "HB_CAP_PER_PAD_2UM")),
    ("层间热阻", *_attr_param(TH, "R_TIER")),
    ("互连功耗占比", *_attr_param(TH, "WIRE_POWER_FRACTION")),
    ("存储层功率比", *_attr_param(TH, "MEM_TIER_Q_RATIO")),
    ("温升预算", *_attr_param(TH, "DT_BUDGET")),
    ("UB 每消息开销", *_ub_o()),
    ("UB 跨机延迟 α", *_ub_a()),
    ("TCP 栈开销", *_tcp_o()),
]


def _crossover_pitch():
    for p_ in np.arange(0.5, 12.001, 0.1):
        r = fold("7nm", 2, float(p_))
        if r.tau_penalty_ps > r.tau_benefit_ps:
            return float(p_)
    return 12.0


SENS_METRICS = {
    "2层折叠频率增益 @1.5μm (%)": (
        lambda: fold("7nm", 2, 1.5).freq_gain * 100,
        lambda v: v < 0, "增益转负 → 折叠不再划算"),
    "判据反转点 pitch (μm)": (
        _crossover_pitch,
        lambda v: v < 1.5, "反转点低于 Kirin 的 1.5μm 工作点"),
    "异构折叠可持续频率 (×)": (
        lambda: TH.sustained(2, "logic-on-memory", "mobile").f_sustained,
        lambda v: v < 0.9, "低于 0.9 → 不再『近乎无损』"),
    "MoE @128卡 UB/RDMA 加速 (×)": (
        lambda: (moe_decode_step(128, "legacy_rdma", 128).t_iter /
                 moe_decode_step(128, "ub_protocol", 128).t_iter),
        lambda v: v < 1, "UB 不再占优"),
    "级联全开加速 @4096卡 (×)": (
        lambda: (sum(iteration_tau(SystemConfig(4096, fabric="legacy_tcp")).values()) /
                 sum(iteration_tau(SystemConfig(4096, k_compute=1.6, k_memory=2.5,
                                                fabric="ub_hione")).values())),
        lambda v: v < 1, "级联优化无净收益"),
}

with tab6:
    c1, c2 = st.columns([1, 3])
    with c1:
        mname = st.selectbox("输出指标", list(SENS_METRICS))
        perturb = st.slider("扰动幅度 ±%", 10, 50, 30, 5) / 100
        pname = st.selectbox("1D 扫描参数", [p_[0] for p_ in SENS_PARAMS])
    with c2:
        mfn, mflip, mdesc = SENS_METRICS[mname]
        base = mfn()

        rows = []
        for label, get, set_ in SENS_PARAMS:
            b = get()
            set_(b * (1 - perturb)); lo = mfn()
            set_(b * (1 + perturb)); hi = mfn()
            set_(b)
            rows.append((label, lo, hi))
        rows.sort(key=lambda r: -abs(r[2] - r[1]))

        m = st.columns(3)
        m[0].metric("基线指标值", f"{base:.3g}")
        m[1].metric("最敏感参数", rows[0][0])
        m[2].metric("其摆幅", f"{abs(rows[0][2]-rows[0][1]):.3g}")

        fig, ax = plt.subplots(figsize=(9, 4.6))
        y = np.arange(len(rows))[::-1]
        for yi, (label, lo, hi) in zip(y, rows):
            ax.barh(yi, lo - base, left=base, height=0.6, color=C[0],
                    alpha=0.85)
            ax.barh(yi, hi - base, left=base, height=0.6, color=C[2],
                    alpha=0.85)
        ax.axvline(base, color=style.MUTED, ls=":", lw=1)
        ax.set_yticks(y, [r[0] for r in rows], fontsize=9)
        ax.set_xlabel(mname)
        ax.set_title(f"龙卷风图：参数 ±{perturb*100:.0f}% 时指标摆动"
                     f"（蓝 = −扰动，黄 = +扰动）")
        st.pyplot(fig); plt.close(fig)

        # 1D 扫描
        _, get, set_ = next(p_ for p_ in SENS_PARAMS if p_[0] == pname)
        b = get()
        fs = np.linspace(0.5, 1.5, 31)
        vs = []
        for f_ in fs:
            set_(b * float(f_))
            vs.append(mfn())
        set_(b)
        vs = np.array(vs)
        flips = np.array([mflip(v) for v in vs])

        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(fs, vs, color=C[0])
        ax.plot([1.0], [base], "o", color=C[0], ms=8)
        ax.axvline(1.0, color=style.MUTED, ls=":", lw=1)
        i = 0
        while i < len(fs):
            if flips[i]:
                j = i
                while j < len(fs) and flips[j]:
                    j += 1
                ax.axvspan(fs[i], fs[min(j, len(fs) - 1)], color=C[5],
                           alpha=0.12)
                i = j
            i += 1
        ax.set_xlabel(f"{pname}（相对基线倍数）")
        ax.set_ylabel(mname)
        ax.set_title(f"1D 扫描（红色区 = {mdesc}）")
        st.pyplot(fig); plt.close(fig)

# ================= Tab 5 参数 =================
with tab5:
    st.markdown("""
| 参数 | 取值 | 出处 |
|------|------|------|
| FO4 门延迟 28→3nm | 15→6 ps (±30%) | Harris; Stillmaker & Baas 2017 |
| 速度饱和指数 α | 1.25 | Sakurai & Newton, IEEE JSSC 1990 |
| 铜电阻率尺寸效应 | ρ(w)=1.68·(1+40nm/w) μΩ·cm | Steinhögl; imec BEOL |
| Rent 指数 / 线长分布 | 0.62 / Davis 闭式 | Bakoglu; Davis-De-Meindl 1998 |
| 3D 线长收缩 | 1/√k × 效率 0.85 | Rahman & Reif 2000 |
| 混合键合 R/C | 0.3Ω / 0.2fF @2μm | imec ECTC; TSMC SoIC |
| 键合界面/BEOL/减薄硅热阻 | 1.2 / 2.0 / 0.34 K·mm²/W | imec ASME JEP 2017; IBM SEMI-THERM 2013 |
| 算力/HBM 锚点 | 1.2 TF/mm²; 1.2TB/s/栈 | NVIDIA H100; Micron HBM3E |
| TCP/RDMA/UB 延迟 | 25μs / 1.5μs / 0.15μs | IX OSDI'14; eRPC NSDI'19; UB-Mesh; CM384 |
| AllReduce 代价 / 梯度量 | 2(n−1)(o+α)+2V(n−1)/nB / 2Ψ | Thakur 2005; ZeRO SC'20 |
| 运算强度 GEMM/decode | 300 / 2 FLOP/B | NVIDIA; Pope 2022; Roofline (Williams 2009) |

完整 30+ 项参数及说明见 `tau_sim/params.py` 与 `REPORT.md`。
论文自身数据（Kirin 实测、UB 500×）只作对照目标，不进入模型。
""")
