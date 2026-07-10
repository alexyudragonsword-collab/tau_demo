"""Layer 2 — 电路层 / LogicFolding (验证论文命题 P2).

线长模型：Davis 先验线长分布 [Davis 1998]（Rent 定则驱动），
2D 版本数值实现；k 层折叠按 Rahman & Reif 思路建模 ——
footprint 缩小 k 倍 → 水平线长理论收缩 1/√k，乘以布局效率
FOLD_EFFICIENCY（实测 2 层达成理论值的 0.6-0.85）。

关键路径模型：LOGIC_DEPTH 级逻辑门 + 各级互连 + 时钟开销。
  互连延迟用最优中继(repeater)线性模型（连续、对线长单调）:
      τ_wire(l) = 2·√(0.38·r·c·rg·cg) · l
  时钟偏斜/裕量取路径延迟的 SKEW_FRACTION [Harris 2002: 5-10%],
  折叠时时钟树线长同比例收缩 → 偏斜同比例下降（论文 -25% 由此
  成为模型输出而非输入）。
  跨层代价：每次穿越混合键合界面付 (R_hb + R_drv)·C_hb，
  以及 gear ratio>1 时的接入绕线 (bird-cage) 额外线长。

密度模型：D_fold = k·D_2D·(1-overhead(k))，对照论文 155→238。

折叠判据（论文不等式）：τ_Benefit > τ_Penalty，扫混合键合 pitch
画出交叉点，对照论文 “gear ratio < 3、越低越好” 的工程结论。
"""

from dataclasses import dataclass

import numpy as np

from . import params as P
from .layer1_device import wire_rc_per_m

SKEW_FRACTION = 0.10       # 时钟偏斜+抖动+建立裕量占路径延迟比例 [Harris]
DRIVER_UPSIZE = 8.0        # 跨层驱动器相对最小尺寸的放大倍数
CROSS_DETOUR_COEF = 2.0    # gear ratio 引起的每次跨层绕线 ≈ coef·(gear-1)·pitch


# ---------------------------------------------------------------------
# Davis 先验线长分布（2D，单位：门距 gate pitch）
# ---------------------------------------------------------------------

def davis_distribution(n_gates: float, p: float):
    """返回 (长度数组 l, 各长度的相对互连数 m(l))，l 以门距计。

    Davis, De, Meindl, IEEE TED 45(3) 1998 的闭式结构因子:
      区域 I  (1 ≤ l ≤ √N):    M(l) ∝ (l³/3 − 2√N·l² + 2N·l)·l^{2p−4}
      区域 II (√N ≤ l ≤ 2√N):  M(l) ∝ (1/6)(2√N − l)³·l^{2p−4}
    """
    n_side = np.sqrt(n_gates)
    l = np.arange(1, int(2 * n_side))
    m = np.where(
        l <= n_side,
        (l ** 3 / 3.0 - 2.0 * n_side * l ** 2 + 2.0 * n_gates * l),
        (2.0 * n_side - l) ** 3 / 6.0,
    ) * l.astype(float) ** (2.0 * p - 4.0)
    return l, np.clip(m, 0.0, None)


def mean_wirelength_gp(n_gates: float, p: float) -> float:
    l, m = davis_distribution(n_gates, p)
    return float(np.sum(l * m) / np.sum(m))


def percentile_wirelength_gp(n_gates: float, p: float, q: float) -> float:
    l, m = davis_distribution(n_gates, p)
    cdf = np.cumsum(m) / np.sum(m)
    return float(l[int(np.searchsorted(cdf, q))])


def critical_path_wires_um(node: str, density_2d: float) -> np.ndarray:
    """关键路径各级线长：取分布高分位的长线（关键路径即最坏路径，
    由长线尾部主导; 0.95→0.9995 分位）。"""
    gp = gate_pitch_um(node, density_2d)
    qs = np.linspace(0.95, 0.9995, P.LOGIC_DEPTH)
    return np.array([percentile_wirelength_gp(P.N_GATES, P.RENT_P, q)
                     for q in qs]) * gp


# ---------------------------------------------------------------------
# 延迟模型
# ---------------------------------------------------------------------

def gate_pitch_um(node: str, density_2d_mtr_mm2: float) -> float:
    """由 2D 晶体管密度反推门距（μm），每门 ~4 管。"""
    gates_per_mm2 = density_2d_mtr_mm2 * 1e6 / 4.0 * P.AREA_UTILIZATION
    return float(1e3 / np.sqrt(gates_per_mm2))


def wire_delay_per_um(node: str) -> float:
    """最优中继互连延迟 (ps/μm)。rg·cg 乘积与器件尺寸无关。"""
    nd = P.NODES[node]
    r, c = wire_rc_per_m(node)
    cg = 0.5e-15
    rg = nd["fo4"] * 1e-12 / (5.0 * cg)
    return float(2.0 * np.sqrt(0.38 * r * c * rg * cg) * 1e-6 * 1e12)


