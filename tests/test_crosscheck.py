"""对拍测试：tau_lab_model.js（浏览器版）vs tau_sim（Python 基线）。

README/REPORT 中"JS 与 Python 逐位对拍一致"这句话的凭据就是本测试。
浏览器版 τ Lab 的模型是 Python 实现的手工移植，一旦任何一侧改动而另一侧
未同步，交互页给出的数字就会与报告脱节——本测试正是为了让这种漂移立刻
失败，而不是等到有人发现两处数字对不上。

需要 node（缺失时自动跳过）。运行方式：
    python tests/test_crosscheck.py
    pytest tests/test_crosscheck.py
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

RTOL = 1e-6          # 同一套公式的两种实现，只允许浮点级差异

# JS 侧：逐项计算与 Python 对应的指标，输出 JSON
JS_PROBE = r"""
const M = require('%s/tau_lab_model.js');
const d = M.deviceScan();
const f = M.fold(2, 1.5, M.RENT_P, M.FOLD_EFF);
const th = M.sustained(2, 'logic-on-memory', 'mobile', f);
const pk = M.pkg(30, M.SURFACE_BW_DENSITY, M.HBM_STACK_BW);
const sum = o => Object.values(o).reduce((a, b) => a + b, 0);
const casBase = M.iterationTau(4096, 'legacy_tcp', 1, 1, 1, 1);
const casFull = M.iterationTau(4096, 'ub_hione', 1.6, 2.5, 1, 1);
const dec = M.decadeTrajectories(4096);
const al = M.alphaDecomp();
console.log(JSON.stringify({
  dev_stage_norm_3nm: d[4].tauStage / d[0].tauStage,
  dev_wirefrac_28nm:  d[0].wireFrac,
  dev_wirefrac_3nm:   d[4].wireFrac,
  fold_wl:      f.wlReduction,
  fold_freq:    f.freqGain,
  fold_density: f.density,
  fold_gear:    f.gear,
  fold_benefit: f.benefit,
  fold_penalty: f.penalty,
  pkg_peak:     pk.peak,
  pkg_bw_edge:  pk.bwEdge,
  pkg_bw_surf:  pk.bwSurf,
  train_eff_ub: M.trainEff(16384, M.FABRICS.ub_hione),
  train_eff_tcp: M.trainEff(16384, M.FABRICS.legacy_tcp),
  moe_ub:       M.moeStep(128, M.FABRICS.ub_protocol),
  moe_rdma:     M.moeStep(128, M.FABRICS.legacy_rdma),
  thermal_f:    th.fSustained,
  cascade_base: sum(casBase),
  cascade_speedup: sum(casBase) / sum(casFull),
  decade_alpha_taufirst: dec.series[2].alpha,
  alpha_total_taufirst:  al.tau_first.alphaTotal,
  alpha_total_legacy:    al.legacy.alphaTotal,
}));
""" % ROOT


def _python_reference() -> dict:
    """用 tau_sim 算出与 JS_PROBE 一一对应的同名指标。"""
    from tau_sim.cascade import (SystemConfig, alpha_decomposition,
                                 decade_trajectories, total_tau)
    from tau_sim.layer1_device import scan_nodes
    from tau_sim.layer2_circuit import fold
    from tau_sim.layer3_chip import evaluate
    from tau_sim.layer4_system import moe_decode_step, train_iteration
    from tau_sim.thermal import sustained

    d = scan_nodes()
    f = fold("7nm", 2, 1.5)
    pk = evaluate(30.0)
    tr = decade_trajectories(n_gpus=4096)
    tf = tr["全栈 τ-first 协同"]
    ad = alpha_decomposition()
    base = total_tau(SystemConfig(4096, fabric="legacy_tcp"))
    full = total_tau(SystemConfig(4096, k_compute=1.6, k_memory=2.5,
                                  fabric="ub_hione"))
    return {
        "dev_stage_norm_3nm": d[4].tau_stage_ps / d[0].tau_stage_ps,
        "dev_wirefrac_28nm": d[0].wire_fraction,
        "dev_wirefrac_3nm": d[4].wire_fraction,
        "fold_wl": f.wl_reduction,
        "fold_freq": f.freq_gain,
        "fold_density": f.density_mtr_mm2,
        "fold_gear": f.gear_ratio,
        "fold_benefit": f.tau_benefit_ps,
        "fold_penalty": f.tau_penalty_ps,
        "pkg_peak": pk.peak_tflops,
        "pkg_bw_edge": pk.bw_edge_tbs,
        "pkg_bw_surf": pk.bw_surf_tbs,
        "train_eff_ub": train_iteration(16384, "ub_hione").scaling_eff,
        "train_eff_tcp": train_iteration(16384, "legacy_tcp").scaling_eff,
        "moe_ub": moe_decode_step(128, "ub_protocol", 128).t_iter,
        "moe_rdma": moe_decode_step(128, "legacy_rdma", 128).t_iter,
        "thermal_f": sustained(2, "logic-on-memory", "mobile").f_sustained,
        "cascade_base": base,
        "cascade_speedup": base / full,
        "decade_alpha_taufirst": (1 / tf[-1]) ** (1 / (len(tf) - 1)),
        "alpha_total_taufirst": ad["tau_first"]["alpha_total"],
        "alpha_total_legacy": ad["legacy"]["alpha_total"],
    }


def _js_values() -> dict:
    """在 node 中执行 JS 模型并取回指标。"""
    out = subprocess.run(["node", "-e", JS_PROBE], capture_output=True,
                         text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(f"node 执行失败:\n{out.stderr[:800]}")
    return json.loads(out.stdout)


def test_js_model_matches_python():
    """JS 移植的每一项指标都应与 Python 基线在浮点误差内一致。"""
    if shutil.which("node") is None:
        print("  SKIP  未找到 node，跳过对拍")
        return
    js, py = _js_values(), _python_reference()

    assert set(js) == set(py), (
        f"两侧指标集合不一致: 仅 JS {set(js) - set(py)}, 仅 PY {set(py) - set(js)}")

    bad = []
    for k in sorted(py):
        a, b = js[k], py[k]
        rel = abs(a - b) / (abs(b) if b else 1.0)
        if rel >= RTOL:
            bad.append(f"    {k}: js={a!r} py={b!r} rel={rel:.2e}")
    assert not bad, "以下指标 JS 与 Python 不一致：\n" + "\n".join(bad)
    print(f"  ({len(py)} 项指标全部一致)")


def _main():
    """无 pytest 时的独立运行入口。"""
    try:
        test_js_model_matches_python()
        print("  PASS  test_js_model_matches_python")
        return 0
    except AssertionError as e:
        print(f"  FAIL  test_js_model_matches_python\n{e}")
        return 1


if __name__ == "__main__":
    sys.exit(_main())
