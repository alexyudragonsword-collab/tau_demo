# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目性质

这不是一个普通的仿真库，而是对一篇论文（何庭波《A Time Scaling Theory for
Multi-Layer Electronic Systems》，ChinaXiv:202605.00224）核心主张的**独立验证**。
**数字本身就是产品**——REPORT.md / CRITIQUE.md 里的每个结论都由代码算出。
因此任何导致数字变化的改动，都等于修改了对外发表的论断。

## 常用命令

```bash
pip install -r requirements.txt

python run_all.py                 # 出中文图 → figures/（并打印与论文的对照表）
python run_all.py --lang en       # 出英文图 → figures_en/
python sensitivity.py             # 17 项参数 ±50% 扰动的稳健性检查

python tests/test_regression.py   # 14 组黄金值（无需 pytest）
python tests/test_crosscheck.py   # JS 移植 vs Python 22 项对拍（需 node）

streamlit run app.py              # 交互 GUI（7 tab）
python build_tau_lab.py           # → tau_lab.html（零依赖单文件）
python build_report.py --html     # → report_full.html（去掉 --html 会同时出 PDF，需 playwright）
python build_critique.py          # → critique.html
python build_dashboard.py         # → dashboard.html
node build_slides.js              # → slides_tau_scaling.pptx（需 npm i pptxgenjs）
```

跑单个测试：测试是普通函数，`python tests/test_regression.py` 会跑全部；
若装了 pytest 可用 `pytest tests/test_regression.py::test_layer2_fold_gains`。

## 铁律

1. **论文数据永远不进入模型。** `tau_sim/params.py` 的 30+ 个参数全部来自独立
   公开文献（逐项注明出处）；论文自称的数字只存在于 `params.PAPER_TARGETS`，
   仅用于画对照柱。**绝不可为了"让结果更接近论文"而调参数**——那会让整个项目
   的论证力归零。唯一已校准的例外（折叠密度的面积开销）已在 REPORT.md §4.2 标注。

2. **`tau_lab_model.js` 是手工移植，不会自动跟随 Python。** 改了 `tau_sim/` 里
   任何公式或常量后，**必须跑 `python tests/test_crosscheck.py`**，否则浏览器版
   交互页会给出与报告不一致的数字。

3. **黄金值测试失败时，不要直接改期望值。** 先判断是 bug 还是有意的模型改动。
   若是后者，要同步更新：测试期望值 → REPORT.md 正文 → CRITIQUE.md（如涉及）
   → 重新生成图与 HTML 页面。

4. **改模型公式后必跑三件事**：`test_regression.py`（结论是否变）、
   `test_crosscheck.py`（JS 是否同步）、`sensitivity.py`（稳健性是否还成立）。

## 架构速览

四层模型彼此不 import（`thermal.py` 依赖 `layer2_circuit` 是唯一例外），
**只有 `cascade.py` 是跨层的**——它把四层折算成一次训练迭代的 τ 四分量
（compute / memory / comm / other）。改某层内部只要 dataclass 字段不变，
cascade 无需改动。

详细数据流、dataclass 契约表、构建管线、扩展指引见 **ARCHITECTURE.md**。

## 已知陷阱

- **`SystemConfig` 的 `k_*` 是加速倍数（>1 表示更快）**，不是绝对值——最容易搞反。
- **`decade_trajectories()` 与 `bottleneck_migration()` 返回的 dict key 是中文字符串**
  （如 `"全栈 τ-first 协同"`）。改这些字符串要同步三处：模型、`run_all.py` 的
  `TR_TRAJ`/`TR_STAGE`、以及 `tau_lab_model.js` 侧的映射。
- **英文图标题比中文宽，双子图标题极易重叠**（fig9/fig10 踩过）。解决办法：
  `fontsize=TS` + 加宽画布 + 精简英文句子。加图后两种语言都要出一遍并检查排版。
- **tau_lab 新增的静态文案必须登记进 `applyStatic()` 的字典**
  （`PANEL_TXT`/`LABELS`/`OPTS`/`H4`），动态文案用 `TT(zh, en)`，否则切到 EN 不生效。
- **SimPy 函数固定 `seed=7`**，结果可复现；DES 只用于验证解析模型，不替代它。
- **`report_full.pdf` 需要 playwright**（不在 requirements.txt 内，属可选）；
  HTML 版无此依赖。
- 沙箱环境里 **LibreOffice 无法渲染 PPTX**，故 slides 只能做结构与内容校验
  （`validate.py` + python-pptx 读取），无法做像素级预览。

## 提交约定

工作分支为 `claude/paper-analysis-model-scenario-m8lzj0`。产物（figures、
生成的 HTML/PDF/PPTX）**入库**——它们是交付物的一部分，且 CI 会重新生成校验。
