"""一键运行全部仿真实验并输出 figures/。

用法: python run_all.py
"""

import os

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
                             bottleneck_migration, iteration_tau)

FIGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(FIGDIR, exist_ok=True)
style.apply_style()
C = style.SERIES

LAYER_NAMES = {"compute": "计算 (器件+电路层)", "memory": "访存 (封装层)",
               "comm": "通信 (系统层)", "other": "软件/其他"}
LAYER_COLORS = {"compute": C[0], "memory": C[2], "comm": C[5], "other": style.MUTED}


def save(fig, name):
    path = os.path.join(FIGDIR, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  saved figures/{name}")


# =====================================================================
# 图 1 — Layer 1: 几何缩放收益趋平 (P1)
# =====================================================================

def fig1_device():
    pts = scan_nodes()
    x = np.arange(len(pts))
    ideal = np.array([p.tau_ideal_ps for p in pts])
    intr = np.array([p.tau_intrinsic_ps for p in pts])
    stage = np.array([p.tau_stage_ps for p in pts])
    ideal, intr, stage = ideal / ideal[0], intr / intr[0], stage / stage[0]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    ax.plot(x, ideal, "--", color=style.MUTED, label="理想平方律 (长沟道假想)")
    ax.plot(x, intr, "-o", color=C[0], label="门本征延迟 FO4 (速度饱和)")
    ax.plot(x, stage, "-o", color=C[5],
            label="级延迟 = 门 + 固定跨度中间布线")
    ax.set_xticks(x, [p.node for p in pts])
    ax.set_ylabel("归一化 τ (28nm = 1)")
    ax.set_xlabel("工艺节点")
    ax.set_title("几何缩放的 τ 收益逐代衰减")
    ax.legend()
    ax.annotate("互连寄生抵消\n晶体管收益", xy=(3.9, stage[-1] - 0.005),
                xytext=(1.7, 1.06), fontsize=9, color=style.INK2,
                arrowprops=dict(arrowstyle="->", color=style.MUTED))

    frac = [p.wire_fraction * 100 for p in pts]
    ax2.bar(x, frac, width=0.55, color=C[2])
    for xi, f in zip(x, frac):
        ax2.text(xi, f + 1.5, f"{f:.0f}%", ha="center", fontsize=9,
                 color=style.INK2)
    ax2.set_ylim(0, max(frac) * 1.18)
    ax2.set_xticks(x, [p.node for p in pts])
    ax2.set_ylabel("互连占级延迟比例 (%)")
    ax2.set_xlabel("工艺节点")
    ax2.set_title("延迟预算被互连接管 → 缩放对象应是 τ 而非尺寸")
    fig.suptitle("Layer 1 · 器件层：纯几何缩放趋平（论文 P1）", y=1.02)
    save(fig, "fig1_device_scaling.png")
    return pts


# =====================================================================
# 图 2 — Layer 2: 折叠判据 τ_Benefit vs τ_Penalty (P2)
# =====================================================================

def fig2_fold_criterion():
    pitches = np.linspace(0.5, 6.0, 45)
    res = pitch_sweep("7nm", 2, pitches)
    ben = np.array([r.tau_benefit_ps for r in res])
    pen = np.array([r.tau_penalty_ps for r in res])

    fig, ax = style.new_fig(7.5, 4.4)
    ax.plot(pitches, ben, color=C[1], label="τ_Benefit（线长缩短的 RC 节省）")
    ax.plot(pitches, pen, color=C[5], label="τ_Penalty（垂直互连 + 绕线代价）")
    # 交叉点
    diff = ben - pen
    idx = np.where(diff < 0)[0]
    if len(idx):
        xc = pitches[idx[0]]
        ax.axvline(xc, color=style.MUTED, lw=1, ls=":")
        ax.annotate(f"判据反转点 ≈ {xc:.1f} μm\n(gear ratio ≈ "
                    f"{xc*1e3/P.TOP_METAL_PITCH_NM:.1f})",
                    xy=(xc, pen[idx[0]]), xytext=(xc + 0.5, pen[idx[0]] + 8),
                    fontsize=9, color=style.INK2,
                    arrowprops=dict(arrowstyle="->", color=style.MUTED))
    ax.axvline(1.5, color=C[0], lw=1, ls="--")
    ax.text(1.55, ax.get_ylim()[1] * 0.92, "Kirin 2026\n(1.5 μm)",
            fontsize=9, color=C[0])
    gear3 = 3 * P.TOP_METAL_PITCH_NM / 1e3
    ax.axvline(gear3, color=style.MUTED, lw=1, ls="--")
    ax.text(gear3 + 0.05, ax.get_ylim()[1] * 0.72,
            "论文工程结论:\ngear ratio < 3", fontsize=9, color=style.INK2)
    ax.set_xlabel("混合键合 pitch (μm)")
    ax.set_ylabel("关键路径 τ 分量 (ps)")
    ax.set_title("Layer 2 · 折叠判据：τ_Benefit > τ_Penalty 的成立区间（论文 P2）")
    ax.legend(loc="center right")
    save(fig, "fig2_fold_criterion.png")
    return res


# =====================================================================
# 图 3 — Layer 2: 折叠收益 vs 论文实测 (P2)
# =====================================================================

def fig3_fold_gains():
    r2 = fold("7nm", tiers=2, hb_pitch_um=1.5)
    r4 = fold("7nm", tiers=4, hb_pitch_um=1.5)

    metrics = ["线长降幅", "频率增益", "密度增幅"]
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
    ax.bar(x - w, model2, w * 0.93, color=C[0], label="模型: 2 层折叠")
    ax.bar(x, model4, w * 0.93, color=style.SEQ[3], label="模型: 4 层折叠")
    ax.bar(x + w, paper, w * 0.93, color=C[2], label="论文实测 (Kirin 2026, 2层)")
    for xi, vals in zip(x, zip(model2, model4, paper)):
        for dx, v in zip((-w, 0, w), vals):
            ax.text(xi + dx, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9,
                    color=style.INK2)
    ax.set_xticks(x, metrics)
    ax.set_ylabel("改善幅度 (%)")
    ax.set_title("Layer 2 · LogicFolding 收益：模型 vs 论文实测（固定 7nm 节点）")
    ax.legend()
    save(fig, "fig3_fold_gains.png")
    return r2, r4


# =====================================================================
# 图 4 — Layer 3: N²-vs-N 扇出困境 (P3)
# =====================================================================

def fig4_fanout():
    sides = np.linspace(8, 64, 60)
    pts = [evaluate(s) for s in sides]
    peak = np.array([p.peak_tflops for p in pts])
    bw_e = np.array([p.bw_edge_tbs for p in pts])
    bw_s = np.array([p.bw_surf_tbs for p in pts])

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    # (a) 访存受限负载 (decode) 的可达算力: N² vs N 的发散
    intensity = P.DECODE_INTENSITY
    ach_e = np.minimum(peak, intensity * bw_e)
    ach_s = np.minimum(peak, intensity * bw_s)
    ax.plot(sides, peak, "--", color=style.MUTED, label="峰值算力 (∝N²)")
    ax.plot(sides, ach_e, color=C[5], label="2.5D 边缘供带宽 → 可达算力 ∝N")
    ax.plot(sides, ach_s, color=C[1], label="3D Folding 表面供带宽 → ∝N²")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([8, 16, 32, 64], ["8", "16", "32", "64"])
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xlabel("die/封装等效边长 N (mm, log)")
    ax.set_ylabel("访存受限负载可达算力 (TFLOPS, log)")
    ax.set_title("(a) 可达算力：斜率 1 vs 斜率 2 的发散")
    ax.legend(fontsize=8.5)

    # (b) ridge 运算强度：维持算力受限所需的 FLOP/Byte
    ridge_e = peak / bw_e
    ridge_s = peak / bw_s
    ax2.plot(sides, ridge_e, color=C[5], label="2.5D ridge (∝N)")
    ax2.plot(sides, ridge_s, color=C[1], label="3D Folding ridge (常数)")
    ax2.axhline(P.GEMM_INTENSITY, color=style.INK2, lw=1, ls="--")
    ax2.text(9, P.GEMM_INTENSITY * 1.12, "训练 GEMM (~300 FLOP/B)",
             fontsize=8.5, color=style.INK2)
    ax2.axhline(P.DECODE_INTENSITY, color=style.INK2, lw=1, ls="--")
    ax2.text(9, P.DECODE_INTENSITY * 1.25, "推理 decode (~2 FLOP/B)",
             fontsize=8.5, color=style.INK2)
    ax2.set_yscale("log")
    ax2.set_xlabel("die/封装等效边长 N (mm)")
    ax2.set_ylabel("ridge 运算强度 (FLOP/Byte, log)")
    idx = np.where(ridge_e > P.GEMM_INTENSITY)[0]
    if len(idx):
        ax2.axvline(sides[idx[0]], color=style.MUTED, lw=1, ls=":")
        ax2.text(sides[idx[0]] - 24, 90,
                 f"N≈{sides[idx[0]]:.0f}mm 后连 GEMM 也访存受限",
                 fontsize=8.5, color=style.INK2)
    ax2.set_title("(b) 2.5D 的 ridge 强度随规模上移")
    ax2.legend(fontsize=8.5, loc="lower right")
    fig.suptitle("Layer 3 · 封装层：N² vs N 扇出困境（论文 P3）", y=1.02)
    save(fig, "fig4_fanout_dilemma.png")


# =====================================================================
# 图 5 — Layer 4: 集群通信 τ (P4)
# =====================================================================

def fig5_cluster():
    ns = np.array([8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096,
                   8192, 16384])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    # (a) 训练扩展效率（大消息 regime）：三代 fabric
    fabs_a = [("legacy_tcp", "传统 TCP/IP 栈 (100GbE)", C[5]),
              ("legacy_rdma", "RDMA/IB (400G)", C[2]),
              ("ub_hione", "UB + Hi-ONE (392GB/s 均匀)", C[1])]
    for fab, label, col in fabs_a:
        eff = [train_iteration(int(n), fab).scaling_eff * 100 for n in ns]
        ax.plot(ns, eff, "-o", ms=4, color=col, label=label)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("GPU/NPU 数")
    ax.set_ylabel("训练扩展效率 (%)")
    ax.set_title("(a) 训练梯度同步（大消息）：带宽扁平化主导")
    ax.legend(fontsize=8.5)

    # (b) MoE decode（小消息 regime）：同物理线只换协议栈 → α 主导
    fabs_b = [("legacy_tcp", "传统 TCP/IP 栈", C[5]),
              ("legacy_rdma", "RDMA/IB", C[2]),
              ("ub_protocol", "UB 协议 (同 400G 物理线)", C[0])]
    ep_ns = np.array([8, 16, 32, 64, 128, 256])
    for fab, label, col in fabs_b:
        t = [moe_decode_step(int(n), fab, experts_parallel=int(n)).t_iter * 1e3
             for n in ep_ns]
        ax2.plot(ep_ns, t, "-o", ms=4, color=col, label=label)
    # SimPy DES 验证点（含链路争用与 5% 抖动）
    for fab, col in [("legacy_rdma", C[2]), ("ub_protocol", C[0]),
                     ("legacy_tcp", C[5])]:
        des = []
        for n in [8, 32, 128]:
            msg = P.MOE_TOKENS_PER_GPU_DECODE * P.MOE_HIDDEN * 2 / n
            t_a2a = simpy_alltoall(n, msg, P.FABRICS[fab])
            des.append((P.MOE_LAYERS * 2 * t_a2a + P.MOE_LAYERS * 8e-6) * 1e3)
        ax2.plot([8, 32, 128], des, "s", ms=7, mfc="none", mec=col, mew=1.6)
    ax2.plot([], [], "s", ms=7, mfc="none", mec=style.INK2, mew=1.6,
             label="SimPy 离散事件仿真验证点")
    ax2.set_xscale("log", base=2)
    ax2.set_yscale("log")
    ax2.set_xlabel("专家并行规模 (卡数)")
    ax2.set_ylabel("MoE decode 每步时间 (ms)")
    ax2.set_title("(b) MoE 推理 all-to-all（小消息）：协议栈 α 主导")
    ax2.legend(fontsize=8.5)
    fig.suptitle("Layer 4 · 系统层：500× 通信 τ 压缩在不同消息 regime 的兑现（论文 P4）",
                 y=1.02)
    save(fig, "fig5_cluster_scaling.png")


# =====================================================================
# 图 6 — 级联实验 A: Amdahl 饱和 (P5)
# =====================================================================

def fig6_amdahl():
    res = amdahl_scan(SystemConfig(n_gpus=4096, fabric="legacy_tcp"))
    fig, ax = style.new_fig(7.5, 4.6)
    for layer in ["comm", "compute", "memory", "other"]:
        frac = res["fractions"][layer]
        ax.plot(res["k"], res[layer], color=LAYER_COLORS[layer],
                label=f"只加速{LAYER_NAMES[layer]}（占比 {frac*100:.0f}%）")
        ax.axhline(1 / (1 - frac), color=LAYER_COLORS[layer], lw=0.9, ls=":",
                   alpha=0.7)
    ax.set_xscale("log")
    ax.set_xlabel("单层 τ 压缩倍数 k")
    ax.set_ylabel("系统 τ 加速")
    ax.set_title("级联实验 A · 单层优化的 Amdahl 饱和（4096 卡, 传统协议栈基线）\n"
                 "虚线 = 各层占比决定的加速上限 1/(1-占比)")
    ax.legend(fontsize=9)
    save(fig, "fig6_amdahl_saturation.png")
    return res


# =====================================================================
# 图 7 — 级联实验 B: 十年轨迹 (P5)
# =====================================================================

def fig7_decade():
    traj = decade_trajectories()
    years = np.arange(len(next(iter(traj.values()))))
    fig, ax = style.new_fig(7.5, 4.6)
    cols = {"只推器件节点": C[5], "只换网络 fabric": C[2],
            "全栈 τ-first 协同": C[1]}
    for name, t in traj.items():
        ax.plot(years, t, "-o", ms=4, color=cols[name], label=name)
        alpha_eq = (1 / t[-1]) ** (1 / (len(years) - 1))
        ax.text(years[-1] + 0.15, t[-1], f"α≈{alpha_eq:.2f}/年",
                fontsize=9, color=cols[name], va="center")
    ax.set_yscale("log")
    ax.set_xlim(0, years[-1] + 2.2)
    ax.set_xlabel("年")
    ax.set_ylabel("系统 τ (归一化, log)")
    ax.set_title("级联实验 B · 十年演进：单点优化饱和，全栈 τ-first 维持年化 α\n"
                 "（论文 τ_{n+1}=τ_n/α 的可持续性取决于跨层协同）")
    ax.legend()
    save(fig, "fig7_decade_trajectories.png")
    return traj


# =====================================================================
# 图 8 — 级联实验 C: 瓶颈迁移 (P5)
# =====================================================================

def fig8_bottleneck():
    stages = bottleneck_migration()
    names = [s[0] for s in stages]
    keys = ["compute", "memory", "comm", "other"]
    x = np.arange(len(stages))
    fig, ax = style.new_fig(9.0, 4.8)
    bottom = np.zeros(len(stages))
    for kkey in keys:
        vals = np.array([s[1][kkey] for s in stages])
        ax.bar(x, vals, 0.62, bottom=bottom, color=LAYER_COLORS[kkey],
               label=LAYER_NAMES[kkey], edgecolor=style.SURFACE, linewidth=2)
        bottom += vals
    # 标注每阶段主导层
    for xi, (name, parts) in enumerate(stages):
        dom = max(parts, key=parts.get)
        total = sum(parts.values())
        ax.text(xi, total + max(bottom) * 0.03,
                f"主导: {LAYER_NAMES[dom].split(' ')[0]}\n"
                f"τ={total:.2f}s", ha="center", fontsize=9, color=style.INK2)
    ax.set_xticks(x, names, fontsize=9)
    ax.set_ylabel("迭代 τ (秒)")
    ax.set_ylim(0, max(bottom) * 1.22)
    ax.set_title("级联实验 C · 瓶颈迁移：每一步优化使主导 τ 层转移\n"
                 "——「主导 τ 层就是下一个投资方向」（4096 卡训练迭代）")
    ax.legend()
    save(fig, "fig8_bottleneck_migration.png")
    return stages


# =====================================================================
# 控制台摘要
# =====================================================================

def summary(fold2, stages):
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
    print("Layer 1 器件层 ...")
    fig1_device()
    print("Layer 2 电路层 / LogicFolding ...")
    fig2_fold_criterion()
    fold2, _ = fig3_fold_gains()
    print("Layer 3 封装层 / N²-vs-N ...")
    fig4_fanout()
    print("Layer 4 系统层 / 集群通信 ...")
    fig5_cluster()
    print("级联实验 A/B/C ...")
    fig6_amdahl()
    fig7_decade()
    stages = fig8_bottleneck()
    summary(fold2, stages)
    print("\n全部图表已输出到 figures/")
