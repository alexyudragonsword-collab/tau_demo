"""关键参数敏感性检查：扰动 ±50% 量级，观察结论方向是否翻转。

用法: python sensitivity.py
检查项：
  S1 折叠判据: 1.5μm pitch 下 2 层折叠频率增益是否保持为正
  S2 判据反转点: 交叉 pitch 是否始终存在且 > Kirin 的 1.5μm
  S3 级联结论: 全栈 τ-first 的年化 α 是否始终高于两种单点策略
"""

import numpy as np

from tau_sim import params as P
from tau_sim import layer2_circuit as L2
from tau_sim.layer2_circuit import fold, pitch_sweep
from tau_sim.cascade import decade_trajectories


def crossover_pitch() -> float:
    res = pitch_sweep("7nm", 2, np.linspace(0.5, 12, 80))
    for r in res:
        if r.tau_penalty_ps > r.tau_benefit_ps:
            return r.hb_pitch_um
    return float("inf")


def alpha_of(traj: np.ndarray) -> float:
    return (1.0 / traj[-1]) ** (1.0 / (len(traj) - 1))


def check(label: str) -> dict:
    r = fold("7nm", 2, 1.5)
    xp = crossover_pitch()
    tr = decade_trajectories()
    alphas = {k: alpha_of(v) for k, v in tr.items()}
    coord = alphas["全栈 τ-first 协同"]
    single = max(a for k, a in alphas.items() if k != "全栈 τ-first 协同")
    ok = (r.freq_gain > 0) and (xp > 1.5) and (coord > single)
    print(f"  {label:<38s} freq {r.freq_gain*100:+5.1f}%  "
          f"反转点 {xp:5.2f}μm  α协同 {coord:.3f} vs 单点最好 {single:.3f}"
          f"   {'OK' if ok else '** 方向翻转 **'}")
    return dict(freq=r.freq_gain, xp=xp, coord=coord, single=single, ok=ok)


def perturb(obj, attr, value):
    old = getattr(obj, attr)
    setattr(obj, attr, value)
    return old


if __name__ == "__main__":
    print("基线:")
    check("baseline")

    print("\n扰动检查 (逐项恢复):")
    cases = [
        (P, "RENT_P", 0.55, "Rent 指数 0.62→0.55"),
        (P, "RENT_P", 0.72, "Rent 指数 0.62→0.72"),
        (L2, "SKEW_FRACTION", 0.05, "时钟裕量 10%→5%"),
        (L2, "SKEW_FRACTION", 0.15, "时钟裕量 10%→15%"),
        (L2, "CROSS_DETOUR_COEF", 1.0, "绕线系数 2→1"),
        (L2, "CROSS_DETOUR_COEF", 4.0, "绕线系数 2→4"),
        (P, "FOLD_EFFICIENCY", 0.60, "折叠效率 0.85→0.60"),
        (P, "FOLD_EFFICIENCY", 1.00, "折叠效率 0.85→1.00"),
        (P, "HB_CAP_PER_PAD_2UM", 1.0e-15, "键合电容 0.2→1.0 fF"),
        (P, "LOGIC_DEPTH", 24, "逻辑深度 16→24"),
    ]
    n_flip = 0
    for mod, attr, val, label in cases:
        old = perturb(mod, attr, val)
        res = check(label)
        n_flip += 0 if res["ok"] else 1
        setattr(mod, attr, old)

    # fabric 参数扰动: TCP 开销减半 / UB 开销加倍（对 UB 不利方向）
    old_tcp = P.FABRICS["legacy_tcp"]["o"]
    old_ub_o = P.FABRICS["ub_protocol"]["o"]
    old_ub_a = P.FABRICS["ub_protocol"]["alpha_inter"]
    P.FABRICS["legacy_tcp"]["o"] = old_tcp / 2
    P.FABRICS["ub_protocol"]["o"] = old_ub_o * 2
    P.FABRICS["ub_protocol"]["alpha_inter"] = old_ub_a * 2
    res = check("TCP 开销减半 + UB 开销加倍")
    n_flip += 0 if res["ok"] else 1
    P.FABRICS["legacy_tcp"]["o"] = old_tcp
    P.FABRICS["ub_protocol"]["o"] = old_ub_o
    P.FABRICS["ub_protocol"]["alpha_inter"] = old_ub_a

    print(f"\n结论方向翻转的扰动数: {n_flip}/{len(cases)+1}")
