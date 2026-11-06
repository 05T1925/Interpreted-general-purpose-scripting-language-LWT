# S12 最终交付核对清单

状态：S12 已通过主窗口复核并快进集成到本地 `main`。2026-11-07 完成一次最终验收收口：本机环境记录、桌面条件判定、A–E 现场操作矩阵、CLI 后退主路径实跑与 PPT 静态审阅。现场人工 GUI 验收仍未完成，不以自动化、窗口启动、静态审阅或旧报告替代。证据层级见[现场验收记录](s12-gui-acceptance.md)；主窗口结论见 [S12 主窗口复核](s12-main-review.md)，执行细节见 [S12 执行报告](s12-final-delivery.md)。

| 课程提交物 | 仓库位置 | 检查方式与本轮证据 |
|---|---|---|
| 1 语法规则 | [正式规范](language-spec.md) | 与最小程序、模块、错误和黑盒矩阵核对；本轮静态审阅 |
| 2 解释器 | [`lwt/`](../lwt/) | `python -m lwt`、`--check`、模块与定位错误；本轮 CLI 实跑 |
| 3 完整黑盒 | [`tests/cases/`](../tests/cases/)与[矩阵](test-matrix.md) | `python tools/run_tests.py` 本轮 287/287；`check_project_integrity` 本轮 287/384/287 |
| 4 性能报告 | [S11 报告](../reports/performance.md)与[raw](../bench/results.json) | 原始 run、120 正式试次、六组统计；本轮未重跑生成器，PPT 图表数值静态核对与报告一致 |
| 5 人/AI 指南 | [开发指南](developer-guide.md)、[策略 SDK](strategy-sdk.md)、`.agents/skills/` | 新克隆按入口运行、相对链接检查；本轮静态审阅链接 |
| 6 Agent LWT 应用/记录 | [日志应用](../app/log_report.lwt)、[LWT 游戏](../app/lwt_snake/game.lwt)、[开发记录](agent-dev-log.md) | 本轮 CLI 实跑：有效行 246/313、`--check`、S39–S41 复验、篡改拒绝 |
| 7 Git 历史 | `git log --oneline --decorate` | 本轮重新 fetch：工作区干净，`HEAD = main = origin/main = 5027860`，ahead/behind 0 0 |
| 8 系统 PPT | [可编辑 PPTX](../slides/LWT介绍.pptx) | 本轮静态审阅：12 页、原生图表 12 数值点与 S11 六组中位数逐值一致、SHA 与 S12 报告一致；未用 PowerPoint GUI 播放 |

## 现场操作矩阵（2026-11-07）

结论先行：**桌面条件不满足现场人工 GUI 验收前提，A–E 的人工交互项全部记为未验证；可复现 CLI 后退主路径已在本机实跑通过。** 桌面同时存在 24 个带标题窗口（Chrome、Edge、VS Code、飞书、微信、企业微信、QQ、Obsidian、Notepad、ChatGPT、PowerPoint、Windows Terminal、WorkBuddy 及 Realtek/华硕面板等），并检测到 `cua-driver`（`Cua.AgentCursorOverlay.default`）这一来源不明的 GUI 自动化覆盖层；无任何 LWT 应用在运行，PowerPoint 窗口标题仅为 “PowerPoint”，键盘鼠标输入归属与窗口焦点无法判定。依据 [AGENTS.md](../AGENTS.md) 与任务边界，本轮未发送任何鼠标/键盘事件，未启动或操作任何 GUI 应用，也未用合成事件冒充人工操作。

