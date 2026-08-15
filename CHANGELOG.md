# 更新日志

本文件记录本项目的演进。格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> **本项目版本号追踪的是「分析与工具」的演进。**由于交付物的本质是仿真数字，
> 每个版本额外标注 **结论影响**：说明该版本是否改变了 REPORT.md / CRITIQUE.md
> 中的任何论断。只改呈现形式、不动模型的版本会明确标注"无结论变更"。

---

## [1.0.0] — 工程基建：可维护、可复验

**结论影响：无模型或结论变更。**但补回了一项此前缺失的可信度凭据（见下）。

### 新增
- `tests/test_regression.py`：14 组黄金值，锁定四层模型、级联实验 A–D 与
  热约束的关键输出——REPORT.md 中每个数字的防线。
- `tests/test_crosscheck.py`：`tau_lab_model.js` 与 Python 基线的 **22 项指标对拍**
  （rtol=1e-6）。此前该脚本从未入库，README/REPORT 中"JS 与 Python 逐位一致"
  的声明**无凭据可复验**；本版本补回，且覆盖项数由原先声称的 14 项增至 22 项。
- `.github/workflows/ci.yml`：每次 push 跑测试 + 双语出图 + 敏感性 + 全部页面构建。
- `ARCHITECTURE.md`：设计原则、四层数据流、dataclass 契约、构建管线、扩展指引。
- `CLAUDE.md`：Claude Code 会话级项目约定（四条铁律与实际踩过的陷阱）。
- `README.en.md`：README 英文版。
- `LICENSE`：MIT（不含被分析论文本身）。

### 变更
- 函数级 docstring 覆盖率 41% → 100%。
- README 修正过时内容：Streamlit tab 数 5 → 7；目录树补全至当前文件集。

### 修复
- `requirements.txt` 缺少 `markdown`——`build_report.py` / `build_critique.py`
  依赖它，此前任何人按 README 步骤走到"生成报告"都会失败。由新增的 CI 流程暴露。

---

## 0.9.0 — 管理层汇报材料

**结论影响：无结论变更。**

### 新增
- `slides_tau_scaling.pptx`：8 页中文汇报（封面 / 背景任务 / 论文核心思想 /
  四层方法 / 关键结果 / 对抗性审阅 / 交付物 / 结论建议），深色三明治版式，
  嵌入 fig3、fig10，每页附讲者备注。
- `build_slides.js`：上述 PPTX 的生成脚本（pptxgenjs）。

---

## 0.8.0 — 四个 HTML 页面中英双语化

**结论影响：无结论变更**（仅呈现语言与图表标签）。

### 新增
- `figures_en/`：全套英文标签图（10 张）。
- `REPORT.en.md`、`CRITIQUE.en.md`、`dashboard_template.en.html`：英译文档。
- 四个页面（`dashboard.html`、`tau_lab.html`、`report_full.html`、`critique.html`）
  右上角 中/EN 切换；正文与图表随语言切换。
- `tau_lab.html` 的完整 JS i18n：六个面板的控件、选项、统计标签、图表坐标轴与
  图例全部随语言切换。

### 变更
- `run_all.py` 增加 `T(zh, en)` 与 `--lang en`，同一套代码出两种语言的图。
- `build_report.py` / `build_critique.py` / `build_dashboard.py` 改为双语渲染管线。

### 修复
- fig9、fig10 英文版双子图标题重叠（英文标题比中文宽）：缩字号 + 加宽画布 + 精简句子。

---

## 0.7.0 — 对抗性附录

**结论影响：新增审阅结论**（不改动既有仿真数字，是对论文主张的独立评估）。

### 新增
- `CRITIQUE.md`：按严重度排序的六条质疑——α≈10/年 是复合速率、UB「500×」
  基线选择性、密度+55% 是面积记账且多层热代价被低估、τ 抽象未定义组合函数 f、
  能量盲区、381 芯片自证式验证；并公平列出最经得起推敲的部分。
- `build_critique.py` → `critique.html`（自包含，图内嵌）。

---

## 0.6.0 — 两个 GUI 补齐 REPORT 的全部仿真

**结论影响：无结论变更**（新面板复现的是既有实验）。

### 新增
- τ Lab 新增「Layer 1 器件层」面板（P1 / fig1），旋钮为布线跨度、铜自由程、
  互连纵横比。
- τ Lab 级联面板增加视图选择器：瓶颈迁移 / Amdahl / 十年轨迹（实验 B）/
  α 分解（实验 D）。
