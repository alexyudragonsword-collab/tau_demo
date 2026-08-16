# Project Cairn 日志

本文件按倒序记录实质性进展——最新条目置于本行下方。每条保持简短，只写摘要与指针；结论沉淀进 `cairn/<topic>.md`。

## 2026-08-16 · ROADMAP 移入 cairn/，改为标准布局

- 按用户决定，`ROADMAP.md` 由根目录 `git mv` 进 `cairn/`（保留文件历史），
  根目录不再保留副本，与 Cairn 标准布局一致。
- **更正初始化时的判断**：初始化条目中"未创建 `cairn/ROADMAP.md` 以免同名歧义"
  的理由已失效——根目录版本既已移走，就不存在两份同名文档。
  更正说明见 `cairn/历史文档清单.md` 末尾。
- 同步更新指向共 8 处：`AGENTS.md`（阅读顺序 + 文档职责表）、`README.md`/`README.en.md`
  （目录树，并补上 Cairn 结构）、`REPORT.md`/`REPORT.en.md`（附录清单）、
  `cairn/项目约定与陷阱.md`、`cairn/历史文档清单.md`。
- 按 Cairn 模板给 ROADMAP 补「当前焦点」：下一优先级为 R1 补能量模型。

## 2026-08-16 · Project Cairn 初始化

- 在已有项目上完成 retrofit 初始化。决策：`git_policy: track`、provider 暂缓对接、
  `migration_mode: inventory_only`、文档语言 `zh`。
- **`CLAUDE.md` 按 Cairn 规范改为一行 `@AGENTS.md`**；原 81 行内容未丢弃：
  四条铁律上提至 `AGENTS.md`，常用命令/架构速览/陷阱迁入 `cairn/项目约定与陷阱.md`。
- 按 `inventory_only` 登记既有九份文档与测试/图表资产，见 `cairn/历史文档清单.md`；
  历史文档一律留在原位不改写。
- 未创建 `cairn/ROADMAP.md`：根目录已有 `ROADMAP.md`，避免同名歧义；
  `AGENTS.md` 阅读顺序已指向根目录版本。
- 详情见 `AGENTS.md` 与 `.cairn/config.yaml`。
