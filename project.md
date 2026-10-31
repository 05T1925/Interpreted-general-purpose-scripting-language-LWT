# LWT 项目上下文

> Agent 的当前入口。最后核对：2026-10-31。先核对 Git 实际状态；本页的远端信息可能随推送变化。协作规则见 [AGENTS.md](AGENTS.md)，分支与同步记录见 [仓库工作流](docs/repository-workflow.md)。

## 目标与评分

[作业原文](大作业内容.md)要求：以 LWT 命名的解释型通用脚本语言及解释器、完整一键黑盒测试、LWT/Python 性能比较、人类和 Agent 指南、Agent 编写的至少 200 行 LWT 应用与开发记录、Git 历史、系统介绍 PPT，并在线下答辩。评分为解释器 20、测试 20、性能 10、指南 20、LWT 应用 30 分。Python/Tkinter 展示层与 Snake 不替代 LWT 应用。

## 当前可核验状态

| 项目 | 当前事实与入口 |
|---|---|
| 本地 Git 主线 | 用户授权将 S23–S30 依次 `--ff-only` 纳入 `main`，保留每个原始提交。S0–S11、S13–S22 此前已在本地 `main`。没有 S12；S31 尚无实现提交。阶段报告中的历史“待审查”是当时快照；主线包含不等于逐阶段审查报告已补齐。 |
| 远端 | `origin` 是 [LWT GitHub 仓库](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT)。2026-10-31 从 S4 的 `de608f7` 正常快进推送主线；最近一次推送后核验 `main=c2228d3`，五个功能里程碑及 `feature/editor-integration` 已推送。后续以 [仓库工作流](docs/repository-workflow.md)和实时 `git ls-remote` 为准。绝不强推。 |
| 解释器与规范 | [正式规范](docs/language-spec.md)、`lwt/`；整数、字符串、布尔/null、数组、record、I/O、控制流、函数、静态模块、受限错误恢复。普通执行：`python -m lwt SOURCE [-- ARGS...]`。 |
| 黑盒与 CI | [覆盖矩阵](docs/test-matrix.md)、`tests/cases/`、`python tools/run_tests.py`、`python tools/check_project_integrity.py`、`.github/workflows/tests.yml`。S30 候选 tip 本地复核：黑盒 287/287、完整性 287 cases / 384 links / 287 referenced cases、全量 unittest 421 项通过。2026-10-31 的远端四格 Actions 曾在 unittest 步骤失败，定位为两个跨平台测试断言问题；修正及证据见[仓库工作流](docs/repository-workflow.md)。验证新 tip 时以 GitHub 最新 SHA 对应的 Actions 为准。 |
| 开发工具 | `python -m lwt --check SOURCE`；`python -m lwt --profile PROFILE SOURCE`；`python -m lwt.lsp_server`；`python -m lwt.debugger SOURCE`。分别见 [静态检查](docs/static-checker.md)、[执行档案](docs/execution-profile.md)、[Language Server](docs/language-server.md)、[调试器](docs/debugger.md)。LSP 不执行目标程序；debugger 执行。 |
| Agent 应用 | [日志分析器](app/log_report.lwt)有 246 行有效 LWT；[应用说明](app/README.md)、[Agent 开发记录](docs/agent-dev-log.md)、25 项 `tests/test_app.py` 和 [多进程读取记录](docs/app-concurrency.md)。日志侦探、分析工作台、语义实验室及独立 Python 贪吃蛇是展示辅助。 |
| 性能证据 | [性能报告](reports/performance.md)和 [原始记录](bench/results.json)保存 S11 正式 run。计时包含新进程启动、导入、解析和执行，不是纯 runtime 速度；不要为刷新数字覆盖原始 run。 |
| 指南 | [开发指南](docs/developer-guide.md)、[Agent Skill](.agents/skills/lwt-app/SKILL.md)、[独立盲测](docs/agent-blind-test.md)。 |
| 下一阶段 | S31 的 `feature/editor-integration` 计划接入 VS Code；该分支目前只有主线起点，尚无已提交实现。共享工作树仍在旧分支 `stage/s31-vscode-extension`，存在未跟踪的 `editors/` 在途文件；后续执行者先检查并保全，再迁移到功能分支，禁止清理覆盖。最后的 S12 负责新克隆、兼容性与远端 CI、人工 GUI 预检、PPT、演示和最终交付，见 [S12 计划](docs/s12-final-delivery-plan.md)。 |

## 当前工作约定

1. 新任务先读取本页、[AGENTS.md](AGENTS.md)和任务相关规范/报告，再查 `git status -sb`、HEAD、`main` 与 `origin/main`。不要把计划当成实现，也不要把阶段报告里的旧状态当成当前 Git 状态。
2. 大阶段使用 `feature/<功能>`、`maintenance/<目的>` 或 `fix/<问题>`；已完成的功能边界用 `milestone/<功能>` 指针。S 编号保留在报告和提交中，不再为每个 S 自动建远端分支。命名与实际指针见[仓库工作流](docs/repository-workflow.md)。
3. 语言行为变化同步规范、示例、黑盒和矩阵；开发工具另做针对性测试。审查时区分执行窗口声明、主窗口复跑、远端 Actions 与人工 GUI 实测。
4. S10 并发 raw、S11 正式 benchmark raw、S28 固定 profile 和 S29 smoke 是已提交证据。读取和校验可以；重新生成需保留旧数据与 run 身份，不覆盖。
5. 本地集成按用户授权完成；在 S12 前仍需逐项整理 S23–S30 的审查记录、核对远端同步与 CI。不能因这次快进合并就宣称所有阶段已经独立验收。

## 常用命令

| 用途 | 命令 |
|---|---|
| 普通运行 | `python -m lwt examples/guide/hello.lwt` |
| 模块示例 | `python -m lwt examples/modules/main.lwt` |
| 静态检查 | `python -m lwt --check --format=json examples/modules/main.lwt` |
| 调试器示例 | `python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt` |
| 黑盒 | `python tools/run_tests.py` |
| 完整性 | `python tools/check_project_integrity.py` |
| 单元测试 | `python -m unittest discover -s tests -q` |
| LWT 应用 | `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` |
| LWT 行数 | `python tools/count_lwt_lines.py app/log_report.lwt` |

历史 S 阶段细节与报告索引见 [阶段路线图](阶段执行与审查路线图.md)；其旧状态文字仍需随最终审查更新。[总体方案](LWT大作业总体方案与复检.md)与[详细规划](详细实施规划.md)提供设计背景，发生冲突时以作业原文、正式规范、当前代码与实测证据为准。