- `tau_lab_model.js` 增加 `deviceScan()`、`decadeTrajectories()`、`alphaDecomp()`。
- Streamlit 新增「器件层」tab（共 7 个）。

### 变更
- 移除 Layer 1 面板初版中一个**不影响模型**的假旋钮（"速度饱和指数 α"——
  该参数在模型里并非运行时变量），换为真实驱动模型的互连纵横比。

---

## 0.5.0 — 图文并茂的完整报告

**结论影响：无结论变更。**

### 新增
- `build_report.py`：把 `REPORT.md` 与 10 张图合并成 `report_full.html`
  （零依赖，图 base64 内嵌）与 `report_full.pdf`（A4，可存档分发）。

### 变更
- `REPORT.md` 结尾文件清单补齐三/四期交付物，并说明 GUI 仅改变呈现形式、
  不引入新的科学主张。

---

## 0.4.0 — 交互式敏感性扫描

**结论影响：无结论变更**（把既有的脚本式敏感性检查交互化）。

### 新增
- τ Lab 面板 5 与 Streamlit tab ⑥：12 个参数 × 5 个输出指标的**龙卷风图**
  （按影响幅度降序，一眼看出最能撼动结论的参数）。
- 1D 参数扫描，并将**结论翻转区**直接着色——把"结论稳健"从口号变成可见区域。

---

## 0.3.0 — 交互式仿真 GUI（双路线）

**结论影响：无结论变更**（JS 移植与 Python 基线逐项一致）。

### 新增
- `tau_lab_model.js` + `tau_lab_template.html` + `build_tau_lab.py`
  → `tau_lab.html`：零依赖单文件，浏览器双击即用，四个交互面板。
- `app.py`：Streamlit 版，直接 import `tau_sim`，含 SimPy 离散事件验证按钮。

---

## 0.2.0 — 热约束与 α 口径分解

**结论影响：新增两组结论。**

### 新增
- `tau_sim/thermal.py` + fig9：多层折叠在温升预算内的可持续频率——
  异构折叠（逻辑+存储）近乎无损 f≈0.98，同构（逻辑+逻辑）2 层降至 0.80、
  4 层 0.60；层间热阻仅占温升预算的次要项，真正的瓶颈是折叠后的功率密度。
  对应论文的开放问题 §6，并有 AMD 3D V-Cache 实测佐证。
- `cascade.alpha_decomposition()` + fig10（实验 D）：把 AI 侧能力拆成
  集成规模 × 单芯片 × 扩展效率——硬件三因子仅 ≈2.0/年（叠加精度演进 ≈2.6/年），
  远不足以解释论文的 α≈10/年；τ 压缩的真实作用是守住 α_eff≈1。
- `dashboard.html`：自包含可视化报告页。

---

## 0.1.0 — 四层级联仿真与五命题验证

**结论影响：建立全部基线结论。**

### 新增
- `tau_sim/`：四层模型——器件层（α-power law + 铜互连尺寸效应）、
  电路层（Davis 线长分布 + LogicFolding 折叠判据）、
  封装层（N²-vs-N + roofline）、系统层（α-β 集合通信 + SimPy 离散事件仿真）。
- `cascade.py`：级联实验 A（Amdahl 饱和）、B（十年轨迹）、C（瓶颈迁移）。
- `params.py`：30+ 校准参数，**逐项注明独立文献出处**；论文自身数据仅作
  "待复现目标"，不进入模型。
- `run_all.py` → fig1–fig8；`sensitivity.py`：17 项参数 ±50% 扰动，0 次结论翻转。
- `REPORT.md`：完整分析报告（论文解读 + 五命题验证 + 局限）。

### 主要结论
- P1 互连占级延迟比例 22%→72%，5nm 后级延迟不降反升。
- P2 折叠线长 −24.9% / 偏斜 −24.9% / 频率 +12.3%（论文 −30% / −25% / +13%）。
- P3 2.5D 的 ridge 强度随规模上移，N≈55mm 后连 GEMM 也访存受限。
- P4 小消息 all-to-all 换协议栈可得 9.8×(RDMA) / 159×(TCP)。
- P5 单层优化 Amdahl 饱和；协同年化 α 1.22 显著优于单点 1.02–1.08；瓶颈逐层迁移。

---

> 只有 1.0.0 建有 GitHub Release；0.x 各版本的内容见上文，对应 commit 可在 git 历史中按上述描述定位。

[1.0.0]: https://github.com/alexyudragonsword-collab/tau_demo/releases/tag/1.0.0
