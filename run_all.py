"""一键运行全部仿真实验并输出图表 / Run all simulations and emit figures.

用法 / Usage:
  python run_all.py            # 中文标签 → figures/
  python run_all.py --lang en  # English labels → figures_en/
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from tau_sim import params as P
from tau_sim import style
from tau_sim.layer1_device import scan_nodes
from tau_sim.layer2_circuit import fold, pitch_sweep
from tau_sim.layer3_chip import evaluate
from tau_sim.layer4_system import (train_iteration, moe_decode_step,
                                   simpy_ring_allreduce, simpy_alltoall,
                                   hierarchical_allreduce_t, alltoall_t)
from tau_sim.cascade import (SystemConfig, amdahl_scan, decade_trajectories,
                             bottleneck_migration, iteration_tau,
                             alpha_decomposition, ALPHA_SCALE, ALPHA_CHIP,
                             ALPHA_PRECISION)
from tau_sim.thermal import scan as thermal_scan

LANG = "en" if "--lang" in sys.argv and "en" in sys.argv else "zh"
FIGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "figures_en" if LANG == "en" else "figures")
os.makedirs(FIGDIR, exist_ok=True)
style.apply_style()
C = style.SERIES


def T(zh, en):
    """返回当前语言对应的字符串（LANG 由 --lang 决定）。"""
    return zh if LANG == "zh" else en


# 英文标题更宽，多面板子图标题缩小字号防重叠（中文用默认）
TS = None if LANG == "zh" else 9.5


# 层名 / layer names（键为模型内部标识）
LAYER_NAMES = {
    "compute": T("计算 (器件+电路层)", "Compute (device+circuit)"),
    "memory": T("访存 (封装层)", "Memory (package)"),
    "comm": T("通信 (系统层)", "Comm (system)"),
    "other": T("软件/其他", "Software/other"),
}
LAYER_COLORS = {"compute": C[0], "memory": C[2], "comm": C[5], "other": style.MUTED}

# 模型返回的中文键 → 英文标签
TR_TRAJ = {
    "只推器件节点": "Device node only",
    "只换网络 fabric": "Fabric swap only",
    "全栈 τ-first 协同": "Full-stack τ-first",
}
TR_STAGE = {
    "阶段0\n传统协议栈": "Stage 0\nLegacy stack",
    "阶段1\n+UB 内存语义\n(免协议转换)": "Stage 1\n+UB mem-semantic\n(no conversion)",
    "阶段2\n+Hi-ONE 光互连\n(带宽扁平化)": "Stage 2\n+Hi-ONE optical\n(bw flatten)",
    "阶段3\n+3D Folding\n(表面供内存)": "Stage 3\n+3D Folding\n(surface memory)",
    "阶段4\n+LogicFolding\n(算力提频)": "Stage 4\n+LogicFolding\n(freq boost)",
}


def tr_traj(name):
    """把 cascade 返回的中文轨迹名按语言翻成英文。"""
    return name if LANG == "zh" else TR_TRAJ[name]


def tr_stage(name):
    """把 bottleneck_migration 返回的中文阶段名按语言翻成英文。"""
    return name if LANG == "zh" else TR_STAGE[name]


def save(fig, name):
    """保存图到 FIGDIR（中文 figures/，英文 figures_en/）并关闭 figure。"""
    path = os.path.join(FIGDIR, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  saved {os.path.basename(FIGDIR)}/{name}")


# =====================================================================
# 图 1 — Layer 1: 几何缩放收益趋平 (P1)
# =====================================================================

def fig1_device():
    """图1 · Layer 1：几何缩放收益趋平（P1）。左轴三条归一化延迟曲线，右轴互连占比柱。"""
    pts = scan_nodes()
    x = np.arange(len(pts))
    ideal = np.array([p.tau_ideal_ps for p in pts])
    intr = np.array([p.tau_intrinsic_ps for p in pts])
    stage = np.array([p.tau_stage_ps for p in pts])
    ideal, intr, stage = ideal / ideal[0], intr / intr[0], stage / stage[0]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    ax.plot(x, ideal, "--", color=style.MUTED,
            label=T("理想平方律 (长沟道假想)", "Ideal square-law (long-channel)"))
    ax.plot(x, intr, "-o", color=C[0],
            label=T("门本征延迟 FO4 (速度饱和)", "Gate intrinsic FO4 (vel.-sat.)"))
    ax.plot(x, stage, "-o", color=C[5],
            label=T("级延迟 = 门 + 固定跨度中间布线",
                    "Stage delay = gate + fixed-span wire"))
    ax.set_xticks(x, [p.node for p in pts])
    ax.set_ylabel(T("归一化 τ (28nm = 1)", "Normalized τ (28nm = 1)"))
    ax.set_xlabel(T("工艺节点", "Process node"))
    ax.set_title(T("几何缩放的 τ 收益逐代衰减",
                   "τ gain from geometric scaling decays per generation"))
    ax.legend()
    ax.annotate(T("互连寄生抵消\n晶体管收益",
                  "Interconnect parasitics\ncancel transistor gains"),
                xy=(3.9, stage[-1] - 0.005), xytext=(1.7, 1.06),
                fontsize=9, color=style.INK2,
                arrowprops=dict(arrowstyle="->", color=style.MUTED))

    frac = [p.wire_fraction * 100 for p in pts]
    ax2.bar(x, frac, width=0.55, color=C[2])
    for xi, f in zip(x, frac):
        ax2.text(xi, f + 1.5, f"{f:.0f}%", ha="center", fontsize=9,
                 color=style.INK2)
    ax2.set_ylim(0, max(frac) * 1.18)
    ax2.set_xticks(x, [p.node for p in pts])
    ax2.set_ylabel(T("互连占级延迟比例 (%)", "Interconnect share of stage delay (%)"))
    ax2.set_xlabel(T("工艺节点", "Process node"))
    ax2.set_title(T("延迟预算被互连接管 → 缩放对象应是 τ 而非尺寸",
                    "Interconnect takes the delay budget → scale τ, not size"))
    fig.suptitle(T("Layer 1 · 器件层：纯几何缩放趋平（论文 P1）",
                   "Layer 1 · Device: pure geometric scaling flattens (P1)"),
                 y=1.02)
    save(fig, "fig1_device_scaling.png")
    return pts


# =====================================================================
# 图 2 — Layer 2: 折叠判据 τ_Benefit vs τ_Penalty (P2)
# =====================================================================

def fig2_fold_criterion():
    """图2 · Layer 2：折叠判据 τ_Benefit vs τ_Penalty 随键合 pitch 的交叉（P2）。"""
    pitches = np.linspace(0.5, 6.0, 45)
    res = pitch_sweep("7nm", 2, pitches)
    ben = np.array([r.tau_benefit_ps for r in res])
    pen = np.array([r.tau_penalty_ps for r in res])

    fig, ax = style.new_fig(7.5, 4.4)
    ax.plot(pitches, ben, color=C[1],
            label=T("τ_Benefit（线长缩短的 RC 节省）",
                    "τ_Benefit (RC saved by shorter wires)"))
    ax.plot(pitches, pen, color=C[5],
            label=T("τ_Penalty（垂直互连 + 绕线代价）",
                    "τ_Penalty (vertical interconnect + detour)"))
    diff = ben - pen
    idx = np.where(diff < 0)[0]
    if len(idx):
        xc = pitches[idx[0]]
        ax.axvline(xc, color=style.MUTED, lw=1, ls=":")
        ax.annotate(T(f"判据反转点 ≈ {xc:.1f} μm\n(gear ratio ≈ "
                      f"{xc*1e3/P.TOP_METAL_PITCH_NM:.1f})",
                      f"Criterion flips ≈ {xc:.1f} μm\n(gear ratio ≈ "
                      f"{xc*1e3/P.TOP_METAL_PITCH_NM:.1f})"),
                    xy=(xc, pen[idx[0]]), xytext=(xc + 0.5, pen[idx[0]] + 8),
                    fontsize=9, color=style.INK2,
                    arrowprops=dict(arrowstyle="->", color=style.MUTED))
    ax.axvline(1.5, color=C[0], lw=1, ls="--")
    ax.text(1.55, ax.get_ylim()[1] * 0.92, "Kirin 2026\n(1.5 μm)",
            fontsize=9, color=C[0])
    gear3 = 3 * P.TOP_METAL_PITCH_NM / 1e3
    ax.axvline(gear3, color=style.MUTED, lw=1, ls="--")
    ax.text(gear3 + 0.05, ax.get_ylim()[1] * 0.72,
            T("论文工程结论:\ngear ratio < 3",
              "Paper's rule:\ngear ratio < 3"), fontsize=9, color=style.INK2)
    ax.set_xlabel(T("混合键合 pitch (μm)", "Hybrid-bonding pitch (μm)"))
    ax.set_ylabel(T("关键路径 τ 分量 (ps)", "Critical-path τ component (ps)"))
    ax.set_title(T("Layer 2 · 折叠判据：τ_Benefit > τ_Penalty 的成立区间（论文 P2）",
                   "Layer 2 · Folding criterion: τ_Benefit > τ_Penalty region (P2)"))
    ax.legend(loc="center right")
    save(fig, "fig2_fold_criterion.png")
    return res


# =====================================================================
# 图 3 — Layer 2: 折叠收益 vs 论文实测 (P2)
# =====================================================================

def fig3_fold_gains():
    """图3 · Layer 2：折叠收益（线长/频率/密度）模型 vs 论文 Kirin 实测（P2）。"""
    r2 = fold("7nm", tiers=2, hb_pitch_um=1.5)
    r4 = fold("7nm", tiers=4, hb_pitch_um=1.5)

    metrics = T(["线长降幅", "频率增益", "密度增幅"],
                ["Wirelength ↓", "Frequency ↑", "Density ↑"])
    model2 = [r2.wl_reduction * 100, r2.freq_gain * 100,
              (r2.density_mtr_mm2 / P.PAPER_TARGETS["density_before"] - 1) * 100]
    model4 = [r4.wl_reduction * 100, r4.freq_gain * 100,
              (r4.density_mtr_mm2 / P.PAPER_TARGETS["density_before"] - 1) * 100]
    paper = [P.PAPER_TARGETS["wire_len_reduction"] * 100,
             P.PAPER_TARGETS["freq_gain"] * 100,
             (P.PAPER_TARGETS["density_after"] /
              P.PAPER_TARGETS["density_before"] - 1) * 100]

    x = np.arange(len(metrics))
    w = 0.27
    fig, ax = style.new_fig(7.5, 4.4)
    ax.bar(x - w, model2, w * 0.93, color=C[0],
           label=T("模型: 2 层折叠", "Model: 2-tier fold"))
    ax.bar(x, model4, w * 0.93, color=style.SEQ[3],
           label=T("模型: 4 层折叠", "Model: 4-tier fold"))
    ax.bar(x + w, paper, w * 0.93, color=C[2],
           label=T("论文实测 (Kirin 2026, 2层)", "Paper (Kirin 2026, 2-tier)"))
    for xi, vals in zip(x, zip(model2, model4, paper)):
        for dx, v in zip((-w, 0, w), vals):
            ax.text(xi + dx, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9,
                    color=style.INK2)
    ax.set_xticks(x, metrics)
    ax.set_ylabel(T("改善幅度 (%)", "Improvement (%)"))
    ax.set_title(T("Layer 2 · LogicFolding 收益：模型 vs 论文实测（固定 7nm 节点）",
                   "Layer 2 · LogicFolding gains: model vs paper (fixed 7nm)"))
    ax.legend()
    save(fig, "fig3_fold_gains.png")
    return r2, r4


# =====================================================================
# 图 4 — Layer 3: N²-vs-N 扇出困境 (P3)
# =====================================================================

def fig4_fanout():
    """图4 · Layer 3：N²-vs-N 扇出困境——可达算力发散与 2.5D ridge 上移（P3）。"""
    sides = np.linspace(8, 64, 60)
    pts = [evaluate(s) for s in sides]
    peak = np.array([p.peak_tflops for p in pts])
    bw_e = np.array([p.bw_edge_tbs for p in pts])
    bw_s = np.array([p.bw_surf_tbs for p in pts])

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    intensity = P.DECODE_INTENSITY
    ach_e = np.minimum(peak, intensity * bw_e)
    ach_s = np.minimum(peak, intensity * bw_s)
    ax.plot(sides, peak, "--", color=style.MUTED,
            label=T("峰值算力 (∝N²)", "Peak compute (∝N²)"))
    ax.plot(sides, ach_e, color=C[5],
            label=T("2.5D 边缘供带宽 → 可达算力 ∝N",
                    "2.5D edge bandwidth → achievable ∝N"))
    ax.plot(sides, ach_s, color=C[1],
            label=T("3D Folding 表面供带宽 → ∝N²",
                    "3D Folding surface bandwidth → ∝N²"))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([8, 16, 32, 64], ["8", "16", "32", "64"])
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xlabel(T("die/封装等效边长 N (mm, log)",
                    "die/package equiv. side N (mm, log)"))
    ax.set_ylabel(T("访存受限负载可达算力 (TFLOPS, log)",
                    "Achievable compute, mem-bound (TFLOPS, log)"))
    ax.set_title(T("(a) 可达算力：斜率 1 vs 斜率 2 的发散",
                   "(a) Achievable compute: slope 1 vs slope 2 diverge"))
    ax.legend(fontsize=8.5)

    ridge_e = peak / bw_e
    ridge_s = peak / bw_s
    ax2.plot(sides, ridge_e, color=C[5], label=T("2.5D ridge (∝N)", "2.5D ridge (∝N)"))
    ax2.plot(sides, ridge_s, color=C[1],
             label=T("3D Folding ridge (常数)", "3D Folding ridge (constant)"))
    ax2.axhline(P.GEMM_INTENSITY, color=style.INK2, lw=1, ls="--")
    ax2.text(9, P.GEMM_INTENSITY * 1.12,
             T("训练 GEMM (~300 FLOP/B)", "Training GEMM (~300 FLOP/B)"),
             fontsize=8.5, color=style.INK2)
    ax2.axhline(P.DECODE_INTENSITY, color=style.INK2, lw=1, ls="--")
    ax2.text(9, P.DECODE_INTENSITY * 1.25,
             T("推理 decode (~2 FLOP/B)", "Inference decode (~2 FLOP/B)"),
             fontsize=8.5, color=style.INK2)
    ax2.set_yscale("log")
    ax2.set_xlabel(T("die/封装等效边长 N (mm)", "die/package equiv. side N (mm)"))
    ax2.set_ylabel(T("ridge 运算强度 (FLOP/Byte, log)",
                     "ridge arithmetic intensity (FLOP/Byte, log)"))
    idx = np.where(ridge_e > P.GEMM_INTENSITY)[0]
    if len(idx):
        ax2.axvline(sides[idx[0]], color=style.MUTED, lw=1, ls=":")
        ax2.text(sides[idx[0]] - 24, 90,
                 T(f"N≈{sides[idx[0]]:.0f}mm 后连 GEMM 也访存受限",
                   f"beyond N≈{sides[idx[0]]:.0f}mm even GEMM is mem-bound"),
                 fontsize=8.5, color=style.INK2)
    ax2.set_title(T("(b) 2.5D 的 ridge 强度随规模上移",
                    "(b) 2.5D ridge intensity rises with scale"))
    ax2.legend(fontsize=8.5, loc="lower right")
    fig.suptitle(T("Layer 3 · 封装层：N² vs N 扇出困境（论文 P3）",
                   "Layer 3 · Package: N²-vs-N fan-out dilemma (P3)"), y=1.02)
    save(fig, "fig4_fanout_dilemma.png")


# =====================================================================
# 图 5 — Layer 4: 集群通信 τ (P4)
# =====================================================================

def fig5_cluster():
    """图5 · Layer 4：大消息扩展效率与小消息 MoE 时延，含 SimPy DES 验证点（P4）。"""
    ns = np.array([8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096,
                   8192, 16384])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    fabs_a = [("legacy_tcp", T("传统 TCP/IP 栈 (100GbE)", "Legacy TCP/IP (100GbE)"), C[5]),
              ("legacy_rdma", "RDMA/IB (400G)", C[2]),
              ("ub_hione", T("UB + Hi-ONE (392GB/s 均匀)", "UB + Hi-ONE (392GB/s uniform)"), C[1])]
    for fab, label, col in fabs_a:
        eff = [train_iteration(int(n), fab).scaling_eff * 100 for n in ns]
        ax.plot(ns, eff, "-o", ms=4, color=col, label=label)
    ax.set_xscale("log", base=2)
    ax.set_xlabel(T("GPU/NPU 数", "GPU/NPU count"))
    ax.set_ylabel(T("训练扩展效率 (%)", "Training scaling efficiency (%)"))
    ax.set_title(T("(a) 训练梯度同步（大消息）：带宽扁平化主导",
                   "(a) Training gradient sync (large msg): bw-flatten dominates"),
                 fontsize=TS)
    ax.legend(fontsize=8.5)

    fabs_b = [("legacy_tcp", T("传统 TCP/IP 栈", "Legacy TCP/IP"), C[5]),
              ("legacy_rdma", "RDMA/IB", C[2]),
              ("ub_protocol", T("UB 协议 (同 400G 物理线)", "UB protocol (same 400G link)"), C[0])]
    ep_ns = np.array([8, 16, 32, 64, 128, 256])
    for fab, label, col in fabs_b:
        t = [moe_decode_step(int(n), fab, experts_parallel=int(n)).t_iter * 1e3
             for n in ep_ns]
        ax2.plot(ep_ns, t, "-o", ms=4, color=col, label=label)
    for fab, col in [("legacy_rdma", C[2]), ("ub_protocol", C[0]),
                     ("legacy_tcp", C[5])]:
        des = []
        for n in [8, 32, 128]:
            msg = P.MOE_TOKENS_PER_GPU_DECODE * P.MOE_HIDDEN * 2 / n
            t_a2a = simpy_alltoall(n, msg, P.FABRICS[fab])
            des.append((P.MOE_LAYERS * 2 * t_a2a + P.MOE_LAYERS * 8e-6) * 1e3)
        ax2.plot([8, 32, 128], des, "s", ms=7, mfc="none", mec=col, mew=1.6)
    ax2.plot([], [], "s", ms=7, mfc="none", mec=style.INK2, mew=1.6,
             label=T("SimPy 离散事件仿真验证点", "SimPy discrete-event validation"))
    ax2.set_xscale("log", base=2)
    ax2.set_yscale("log")
    ax2.set_xlabel(T("专家并行规模 (卡数)", "Expert-parallel size (chips)"))
    ax2.set_ylabel(T("MoE decode 每步时间 (ms)", "MoE decode step time (ms)"))
    ax2.set_title(T("(b) MoE 推理 all-to-all（小消息）：协议栈 α 主导",
                    "(b) MoE all-to-all (small msg): stack α dominates"),
                  fontsize=TS)
    ax2.legend(fontsize=8.5)
    fig.suptitle(T("Layer 4 · 系统层：500× 通信 τ 压缩在不同消息 regime 的兑现（论文 P4）",
                   "Layer 4 · System: 500× comm-τ pays off by message regime (P4)"),
                 y=1.02)
    save(fig, "fig5_cluster_scaling.png")


# =====================================================================
# 图 6 — 级联实验 A: Amdahl 饱和 (P5)
# =====================================================================

def fig6_amdahl():
    """图6 · 级联实验 A：单层优化的 Amdahl 饱和与各层加速上限（P5）。"""
    res = amdahl_scan(SystemConfig(n_gpus=4096, fabric="legacy_tcp"))
    fig, ax = style.new_fig(7.5, 4.6)
    for layer in ["comm", "compute", "memory", "other"]:
        frac = res["fractions"][layer]
        ax.plot(res["k"], res[layer], color=LAYER_COLORS[layer],
                label=T(f"只加速{LAYER_NAMES[layer]}（占比 {frac*100:.0f}%）",
                        f"Speed up {LAYER_NAMES[layer]} only ({frac*100:.0f}% share)"))
        ax.axhline(1 / (1 - frac), color=LAYER_COLORS[layer], lw=0.9, ls=":",
                   alpha=0.7)
    ax.set_xscale("log")
    ax.set_xlabel(T("单层 τ 压缩倍数 k", "Single-layer τ compression k"))
    ax.set_ylabel(T("系统 τ 加速", "System τ speedup"))
    ax.set_title(T("级联实验 A · 单层优化的 Amdahl 饱和（4096 卡, 传统协议栈基线）\n"
                   "虚线 = 各层占比决定的加速上限 1/(1-占比)",
                   "Cascade A · Amdahl saturation of single-layer optimization "
                   "(4096 chips, legacy-stack baseline)\n"
                   "dashed = per-layer ceiling 1/(1-share)"))
    ax.legend(fontsize=9)
    save(fig, "fig6_amdahl_saturation.png")
    return res


# =====================================================================
# 图 7 — 级联实验 B: 十年轨迹 (P5)
# =====================================================================

def fig7_decade():
    """图7 · 级联实验 B：十年演进三条路线的系统 τ 轨迹与年化 α（P5）。"""
    traj = decade_trajectories()
    years = np.arange(len(next(iter(traj.values()))))
    fig, ax = style.new_fig(7.5, 4.6)
    cols = {"只推器件节点": C[5], "只换网络 fabric": C[2],
            "全栈 τ-first 协同": C[1]}
    for name, t in traj.items():
        ax.plot(years, t, "-o", ms=4, color=cols[name], label=tr_traj(name))
        alpha_eq = (1 / t[-1]) ** (1 / (len(years) - 1))
        ax.text(years[-1] + 0.15, t[-1], T(f"α≈{alpha_eq:.2f}/年", f"α≈{alpha_eq:.2f}/yr"),
                fontsize=9, color=cols[name], va="center")
    ax.set_yscale("log")
    ax.set_xlim(0, years[-1] + 2.2)
    ax.set_xlabel(T("年", "Year"))
    ax.set_ylabel(T("系统 τ (归一化, log)", "System τ (normalized, log)"))
    ax.set_title(T("级联实验 B · 十年演进：单点优化饱和，全栈 τ-first 维持年化 α\n"
                   "（论文 τ_{n+1}=τ_n/α 的可持续性取决于跨层协同）",
                   "Cascade B · Ten-year evolution: single-point optimization "
                   "saturates, full-stack τ-first sustains annual α\n"
                   "(sustainability of τ_{n+1}=τ_n/α needs cross-layer synergy)"))
    ax.legend()
    save(fig, "fig7_decade_trajectories.png")
    return traj


# =====================================================================
# 图 8 — 级联实验 C: 瓶颈迁移 (P5)
# =====================================================================

def fig8_bottleneck():
    """图8 · 级联实验 C：五阶段瓶颈迁移，主导 τ 层逐步转移（P5）。"""
    stages = bottleneck_migration()
    names = [tr_stage(s[0]) for s in stages]
    keys = ["compute", "memory", "comm", "other"]
    x = np.arange(len(stages))
    fig, ax = style.new_fig(9.0, 4.8)
    bottom = np.zeros(len(stages))
    for kkey in keys:
        vals = np.array([s[1][kkey] for s in stages])
        ax.bar(x, vals, 0.62, bottom=bottom, color=LAYER_COLORS[kkey],
               label=LAYER_NAMES[kkey], edgecolor=style.SURFACE, linewidth=2)
        bottom += vals
    for xi, (name, parts) in enumerate(stages):
        dom = max(parts, key=parts.get)
        total = sum(parts.values())
        ax.text(xi, total + max(bottom) * 0.03,
                T(f"主导: {LAYER_NAMES[dom].split(' ')[0]}\nτ={total:.2f}s",
                  f"Dominant: {LAYER_NAMES[dom].split(' ')[0]}\nτ={total:.2f}s"),
                ha="center", fontsize=9, color=style.INK2)
    ax.set_xticks(x, names, fontsize=9)
    ax.set_ylabel(T("迭代 τ (秒)", "Iteration τ (s)"))
    ax.set_ylim(0, max(bottom) * 1.22)
    ax.set_title(T("级联实验 C · 瓶颈迁移：每一步优化使主导 τ 层转移\n"
                   "——「主导 τ 层就是下一个投资方向」（4096 卡训练迭代）",
                   "Cascade C · Bottleneck migration: each step shifts the "
                   "dominant τ layer\n"
                   "— 'the dominant τ layer is the next investment' "
                   "(4096-chip training iteration)"))
    ax.legend()
    save(fig, "fig8_bottleneck_migration.png")
    return stages


# =====================================================================
# 图 9 — 热约束: 多层折叠的可持续频率
# =====================================================================

def fig9_thermal():
    """图9 · 热约束：多层折叠可持续频率与温升构成（论文开放问题 §6）。"""
    res = thermal_scan()
    tiers = [1, 2, 3, 4]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.4 if LANG == "en" else 11.5, 4.4))

    combos = [
        (("logic-on-memory", "mobile"),
         T("逻辑+存储折叠 · 移动无源", "Logic+memory fold · mobile passive"), C[1]),
        (("logic-on-memory", "ai"),
         T("逻辑+存储折叠 · AI 液冷", "Logic+memory fold · AI liquid"), C[0]),
        (("logic-on-logic", "mobile"),
         T("逻辑+逻辑折叠 · 移动无源", "Logic+logic fold · mobile passive"), C[2]),
        (("logic-on-logic", "ai"),
         T("逻辑+逻辑折叠 · AI 液冷", "Logic+logic fold · AI liquid"), C[5]),
    ]
    burst = [r.f_burst for r in res[("logic-on-logic", "mobile")]]
    ax.plot(tiers, burst, "--", color=style.MUTED,
            label=T("电路极限 (Layer 2, 无热约束)", "Circuit limit (no thermal)"))
    for key, label, col in combos:
        ax.plot(tiers, [r.f_sustained for r in res[key]], "-o", ms=4,
                color=col, label=label)
    ax.axhline(1.0, color=style.BASELINE, lw=0.8)
    ax.set_xticks(tiers)
    ax.set_xlabel(T("折叠层数", "Fold tiers"))
    ax.set_ylabel(T("可持续频率 (相对 2D 基线)", "Sustainable freq (rel. 2D)"))
    ax.set_title(T("(a) 温升预算内的可持续频率\n逻辑+逻辑全功率折叠受 TDP 惩罚, 异构折叠近乎无损",
                   "(a) Sustainable freq within ΔT budget\nlogic+logic pays TDP; "
                   "heterogeneous near-lossless"), fontsize=TS)
    ax.legend(fontsize=8)

    key = ("logic-on-logic", "ai")
    grad = np.array([r.dt_gradient for r in res[key]])
    hs = 60.0 - grad
    hs[0], grad[0] = 60.0, 0.0
    x = np.arange(len(tiers))
    ax2.bar(x, hs, 0.55, color=style.SEQ[1],
            label=T("散热面热阻项 (TDP 约束)", "Heatsink resistance (TDP limit)"),
            edgecolor=style.SURFACE, linewidth=2)
    ax2.bar(x, grad, 0.55, bottom=hs, color=C[5],
            label=T("层间热阻梯度 (硅+键合界面)", "Inter-tier gradient (Si+bond)"),
            edgecolor=style.SURFACE, linewidth=2)
    for xi, g in zip(x, grad):
        if g > 0:
            ax2.text(xi, 61.5, T(f"梯度 {g:.1f}K", f"grad {g:.1f}K"),
                     ha="center", fontsize=8.5, color=style.INK2)
    ax2.set_xticks(x, [T(f"{k}层", f"{k}-tier") for k in tiers])
    ax2.set_ylim(0, 70)
    ax2.set_ylabel(T("温升构成 (K, 预算 60K)", "ΔT composition (K, budget 60K)"))
    ax2.set_title(T("(b) 温升构成 (AI·逻辑+逻辑)\n瓶颈是折叠后的功率密度, 层间热阻是次要项",
                    "(b) ΔT composition (AI·logic+logic)\nbottleneck = folded "
                    "power density; inter-tier secondary"), fontsize=TS)
    ax2.legend(fontsize=8.5, loc="lower right")
    fig.suptitle(T("热约束 · 多层折叠的可持续性（对应论文开放问题 §6）",
                   "Thermal constraint · sustainability of multi-tier folding "
                   "(paper open problem §6)"), y=1.04)
    save(fig, "fig9_thermal_constraint.png")
    return res


# =====================================================================
# 图 10 — 实验 D: α≈10/年 的口径分解
# =====================================================================

def fig10_alpha():
    """图10 · 级联实验 D：论文 AI 侧 α≈10/年 的口径分解。"""
    d = alpha_decomposition()
    years = d["years"]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.4 if LANG == "en" else 11.5, 4.4))

    cols = {"legacy": C[5], "tau_first": C[1]}
    labels = {"legacy": T("legacy fabric 固定 (RDMA/IB)", "legacy fabric fixed (RDMA/IB)"),
              "tau_first": T("τ-first: fabric 随算力同步演进",
                             "τ-first: fabric co-evolves with compute")}
    for strat in ["legacy", "tau_first"]:
        r = d[strat]
        ax.plot(years, r["capability"], "-o", ms=4, color=cols[strat],
                label=labels[strat])
        ax.text(years[-1] + 0.15, r["capability"][-1],
                T(f"α≈{r['alpha_total']:.2f}/年\n({r['capability'][-1]:.0f}×/十年)",
                  f"α≈{r['alpha_total']:.2f}/yr\n({r['capability'][-1]:.0f}×/decade)"),
                fontsize=8.5, color=cols[strat], va="center")
    ax.set_yscale("log")
    ax.set_xlim(0, 12.6)
    ax.set_xlabel(T("年", "Year"))
    ax.set_ylabel(T("系统有效算力 (相对第 0 年, log)",
                    "System effective compute (rel. year 0, log)"))
    ax.set_title(T("(a) 弱扩展十年轨迹：模型规模随算力增长\nfabric 不演进则扩展效率坍塌 (0.47→0.08)",
                   "(a) Weak-scaling decade: model grows with compute\nno fabric "
                   "evolution → efficiency collapses (0.47→0.08)"), fontsize=TS)
    ax.legend(fontsize=8.5, loc="upper left")

    factors = [
        (T("集成规模\nα_scale", "Integration\nα_scale"), ALPHA_SCALE, style.SEQ[1]),
        (T("单芯片\nα_chip", "Per-chip\nα_chip"), ALPHA_CHIP, style.SEQ[2]),
        (T("扩展效率 α_eff\n(τ-first)", "Scaling eff α_eff\n(τ-first)"),
         d["tau_first"]["alpha_eff"], C[1]),
        (T("扩展效率 α_eff\n(legacy)", "Scaling eff α_eff\n(legacy)"),
         d["legacy"]["alpha_eff"], C[5]),
        (T("精度/数制\n(模型外)", "Precision\n(out of model)"), ALPHA_PRECISION, style.MUTED),
    ]
    x = np.arange(len(factors))
    vals = [f[1] for f in factors]
    ax2.bar(x, vals, 0.55, color=[f[2] for f in factors])
    for xi, v in zip(x, vals):
        ax2.text(xi, v + 0.02, f"{v:.2f}×", ha="center", fontsize=9,
                 color=style.INK2)
    ax2.axhline(1.0, color=style.BASELINE, lw=0.8)
    prod_tau = ALPHA_SCALE * ALPHA_CHIP * d["tau_first"]["alpha_eff"]
    prod_all = prod_tau * ALPHA_PRECISION
    ax2.set_xticks(x, [f[0] for f in factors], fontsize=8)
    ax2.set_ylim(0, 1.85)
    ax2.set_ylabel(T("年化倍率", "Annualized factor"))
    ax2.set_title(T(f"(b) α 的因子分解: 硬件三因子积 ≈ {prod_tau:.1f}×/年\n"
                    f"叠加精度演进 ≈ {prod_all:.1f}×/年 — 论文 α≈10 还需算法/软件因子",
                    f"(b) α decomposition: 3 hardware factors ≈ {prod_tau:.1f}×/yr\n"
                    f"+precision ≈ {prod_all:.1f}×/yr — α≈10 needs algo/software"),
                  fontsize=TS)
    fig.suptitle(T("级联实验 D · 论文 AI 侧 α 的口径分解（论文 §2）",
                   "Cascade D · accounting decomposition of the paper's AI-side α (§2)"),
                 y=1.04)
    save(fig, "fig10_alpha_decomposition.png")
    return d


# =====================================================================
# 控制台摘要
# =====================================================================

def summary(fold2, stages):
    """控制台打印模型结果与论文数字的对照表。"""
    tgt = P.PAPER_TARGETS
    print("\n" + "=" * 68)
    print("对照论文数字（模型输入均来自独立文献, 详见 tau_sim/params.py）")
    print("=" * 68)
    print(f"  线长降幅   模型 {fold2.wl_reduction*100:5.1f}%   "
          f"论文 {tgt['wire_len_reduction']*100:.0f}%")
    print(f"  频率增益   模型 {fold2.freq_gain*100:5.1f}%   "
          f"论文 {tgt['freq_gain']*100:.0f}%")
    print(f"  密度       模型 {fold2.density_mtr_mm2:5.0f}    "
          f"论文 {tgt['density_after']:.0f}  MTr/mm²")
    t0 = sum(stages[0][1].values())
    t4 = sum(stages[-1][1].values())
    print(f"  系统迭代 τ 阶段0→4: {t0:.2f}s → {t4:.2f}s "
          f"(共 {t0/t4:.1f}×), 主导层迁移: "
          + " → ".join(max(s[1], key=s[1].get) for s in stages))


if __name__ == "__main__":
    print(f"[lang={LANG}] → {os.path.basename(FIGDIR)}/")
    print("Layer 1 ...")
    fig1_device()
    print("Layer 2 / LogicFolding ...")
    fig2_fold_criterion()
    fold2, _ = fig3_fold_gains()
    print("Layer 3 / N²-vs-N ...")
    fig4_fanout()
    print("Layer 4 / cluster ...")
    fig5_cluster()
    print("Cascade A/B/C ...")
    fig6_amdahl()
    fig7_decade()
    stages = fig8_bottleneck()
    print("Thermal ...")
    thermal = fig9_thermal()
    print("Cascade D / alpha ...")
    alpha = fig10_alpha()
    summary(fold2, stages)
    r2m = thermal[("logic-on-memory", "mobile")][1]
    print(f"  热约束     2层异构折叠可持续 f={r2m.f_sustained:.2f}, "
          f"burst=+{(r2m.f_burst-1)*100:.0f}%")
    print(f"  α 口径     τ-first {alpha['tau_first']['alpha_total']:.2f}/年 "
          f"vs legacy {alpha['legacy']['alpha_total']:.2f}/年")
    print(f"\n全部图表已输出到 {os.path.basename(FIGDIR)}/")
