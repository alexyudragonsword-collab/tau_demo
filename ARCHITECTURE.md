# 架构与开发指南

面向**维护者/二次开发者**。想看结论请读 [REPORT.md](REPORT.md)，想跑起来请读 [README.md](README.md)。

---

## 1. 设计原则（改代码前必须理解的一条）

> **论文自身的数据只作"待复现目标"，永远不进入模型。**

`tau_sim/params.py` 里 30+ 个参数全部来自独立公开文献（IRDS、Sakurai、Davis、
imec、Thakur、ZeRO…），逐项注明出处。论文宣称的数字（Kirin 的 −30%/+13%、
UB 的 500×）只出现在 `params.PAPER_TARGETS` 中，仅用于画对照柱和打印对照表。

这条原则决定了一件事：**如果你为了"让结果更接近论文"而调参数，整个项目的论证力就归零了。**
唯一允许的例外已在 REPORT.md §4.2 显式标注（折叠密度的面积开销经过校准，
因此密度项是一致性检验而非独立预测）。

---

## 2. 数据流：四层如何级联成系统 τ

```
                    params.py  (30+ 文献校准常量, 单一事实源)
                        │
        ┌───────────────┼───────────────┬────────────────┐
        ▼               ▼               ▼                ▼
   layer1_device   layer2_circuit  layer3_chip     layer4_system
   FO4 + 铜尺寸     Davis 线长 +    N²-vs-N +       α-β 集合通信
   效应 → 级延迟    折叠判据        roofline        + SimPy DES
        │               │               │                │
        │               ▼               │                │
        │          thermal.py           │                │
        │      (调 fold() 拿 freq_gain  │                │
        │       与 wl_reduction, 求     │                │
        │       温升预算内可持续频率)    │                │
        │               │               │                │
        └───────────────┴───────┬───────┴────────────────┘
                                ▼
                          cascade.py
             把四层折算成一次训练迭代的 τ 四分量：
             compute / memory / comm / other
                                │
        ┌───────────────┬───────┴────────┬───────────────┐
        ▼               ▼                ▼               ▼
   实验A Amdahl    实验B 十年轨迹   实验C 瓶颈迁移   实验D α 分解
```

**关键：只有 `cascade.py` 是"跨层"的。** 四个 layer 模块彼此不 import
（thermal 依赖 layer2 是唯一例外，因为热约束必须知道折叠后的功率密度）。
新增一层或改某层内部，只要 dataclass 字段不变，`cascade.py` 无需改动。

### cascade 的四分量从哪来

| 分量 | 来源 | 说明 |
|---|---|---|
| `compute` | 总 FLOP / (卡数 × 单卡算力) / `k_compute` | `k_compute` 是器件+电路层的加速杠杆 |
| `memory` | `compute × 0.25/0.45` / `k_memory` | 占比取自大规模训练实测（MFU≈40%） |
| `comm` | `layer4.hierarchical_allreduce_t()` + 小消息 × (o+α) | 唯一真正调用其他层模型的分量 |
| `other` | `compute × 0.05/0.45` / `k_other` | 软件栈 |

`SystemConfig` 的 `k_*` 是**相对基线的加速倍数（>1 更快）**，不是绝对值——
这是全项目最容易搞反的约定。

---

## 3. 公共 API 与数据契约

修改这些 dataclass 的字段名会同时打断 `run_all.py`、`app.py`、测试和 JS 移植。

| 模块 | 入口函数 | 返回 |
|---|---|---|
| `layer1_device` | `device_tau(node)` / `scan_nodes()` | `DeviceTau(tau_intrinsic_ps, tau_ideal_ps, tau_wire_ps, tau_stage_ps, wire_fraction, wire_ps_per_mm)` |
| `layer2_circuit` | `fold(node, tiers, hb_pitch_um)` / `pitch_sweep(...)` | `FoldResult(gear_ratio, wl_reduction, skew_reduction, tau_crit_2d_ps, tau_crit_3d_ps, freq_gain, tau_benefit_ps, tau_penalty_ps, density_mtr_mm2)` |
| `layer3_chip` | `evaluate(side_mm)` / `scan_die_size(...)` | `PackagePoint(peak_tflops, bw_edge_tbs, bw_surf_tbs, util_edge, util_surf)` |
| `layer4_system` | `train_iteration(n, fabric)` / `moe_decode_step(n, fabric, ep)` | `IterResult(t_compute, t_comm, t_iter, scaling_eff)` |
| `layer4_system` | `simpy_ring_allreduce(...)` / `simpy_alltoall(...)` | `float` 秒；**固定 seed=7，可复现** |
| `thermal` | `sustained(tiers, style, cooling)` / `scan(...)` | `ThermalResult(f_sustained, f_burst, dt_gradient)` |
| `cascade` | `iteration_tau(cfg)` / `total_tau(cfg)` | `dict{compute,memory,comm,other}` / `float` |
| `cascade` | `amdahl_scan` / `decade_trajectories` / `bottleneck_migration` / `alpha_decomposition` | 见各函数 docstring |

**注意**：`decade_trajectories()` 与 `bottleneck_migration()` 返回的 **key 是中文字符串**
（如 `"全栈 τ-first 协同"`）。`run_all.py` 用 `TR_TRAJ` / `TR_STAGE` 映射表翻成英文，
JS 侧用 `TR_TRAJ`。改这些字符串要同步三处。

