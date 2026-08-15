"""回归测试：锁定四层模型与级联实验的关键输出（黄金值）。

这些数字是 REPORT.md / CRITIQUE.md 中所有结论的来源。任何一处漂移
都意味着报告里的某个论断已经失效——所以此处用紧容差锁死。

运行方式（二选一）：
    python tests/test_regression.py     # 无需 pytest
    pytest tests/test_regression.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tau_sim import params as P                                   # noqa: E402
from tau_sim.cascade import (SystemConfig, alpha_decomposition,   # noqa: E402
                             amdahl_scan, bottleneck_migration,
                             decade_trajectories, iteration_tau, total_tau)
from tau_sim.layer1_device import scan_nodes                      # noqa: E402
from tau_sim.layer2_circuit import fold                           # noqa: E402
from tau_sim.layer3_chip import evaluate                          # noqa: E402
from tau_sim.layer4_system import (moe_decode_step,               # noqa: E402
                                   simpy_alltoall, train_iteration)
from tau_sim.thermal import sustained                             # noqa: E402

RTOL = 1e-5


def close(actual, expected, rtol=RTOL, label=""):
    """断言相对误差在容差内；失败信息带上标签便于定位。"""
    denom = abs(expected) if expected else 1.0
    rel = abs(actual - expected) / denom
    assert rel < rtol, f"{label}: 实得 {actual!r}, 期望 {expected!r} (rel={rel:.2e})"


# ---------------------------------------------------------------- Layer 1

def test_layer1_stage_delay_stops_improving():
    """P1：级延迟 28→3nm 归一化轨迹，5nm 后不降反升。"""
    d = scan_nodes()
    got = [p.tau_stage_ps / d[0].tau_stage_ps for p in d]
    want = [1.0, 0.861054, 0.871321, 0.991776, 1.101768]
    for g, w, nd in zip(got, want, [p.node for p in d]):
        close(g, w, label=f"L1 stage_norm@{nd}")
    assert got[-1] > 1.0, "3nm 级延迟应劣于 28nm（互连反超）"


def test_layer1_interconnect_share():
    """P1：互连占级延迟比例 22%→72%。"""
    d = scan_nodes()
    got = [p.wire_fraction for p in d]
    want = [0.219833, 0.335556, 0.522462, 0.632903, 0.716758]
    for g, w, nd in zip(got, want, [p.node for p in d]):
        close(g, w, label=f"L1 wire_frac@{nd}")


# ---------------------------------------------------------------- Layer 2

def test_layer2_fold_gains():
    """P2：2 层折叠 @1.5μm 的线长/偏斜/频率/密度，对照论文 Kirin 数字。"""
    f = fold("7nm", 2, 1.5)
    close(f.wl_reduction, 0.248959, label="L2 wl_reduction")
    close(f.skew_reduction, 0.248959, label="L2 skew_reduction")
    close(f.freq_gain, 0.122504, label="L2 freq_gain")
    close(f.density_mtr_mm2, 238.70, label="L2 density")
    close(f.gear_ratio, 2.083333, label="L2 gear_ratio")


def test_layer2_criterion_holds_at_kirin_pitch():
    """P2：1.5μm 工作点判据成立；判据在 ~3.1μm 反转。"""
    f = fold("7nm", 2, 1.5)
    close(f.tau_benefit_ps, 32.797143, label="L2 tau_benefit")
    close(f.tau_penalty_ps, 5.280505, label="L2 tau_penalty")
    assert f.tau_benefit_ps > f.tau_penalty_ps, "1.5μm 处折叠判据应成立"

    flip = next(p / 10 for p in range(5, 121)
                if fold("7nm", 2, p / 10).tau_penalty_ps
                > fold("7nm", 2, p / 10).tau_benefit_ps)
    assert 3.0 <= flip <= 3.3, f"判据反转点应在 ~3.1μm，实得 {flip}"


# ---------------------------------------------------------------- Layer 3

def test_layer3_fanout_dilemma():
    """P3：算力 ∝N²、边缘带宽 ∝N、表面带宽 ∝N² 的标度关系。"""
    p30 = evaluate(30.0)
    close(p30.peak_tflops, 1080.0, label="L3 peak@30mm")
    close(p30.bw_edge_tbs, 6.545455, label="L3 bw_edge@30mm")
    close(p30.bw_surf_tbs, 27.0, label="L3 bw_surf@30mm")

    p60 = evaluate(60.0)
    close(p60.peak_tflops / p30.peak_tflops, 4.0, rtol=1e-9, label="peak ∝N²")
    close(p60.bw_edge_tbs / p30.bw_edge_tbs, 2.0, rtol=1e-9, label="edge ∝N")
    close(p60.bw_surf_tbs / p30.bw_surf_tbs, 4.0, rtol=1e-9, label="surf ∝N²")


# ---------------------------------------------------------------- Layer 4

def test_layer4_training_scaling_efficiency():
    """P4：16k 卡训练扩展效率（大消息 regime）三代 fabric。"""
    close(train_iteration(16384, "legacy_tcp").scaling_eff, 0.06977,
          label="L4 train tcp")
    close(train_iteration(16384, "legacy_rdma").scaling_eff, 0.170357,
          label="L4 train rdma")
    close(train_iteration(16384, "ub_hione").scaling_eff, 0.263881,
          label="L4 train ub_hione")


def test_layer4_moe_small_message_speedup():
    """P4：MoE 小消息 UB 相对 RDMA/TCP 的加速比（≈9.8× / 159×）。"""
    tcp = moe_decode_step(128, "legacy_tcp", 128).t_iter
    rdma = moe_decode_step(128, "legacy_rdma", 128).t_iter
    ub = moe_decode_step(128, "ub_protocol", 128).t_iter
    close(tcp, 0.401713843, label="L4 moe tcp")
    close(rdma, 0.024708461, label="L4 moe rdma")
    close(ub, 0.002526461, label="L4 moe ub")
    close(rdma / ub, 9.780, rtol=1e-3, label="UB vs RDMA")
    close(tcp / ub, 159.0, rtol=1e-2, label="UB vs TCP")


def test_layer4_des_validates_analytic_model():
    """SimPy 离散事件仿真应与解析模型同量级（验证而非替代）。"""
    for fab in ["legacy_rdma", "ub_protocol"]:
        n = 32
        msg = P.MOE_TOKENS_PER_GPU_DECODE * P.MOE_HIDDEN * 2 / n
        des = simpy_alltoall(n, msg, P.FABRICS[fab])
        ana = moe_decode_step(n, fab, n).t_iter / (P.MOE_LAYERS * 2)
        assert 0.3 < des / ana < 3.0, \
            f"{fab}: DES {des:.3e} 与解析 {ana:.3e} 偏离超过 3×"


# ---------------------------------------------------------------- 级联

def test_cascade_baseline_composition():
    """P5：4096 卡传统协议栈基线的 τ 构成——通信占 67%。"""
    parts = iteration_tau(SystemConfig(4096, fabric="legacy_tcp"))
    close(parts["compute"], 1.464844, label="CAS compute")
    close(parts["memory"], 0.813802, label="CAS memory")
    close(parts["comm"], 4.926897, label="CAS comm")
    close(parts["other"], 0.16276, label="CAS other")
    fr = amdahl_scan(SystemConfig(4096, fabric="legacy_tcp"))["fractions"]
    close(fr["comm"], 0.668661, label="CAS comm frac")
    assert max(fr, key=fr.get) == "comm", "基线主导层应为通信"


def test_cascade_amdahl_ceilings():
    """实验 A：单层优化的加速上限 = 1/(1-占比)。"""
    fr = amdahl_scan(SystemConfig(4096, fabric="legacy_tcp"))["fractions"]
    close(1 / (1 - fr["comm"]), 3.017, rtol=1e-3, label="comm 上限")
    close(1 / (1 - fr["compute"]), 1.248, rtol=1e-3, label="compute 上限")


def test_cascade_decade_trajectories():
    """实验 B：十年轨迹——协同 α 1.22 显著优于单点 1.02/1.08。"""
    tr = decade_trajectories()
    want = {"只推器件节点": 0.850338, "只换网络 fabric": 0.470071,
            "全栈 τ-first 协同": 0.141258}
    alphas = {}
    for name, v in tr.items():
        close(float(v[-1]), want[name], label=f"CAS decade {name}")
        alphas[name] = (1 / v[-1]) ** (1 / (len(v) - 1))
    close(alphas["全栈 τ-first 协同"], 1.216, rtol=1e-3, label="协同 α")
    assert alphas["全栈 τ-first 协同"] > alphas["只换网络 fabric"] \
        > alphas["只推器件节点"], "协同应优于任一单点路线"


def test_cascade_alpha_decomposition():
    """实验 D：α 口径分解——硬件三因子仅 ≈2.0/年，legacy 效率坍塌。"""
    ad = alpha_decomposition()
    close(ad["legacy"]["alpha_total"], 1.665850, label="alpha legacy total")
    close(ad["tau_first"]["alpha_total"], 2.007743, label="alpha tf total")
    close(ad["legacy"]["alpha_eff"], 0.843469, label="alpha legacy eff")
    close(ad["tau_first"]["alpha_eff"], 1.016579, label="alpha tf eff")
    assert ad["tau_first"]["alpha_total"] < 3.0, \
        "硬件因子远不足以解释论文的 α≈10/年（CRITIQUE S1 的依据）"


def test_cascade_bottleneck_migration():
    """实验 C：五阶段瓶颈迁移，总加速 ≈3.0×。"""
    st = bottleneck_migration(4096)
    tots = [sum(s[1].values()) for s in st]
    for g, w in zip(tots, [7.368303, 4.219289, 3.463623, 2.975342, 2.426026]):
        close(g, w, label="CAS stage total")
    doms = [max(s[1], key=s[1].get) for s in st]
    assert len(set(doms)) > 1, "主导 τ 层应在阶段间迁移"

    speedup = (total_tau(SystemConfig(4096, fabric="legacy_tcp")) /
               total_tau(SystemConfig(4096, k_compute=1.6, k_memory=2.5,
                                      fabric="ub_hione")))
    close(speedup, 3.037191, label="CAS 全开加速")


# ---------------------------------------------------------------- 热约束

def test_thermal_heterogeneous_fold_is_near_lossless():
    """热约束：异构折叠近乎无损 (0.98)，同构 4 层大幅降频 (0.59)。"""
    close(sustained(2, "logic-on-memory", "mobile").f_sustained, 0.976889,
          label="TH lom/mobile 2 层")
    close(sustained(4, "logic-on-logic", "ai").f_sustained, 0.593525,
          label="TH lol/ai 4 层")
    assert sustained(2, "logic-on-memory", "mobile").f_sustained > \
        sustained(2, "logic-on-logic", "mobile").f_sustained, \
        "异构折叠应优于同构折叠"


# ---------------------------------------------------------------- runner

def _main():
    """无 pytest 时的独立运行入口：依次执行全部 test_* 并汇总。"""
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}\n        {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
