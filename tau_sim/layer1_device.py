"""Layer 1 — 晶体管/器件层：几何缩放收益趋平 (验证论文命题 P1).

模型：
  本征门延迟   τ_int ∝ FO4，按 α-power law 缩放 (速度饱和, α≈1.25)
  长沟道对照   τ_sq  ∝ Lg²·Vdd/(Vdd-Vth)²   (理想平方律假想)
  级延迟       τ_stage = FO4 + τ_wire(L_span)
其中 τ_wire 用最优中继线性模型 2√(0.38·r·c·rg·cg)·L，
L_span 为固定的中间层布线跨度 —— IP 块内布线跨度不随节点收缩
（芯片尺寸与模块 reach 基本不变），这是 Ho/Mai/Horowitz
"The Future of Wires" (Proc. IEEE 2001) 的标准处理。
线电阻 r 随节点变细因铜尺寸效应急剧上升 → 互连接管延迟预算。
"""

from dataclasses import dataclass

import numpy as np

from . import params as P

WIRE_SPAN_UM = 50.0   # 典型 intermediate 布线跨度 (μm)，跨节点不变


@dataclass
class DeviceTau:
    node: str
    tau_intrinsic_ps: float      # FO4 (速度饱和)
    tau_ideal_ps: float          # 长沟道平方律假想
    tau_wire_ps: float           # 固定跨度中间布线延迟
    tau_stage_ps: float          # 级延迟 = 门 + 线
    wire_fraction: float         # 互连占级延迟比例
    wire_ps_per_mm: float        # 最优中继线延迟 (ps/mm)


def wire_rc_per_m(node: str) -> tuple[float, float]:
    """该节点细间距互连的 (R/m, C/m)。"""
    nd = P.NODES[node]
    w = nd["w"] * 1e-9
    h = w * P.WIRE_AR
    return P.rho_cu(nd["w"]) / (w * h), P.WIRE_CAP_PER_M


def buffered_wire_ps_per_um(node: str) -> float:
    """最优中继互连延迟 (ps/μm)；rg·cg 乘积与驱动尺寸无关。"""
    nd = P.NODES[node]
    r, c = wire_rc_per_m(node)
    cg = 0.5e-15
    rg = nd["fo4"] * 1e-12 / (5.0 * cg)
    return float(2.0 * np.sqrt(0.38 * r * c * rg * cg) * 1e-6 * 1e12)


def device_tau(node: str, ref_node: str = "28nm") -> DeviceTau:
    nd, ref = P.NODES[node], P.NODES[ref_node]

    tau_int = nd["fo4"]

    # 长沟道平方律假想（速度饱和不存在时几何缩放本应有的收益）
    def sq_delay(n):
        return n["lg"] ** 2 * n["vdd"] / (n["vdd"] - n["vth"]) ** P.MU_LONG_CHANNEL

    tau_sq = ref["fo4"] * sq_delay(nd) / sq_delay(ref)

    per_um = buffered_wire_ps_per_um(node)
    tau_wire = per_um * WIRE_SPAN_UM
    tau_stage = tau_int + tau_wire
    return DeviceTau(node, tau_int, tau_sq, tau_wire, tau_stage,
                     tau_wire / tau_stage, per_um * 1e3)


def scan_nodes() -> list[DeviceTau]:
    return [device_tau(n) for n in P.NODE_ORDER]
