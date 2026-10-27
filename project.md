# LWT 项目上下文

> 供编程 Agent 开始任务时快速读取。最后核对：2026-10-27。这里记录**真实当前状态**；总体取舍见[总体方案](LWT大作业总体方案与复检.md)，技术草案见[详细实施规划](详细实施规划.md)，派发和审查节奏见[阶段路线图](阶段执行与审查路线图.md)。文档中的“计划命令”尚不可运行时不得报告为通过。

## 项目目标

完成[教师要求](大作业内容.md)中的 LWT 解释型通用脚本语言、解释器、完整黑盒测试、与 Python 的性能比较、人和 Agent 指南、Agent 编写的 ≥200 行完整应用、开发记录、Git 历史和介绍 PPT。最终需线下答辩演示。语言名 **LWT** 已由用户确认；解释器宿主语言选 Python 3.10+ 标准库。

## 当前状态

| 项目 | 状态 | 证据或说明 |
|---|---|---|
| Git 本地仓库 | 已建立 | `main` 有原始规划提交；已合并远端独立的 README 初始提交 |
| GitHub `origin` | 已绑定；本地阶段进度尚未推送 | [目标仓库](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT)；S13 审计时实时查询的 `origin/main` 为 S4 提交 `de608f7`；S13 已审查并合入本地 `main`，未推送；S14 开工时以实时 Git 状态确认本地基线和 ahead 数 |
| 总方向与详细规划 | 已编写并提交 | 根目录两份 Markdown；可随实施修订 |
| 阶段接力路线图 | 已编写 | S0–S11、S13–S18 已审查并合入本地 `main`；S19 阶段分支实施完成，等待主窗口审查；S12 仍为最终收尾且未开始 |
| 正式语法规范 | S1 已审查通过；S2 澄清已随实现合入 | [语言规范](docs/language-spec.md)正文含重复 record 字段错误和注释 BOM 规则 |
| CLI、错误模型与词法分析 | S2 已审查通过并合入 `main` | `lwt/cli.py`、`lwt/errors.py`、`lwt/lexer.py` |
| AST 与语法分析 | S3 带遗留通过并合入 `main`；访问符位置遗留已由 S4 独立提交修复；S6 已验证运行时定位 | `lwt/ast_nodes.py`、`lwt/parser.py`；索引/字段节点保留 `[`/`.` 位置；S6 CLI 用例验证访问错误定位 |
| 基本值、表达式、变量与基础 I/O | S4 已审查通过并合入 `main`；S6 复用其标量与整数格式化 | `lwt/runtime.py`；保持标量、变量/块、`emit`、`input()` 行为 |
| 分支、循环、作用域与函数 | S5 已审查并快进合入本地 `main`；尚未推送 | `when/otherwise`、`while`、顶层函数预登记、调用/递归/return；S6 已补齐 `each` |
| 数组、record 与 `each` | S6 已审查并快进合入本地 `main`；尚未推送 | 数组索引/赋值/别名/`push`；record 预登记、构造和字段读写；浅快照遍历；身份相等和循环安全显示 |
| 文件/文本内置函数与 CLI 集成 | S7 已审查并快进合入本地 `main` | 已支持 `args()`、`read_text()`、`len()`、`split()`、`trim()`、`to_int()`、`str()`、`fail()`；S7 提交 `4f11b80`，未推送 |
| 阶段性 lexer/parser/runtime/CLI 测试 | S7 主窗口复核通过 | Python 3.13.7；`python -m unittest discover -s tests -v`：157 项通过；`compileall`、diff 检查和跨功能示例通过；不是最终黑盒测试集 |
| 黑盒测试/CI | S8 已审查；S13 本机复核；S14 增加结构门禁 | 194 个用例（189 执行 LWT 源、5 个 CLI override）；runner、63 条规范矩阵记录、GitHub Actions 四格工作流。S14 的 `python tools/check_project_integrity.py` 检查配对/metadata/唯一 ID 和 287 个矩阵链接。本轮 Windows Python 3.13.7、WSL Ubuntu 24.04 Python 3.12.3 各 194/194；全量 unittest 各 219 项通过。Python 3.10 和远端 Actions 仍未验证 |
| 人类/Agent 指南与仓库 Skill | S9 已审查通过并合入本地 `main` | `docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/agent-blind-test.md`；三个独立上下文各自完成数组去重、record 统计、文本筛选，主窗口复跑通过。Skill 自动路由当前平台不可观察 |
| 完整 Agent 应用 | S10、S15–S18 已审查并合入本地 `main`；S19 阶段分支待审查 | [`app/log_report.lwt`](app/log_report.lwt) 保持 246 行有效代码；[`tests/test_app.py`](tests/test_app.py) 保持 25 项 CLI 集成测试。S18 新增 LWT 报告驱动工作台；S19 修复 Unicode 报告拆行，新增 Python/Tkinter 语义教学前端，课程 LWT 应用仍是日志分析器。 |
| 性能报告与 PPT | S11 已审查通过；S13 已独立复核性能 raw；PPT 待 S12 | 正式 run `291bd4e2-8a3e-4de6-be86-46b62980e656`：120 个计时子进程/60 个配对、12 个 warm-up，全部有效；本轮再次核验输出 Base64/长度/hash、pair 链接、六组 median/min/max/range/ratio 与报告一致。没有重跑或覆盖 raw，也未根据端到端比值做优化 |
| S13 全项目复检 | 已通过主窗口审查并合入本地 `main` | [`docs/comprehensive-review.md`](docs/comprehensive-review.md)；主窗口在 S13 分支复跑黑盒 194/194、全量 unittest 211 项、compileall，并核验 401 个 Markdown 链接；无阻断问题，Python 3.10/Linux 和远端 Actions 遗留转交 S14/S12 |
| S14 改进与优化 | 已通过主窗口审查并合入本地 `main` | 阶段分支最终提交 `f2dda1f7085b7c6dc56aa90cb490c4cc9b1c4e33`；代码提交 `9361f37a5c9bcd2bc7d07bbbb24949e38b35d7b6`。本窗口复跑 Windows Python 3.13.7 下 219 项 unittest、194/194 黑盒、完整性检查、compileall 和有效 LWT 行数检查，均通过。报告保留 Python 3.10 和远端 Actions 未验证风险；详见[`docs/s14-improvements.md`](docs/s14-improvements.md)。 |
| S15 应用交互升级 | 已通过主窗口审查并快进合入本地 `main`；手动 GUI 全流程曾交由 S16 验收，剩余桌面验收由 S17 复试 | 阶段最终提交 `390d484e2f21a044fcd8c9e8121712c215e1b309`，从基线 `f6ef8c62737c91a18b793c12658804cba7fca810` 快进合入。主窗口复跑全量 unittest 230 项、黑盒 194/194、完整性检查 194/287/194、compileall 和 LWT 行数 246，全部通过。GUI 的正确计分、报告窗、重开、文件选择/错误恢复、Enter 和缩放尚未形成可归因的完整手工验收。详见 [`docs/s15-app-gui.md`](docs/s15-app-gui.md)。未推送。 |
| S16 应用全面复检与独立贪吃蛇 | 带非阻断遗留通过，已快进合入本地 `main` | 主窗口在 Windows CPython 3.13.7 独立复跑全量 241 项 unittest、194 项语言黑盒、完整性检查、compileall、Snake/日志侦探/S10 定向测试、246 行 LWT 行数和 Markdown 链接，均通过；保护的 S10/S11 原始文件无差异。S15 GUI 全流程及 Snake 桌面交互受接口限制仍未验证，转交 S17 优先尝试。详见报告：[S16 应用复检与贪吃蛇](docs/s16-app-review-snake.md)。 |
| S17 应用复检、视觉与交互打磨 | 带非阻断桌面遗留通过并快进合入本地 `main` | 阶段最终 SHA `86f40826fc2723f7a17a6d73944f184d3c7993b0`；主窗口独立复跑 243 项 unittest、194/194 黑盒、完整性检查、compileall 和 246 行统计，并实际操作两款 GUI 的主路径。剩余桌面边界见 [复核记录](docs/s17-main-review.md)。 |
| S18 LWT 驱动分析工作台与证据强化 | 带非阻断 Unicode 边界遗留通过并合入本地 `main` | [S18 工作报告](docs/s18-workbench.md)、[展示说明](docs/s18-app-showcase.md)与[主窗口复核](docs/s18-main-review.md)；保留五题挑战，新增严格报告解析、交互查询、可视图表和可追溯原始输出。主窗口复跑 256 项 unittest、194/194 黑盒；合法 U+2028 消息触发视图误拆行，S19 首项处理。 |
| S19 语言语义实验室与报告边界修复 | 阶段分支实施完成，等待主窗口审查 | [S19 执行报告](docs/s19-language-lab.md)；LF-only 报告解析修复，新增 6 个真实 CLI 教学示例、11 项定向测试；GUI 手工验收限制如实记录。 |

