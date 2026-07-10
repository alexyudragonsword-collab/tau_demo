"""Layer 3 — 芯片/封装层：N² vs N 扇出困境 (验证论文命题 P3).

模型：
  算力       C(N) = c·N²           (die 面积)
  2.5D 带宽  B_edge(N) = b_e·N     (HBM/SerDes 走周长, 只随边长线性)
  3D 带宽    B_surf(N) = b_s·N²    (混合键合表面, 随面积)
  Roofline   有效算力 = min(C, I·B)，I 为负载运算强度 (FLOP/Byte)

输出：算力利用率随 die 边长（及等效算力代际）的演化 ——
2.5D 曲线随规模坍塌、3D 保持 N² 对齐。
"""

from dataclasses import dataclass

import numpy as np

from . import params as P


@dataclass
class PackagePoint:
    side_mm: float
    peak_tflops: float
    bw_edge_tbs: float
    bw_surf_tbs: float
    util_edge: dict          # {负载: 利用率}
    util_surf: dict


def evaluate(side_mm: float,
             workloads: dict | None = None) -> PackagePoint:
    workloads = workloads or {"训练 GEMM": P.GEMM_INTENSITY,
                              "推理 decode": P.DECODE_INTENSITY}
    peak = P.COMPUTE_DENSITY_TFLOPS_MM2 * side_mm ** 2          # TFLOPS
    # 2.5D：HBM 栈沿两条边排布
    n_stacks = (P.EDGE_SIDES_FOR_HBM * side_mm) / P.HBM_STACK_EDGE_MM
    bw_edge = n_stacks * P.HBM_STACK_BW_TBS                     # TB/s
    # 3D folding：内存经表面混合键合供给
    bw_surf = P.SURFACE_BW_TBS_MM2 * side_mm ** 2               # TB/s

    # I (FLOP/B) × BW (TB/s) = I·BW TFLOPS
    def util(bw_tbs):
        return {name: min(1.0, intensity * bw_tbs / peak)
                for name, intensity in workloads.items()}

    return PackagePoint(side_mm, peak, bw_edge, bw_surf,
                        util(bw_edge), util(bw_surf))


def scan_die_size(sides_mm: np.ndarray | None = None) -> list[PackagePoint]:
    """扫描 die 边长。>26mm 的“边长”解释为多 reticle 拼接的等效边长
    （wafer-scale / SuperChip 方向），扇出困境在该区间最尖锐。"""
    if sides_mm is None:
        sides_mm = np.linspace(8, 60, 40)
    return [evaluate(s) for s in sides_mm]


def bytes_per_flop_trend(sides_mm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """两种封装的 Byte/FLOP 供给能力随规模的变化（拓扑赤字的直接度量）。"""
    pts = [evaluate(s) for s in sides_mm]
    edge = np.array([p.bw_edge_tbs * 1e12 / (p.peak_tflops * 1e12) for p in pts])
    surf = np.array([p.bw_surf_tbs * 1e12 / (p.peak_tflops * 1e12) for p in pts])
    return edge, surf
