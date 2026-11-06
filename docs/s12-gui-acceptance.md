# S12 现场人工验收与最终交付证据收口记录

日期：2026-11-07。阶段：S12 最终交付收口，非新功能阶段。基线、分支、提交与远端状态见[第 6 节](#6-git-基线与提交)。本文只记录本轮实际操作与本轮可观察证据；历史报告中的检查不冒充本轮实测，自动化/静态/CLI 证据不冒充现场人工 GUI 验收。

## 结论

**桌面条件不满足现场人工 GUI 验收前提，A–E 的人工交互项全部记为未验证；可复现的 CLI 后退主路径在本机实跑通过，PPT 静态审阅数字与仓库最终报告一致。** 本轮没有发现阻断缺陷，没有新增产品功能，没有改动解释器、正式规范、测试用例、LWT 应用、固定回放/策略证据、S10/S11 原始数据，未运行任何会重写固定原始数据的生成器，未覆盖 PPT 或已有证据文件。现场人工操作、PowerPoint 实际播放与教师线下验收仍由提交者依课程实际流程完成。

证据层级定义：

- **人工桌面**：真实物理鼠标键盘、窗口焦点、视觉体验由人在无遮挡桌面实操确认。
- **CLI 实测**：本轮在本机真实运行公开 CLI，记录退出码与输出；不是人工 GUI，也不是历史报告。
- **静态审阅**：解析文件结构/文本/数值（如 PPTX 包、图表 XML、文档链接）；不产生运行时行为证据。
- **自动化测试**：项目自带的黑盒 runner、unittest 与合成事件集成测试。
- **历史报告**：先前阶段报告与 S12 执行/复核报告中记录的事实，按其记录时点有效，不替代本轮实测。

## 1. 执行前检查

- 阅读 `AGENTS.md`、`project.md`、`docs/s12-main-review.md`、`docs/s12-final-delivery.md`、`docs/final-acceptance-checklist.md`、`docs/demo-script.md`、`docs/repository-workflow.md`。
- 重新 `git fetch origin --prune`（退出 0，非沿用旧报告）；核对前 `git status --short --branch` 为干净的 `## main...origin/main`。
- `HEAD`、`main`、`origin/main`（fetch 前与后）均为 `5027860efc8a1cce342ca13b1434d7724aeeffc4`；`git rev-list --left-right --count main...origin/main` 为 `0 0`。工作区干净，无用户未提交改动需要保留。
- 远端阶段分支清单：`origin/feature/{editor-integration,lwt-counterfactual-lab,lwt-snake-game,lwt-snake-strategy,lwt-strategy-arena,lwt-strategy-workshop,lwt-witness-discovery,testing-workbench}`、`origin/milestone/{course-deliverables,developer-tools,final-delivery,interactive-apps,language-core,language-extensions}`、`origin/main`。

## 2. 本机环境（本轮可观察记录）

| 项目 | 观测值 | 获取方式 |
|---|---|---|
| 操作系统 | Microsoft Windows 11 家庭版 中文版，10.0.26200（Build 26200），64 位 | `Get-CimInstance Win32_OperatingSystem` |
| 会话 | `SESSIONNAME=Console`，`UserInteractive=True`，PowerShell SessionId=1 | `qwinsta` / `[Environment]::UserInteractive` |
| Python | 3.13.7，`C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe` | `python --version` / `sys.version` |
| Tk / Tcl | Tk 8.6 / Tcl 8.6 | `tkinter.TkVersion` / `_tkinter.TCL_VERSION`（仅导入，未创建窗口） |
| 屏幕分辨率 | 2560 × 1600（当前主屏）；显卡 NVIDIA GeForce RTX 4060 Laptop GPU / Intel UHD Graphics | `Win32_VideoController.CurrentHorizontal/VerticalResolution` |
| 缩放 | `Win8DpiScaling=0`、`LogPixels` 未设置；未观察到自定义 DPI 百分比 | `HKCU:\Control Panel\Desktop`（只读） |
| VS Code | 1.144.0 | `Code.exe` 文件版本（未启动） |
| PowerPoint | Microsoft 365 - zh-cn 16.0.20527.20150 | 卸载注册表（未启动 GUI）；但进程 `POWERPNT.EXE`（PID 66240）本轮开始时已在运行 |
| GitHub API | 可达（候选 run 41572881428 返回 HTTP 200）；`gh` CLI 未安装 | `curl` / `gh --version` |

说明：`Add-Type` 被本机安全策略拦截，屏幕分辨率改用只读 WMI 获取；Tk/Tcl 仅导入模块读取版本，未创建任何 GUI 窗口。窗口/进程探测全部为只读。

## 3. 桌面条件判定（决定是否允许 GUI 操作）

**判定：不满足，立即停止一切 GUI 操作。** 只读枚举带标题的顶层窗口，本轮开始时同时存在 24 个窗口：Realtek Audio Console、计算器、ChatGPT、Chrome（标题“初发 - Google Chrome”）、Visual Studio Code（打开私人面试文档）、飞书、Microsoft Edge（课堂测试 PDF 等 8 个页面）、Notepad（求职相关文本）、Obsidian、NxDock、PowerPoint、QQ、微信、WeMail、企业微信、Windows Terminal（管理员 PowerShell）、WorkBuddy、以及 AsHotplugCtrl / AsMonitorControl / AsHDRControl 等面板进程。

- **遮挡**：目标 LWT 应用无一是当前可确认的前台窗口；桌面并非无遮挡。
- **输入归属不明**：检测到进程 `cua-driver`，窗口标题 `Cua.AgentCursorOverlay.default`——来源不明的 GUI 自动化光标覆盖层。无法确认键鼠事件归属本验收任务。
- **窗口焦点无法确定**：`POWERPNT.EXE`（PID 66240）在运行，但标题仅为 “PowerPoint”，无法确认是否为本答辩 PPT，也无法确认焦点。
- **无 LWT 应用在运行**：未发现 language_lab / log_detective / lwt_snake 相关 python 进程。
- **本执行主体能力边界**：本轮由命令行 Agent 执行，任何输入均为合成事件；任务边界明确禁止用合成事件冒充物理键鼠。

依据任务规则“若有其他应用遮挡、来源不明的键鼠输入或窗口焦点无法确定，不发送鼠标/键盘事件，并将对应项目记为未验证”，本轮**未发送任何鼠标/键盘事件，未启动、激活或关闭任何 GUI 应用，未用截图或窗口启动充当人工验收**。

## 4. 现场操作矩阵 A–E

每项标注本轮状态与证据层级；CLI 命令原文与输出见第 5 节。

### A. 语义实验室 —— 未验证（人工交互）；CLI 后退通过

- 未做：界面选择示例、先提交预测再运行、解释区核对、重置、窗口缩放、常用键盘操作、中文输入法状态、输入焦点。
- 原因：桌面条件不满足（第 3 节），无人工桌面输入。
- 后退 CLI 实测：`python -m lwt examples/guide/hello.lwt` → 0；`python -m lwt examples/language_lab/division_by_zero.lwt` → 3。说明解析器/运行器/定位错误在 CLI 层可用；这不覆盖 GUI 的预测流程、输入法与焦点行为。

### B. 日志分析工作台与挑战 —— 人工 GUI 未验证；CLI 通过

- 未做：工作台 GUI 的默认查询与组合筛选点击、完整原始报告查看、无效文件制造错误再恢复、五题挑战反馈/计分/结束页/重新开始。未编辑或覆盖任何固定 fixture。
- CLI 实测通过：默认 `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` → 0，Total 7 / Valid 6 / Malformed 1 / Matched 6，ERROR/INFO/WARN 各 2；过滤式 `--level WARN --keyword retry --top 2` → 0，Matched 1 / WARN 1 / cache 1。两条输出与 `app/fixtures/sample.expected.txt` 及 [S12 执行报告](s12-final-delivery.md) 记录的语义一致。
- 后退说明：CLI 证明日志分析核心（坏行、等级、关键字、top）可用；挑战流程、计分与结束/重开是 GUI 专属路径，未验证。

### C. LWT Snake —— 人工 GUI 未验证；CLI 通过

- 未做：方向键/WASD、暂停/继续、提示、自动驾驶、手动接管、重开，失焦行为，录制/回放/接管入口，游戏结束态视觉。未改游戏规则、策略或回放证据。
- CLI 实测通过：`python -m lwt --check app/lwt_snake/game.lwt` → 0；`arena --check-strategy mobility-lookahead` → 0（帧序列 R/SPACE、L/SPACE、NONE/TRAPPED、BAD_FRAME/BAD_SEQUENCE、EOF clean）；`replay --verify app/lwt_snake/replays/demo-parent.json` → 0（Verified 10 transactions）；`arena --verify reports/s39-demo/result.json` → 0（Verified 9 matches）。
- 后退说明：CLI 证明规则由 LWT 计算、协议与验真链可用；真实键盘、焦点、失焦与渲染未验证。

### D. S41 只读见证查看器 —— 人工 GUI 未验证；CLI 通过

- 未做：从固定演示证据载入见证、重新验证、命中结果查看、步骤切换、错误反馈、窗口关闭与再打开。保持 `reports/s41-*` 原始证据不变。
- CLI 实测通过：`witness --verify reports/s41-found` → 0（`found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs`）；`reports/s41-none` → 0（`found=false scanned=1/1`）；`reports/s41-tampered` → 3（`WitnessError: agent feedback evidence mismatch`）；`counterfactual --explain reports/s41-found/analysis` → 0（baseline `R/SPACE` 与 bfs `D/FOOD`，score 10→10、phase RUNNING）。
- 临时副本篡改拒绝：复制 `reports/s41-found` 到系统临时目录（`lwt-s12-acceptance-tamper-<随机后缀>`），仅改副本 `agent-feedback.json.question`，`witness --verify <temp>` → 3（`WitnessError: agent feedback evidence mismatch`）；仓库原件未改，临时副本保留在 `%TEMP%`。
- 后退说明：CLI 完整覆盖见证载入/验真/篡改拒绝的数据链；Tk 查看器的交互与视觉未验证。

### E. PPT 与答辩演练 —— 人工播放未验证；静态审阅通过；CLI 主线通过

- 未做：用 PowerPoint 实际打开并逐页播放/浏览全部 12 页、5–8 分钟主线现场演练、字体替换/裁切/图表可读性的人工目视核对。本轮未启动或操作 PowerPoint GUI。
- 静态审阅通过（层级：静态审阅，非人工播放）：
  - `slides/LWT介绍.pptx` SHA-256 `0e680d17d0b0f09315a6519b15c9516ee04dac34df7dc8e42ea771c797b5fe5d`，与 [S12 执行报告](s12-final-delivery.md) 记录一致（文件未被改动）。
  - 12 页；页文本中的展示数字：287/287 黑盒、日志分析器 246 行、LWT 游戏 313 行、日志报告 Total 7 / Valid 6 / Malformed 1 / Matched 6、过滤 Matched 1，均与仓库最终报告及本轮 CLI 实测一致。
  - 原生图表位于 `ppt/slides/charts/chart1.xml`，两系列 `LWT 中位数 ms` = `[108.117, 107.483, 129.590, 111.168, 129.359, 182.926]`、`Python 中位数 ms` = `[39.187, 37.394, 38.389, 40.837, 38.826, 36.707]`，类别 `算术/数组 × 100/1000/5000`，共 12 数值点；嵌入工作簿 `ppt/embeddings/chart-data-snapshot-001.xlsx` 的 B2:B7 / D2:D7 同值。与 [S11 性能报告](../reports/performance.md) 六组中位数逐值一致。
- 静态审阅不能证明：PowerPoint 中的字体替换、逐页裁切、图表可读性、讲述顺序流畅度；这些保留为未验证。
- CLI 演示主线本轮实跑通过（见第 5 节），无需 GUI 即可完成 5–8 分钟主线的证据链命令。

## 5. 本轮命令与结果（证据层级：CLI 实测 / 静态审阅，逐条记录）

工作目录为仓库根；按"基线 → 解释器 → 完整性 → 黑盒 → 应用 → 游戏/见证 → 静态"顺序执行。以下均为本轮真实退出码与关键输出。

| 命令 | 退出码 | 关键输出 / 结论 |
|---|---|---|
| `git fetch origin --prune` | 0 | `HEAD=main=origin/main=5027860`，ahead/behind `0 0` |
| `python -m lwt examples/guide/hello.lwt` | 0 | `hello, LWT` / `42` |
| `python -m lwt examples/language_lab/division_by_zero.lwt` | 3 | `2:8: RuntimeError: division by zero` |
| `python tools/check_project_integrity.py` | 0 | `cases=287; matrix_links=384; referenced_cases=287` |
| `python tools/run_tests.py` | 0 | `passed=287 failed=0 total=287`，9 类别，183.111s |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 0 | total 7 / valid 6 / malformed 1 / matched 6；ERROR/INFO/WARN 各 2 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | 0 | matched 1 / WARN 1 / cache 1 |
| `python -m lwt --check app/lwt_snake/game.lwt` | 0 | `Check passed: 1 source file(s).` |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0 | `Effective LWT lines: 246` |
| `python tools/count_lwt_lines.py app/lwt_snake/game.lwt` | 0 | `Effective LWT lines: 313` |
| `python -m lwt examples/modules/main.lwt` | 0 | `demo:2` |
| `python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-parent.json` | 0 | `Verified 10 transactions.` |
| `python -m app.lwt_snake.arena --check-strategy mobility-lookahead --catalog ...` | 0 | 静态与 LWA1 烟测通过；帧 R/SPACE、L/SPACE、NONE/TRAPPED、BAD_FRAME/BAD_SEQUENCE、EOF clean |
| `python -m app.lwt_snake.arena --verify reports/s39-demo/result.json --catalog ...` | 0 | `Verified 9 matches: game and policy decisions.` |
| `python -m app.lwt_snake.witness --verify reports/s41-found --catalog ...` | 0 | `found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs` |
| `python -m app.lwt_snake.witness --verify reports/s41-none --catalog ...` | 0 | `found=false scanned=1/1` |
| `python -m app.lwt_snake.witness --verify reports/s41-tampered --catalog ...` | 3 | `WitnessError: agent feedback evidence mismatch` |
| `python -m app.lwt_snake.counterfactual --explain reports/s41-found/analysis --catalog ...` | 0 | baseline `R/SPACE`、bfs `D/FOOD`，score 10→10、phase RUNNING |
| 临时副本 `witness --verify`（副本改 question） | 3 | `WitnessError: agent feedback evidence mismatch`；仓库原件未改 |
| 静态审阅 `slides/LWT介绍.pptx` | — | 12 页、SHA 一致、图表 12 数值点与 S11 六组逐值一致（见 4.E） |

说明：证据链批量命令曾在一次长命令链中于 `run_tests.py`（183s）之后被工具级 `SIGTERM` 中断；被中断的 `witness s41-tampered` 与 `counterfactual --explain` 随后以独立命令重跑并通过（退出码分别为 3 与 0，上表已按重跑结果记录）。这不改变仓库文件，也不是产品缺陷。

## 6. Git 基线与提交

- 收口基线：`HEAD = main = origin/main = 5027860efc8a1cce342ca13b1434d7724aeeffc4`，工作区干净，`fetch` 后 ahead/behind `0 0`。
- 本轮按仓库工作流从 `main` 创建 `milestone/final-acceptance`（里程碑/文档收口，非 codex 前缀），仅提交文档变更；正常提交与推送，不强推、不 reset、不改写 `main`。提交 SHA、推送后远端核对与精确 SHA 的 Actions 状态在下表完成后据实填写；查询工具不可用、限流或 run 仍在运行时如实写明，不沿用候选旧 SHA 的 CI 结论。
- 本轮为文档变更，未改动程序代码，按项目门槛不重跑全量测试；第 5 节中 `run_tests.py` 与定向 CLI 属于答辩路径取证，非因代码改动而重跑。

| 项 | 值（提交推送后填写） |
|---|---|
| 收口分支 | `milestone/final-acceptance` |
| 本轮提交 SHA | 待提交后记录 |
| 推送后远端分支 SHA | 待推送后 `git ls-remote` 核对记录 |
| 该精确 SHA 的 Actions | 待查询记录 |

## 7. 遗留事项与交接

- **现场人工 GUI 验收（A–E）**：必须在无遮挡、输入归属明确的桌面，由提交者用真实物理鼠标键盘逐项完成；重点为语义实验室预测流程与输入法、日志工作台文件错误后恢复与五题挑战计分/结束/重开、LWT Snake 键盘/失焦/接管/结束态、S41 查看器载入/切换/错误反馈/关闭再开、PowerPoint 逐页播放与数字可读性。本轮桌面同时存在多窗口与 `cua-driver` 覆盖层，不满足前提，故保留未验证。
- **演示 CLI 后退**：本轮已实跑第 5 节全部命令，可在无 GUI 环境重复执行；讲述顺序见[演示脚本](demo-script.md)。
- **远端最终 SHA 的 CI**：候选 `e1249f5` 的四格成功不自动适用于本轮新提交；以本轮提交 SHA 的新 run 逐格核对为准。
- **教师线下验收、评分与归档**：不属于本执行窗口；本轮不声称教师已验收、不预判分数、不打标签、不发布。
- 未发现阻断缺陷；若后续现场人工验收发现可复现阻断缺陷，按仓库工作流先留复现证据，再单独最小修复、验证与复核，非阻断优化不纳入本轮。