def critical_path_tau(node: str, wire_lens_um: np.ndarray,
                      n_cross: int = 0, hb_pitch_um: float = 2.0,
                      skew_scale: float = 1.0) -> float:
    """关键路径延迟 (ps) = 门 + 互连 + 跨层 + 时钟开销。"""
    nd = P.NODES[node]
    cg = 0.5e-15
    rg = nd["fo4"] * 1e-12 / (5.0 * cg)

    tau_gates = P.LOGIC_DEPTH * nd["fo4"]
    tau_wires = wire_delay_per_um(node) * float(np.sum(wire_lens_um))

    # 跨层：混合键合点电容按焊盘面积随 pitch² 缩放
    c_hb = P.HB_CAP_PER_PAD_2UM * (hb_pitch_um / 2.0) ** 2
    tau_cross = n_cross * (P.HB_RES_PER_PAD + rg / DRIVER_UPSIZE) * c_hb * 1e12

    tau_path = tau_gates + tau_wires + tau_cross
    return float(tau_path * (1.0 + SKEW_FRACTION * skew_scale))


# ---------------------------------------------------------------------
# 折叠
# ---------------------------------------------------------------------

@dataclass
class FoldResult:
    tiers: int
    hb_pitch_um: float
    gear_ratio: float
    wl_reduction: float           # 平均线长降幅
    skew_reduction: float         # 时钟偏斜降幅（模型输出）
    tau_crit_2d_ps: float
    tau_crit_3d_ps: float
    freq_gain: float
    tau_benefit_ps: float         # 水平 RC 节省 + 偏斜收紧
    tau_penalty_ps: float         # 垂直互连 + 绕线代价
    density_mtr_mm2: float


def fold(node: str = "7nm", tiers: int = 2, hb_pitch_um: float = 1.5,
         density_2d: float = None, efficiency: float = None) -> FoldResult:
    """k 层折叠 vs 2D 平面（代表性处理核全域折叠）。"""
    density_2d = density_2d or P.PAPER_TARGETS["density_before"]
    eff = efficiency if efficiency is not None else P.FOLD_EFFICIENCY

    wl_2d = critical_path_wires_um(node, density_2d)
    tau_2d = critical_path_tau(node, wl_2d)

    # 水平收缩：footprint /k → 线长×(1 − eff·(1−1/√k))
    shrink = 1.0 - eff * (1.0 - 1.0 / np.sqrt(tiers))
    wl_3d = wl_2d * shrink
    # 时钟树线长同比例收缩 → 偏斜同比例下降
    skew_scale = shrink
    # 跨层：关键路径约半数级间跳变穿越键合界面（全域折叠）
    n_cross = int(np.ceil(P.LOGIC_DEPTH / 2.0))
    # bird-cage 绕线：键合点比顶层金属稀疏 (gear>1) 时的接入绕行
    gear = hb_pitch_um * 1e3 / P.TOP_METAL_PITCH_NM
    detour_um = CROSS_DETOUR_COEF * max(gear - 1.0, 0.0) * hb_pitch_um
    wl_3d_eff = wl_3d.copy()
    wl_3d_eff[:n_cross] += detour_um

    tau_3d = critical_path_tau(node, wl_3d_eff, n_cross=n_cross,
                               hb_pitch_um=hb_pitch_um,
                               skew_scale=skew_scale)

    # 判据分解（以“只有线长收缩、无跨层代价”的假想为参照）
    tau_ideal_3d = critical_path_tau(node, wl_3d, skew_scale=skew_scale)
    tau_benefit = tau_2d - tau_ideal_3d
    tau_penalty = tau_3d - tau_ideal_3d

    overhead = P.FOLD_AREA_OVERHEAD_2T * (1.0 + 0.35 * (tiers - 2))
    density = density_2d * tiers * (1.0 - overhead)

    return FoldResult(
        tiers=tiers, hb_pitch_um=hb_pitch_um, gear_ratio=gear,
        wl_reduction=1.0 - shrink,
        skew_reduction=1.0 - skew_scale,
        tau_crit_2d_ps=tau_2d, tau_crit_3d_ps=tau_3d,
        freq_gain=tau_2d / tau_3d - 1.0,
        tau_benefit_ps=tau_benefit, tau_penalty_ps=tau_penalty,
        density_mtr_mm2=density,
    )


def pitch_sweep(node: str = "7nm", tiers: int = 2,
                pitches_um: np.ndarray = None) -> list[FoldResult]:
    """扫描混合键合 pitch，寻找 τ_Benefit / τ_Penalty 交叉点。"""
    if pitches_um is None:
        pitches_um = np.linspace(0.5, 6.0, 40)
    return [fold(node, tiers, p) for p in pitches_um]
