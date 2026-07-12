# tau_demo — τ Scaling 理论的全栈级联仿真验证

对何庭波（Huawei）《A Time Scaling Theory for Multi-Layer Electronic Systems》
（ChinaXiv:202605.00224）核心思想的独立仿真论证。

用晶体管 → 电路 → 芯片/封装 → 系统四层级联模型，内嵌 LogicFolding、
N²-vs-N 扇出困境、UB 集群通信三个子模型，检验论文的五个核心命题
（P1 几何缩放趋平、P2 折叠判据、P3 拓扑赤字、P4 通信 τ 压缩、
P5 全栈共享优化目标与瓶颈迁移）。

**分析结论见 [REPORT.md](REPORT.md)。**

## 快速开始

```bash
pip install -r requirements.txt
python run_all.py       # 生成 figures/fig1-fig10 + 控制台对照表
python sensitivity.py   # 关键参数 ±50% 扰动的稳健性检查（17 项）
```

## 交互式 GUI（两个版本）

```bash
streamlit run app.py    # 本地完整版：五个 tab，复用 tau_sim 全部模型（含 SimPy DES 验证按钮）
python build_tau_lab.py # 生成 tau_lab.html：浏览器免安装版（模型 JS 移植，
                        # 与 Python 基线 14 项指标对拍误差 0），直接双击打开
```

两个 GUI 现已覆盖 REPORT.md 的全部仿真（浏览器版 6 面板 / Streamlit 7 tab）：
器件层几何缩放趋平（P1）、折叠实验台（判据交叉 + 热约束）、封装 N²-vs-N、
集群通信（大/小消息 regime，UB 参数可压力测试）、级联实验 A/B/C/D
（瓶颈迁移 / Amdahl / 十年轨迹 / α 分解，浏览器版用视图选择器切换）、
**敏感性扫描**（12 参数 × 5 指标的交互式龙卷风图 + 1D 结论翻转区扫描）。
唯一不在浏览器版的是 SimPy 离散事件验证点（JS 跑不了 simpy，仅 Streamlit 有）。

## 图文并茂的完整报告

```bash
python build_report.py        # 生成 report_full.html + report_full.pdf
python build_report.py --html # 只生成 HTML
```

把 `REPORT.md` 与 `figures/` 的 10 张图合并成单文件报告：`report_full.pdf`
（可存档/分发/打印）与 `report_full.html`（零依赖，浏览器直接打开）。

## 结果速览（模型输入全部来自独立公开文献）

| 命题 | 模型结果 | 论文对照 |
|------|---------|---------|
| P2 折叠线长/偏斜/频率 | −24.9% / −24.9% / +12.3% | −30% / −25% / +13% (Kirin 2026) |
| P2 折叠判据反转点 | gear ratio ≈ 4.3（敏感区 3.3–6.2） | 工程结论 <3（安全侧） |
| P3 2.5D ridge 上移 | N≈55mm 后 GEMM 也访存受限 | "拓扑赤字无法靠晶体管弥补" |
| P4 小消息 all-to-all | 同物理线换协议栈 9–150× | UB ≈500× τ 压缩 |
| P5 十年年化 α | 协同 1.22 vs 单点 1.02–1.08 | τ_{n+1}=τ_n/α 需跨层协同 |
| 热约束（二期） | 异构折叠可持续 f≈0.98，同构 0.80 | 论文开放问题 §6；AMD X3D 佐证 |
| α≈10/年口径（二期） | 硬件三因子 ≈2.0/年，效率坍塌时仅 1.67 | τ 压缩的作用是守住 α_eff≈1 |

## 目录结构

```
tau_sim/
├── params.py          # 全部校准参数（逐项注明文献出处）
├── layer1_device.py   # 器件层：FO4 + 铜互连尺寸效应
├── layer2_circuit.py  # 电路层：Davis 线长分布 + LogicFolding
├── layer3_chip.py     # 封装层：N²-vs-N + roofline
├── layer4_system.py   # 系统层：α-β 集合通信 + SimPy 离散事件仿真
├── thermal.py         # 热约束：多层折叠可持续频率
└── cascade.py         # 级联：Amdahl / 十年轨迹 / 瓶颈迁移 / α 分解
run_all.py             # 一键运行全部实验 (fig1-fig10)
sensitivity.py         # 敏感性检查（17 项扰动）
build_dashboard.py     # 生成自包含可视化页面 dashboard.html
figures/               # 仿真输出图表
REPORT.md              # 完整分析报告（论文解读 + 结果 + 局限）
```
