"""热约束模型 — 多层折叠的可持续频率 (对应论文开放问题 §6 热预算).

一维热阻网络（3D 堆叠标准处理）：
  最热层(离散热面最远)温升
    ΔT = R_hs·Q_total + Σ_{i=1}^{k-1} R_tier·Q_below(i)
  R_hs   : 散热方案的结-环境等效热阻 (按 2D 基线用满温升预算标定)
  R_tier : 层间热阻 = 减薄硅片导热 + 混合键合界面 + BEOL

功率-频率-电压耦合（复用 α-power law）：
  q ∝ C_dyn·V²·f,  f ∝ (V−Vth)^α / V
折叠的线电容缩短同时降低 C_dyn（Layer 2 线长降幅 × 线电容占比）。

两类折叠、两种散热场景：
  logic-on-logic  : 每层都是全功率逻辑（AI 加速器方向）
  logic-on-memory : 第二层为 SRAM/低功率层（Kirin 2026 实际形态）
  mobile (无源)   / ai (液冷)

输出：给定层数下，满足温升预算的最大可持续频率（相对 2D 基线），
与电路极限（Layer 2 burst 频率增益）对照。
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from . import params as P
from .layer2_circuit import fold

# ---- 热参数（独立文献实测）----
R_SI_THINNED = 0.34     # K·mm²/W, 50μm 减薄硅 (k_si≈147 W/mK, 标准值)
R_HB = 1.2              # K·mm²/W, Cu/SiO₂ W2W 混合键合界面
                        # [Oprins et al. (imec), ASME JEP 139(1), 2017 实测]
R_BEOL = 2.0            # K·mm²/W, BEOL 金属栈 (实测 0.5-5.5 随通孔密度)
                        # [Colgan et al. (IBM), SEMI-THERM 2013]
DT_BUDGET = 60.0        # K, Tj,max 105°C − 散热面 45°C
Q0 = {"mobile": 0.25,   # W/mm², 2D 基线可持续功率密度（移动 P 核簇,
                        # 介于整片均值 0.05 与热点 1.5 之间）
      "ai": 0.86}       # H100 级: 700W/814mm² [NVIDIA datasheet]
WIRE_POWER_FRACTION = 0.45   # 动态功耗中互连电容占比 [Horowitz/Dally 量级]
MEM_TIER_Q_RATIO = 0.2       # SRAM 层相对逻辑层的功率密度

R_BOND = R_HB + R_BEOL       # 层间界面复合热阻 (敏感性扫 1-10)
R_TIER = R_SI_THINNED + R_BOND


def freq_of_v(v: float, node: str = "7nm") -> float:
    """α-power law: f ∝ (V−Vth)^α / V，归一化到额定 V。"""
    nd = P.NODES[node]
    v0, vth = nd["vdd"], nd["vth"]
    return ((v - vth) ** P.ALPHA_POWER / v) / ((v0 - vth) ** P.ALPHA_POWER / v0)


def v_of_freq(x: float, node: str = "7nm") -> float:
    """数值反解 f→V（x 为相对频率）。"""
    nd = P.NODES[node]
    lo, hi = nd["vth"] + 1e-3, nd["vdd"] * 1.3
    return brentq(lambda v: freq_of_v(v, node) - x, lo, hi)


@dataclass
class ThermalResult:
    tiers: int
    style: str            # logic-on-logic / logic-on-memory
    cooling: str
    f_sustained: float    # 可持续频率 (相对 2D 基线)
    f_burst: float        # 电路极限 (Layer 2)
    dt_gradient: float    # 层间梯度占温升 (K, 在 f_sustained 处)


def _delta_t(k: int, q_tier: np.ndarray, r_hs: float) -> float:
    """最热层温升。q_tier[0] 靠近散热面。"""
    q_total = float(np.sum(q_tier))
    grad = sum(R_TIER * float(np.sum(q_tier[i + 1:])) for i in range(k - 1))
    return r_hs * q_total + grad


def sustained(tiers: int, style: str = "logic-on-logic",
              cooling: str = "mobile", node: str = "7nm") -> ThermalResult:
    """满足温升预算的最大可持续频率。

    2D 基线: 单层逻辑在 (V0,f0,q0) 恰好用满预算 → 标定 R_hs。
    折叠: footprint 缩小、每 mm² 叠 k 层; 线电容降低使每操作能耗下降。
    """
    q0 = Q0[cooling]
    r_hs = DT_BUDGET / q0                      # 2D 基线标定 (单层, 无层间梯度)

    fr = fold(node, tiers=tiers) if tiers > 1 else None
    f_burst = 1.0 + (fr.freq_gain if fr else 0.0)
    # 折叠使互连电容下降 → 动态功耗因子
    c_dyn = 1.0 - WIRE_POWER_FRACTION * (fr.wl_reduction if fr else 0.0)

    # 各层相对功率权重（靠近散热面的排更热的逻辑层）
    if style == "logic-on-memory":
        weights = np.array([1.0] + [MEM_TIER_Q_RATIO] * (tiers - 1))
    else:
        weights = np.ones(tiers)

    def dt_at(x: float) -> float:
        v = v_of_freq(x, node)
        nd = P.NODES[node]
        p_factor = c_dyn * (v / nd["vdd"]) ** 2 * x    # q ∝ C·V²·f
        q_tier = q0 * weights * p_factor
        return _delta_t(tiers, q_tier, r_hs)

    if tiers == 1:
        return ThermalResult(1, style, cooling, 1.0, 1.0, 0.0)

    # 解 dt_at(x) = DT_BUDGET；上限取电路极限 f_burst
    if dt_at(f_burst) <= DT_BUDGET:
        x = f_burst
    else:
        x = brentq(lambda t: dt_at(t) - DT_BUDGET, 0.05, f_burst)
    v = v_of_freq(x, node)
    nd = P.NODES[node]
    q_tier = q0 * weights * c_dyn * (v / nd["vdd"]) ** 2 * x
    grad = sum(R_TIER * float(np.sum(q_tier[i + 1:])) for i in range(tiers - 1))
    return ThermalResult(tiers, style, cooling, x, f_burst, grad)


def scan(styles_coolings: list[tuple[str, str]] | None = None,
         max_tiers: int = 4) -> dict:
    """扫描层数 × (折叠形态, 散热场景)。"""
    combos = styles_coolings or [
        ("logic-on-memory", "mobile"),
        ("logic-on-logic", "mobile"),
        ("logic-on-memory", "ai"),
        ("logic-on-logic", "ai"),
    ]
    out = {}
    for style, cooling in combos:
        out[(style, cooling)] = [sustained(k, style, cooling)
                                 for k in range(1, max_tiers + 1)]
    return out