---

## 4. 两个 GUI 与构建管线

```
tau_sim/*.py ──────────────────► app.py            (Streamlit, 直接 import)
     │
     │ 手工移植（非自动生成！）
     ▼
tau_lab_model.js ──┐
                   ├── build_tau_lab.py ──► tau_lab.html   (零依赖单文件)
tau_lab_template.html ─┘   把 {{MODEL_JS}} 内联进模板

REPORT.md + REPORT.en.md ──┐
figures/ + figures_en/     ├── build_report.py ──► report_full.html + .pdf
                           │
CRITIQUE.md + .en.md ──────┴── build_critique.py ──► critique.html
                                (复用 build_report 的双语渲染管线)

dashboard_template.html + .en.html ── build_dashboard.py ──► dashboard.html
```

### 最容易踩的坑：JS 移植是手写的

`tau_lab_model.js` 不是从 Python 自动生成的，**它是同一套公式的第二份实现**。
改了 `tau_sim` 里的任何公式或常量，JS 侧不会自动跟随。

防线是 `tests/test_crosscheck.py`：它在 node 里跑 JS 模型，与 Python 逐项比对
22 个指标（rtol=1e-6）。**改完模型必须跑它**，否则交互页会给出与报告不一致的数字。

JS 侧命名约定与 Python 不同（camelCase，且 `fold()` 固定 7nm）：

| Python | JS |
|---|---|
| `fold("7nm", tiers, pitch)` → `.wl_reduction` | `M.fold(tiers, pitch, rentP, eff)` → `.wlReduction` |
| `evaluate(side)` → `.peak_tflops` | `M.pkg(side, surf, hbm)` → `.peak` |
| `train_iteration(n, "ub_hione")` | `M.trainEff(n, M.FABRICS.ub_hione)`（传对象，非字符串） |
| `sustained(tiers, style, cooling)` | `M.sustained(tiers, style, cooling, foldResult)`（须显式传 fold 结果） |

---

## 5. 常见修改怎么做

### 加一个参数
1. 加到 `tau_sim/params.py`，**必须写文献出处注释**；
2. 若参与敏感性检查，加到 `sensitivity.py` 的监测列表；
3. 若要在 GUI 里可调，加到 `tau_lab_model.js` 的 `M.PARAMS` 与 `app.py` 的 `SENS_PARAMS`（两处的 label 要一致）；
4. 跑 `python tests/test_regression.py`——黄金值变了说明影响了结论，**先确认这是你想要的**，再更新测试里的期望值并同步 REPORT.md。

### 加一个仿真图
1. 在 `run_all.py` 写 `figN_xxx()`，所有面向用户的字符串包一层 `T(中文, English)`；
2. 在 `__main__` 里调用；
3. 两种语言都跑一遍：`python run_all.py && python run_all.py --lang en`；
4. **检查英文版排版**——英文标题比中文宽，双子图标题极易重叠（fig9/fig10 就踩过，
   解决办法是 `fontsize=TS` + 加宽画布 + 精简英文句子）；
5. 若要进报告，在 `REPORT.md`/`REPORT.en.md` 引用文件名，并在 `build_report.py`
   的 `CAPTIONS`/`CAPTIONS_EN` 加图注。

### 加一个 GUI 面板
- **Streamlit**：在 `app.py` 加一个 tab，直接 import 模型即可；
- **浏览器版**：先在 `tau_lab_model.js` 实现模型函数 → 在 `tau_lab_template.html`
  加 section 与 `panelN()` → 加进 `bind([...])` → 所有静态文案登记到 `applyStatic()`
  的字典（`PANEL_TXT`/`LABELS`/`OPTS`/`H4`），动态文案用 `TT(zh, en)` → `python build_tau_lab.py` 重建。

### 改模型公式
必跑三件事：`python tests/test_regression.py`（结论是否变）、
`python tests/test_crosscheck.py`（JS 是否同步）、`python sensitivity.py`（稳健性是否还成立）。

---

## 6. 测试

| 文件 | 作用 | 依赖 |
|---|---|---|
| `tests/test_regression.py` | 锁定 14 组黄金值（四层 + 级联 + 热约束），报告里每个数字的防线 | 仅 Python |
| `tests/test_crosscheck.py` | JS 移植 vs Python 基线 22 项指标对拍（rtol=1e-6） | 需要 `node` |

两者都可独立运行（`python tests/xxx.py`）也兼容 pytest。CI 见 `.github/workflows/ci.yml`。

**黄金值失败时不要直接改期望值**——先判断是 bug 还是有意的模型改动。若是后者，
同时更新：测试期望值 → REPORT.md 正文 → CRITIQUE.md（如涉及）→ 重新生成图与 HTML。

---

## 7. 已知局限（继承自模型，非 bug）

- 折叠**密度**项经过面积开销校准，是一致性检验而非独立预测（REPORT §4.2）；
- UB 的延迟/带宽参数取自华为自述论文，无独立第三方基准（CRITIQUE S2）；
- 未建模计算-通信重叠，故绝对扩展效率偏保守，跨 fabric 的**相对**比较仍有效；
- `alpha_decomposition()` 的三因子年率（1.58/1.25/1.30）是本模型的设定，非论文给定。
