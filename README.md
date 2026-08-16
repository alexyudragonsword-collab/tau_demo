# tau_demo — τ Scaling 理论的全栈级联仿真验证

[English](README.en.md) ｜ 中文

对何庭波（Huawei）《A Time Scaling Theory for Multi-Layer Electronic Systems》
（ChinaXiv:202605.00224）核心思想的独立仿真论证。

用晶体管 → 电路 → 芯片/封装 → 系统四层级联模型，内嵌 LogicFolding、
N²-vs-N 扇出困境、UB 集群通信三个子模型，检验论文的五个核心命题
（P1 几何缩放趋平、P2 折叠判据、P3 拓扑赤字、P4 通信 τ 压缩、
P5 全栈共享优化目标与瓶颈迁移）。

**分析结论见 [REPORT.md](REPORT.md)；对抗性审阅见 [CRITIQUE.md](CRITIQUE.md)；
二次开发见 [ARCHITECTURE.md](ARCHITECTURE.md)。**

> **模型输入全部来自独立公开文献**（逐项出处见 `tau_sim/params.py`）。
> 论文自身数据只作"待复现目标"，不进入模型——这是本仿真具备论证力的前提。

## 快速开始

```bash
pip install -r requirements.txt
python run_all.py           # 生成 figures/fig1-fig10 (中文标签) + 控制台对照表
python run_all.py --lang en # 生成 figures_en/ (英文标签)
python sensitivity.py       # 关键参数 ±50% 扰动的稳健性检查（17 项）
```

## 测试

```bash
python tests/test_regression.py   # 14 组黄金值：报告里每个数字的防线
python tests/test_crosscheck.py   # JS 移植 vs Python 基线 22 项对拍（需 node）
```

两者兼容 pytest，也可独立运行。CI（`.github/workflows/ci.yml`）在每次 push
上跑测试 + 双语出图 + 敏感性 + 全部页面构建。

**改了模型公式，这两个测试都必须跑**——`tau_lab_model.js` 是手工移植，
不会自动跟随 Python 侧的改动。

## 交互式 GUI（两个版本）

```bash
streamlit run app.py    # 本地完整版：7 个 tab，复用 tau_sim 全部模型（含 SimPy DES 验证）
python build_tau_lab.py # 生成 tau_lab.html：零依赖单文件，双击即用
```

两个 GUI 覆盖 REPORT.md 的全部仿真（浏览器版 6 面板 / Streamlit 7 tab）：
器件层几何缩放趋平（P1）、折叠实验台（判据交叉 + 热约束）、封装 N²-vs-N、
集群通信（大/小消息 regime，UB 参数可压力测试）、级联实验 A/B/C/D
（瓶颈迁移 / Amdahl / 十年轨迹 / α 分解，浏览器版用视图选择器切换）、
**敏感性扫描**（12 参数 × 5 指标的交互式龙卷风图 + 1D 结论翻转区扫描）。
唯一不在浏览器版的是 SimPy 离散事件验证点（JS 跑不了 simpy，仅 Streamlit 有）。

## 报告与汇报材料

```bash
python build_report.py        # report_full.html + report_full.pdf（PDF 需 playwright）
python build_report.py --html # 只生成 HTML
python build_critique.py      # critique.html（对抗性附录）
python build_dashboard.py     # dashboard.html（可视化报告页）
node build_slides.js          # slides_tau_scaling.pptx（8 页中文汇报，需 npm i pptxgenjs）
```

> **中英双语**：四个 HTML 页面（`dashboard.html`、`tau_lab.html`、`report_full.html`、
> `critique.html`）均带右上角 中/EN 切换；正文与图表随语言切换（英文用 `figures_en/`）。
> 英译文档：`REPORT.en.md`、`CRITIQUE.en.md`、`dashboard_template.en.html`。

## 结果速览（模型输入全部来自独立公开文献）

| 命题 | 模型结果 | 论文对照 |
|------|---------|---------|
| P1 互连接管延迟预算 | 占比 22%→72%，5nm 后级延迟不降反升 | "局部互连寄生 R、C 反超本征延迟" |
| P2 折叠线长/偏斜/频率 | −24.9% / −24.9% / +12.3% | −30% / −25% / +13% (Kirin 2026) |
| P2 折叠判据反转点 | gear ratio ≈ 4.3（敏感区 3.3–6.2） | 工程结论 <3（安全侧） |
| P3 2.5D ridge 上移 | N≈55mm 后 GEMM 也访存受限 | "拓扑赤字无法靠晶体管弥补" |
| P4 小消息 all-to-all | 同物理线换协议栈 9.8×(RDMA) / 159×(TCP) | UB ≈500× τ 压缩 |
| P5 十年年化 α | 协同 1.22 vs 单点 1.02–1.08 | τ_{n+1}=τ_n/α 需跨层协同 |
| 热约束 | 异构折叠可持续 f≈0.98，同构 0.80 | 论文开放问题 §6；AMD X3D 佐证 |
| α≈10/年口径 | 硬件三因子 ≈2.0/年，效率坍塌时仅 1.67 | τ 压缩的作用是守住 α_eff≈1 |

## 目录结构

```
tau_sim/                  # 仿真模型（四层 + 热约束 + 级联）
├── params.py             # 全部校准参数（逐项注明文献出处）
├── layer1_device.py      # 器件层：FO4 + 铜互连尺寸效应
├── layer2_circuit.py     # 电路层：Davis 线长分布 + LogicFolding
├── layer3_chip.py        # 封装层：N²-vs-N + roofline
├── layer4_system.py      # 系统层：α-β 集合通信 + SimPy 离散事件仿真
├── thermal.py            # 热约束：多层折叠可持续频率
└── cascade.py            # 级联：Amdahl / 十年轨迹 / 瓶颈迁移 / α 分解
tests/                    # 回归测试 + JS↔Python 对拍
run_all.py                # 一键运行全部实验（--lang en 出英文图）
sensitivity.py            # 敏感性检查（17 项扰动）
app.py                    # Streamlit 交互 GUI（7 tab）
tau_lab_model.js          # 模型的 JS 移植（手工，靠对拍测试保证一致）
tau_lab_template.html     # 浏览器版 τ Lab 模板（含 i18n）
build_tau_lab.py          # → tau_lab.html（零依赖单文件）
build_report.py           # → report_full.html/.pdf（双语渲染管线）
build_critique.py         # → critique.html
build_dashboard.py        # → dashboard.html
build_slides.js           # → slides_tau_scaling.pptx（8 页汇报）
figures/  figures_en/     # 仿真输出图表（中/英两套）
REPORT.md   REPORT.en.md  # 完整分析报告（论文解读 + 结果 + 局限）
CRITIQUE.md CRITIQUE.en.md# 对抗性附录（最易受质疑的假设与结论）
ARCHITECTURE.md           # 架构与开发指南
CHANGELOG.md              # 版本演进（每版标注对结论有无影响）
AGENTS.md / CLAUDE.md     # Project Cairn 协作规则入口（CLAUDE.md 为 @AGENTS.md 桩）
cairn/                    # 项目知识层（Project Cairn）
├── ROADMAP.md            # 待办与未来工作（区分本仿真欠账 / 论文开放问题）
├── LOG.md                # 时序日志（最新在上）
├── 项目约定与陷阱.md      # 常用命令、架构速览、踩过的坑
└── 历史文档清单.md        # 既有文档的登记与权威性说明
```