## 已定技术决策

1. 解释器采用 Token → AST → 运行时树遍历；不直接用 Python `eval/exec` 执行 LWT 源码。
2. LWT 至少支持整数、字符串、数组、命名结构、基础 I/O、分支循环、函数定义与调用。`record`、`when/otherwise`、`each`、`emit` 是规划中的可见特色；具体语义已写入[已审查语言规范](docs/language-spec.md)，S2 分支已补入重复字段诊断和注释 BOM 处理两项澄清。
3. 测试用 `.lwt` 写被测程序；Python 驱动只从 CLI 比较 stdout、stderr、退出码。覆盖矩阵比用例总数更重要。
4. 性能采用 LWT/Python 同算法、同输入、相同输出校验的新进程端到端计时；报告原始重复测量，不预设结果。
5. S10 Agent 应用是只读 LWT CLI 日志分析器；多个独立进程读取同一固定文件的证据只说明进程级输出一致性。S15 增加 Python/Tkinter 游戏界面，所有日志读取、过滤与统计仍由公开 LWT CLI 处理；不宣称支持 LWT 图形接口或线程。
6. 提交物逐阶段形成。语义变更需同步正式规范、示例和测试；`project.md` 的状态随阶段更新。

## 已审查阶段与下一步工作顺序

1. **S1、S2 已审查通过**：S1 语言规范和 S2 CLI/错误/词法实现均已合入 `main`；S2 同步补齐重复 `record` 字段诊断和注释 BOM 规则。
2. **S3：AST 与语法分析**：已审查并合入 `main`。S4 首项独立提交 `69eee93` 为索引/字段节点添加访问符位置，表达式起点和字段名位置均保留；S6 已通过 CLI 黑盒测试验证索引和字段运行时错误的访问符位置。
3. **S4：基本值、表达式、变量与基础输入输出**：已审查通过并合入 `main`。支持标量 runtime、变量/块作用域、`emit`、`input()` 和任意精度十进制整数；当时尚未实现的结构在 S4 阶段由执行前预检拒绝，数组/record 等已分别由 S6 实现。S7 的 `to_int()`/`str()` 已复用并验证 S4/S6 的小块十进制转换策略。
4. **S5：分支、循环、作用域与函数**：已审查并快进合入本地 `main`。主窗口独立复跑 101 项测试，并实际运行两个阶段示例，均通过。支持 `when/otherwise`、`while`、顶层函数预登记、前向/相互/递归调用和 return。`origin/main` 仍停留在 S4；本地 S5 提交尚未推送。
5. **S6：数组、结构与 `each`**：已审查并快进合入本地 `main`。主窗口复跑 137 项测试、`compileall` 和 collections 示例均通过；已覆盖数组/record 别名、访问和赋值顺序、record 构造字段预验证、`push`、`each` 浅快照、循环相等和显示。S6 尚未推送远端。
6. **S7：文件/文本内置函数与完整集成**：已审查并快进合入本地 `main`，提交 `4f11b80`；未推送。主窗口复跑 157 项 unittest、`compileall`、diff 检查及 `examples/text_tools.lwt`，均通过；八个内置函数和 CLI 参数接线符合规范，有效语法不再走临时 `Incomplete`/1。
7. **S8：完整黑盒测试、覆盖矩阵与 CI**：已审查并快进合入本地 `main`，阶段提交 `e2c5f2b`，主窗口补强提交 `8789408`；未推送。194 项黑盒覆盖 63 条规范规则记录，runner 经公开 CLI 执行。主窗口发现并修复空用例集误报成功的问题，新增回归测试。主窗口复跑 194 项黑盒、174 项 unittest、compileall、diff 检查及临时目录启动，均通过。远端 Actions 未触发，Python 3.10/Linux 尚未实测。
8. **S9：人类/Agent 指南与独立盲测**：已通过主窗口审查并快进合入本地 `main`，阶段最终提交 `165451a5ff2b6f7febba69514bb3a5095fba3b09`。主窗口复跑 194 项黑盒、174 项 unittest、compileall 和所有指南/盲测 CLI 示例；三份独立工作树和各自产物已核对。Skill 自动路由当前平台不可观察，文档未声称自动触发已通过。
9. **S10：Agent 编写的完整 LWT 应用**：已在 `stage/s10-agent-log-analyzer` 实现只读日志分析器，246 行有效 LWT；公开 CLI 应用测试 25 项；样例输出及过滤输出符合契约；并发固定文件以 1/2/4 独立进程各 5 轮验证，全部 stdout 与 warm-up 字节一致、stderr 空、退出码 0。主窗口审查时复跑黑盒 194/194、全量 unittest 199 项、应用测试 25 项、compileall、行数工具和并发驱动，均通过。审查补充提交 `56e1c23` 明确以 `--` 开头的选项值限制、强化默认 Top-5 截断用例和 usage 退出码断言；随后阶段分支已快进合入本地 `main`。过程和原始证据见 `docs/agent-dev-log.md`、`docs/app-concurrency.md`、`reports/app-concurrency.json`。未推送。
10. **S11：LWT/Python 性能实验与报告**：已在 `stage/s11-performance-report` 上实现 arithmetic 与 array_scan 两组成对程序、标准库 runner 和定向测试。校准中的 Windows stdout 换行差异已修正；失败 run 保留，修复后校准有效。正式 run `291bd4e2-8a3e-4de6-be86-46b62980e656` 由干净提交 `c6f38a0e9ee796c9ac82498599d91da542ae325a` 采集，120/120 正式子进程及 12/12 warm-up 均通过；主窗口从原始 JSON 独立复算六组 median/min/max/range/ratio，并复核输出哈希和源文件哈希。主窗口发现失败子进程和其无效配对可能被重复计为两次失败，已在提交 `2d2585c` 拆分计数并加回归测试；定向测试 12 项、全量 unittest 211 项通过。S11 已审查通过并快进合入本地 `main`，未推送。
11. **S13：全面复检、证据审计与有根据的优化**：已通过主窗口审查并合入本地 `main`。报告[`docs/comprehensive-review.md`](docs/comprehensive-review.md) 记录课程交付追踪、规范/实现/矩阵映射、S10/S11 证据、逐项命令结果和风险。审计阶段没有定位到运行时性能热点，因此未做性能代码改动；S13 执行未制作 PPT、未做新克隆验收、未推送。
12. **S14：审计遗留处理、质量保障升级与证据驱动优化**：已通过主窗口审查并快进合入本地 `main`；阶段分支最终提交 `f2dda1f`。新增标准库完整性检查并接入 CI；结构/矩阵测试 7 项、权限错误 CLI 测试 1 项通过；执行窗口报告 Windows 3.13.7 和 Ubuntu/Linux 3.12.3 全量回归通过。本窗口在 Windows 3.13.7 独立复跑 219 项 unittest、194/194 黑盒、完整性检查、compileall 和 LWT 行数统计，均通过。Python 3.10/远端 CI 与远端同步留待 S12；未做 runtime profile/优化，理由和证据见报告。
13. **S15：日志分析器 GUI 小游戏增强**：已审查通过并快进合入本地 `main`，阶段最终提交 `390d484e2f21a044fcd8c9e8121712c215e1b309`。主窗口复跑 `python -m unittest discover -s tests -q`（230 项）、`python tools/run_tests.py`（194/194）、`python tools/check_project_integrity.py`（194 cases、287 matrix links、194 referenced cases）、`python -m compileall -q lwt tests tools bench app` 和有效 LWT 行数检查（246 行），均通过；`git diff --check main...HEAD` 通过。Tkinter/Tk 8.6 曾成功启动，但 GUI 全流程未能归因于执行窗口操作，故保留正确计分、报告窗口、重新开始、GUI 文件选择/错误恢复、Enter、缩放等手工验收项。该遗留不阻挡合入，将由 S16 首先进行可复核验收。S10 并发数据和 S11 性能 raw 未改；未推送。
14. **S16：应用全面复检与独立图形化贪吃蛇**：已带非阻断遗留通过并快进合入本地 `main`。从基线 `09cf5f5eb4d1dded17fd43b84d3e5b48e0dd62b6` 建立 `stage/s16-app-review-snake`，最终提交 `33570839766f3c0fa04da2b09de0b6158262c92f`。S10/S15 定向审计未发现可复现缺陷；未改 `app/log_report.lwt`、既有 CLI 契约、25 项 S10 测试、S10 并发 raw 或 S11 性能报告/JSON。新增独立 Python/Tkinter 贪吃蛇和 11 项无头测试；主窗口独立复跑全量 unittest 241 项、语言黑盒 194/194、完整性检查、compileall、246 行 LWT 统计及相关定向测试，均通过。桌面接口缺少可操作窗口和输入能力，S15 GUI 全流程和 Snake 桌面实测仍未验证；S17 首项再尝试，不能以自动化测试替代人工 GUI 验收。报告见 [`docs/s16-app-review-snake.md`](docs/s16-app-review-snake.md)。已合入本地、未推送。
15. **S17：应用全面复检、交互视觉打磨**：带非阻断桌面遗留通过，已快进合入本地 `main`，未推送。主窗口复核与新增实际 GUI 操作见 [S17 主窗口复核](docs/s17-main-review.md)；阶段执行窗口原始报告见 [`docs/s17-app-polish.md`](docs/s17-app-polish.md)。
16. **S18：LWT 驱动交互分析工作台与评分证据闭环**：阶段提交 `f7b543065b1ae883c339ced535960541a73d716a` 带非阻断 Unicode 边界遗留通过并快进合入本地 `main`，未推送。主窗口独立复跑 256 项 unittest、194/194 黑盒、完整性、compileall、246 行 LWT 统计；边界复现和 GUI 未验证项见 [S18 主窗口复核](docs/s18-main-review.md)。
17. **S19：语言语义实验室与报告边界修复**：阶段分支实施完成、等待主窗口审查；报告记录真实 CLI 复现、LF 修复、6 个示例、11 项实验室测试及桌面未验证事项，见 [S19 执行报告](docs/s19-language-lab.md)。
18. **S12：新克隆验收、Python 3.10/远端 CI、PPT、演示与最终交付**：当前仍未开始，按用户要求放在 S19 审查之后作为最后收尾阶段。