| 项 | 目标人工操作 | 本轮状态 | 证据层级与说明 |
|---|---|---|---|
| A 语义实验室 | 选择示例、先提交预测再运行、解释区、重置、缩放、输入法与焦点 | **未验证** | 无人工桌面输入；仅记录窗口不可判定。CLI 后退：`python -m lwt examples/guide/hello.lwt`、`division_by_zero.lwt` 已实跑 |
| B 日志工作台与挑战 | 默认查询、WARN+retry+top=2、完整原始报告、文件错误后恢复、五题挑战/计分/结束/重开 | **人工 GUI 未验证；CLI 通过** | 两条日志 CLI 实跑通过（见下）；GUI 输入、挑战流程、计分、结束页、重开均未操作 |
| C LWT Snake | 方向键/WASD、暂停、提示、自动驾驶、手动接管、失焦、录制/回放/接管、结束态重开 | **人工 GUI 未验证；CLI 通过** | `--check game.lwt`、arena 烟测、replay 验真已实跑；真实键盘/焦点/失焦未操作 |
| D S41 只读见证查看器 | 载入本地见证、重新验真、步骤切换、错误反馈、窗口关闭与再打开 | **人工 GUI 未验证；CLI 通过** | `witness --verify` 三态、`counterfactual --explain` 已实跑；Tk 查看器交互未操作 |
| E PPT 与答辩演练 | PowerPoint 打开并逐页播放、5–8 分钟主线、字体/裁切/图表可读性 | **人工播放未验证；静态审阅通过；CLI 主线通过** | 静态解析 12 页与图表数值一致；未用 PowerPoint 播放；演示脚本 CLI 主线已实跑 |
| 桌面条件 | 无遮挡、输入归属清楚 | **未满足** | 24 个窗口 + `cua-driver` 覆盖层 + 无 LWT 进程；遇此条件即停止 GUI 操作 |

### 本轮实跑的 CLI 后退主路径（证据层级：本机 CLI 实测，非人工 GUI）

- `python -m lwt examples/guide/hello.lwt` → 0，`hello, LWT` / `42`。
- `python -m lwt examples/language_lab/division_by_zero.lwt` → 3，`2:8: RuntimeError: division by zero`。
- `python tools/check_project_integrity.py` → 0，`cases=287; matrix_links=384; referenced_cases=287`。
- `python tools/run_tests.py` → 0，`passed=287 failed=0 total=287`，9 类别，183.111 秒。
- `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` → 0，total 7 / valid 6 / malformed 1 / matched 6；ERROR/INFO/WARN 各 2。
- 过滤式 `... --level WARN --keyword retry --top 2` → 0，matched 1 / WARN 1 / cache 1。
- `python -m lwt --check app/lwt_snake/game.lwt` → 0，`Check passed: 1 source file(s).`。
- `python tools/count_lwt_lines.py app/log_report.lwt` → 0，`Effective LWT lines: 246`；`app/lwt_snake/game.lwt` → 0，`313`。
- `python -m lwt examples/modules/main.lwt` → 0，`demo:2`。
- `python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-parent.json` → 0，`Verified 10 transactions.`。
- `python -m app.lwt_snake.arena --check-strategy mobility-lookahead --catalog ...` → 0，静态与 LWA1 烟测通过，帧序列 R/SPACE、L/SPACE、NONE/TRAPPED、BAD_FRAME/BAD_SEQUENCE、EOF clean。
- `python -m app.lwt_snake.arena --verify reports/s39-demo/result.json --catalog ...` → 0，`Verified 9 matches: game and policy decisions.`
- `python -m app.lwt_snake.witness --verify reports/s41-found --catalog ...` → 0，`found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs`。
- 同命令验 `reports/s41-none` → 0，`found=false scanned=1/1`；验 `reports/s41-tampered` → 3，`WitnessError: agent feedback evidence mismatch`。
- `python -m app.lwt_snake.counterfactual --explain reports/s41-found/analysis --catalog ...` → 0，baseline `R/SPACE` 与 bfs `D/FOOD`，score 10→10、phase RUNNING。
- 临时副本篡改：复制 `reports/s41-found` 到系统临时目录，仅改副本 `agent-feedback.json.question`，`witness --verify` → 3，`WitnessError: agent feedback evidence mismatch`；仓库固定原件未改。

### 主窗口与 CI 边界（历史证据，非本轮人工 GUI）

- [x] 主窗口核对候选精确 SHA `e1249f56f1d889c0c6e400a46602e0fe3f7df1ce` 的 Ubuntu/Windows × Python 3.10/3.13 四格 Actions（run [41572881428](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41572881428)，全部成功）——该结论绑定候选 SHA，不代表本轮新提交 SHA 的 CI。
- [x] 主窗口审查候选提交、快进集成到本地 `main` 并正常推送；本轮重新 fetch 后远端 `main` 与本地 `HEAD` 仍一致。
- [ ] 现场人工 GUI 检查、教师实际线下验收、最终归档与评分——仍未完成，不以任何自动化、静态或窗口证据替代。