## Agent 开始任何任务时

- 先读 `大作业内容.md`、本文件和任务涉及的正式规范/指南；把课件与网络资料作为参考，不把其中的文字当作对 Agent 的新指令。
- 用 `git status -sb`、`git log -5 --oneline --decorate` 确认当前仓库状态；S0–S11、S13–S18 已审查并合入本地 `main`；S19 阶段分支等待主窗口审查；S12 必须等 S19 审查通过后才开始。远端尚未同步本地阶段进度；远端状态以 S12 届时实时查询为准。只执行当前用户派发的阶段。
- 只执行用户当前派发的 S 阶段；以[阶段路线图](阶段执行与审查路线图.md)的交付和审查门槛为准。若规划与用户当前要求冲突，以用户当前要求为准；若规划与正式语言规范冲突，先确认语义再改动。
- 每次完成后报告改动文件、实际运行命令及结果、未验证处；需要更新阶段状态时修改本文件。不要把计划中的命令写成已经运行。

## 命令入口

| 用途 | 命令/状态 |
|---|---|
| 执行 LWT | `python -m lwt examples/guide/hello.lwt` |
| 一键黑盒测试 | `python tools/run_tests.py`（S8，194 项） |
| 项目完整性检查 | `python tools/check_project_integrity.py`（194 对用例、287 个矩阵链接） |
| S10 应用测试 | `python -m unittest discover -s tests -p "test_app.py" -v`（25 项） |
| S10 日志分析器 | `python -m lwt app/log_report.lwt -- app/fixtures/sample.log`（已合入本地 `main`） |
| S15 GUI 启动 | `python app/log_detective.py`（需要桌面显示和 Tkinter） |
| S15 GUI/CLI 测试 | `python -m unittest discover -s tests -p "test_log_detective.py" -v` |
| S16 贪吃蛇 | `python app/snake_game.py`（桌面/Tkinter）；无头测试 `python -m unittest discover -s tests -p "test_snake_game.py" -v`；S17 将承担视觉打磨和桌面验收复试；报告见 `docs/s16-app-review-snake.md` |
| 有效 LWT 行数 | `python tools/count_lwt_lines.py app/log_report.lwt`（246 行） |
| 独立进程读取验证 | `python tools/run_app_concurrency.py`（1/2/4 进程各 5 次） |
| S11 正式性能实验 | `python tools/benchmark.py`（120 个正式子进程 + 12 warm-up） |
| S11 非正式校准 | `python tools/benchmark.py --calibration`（raw 记录保留但不进入正式报告统计） |
| S11 报告与原始数据 | [`reports/performance.md`](reports/performance.md)、[`bench/results.json`](bench/results.json) |
| S13 综合审计 | 已通过主窗口审查；证据见 [`docs/comprehensive-review.md`](docs/comprehensive-review.md) |
| S14 改进与优化 | 已通过主窗口审查并合入本地 `main`；报告见 [`docs/s14-improvements.md`](docs/s14-improvements.md) |
| S15 应用 GUI 小游戏 | 已通过主窗口审查并合入本地 `main`；手工验收遗留经 S16 复检后由 S17 复试；报告见 [`docs/s15-app-gui.md`](docs/s15-app-gui.md) |
| S16 独立贪吃蛇 | 已通过主窗口审查并合入本地 `main`；桌面验收与 S15 遗留转交 S17；报告见 [`docs/s16-app-review-snake.md`](docs/s16-app-review-snake.md) |
| S17 GUI 复检与打磨 | 已审查并合入本地 `main`；主路径实测及剩余边界见 [主窗口复核](docs/s17-main-review.md) |
| S18 交互分析工作台 | 已带遗留通过并合入本地 `main`；[主窗口复核](docs/s18-main-review.md) |
| S19 语言语义实验室 | 已实施，阶段分支等待主窗口审查；[工作报告](docs/s19-language-lab.md) |
| 最终应用/答辩演示 | 延后至 S19 主窗口审查通过后进入最终阶段 S12；当前未开始 |

## 完成定义与重点风险

所有必需功能都有正常、边界、错误测试；一键命令在新克隆目录可运行；性能实验先验证 warm-up，正式输出校验位于计时区间外，失败样本留存；Agent 应用有至少 200 行有效 LWT、功能和并发读取证据；Git 历史与 PPT 的数值对应真实提交。最需防止的是“文档写了但代码没有”“Agent 说已测试但没有命令输出”“性能口径不一致”“测试数量代替语义覆盖”。

## 资料入口

- [作业原文](大作业内容.md)；[语言规范草案](docs/language-spec.md)；[总方向](LWT大作业总体方案与复检.md)；[详细规划](详细实施规划.md)；[阶段路线图](阶段执行与审查路线图.md)。
- [GitHub 仓库](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT)。
- 上级目录的三份课程 PDF；详细规划末尾列出已经核对的官方/原作者资料。
