# S10 Agent 开发记录

日期：2026-10-07。本文只记录可观察的指令、文件、提交、命令结果和审查状态，不包含隐藏思维链。

## 身份、基线与方法

- **阶段分支：** `stage/s10-agent-log-analyzer`。
- **基线：** 已审查并合入本地 `main` 的 S9 状态 `a4bb0116ff44b91496d265b4eb3dc2d5e27cadae`；开工时工作区干净，远端 `origin/main` 为 `de608f7fbf50946715d370df014657169eb8f26d`，仍处 S4。
- **执行环境：** Windows 11 `10.0.26200`，Python `3.13.7`，64 位；本阶段不安装第三方依赖。
- **Agent/模型：** Codex 执行窗口。平台没有向本记录暴露精确模型标签或本任务内部 session ID；不推断模型路由。没有把自动 `lwt-app` Skill 触发记作已观察事实。
- **Skill 使用方式：** 按 S10 提示显式读取并遵循 `.agents/skills/lwt-app/SKILL.md`，并查阅其链接的开发指南、正式语言规范和测试覆盖矩阵。当前界面不能验证 Skill 是否被自动选中。
- **实际任务：** 用户派发的“S10 执行任务：Agent 编写完整 LWT 日志分析器与并发读取验证”。任务要求只用 LWT 实现只读日志分析，应用逻辑不进入 Python 驱动；冻结输入/CLI/报告契约；通过公开 CLI 测试；用固定文件对 1/2/4 个独立进程各做 5 次并发读取；记录原始输出、退出码、SHA、时间和环境；不改语言语义、不做 S11 性能比较、不合并或推送。

## 设计与实现决定

1. `app/log_report.lwt` 先完整解析并验证应用参数，再读文件或输出报告。参数错误通过 LWT `fail()` 产生单行 usage 运行时诊断，stdout 为空。输入文件读取失败沿用 `read_text()` 的运行时错误行为，不捕获或伪装解释器错误。
2. 有效记录只按 `|` 分割后的字段数恰为 4 判断；空字段合法，坏行继续计数并继续处理。逻辑行拆分只从非空文本最后移除一个由终止 LF 产生的空分割项；此前的空行保留并计作坏行。
3. `--level` 精确匹配 level；`--keyword` 用规范已有的 `split(message, keyword)` 判断 message 子串，不检查其他字段。两个筛选条件是 AND。级别按名字升序，模块按 count 降序、名字升序；`--top` 不影响级别统计和前三条示例。
4. LWT 没有字符串索引。`--top` 的 ASCII 数字校验在 LWT 中依次用每个数字字符串调用 `split` 并移除出现项，再确认没有剩余字符，然后调用 `to_int()`；负号、加号、空白、空串和非数字会得到 usage 错误。单独记录 `has_top`，因此显式重复 `--top 5` 也会被拒绝。
5. 聚合只用 LWT 数组与 record 线性查找，不添加字典、类、解释器 API 或其他内置函数。若有 `R` 条匹配记录、`M` 个不同模块和 `L` 个不同级别，聚合为 `O(R×(M+L))`；级别选择排序 `O(L²)`；输出 `K=min(M, top)` 个模块的选择排序 `O(M×K)`。应用一次性读取整个文件并保留逻辑行。
6. 并发驱动的线程池/barrier 只负责同时启动外部子进程。被测应用始终是 `python -m lwt`；用参数列表、`shell=False`、显式仓库 `cwd`、有限 timeout 和 `communicate()` 收集输出。每轮比较字节、返回码和 stderr，并在试验后复核固定输入哈希。

## 可观察工作记录

| 顺序 | 提交/节点 | 实际工作和结果 |
|---:|---|---|
| 1 | 基线 `a4bb0116ff44b91496d265b4eb3dc2d5e27cadae` | 核对当前分支、工作区、远端和 S9 审查状态；确认预期基线一致；从本地 `main` 创建 S10 阶段分支。 |
| 2 | `f7bde96f95861c6090d343b0a181061b93b3d601` | 添加 LWT 应用、固定样例和异常 fixture、`app/README.md`、`tools/count_lwt_lines.py` 及初始公开 CLI 集成测试。样例 CLI 实际输出与规范样例一致。 |
| 3 | `476084d7ddee26b14c8170585343b1cbcd37c7c1` | 添加 120 行并发 fixture 和独立进程测试工具。首次并发运行对 1/2/4 进程各 5 轮均观察到输出一致、成功退出且 stderr 为空。 |
| 4 | `da8210f7d9b6786fe4f5efedfa10bec4f685ea32` | 自查后增强驱动：记录并检查输入文件试验前后 SHA-256，输入有变化时整体失败；再次运行完整并发试验。 |
| 5 | `4e010043cde9239128ec13d61ec15e0ca2a44117` | 增加 6000 位十进制 `--top` 集成测试，确认 CLI 输入经 LWT `to_int()` 处理，不触发宿主 Python 的十进制位数限制。 |
| 6 | 本提交前的收尾 | 更新根 README、`project.md`、总体方案、详细规划和阶段路线图；准备本开发记录。当前主窗口审查尚未发生，不能记录审查通过或人工审查修复。 |

### 自查修改、命令失败与修复

- 编写参数解析时，自查发现默认 `top=5` 不能用来判断用户是否已显式提供 `--top`，因此在 `Options` record 增加 `has_top`，确保第二个 `--top 5` 也按重复参数拒绝；在自动化测试前完成修正。
- 自查发现空字符串不能被 `begins_with_option()` 误判成以 `--` 开头，否则空 keyword 会被报告成缺少值。函数增加空串特例，并由参数集成测试覆盖。
- 早期先调用 `python tools/count_lwt_lines.py app/log_report.lwt` 时，计数工具尚未创建，命令返回文件不存在；随后新增工具并重跑成功，结果为 246。该次顺序失误不是 LWT 应用或测试失败。
- 本阶段未发生应用 CLI、S10 集成测试或并发验收失败；首次正式定向测试即通过。主窗口人工审查仍待进行。

## 实际验证

| 命令 | 实际结果 |
|---|---|
| `python tools/run_tests.py` | S8 语言黑盒仍为 194 项，194 通过、0 失败；应用测试没有并入 S8 用例矩阵。 |
| `python -m unittest discover -s tests -q` | 199 项通过（S9 的 174 项基线 + 25 项 S10 应用测试）。 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | S10 定向集 25 项通过。 |
| `python -m compileall -q lwt tests tools` | 退出码 0。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | `Effective LWT lines: 246`；排除空行、纯注释行和仅花括号/分号的行。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 退出码 0、stderr 空；stdout 与 `app/fixtures/sample.expected.txt` 逐字匹配。6 条有效、1 条坏记录。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | 退出码 0、stderr 空；1 条匹配，level 为 `WARN|1`，module 为 `cache|1`，示例为规范指定的 WARN retry 行。 |
| `python tools/run_app_concurrency.py` | warm-up 成功；在提交 `4e010043cde9239128ec13d61ec15e0ca2a44117` 上对 1、2、4 个进程各完成 5 个试次，共 35 个进程；每个 stdout 与 warm-up 字节相同，所有 return code 为 0、stderr 为空，输入前后哈希一致。 |
| 本地干净克隆复现 | 使用 `git clone --local --no-hardlinks --branch stage/s10-agent-log-analyzer <repo> <temp>/checkout` 创建临时克隆，克隆 HEAD 为 `99acb37af431b1ba40f9266c1d67ee0e393d9f9f`；在克隆根目录运行 README 默认命令 `python -m lwt app/log_report.lwt -- app/fixtures/sample.log`，退出码 0、stderr 为空，stdout 与克隆内 expected 文件逐字匹配。临时克隆在测试结束时删除。 |

并发固定文件为 `app/fixtures/concurrency.log`，120 条记录、7846 bytes，SHA-256 `512fa16f3d0ea7911709dbf4ee5a3ba13a05f926be01c071106973aa9909a118`。应用源文件来自提交 `f7bde96f95861c6090d343b0a181061b93b3d601`，其 SHA-256 为 `39807dd117813578896bc68165f161c48c106a99603a22406c7e4e637aa8acc1`。最后一次试验每组 5 个批次墙钟时间（毫秒）为：1 进程 `[114.724, 117.517, 119.408, 116.536, 119.902]`；2 进程 `[128.779, 133.330, 131.858, 133.494, 132.105]`；4 进程 `[141.669, 141.270, 139.623, 142.419, 139.272]`。每个子进程的返回码、完整 stdout/stderr Base64 原字节、长度和 SHA-256，以及命令、OS、Python、日期和计时数据均在 [`reports/app-concurrency.json`](../reports/app-concurrency.json)；方法、结果表和限制见 [`docs/app-concurrency.md`](app-concurrency.md)。

计时采用 `time.perf_counter_ns()` 测整批端到端墙钟时间，包含子进程启动、Python 导入、LWT 词法/语法分析、应用执行、输出和文件读取；不将其解释为纯磁盘吞吐、LWT/Python 性能对比或“更多进程更快”。Python 标准库接口依据官方 [subprocess 文档](https://docs.python.org/3/library/subprocess.html)和 [time.perf_counter_ns 文档](https://docs.python.org/3/library/time.html#time.perf_counter_ns)，访问日期为 2026-10-07。

## 审查状态与限制

- 自查已核对语言规范约束、CLI 边界、报告布局、空字段、末尾 LF、连续换行、坏行后继续处理、Unicode 子串、大小写、并列排序、0/默认/top 1、参数失败诊断和文件读取失败。
- 没有变更 `lwt/`、语言规范、S8 的 `tests/cases/` 或覆盖矩阵；没有 Python 日志解析/聚合实现。
- 当前仅在 Windows 11 / Python 3.13.7 运行；没有在 Linux 或 Python 3.10 运行本应用。S8 既有远端 Actions 未触发状态不因本阶段而改变。
- 并发数据对固定提交、固定输入和本机环境有效；OS 文件缓存、后台负载及应用一次性读全文件限制仍适用。输入没有被应用修改；不测试其他写进程同时改写文件。
- S10 实现和测试完成，**等待主窗口审查**；本记录不预写审查通过。阶段分支未推送、未合入 `main`，S11 未开始。

## S15｜日志侦探 GUI 与 CLI 集成（2026-10-07）

### 接收任务和范围判断

- **实际任务：** 用户派发 S15，要求在保留 S10 LWT 日志分析器和既有证据的情况下，增加可实际交互的 Python/Tkinter 桌面小游戏；题目统计必须来自公开 LWT CLI。另要求无头自动测试、Tk 可用时手动验收、同步阶段文档并按代码/测试/文档分次提交。
- **阶段基线：** 本地 `main` `f6ef8c62737c91a18b793c12658804cba7fca810`，工作区初始干净；从该基线创建 `stage/s15-log-detective-gui`。开工时远端跟踪值和实时 `git ls-remote origin refs/heads/main` 为 `de608f7fbf50946715d370df014657169eb8f26d`，不作为分支基线。
- **保留的契约：** `app/log_report.lwt` 246 行有效 LWT；既有 CLI 默认和 AND 过滤输出；25 项 `tests/test_app.py`；固定并发输入及其历史 raw/Markdown；不改运行时、正式语言规范、黑盒矩阵和 S11 性能 raw。课程要求的 ≥200 行 LWT 应用仍是应用主体，GUI 是宿主端体验增强。
- **环境事实：** Windows CPython 3.13.7；`tkinter` 可导入，Tk 8.6。`python -m tkinter` 诊断窗实际显示 Tcl/Tk 8.6.15 并通过 Quit 关闭。Tkinter 可为可选模块，不能推断所有 Python 安装都提供 GUI。

### 设计选择和实际迭代

1. 将模块分成无 Tk 的 `app/log_detective_core.py`、Tk 视图 `app/log_detective_ui.py` 和启动入口 `app/log_detective.py`。根路径由 `__file__` 定位；入口路径可以从仓库外以绝对路径启动。
2. 五道默认题覆盖 INFO、WARN、`retry` 关键词、ERROR 和 `WARN AND retry`。每题调用 `sys.executable -m lwt ...`，使用 argv 列表、`shell=False`、仓库根 `cwd`、UTF-8 和 20 秒 timeout。Python 只从完整 LWT 报告严格读取且只接受唯一一行 `Matched records: N`；不读/拆分日志、不计算答案。
3. GUI 查询放入后台线程，通过 `queue.Queue` 返回结果，窗口控件只在 Tk 主线程更新；入口导入不创建根窗口。答案支持 Enter；题号、进度、分数、正误文字、正确答案、最终得分和重开均有明确状态。
4. 报告解析拒绝缺失、重复、负数、非十进制字段；捕获 Python 十进制整数位数限制并转成可读分析器错误。进程超时、启动失败、无效参数、CLI 非零退出和意外报告格式也转成 `AnalyzerError`。界面捕获可读错误，仍可重开或另选日志。
5. 早期集成测试曾错误假设报告会回显过滤命令；实际固定 stdout 只含统计内容，没有参数回显。我依据 S10 CLI 契约把断言改为核对 `WARN|1` 和真实示例记录后重跑通过，没有修改 LWT 程序。
6. 自查时发现报告子进程结束后未重渲染答题按钮状态，且失败查询时提交按钮可能提前启用。修正为查询结果成功后才允许提交，并在完整报告窗口打开后恢复当前游戏控件；修复单独提交，避免把此状态问题留给主窗口。
7. 桌面窗口启动并显示。另从临时目录以绝对入口路径启动了第二个窗口，窗口成功创建；其他窗口遮挡了默认路径完整内容。开始时观察到默认样例与 0/5 起始画面；后续观察到第 4/5 题、答错文字、正确值 2、当前输入 6、得分 0、下一题按钮，以及“挑战完成”结果页。操作期间计算机使用工具报告桌面用户输入，无法把后续点击/输入归因于本执行窗口；因此不将正确作答、报告窗口、重开、自选文件、错误恢复、键盘和缩放的完整人工流程记作已通过。该限制在 [`s15-app-gui.md`](s15-app-gui.md) 中保留，供主窗口复核。
8. 没有实施独立 Agent 盲测或把自动路由说成触发；也没有独立主窗口代码审查。本记录只含执行窗口自查和实际命令证据。

### 提交

| 顺序 | 提交 | 内容 |
|---:|---|---|
| 1 | `b8cb5604ba5e8968b099b9b42e52f90fc74ac573` | 桌面启动入口、纯查询/报告/游戏状态逻辑和 Tkinter UI。 |
| 2 | `2c49b356bfc34c3f56ff6b2a22705127dddafa2b` | 11 项无头单元及真实公开 CLI 集成测试。 |
| 3 | `5fd6f399814577b5d180905007fb7059ac73cd62` | 复核后修复完整报告完成时控件状态恢复和查询前答案按钮状态。 |
| 4 | 文档提交 | 本开发记录、S15 报告以及 README、project、总体方案、详细规划和路线图更新；文档提交的最终 SHA 由执行报告给出。 |

### 实际命令和结果

| 命令/检查 | 结果 |
|---|---|
| `python --version` | Python 3.13.7，退出码 0。 |
| `python tools/check_project_integrity.py` | 退出码 0；194 cases、287 matrix links、194 referenced cases。 |
| `python tools/run_tests.py` | 退出码 0；语言黑盒 194/194 通过。 |
| `python -m unittest discover -s tests -q` | 退出码 0；230 项通过。 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 退出码 0；原 S10 应用测试 25 项通过。 |
| `python -m unittest discover -s tests -p "test_log_detective.py" -v` | 退出码 0；11 项通过，含默认/AND/Unicode 路径真实 CLI 集成、状态机及错误处理。 |
| `python -m compileall -q lwt tests tools bench app` | 退出码 0。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 退出码 0；有效 LWT 行数 246。 |
| `git diff --check` / `git diff --check main...HEAD` | 退出码均为 0；没有空白错误。 |
| Markdown 本地链接与代码围栏 | 19 个 Markdown 文件、426 个本地链接；代码围栏平衡，检查通过。 |
| 默认 CLI 示例 | 退出码 0，stderr 空；6 条匹配、6 条有效记录、1 条坏记录，与已提交期望输出契约一致。 |
| `--level WARN --keyword retry --top 2` CLI 示例 | 退出码 0，stderr 空；1 条匹配，`WARN|1`、`cache|1` 和 `retry scheduled` 样例。 |
| `python tools/run_app_concurrency.py` | 在临时一次性 worktree 的最终代码提交 `5fd6f399814577b5d180905007fb7059ac73cd62` 中执行以避免覆盖 S10 已提交 raw；退出码 0。Warm-up 成功，1/2/4 进程各 5 轮、共 35 个子进程；每个 stdout 与 warm-up 字节相同，所有 return code 为 0、stderr 为空，输入 SHA-256 前后未变（`9db070518d4bfa375e62eca0000e84835432e03e4156778b6c204a7a50321214`）。批次毫秒：1 `[187.911, 172.352, 180.338, 168.139, 195.441]`，2 `[192.580, 200.891, 183.362, 181.600, 181.868]`，4 `[190.779, 206.275, 192.049, 192.046, 199.309]`。临时 worktree 中生成的 raw 已随目录删除，原始 S10 报告文件未改；不据此作性能结论。 |

正式 S11 `bench/results.json` 未重新运行或改写。Python 3.10、远端 Actions 和完整可归因的人工 GUI 操作轨迹尚未验证；Python 3.10、远端 CI、新克隆、PPT 和最终演示交由 S12。S15 没有合并或推送，当前结论为**实施完成，等待主窗口审查**。

## S16｜应用复检与独立贪吃蛇（2026-10-07）

- **分支与基线：** `stage/s16-app-review-snake`；基线为已审查本地 `main` 的 `09cf5f5eb4d1dded17fd43b84d3e5b48e0dd62b6`。开工时工作区干净，S15 最终提交 `390d484e2f21a044fcd8c9e8121712c215e1b309` 为基线祖先。实时 `origin/main` 为 `de608f7fbf50946715d370df014657169eb8f26d`，本地比远端领先 44 个提交；未推送。
- **工作范围：** 完成 S15 GUI 遗留的桌面可用性检查；定向审计 S10/S15 应用及相关测试/fixture/并发文档；新增独立 Python/Tkinter 贪吃蛇、无头核心、界面、规则测试和文档。课程要求的 246 行有效 LWT 日志分析器仍是 LWT 应用主体。
- **审计结论：** S10/S15 自动测试和代码复核没有发现可稳定复现的缺陷。子进程继续使用参数数组、`sys.executable -m lwt`、仓库根 `cwd`、`shell=False`、UTF-8 与 timeout；工作线程只等待 CLI，Tk 更新由主线程队列轮询处理。未改日志分析器、CLI 契约或现有应用实现。
- **贪吃蛇提交：** `930c6d13d8f7cbffb9cb98a91e81b64ff846d2ef` 添加启动入口、纯状态核心、Tkinter Canvas UI 和 11 项无头测试。实现固定 tick、碰撞、增分/增长、反向输入拒绝、即将离开的尾格规则、自动失焦暂停、随机空格投食与满盘胜利。
- **人工 GUI 验收限制：** `python -c "import tkinter; print(tkinter.TkVersion)"` 实际输出 Tk 8.6，但本会话桌面工具返回 `apps: []`，`cua.listApps()` / `cua.listWindows()` 不可用，无法实际点击、键入或归因窗口操作。因此 S15 游戏的计分/报告/重开/文件选择/错误恢复/Enter/缩放均未验证，Snake 的窗口/按键/缩放/焦点实测也未验证。完整逐项记录在[`docs/s16-app-review-snake.md`](s16-app-review-snake.md)。
- **最终自动验证：** `python -m unittest discover -s tests -p "test_snake_game.py" -v` 11 项通过；S15 `test_log_detective.py` 11 项通过；S10 `test_app.py` 25 项通过；全量 unittest 241 项通过；黑盒测试 194/194；完整性检查 194 cases / 287 matrix links / 194 referenced cases；compileall 通过；LWT 行数 246；默认和组合过滤 CLI 均退出码 0。
- **历史证据：** 未运行 `python tools/run_app_concurrency.py`，因为没有发现影响既有并发结论的缺陷且该命令会覆盖受保护 raw；未运行正式性能基准。S10 并发记录和 S11 性能 JSON/报告未更改。S12 未开始。
- **阶段状态：** 实施完成，等待主窗口审查；没有合并或推送。完整命令表和风险列于[`S16 执行报告`](s16-app-review-snake.md)。

## S17｜应用复检与 GUI 视觉/交互打磨（2026-10-07）

- **基线与分支：** 开工在干净 `main`，HEAD `ffc276f941c591f804ad7b78d976c36ee87bf59a`，与提示规划基线相同。`git status -sb` 显示本地 `main` 比 `origin/main` 跟踪值 ahead 48；本阶段未查询实时远端，未同步或推送。由该基线创建 `stage/s17-app-polish`。
- **桌面接口与启动尝试：** `cua.getState()` 返回 `apps: []`，只列浏览器表面且浏览器状态请求失败；没有截图、点击或键盘输入操作。Windows CPython 3.13.7、Tk 8.6。代码修改后分别启动 `app/log_detective.py` 与 `app/snake_game.py`；系统主窗口标题为 `LWT 日志侦探` 和 `LWT 贪吃蛇`，两者窗口句柄非零，WM_CLOSE 后进程均以退出码 0 结束。没有人工执行窗口中的任何玩法流程。
- **审查与改进：** 核对 S10 LWT CLI 边界、S15 worker/queue/Tk 主线程交互与关闭轮询、Snake 单挂起 `after` 定时器和焦点暂停。新建共享 `app/ui_theme.py`，使用 Tk `TkDefaultFont` 回退；日志侦探更新卡片、动态换行、正误/忙闲状态显示、Enter 事件收尾和关闭轮询取消；Snake 更新 HUD/控制说明/动态遮罩与小格网格细节。
- **缺陷复现与修复：** GAME_OVER/WON 的旧主按钮分支只调用 `restart()`，无头复现得到 `ready` 且 tick 不会安排，与“再来一局”文案不符。`SnakeGame.activate_primary_action()` 现在对终态重置后立即开始；应用主按钮共用该状态动作。添加终态输局、满盘胜利各一项回归，断言新局状态 RUNNING、得分归零、蛇身重置。此结果是可控状态测试，不是 GUI 点击实测。
- **代码/测试提交：** `7412e83` 整理两款 UI 与共享主题；`8e5d26c` 加入 Snake 终态动作回归测试。完整 SHA 与最终文档提交见阶段执行报告和 Git 日志。
- **实际自动验证：** Snake 定向 13 项、Log Detective 11 项、S10 应用 CLI 25 项、全量 unittest 243 项通过；黑盒 194/194；完整性检查 194 cases / 287 matrix links / 194 referenced cases；compileall 通过；有效 LWT 行数 246；默认与组合过滤 CLI 退出码 0。`git diff --check` 通过。完整命令摘要、人工验收矩阵和保护文件 Git blob ID 对比见 [`docs/s17-app-polish.md`](s17-app-polish.md)。
- **保护范围：** 六个保护文件 `app/log_report.lwt`、`tests/test_app.py`、S10 并发 JSON/报告和 S11 性能 JSON/报告的工作区 blob ID 均与基线一致。没有改动 `lwt/`、规范或 S8 黑盒；未运行 `tools/run_app_concurrency.py` 或 `tools/benchmark.py`。
- **阶段状态：** 实施完成，等待主窗口审查。两款 GUI 的具体交互、缩放、焦点切换和状态提示需在具有窗口输入/截图能力的环境逐项确认；S12 未开始，阶段未合并或推送。

## S18｜LWT 驱动交互分析工作台与应用证据强化（2026-10-27）

- **实际接收的 Agent 提示：** 用户要求在已审查本地 `main` `8be88474316238532294f6bb7e83b0cdb8ebfdb5` 上建立 `stage/s18-lwt-analysis-workbench`，按“纯报告解析与测试 → GUI 工作台与测试 → 数据/文档与阶段状态”实施；新增可过滤、查看图表和同一次 LWT 原始报告的分析工作台，保留五题挑战与独立 Snake，保护 S10/S11 原始证据，不执行 S12。
- **Agent 生成内容：** 纯报告模型 `app/log_report_view.py`、13 项报告/状态测试、Tk 工作台 `app/log_workbench_ui.py`、原日志侦探集成、确定性 UTF-8 演示日志、应用展示说明和本阶段报告。没有生成第二套 Python 日志解析/聚合代码；没有改写 `app/log_report.lwt`。
- **人工/执行窗口复核与修正：** 先读取课程要求、S17 主窗口复核、S18 规划和现有 CLI/GUI/测试；实跑开工基线。检查解析器时发现原先用 `startswith("Total lines: ")` 判定重复字段，会误拒绝一条合法示例记录，其时间戳恰以该文本开头；改为只匹配完整的“字段名: 数字”行，并补专门回归。检查大窗口布局，发现挑战视图把反馈行设置为扩展行，改为答题区下方扩展。审查异步状态时加入请求版本，条件变化或切走选项卡后不接受旧结果。解析器只消费已有 LWT 报告；Top 排行截断不要求模块计数之和等于匹配数。
- **可归因实测：** 基线黑盒 194/194、unittest 243；实施后黑盒 194/194、unittest 256、新增 13、S10 25、旧挑战 11、Snake 13、完整性 194/287/194、compileall 和 246 行统计均通过。公开 CLI 的默认、组合过滤、零匹配、Top 0、丰富 fixture、错误退出均实跑。桌面实际启动并点击工作台默认查询，截图显示 7/6/1/6、级别各 2 和实际 argv；随后工具在继续输入条件时检测到其他用户输入并中断，故不把第五题、文件选择、错误恢复、Snake 键盘等列为本轮手工通过。完整记录见 [S18 工作报告](s18-workbench.md)。
- **责任与状态：** 这是 Agent 辅助开发且经执行窗口复核和实际测试的阶段成果，尚无主窗口独立审查结论；未合并/推送，S12 未开始。Snake 是 Python/Tkinter 附加演示而非 LWT 应用。课程的 Agent 应用证据主体仍为 246 行 LWT 日志分析器与公开 CLI。

## S19｜LWT 语义实验室、报告边界修复与展示增强（2026-10-27）

- **实际接收的任务提示：** 用户要求从已审查本地 `main` `c966f97096fd590a77176c9b18f8f45fee5fed31` 创建 `stage/s19-language-lab-robustness`；先用公开 CLI 复现报告 `splitlines()` 对合法 U+2028 的误拆，再严格按 LF 修复；实现固定白名单、只读、后台运行的 Python/Tkinter 语义实验室，展示源码、规范章节、观察点、真实 CLI 命令及输出；为 GUI 相关功能补无头和 CLI 证据；更新全部状态文档并分层提交。明确禁止修改 LWT 运行时/语言规范、日志统计实现、保护的 S10/S11 数据、合并/推送或开始 S12。
- **Agent 生成内容：** `app/language_lab.py` 启动入口、`app/language_lab_core.py` 固定六例清单/只读源码加载/受限子进程/结果预期与状态机、`app/language_lab_ui.py` Tk 前端；新增 `examples/language_lab/division_by_zero.lwt` 和 `tests/test_language_lab.py` 十一项测试。六类示例实际复用分支循环、递归、数组/record/each 浅快照、文本函数与 CLI 参数、stdin，以及运行时错误定位。
- **复核补强：** 代码提交后继续检查启动失败路径，发现系统没有 Tkinter 时顶层导入会先产生回溯。将 Tk 导入移入 `launch()` 并转换为可读 `RuntimeError`，增加缺失 Tkinter 和 Tcl 无显示环境两项测试；`test_language_lab.py` 从 9 项增至 11 项。
- **人工代码复核与修正：** 先构造 UTF-8 日志 `t|INFO|app|alpha<U+2028>beta` 并调用 `python -m lwt app/log_report.lwt -- <临时日志>`；CLI 退出码 0、stderr 空且报告原文保留 U+2028，但旧视图解析器误报“匹配示例数量与匹配数不符”。改为只移除协议末尾一个 LF 并按 `"\n"` 拆分；未放宽标题、字段顺序、重复项、计数关系、Top 截断或示例数校验。回归覆盖 U+0085/U+2028/U+2029/VT/FF，并保留额外末尾 LF、缺字段、重复字段与错误计数的拒绝例。复核语义实验室没有任意源文件入口、不调用 `eval/exec`，子进程使用 argv、UTF-8、仓库根 cwd、`shell=False` 与 12 秒 timeout；工作线程只向队列写结果，Tk 只由主线程更新。布局令源码/输出面板占据扩展行。
- **真实 CLI 结果：** 六个例子都经 `sys.executable -m lwt` 实跑，均与白名单中的 stdout/退出码预期一致。控制流为 `0\n-1\n2\n-3\n`；递归为 `120\n`；集合输出 `draft`、`review`、观察数组和最终 `Task` 数组；文本/参数为 `2`、`[12, "apple", 5]`、`[7, "pear", 4]`；stdin 输入中文并按预期回显；错误例退出码 3，stderr 定位到 `:2:8: RuntimeError: division by zero`，没有 Python traceback。
- **桌面验收边界：** 启动自身窗口后发现其他应用占据/遮挡桌面，未继续向日志侦探、语义实验室或 Snake 发送点击/键盘输入；关闭了本轮启动的进程。故工作台组合查询/旧结果清除/原始报告/零匹配/文件恢复/Unicode 路径/缩放、第五题结束页及重开、Snake 按键/失焦/终态重开均没有本轮人工点击证据。详见 [S19 执行报告](s19-language-lab.md)，不把无头状态测试或窗口几何信息冒充人工验收。
- **实际验证：** `python tools/run_tests.py` 为 194/194；项目完整性 194 cases/287 links/194 IDs；全量 unittest 268 项；S10 应用 25、报告视图 14、语义实验室 11、日志侦探 11、Snake 13 项定向测试均通过；compileall、246 行 LWT 统计、28 个 Markdown 文件/520 个本地链接/围栏检查与最终 `git diff --check main...HEAD` 均通过。默认及 WARN/retry 示例用公开 CLI 实跑。保护文件差异为空。
- **责任与状态：** 课程 LWT 应用 `app/log_report.lwt` 保持 246 行，S10 CLI 测试保持 25 项；语言黑盒仍为 194/194。没有修改运行时、正式语言规范或语言黑盒矩阵。保护的 S10 并发和 S11 性能文件未改，且没有运行证据生成器。阶段提交与完整检查结果以 [S19 执行报告](s19-language-lab.md)为准；实施完成，等待主窗口审查。S12 未开始。

## S20｜课程演示交互与 GUI 验收收口（2026-10-27）

- **实际接收的任务提示：** 用户要求从已审查的本地 `main` 基线 `44f85e9b2b3a1c3c12e57f66d0adb286588ffbf6` 创建 `stage/s20-teaching-demo-acceptance`；修正 Tkinter/Tcl 启动失败退出码；将现有六个 LWT CLI 教学示例改成先预测、再运行、最后解释；尝试桌面验收并区分实操、无头测试和未验证；更新阶段文档、分层提交。明确保留 S10/S11 证据，不改 LWT 语义/运行时，不合并、推送或开始 S12。
- **计划基线差异：** `docs/s20-optimization-plan.md` 初稿写的是 `3057df6...`，用户当前指令明确指定 `44f85e9...`；执行窗口核验后使用指定的 `main` HEAD，未用落后的 `origin/main` 覆盖。`origin/main` 实际 ref 为 `de608f7fbf50946715d370df014657169eb8f26d`，相对基线落后 69 个提交，未 fetch 或推送。
- **Agent 实施内容：** 将入口改为 `main() -> int`；只捕获 Tk/Tcl 预期启动错误并返回 1，正常 shim 主循环退出返回 0；未预期 UI 异常保留 traceback。六个 `LabExample` 增加题目、有限选项、固定答案和解释；`LabSession` 增加选择/提交/重置/关闭、过期 revision 拒绝和预测正确性状态；Tk 前端在提交前禁用运行、运行中锁定可能改变状态的控件，并通过主线程队列更新界面。
- **人工代码复核与修正：** 复核发现通用“符合记录预期”不足以让答辩人理解 exit 3 是正确的预期诊断；加入结果摘要，使成功例标注成功、预期错误例明确写“按预期报告 RuntimeError”，并测试该摘要。核对六例固定答案与 stdout/退出契约一致，预测正确性与实际 CLI 契约不共用一项状态。未增加任意源码、Python 解释、`eval/exec`、第三方依赖或 LWT 语法。
- **入口证据：** 四项真实子进程测试覆盖 Tkinter 导入失败、Tcl 初始化失败、隔离成功 shim 和未预期 UI RuntimeError。前两项 stdout 为空、stderr 有诊断、非零退出且无 traceback；成功 shim 返回 0；未预期 RuntimeError 返回非零并保留 traceback。
- **六例 CLI 结果：** 六个示例均用实际 `sys.executable -m lwt` 子进程复跑并与固定预期吻合。控制流 stdout `0/-1/2/-3`；前向递归 `120`；集合快照访问 `draft/review`，并显示更新后的 record 数组；文本/参数首行 `2`，随后两行列表；stdin 接收 `LWT 输入演示` 并按例输出；除零返回 exit 3、`:2:8: RuntimeError: division by zero`、无 Python traceback。使用 `--` 的文本例参数是 `examples/fixtures/text_tools.txt` 与 `preview`。
- **桌面验收：** 启动了语义实验室目标窗口并取得目标窗口截图；截图显示另一应用窗口覆盖目标窗口，无法确保输入可归因。本窗口遵守任务要求，在第一次观察后没有激活、点击、键入或向其他应用切换；本轮所有 GUI 人工操作（语义实验室、分析工作台、日志侦探、Snake）均未验证。窗口启动/句柄不作为 GUI 交互通过。无头和 CLI 证据分别列在 [S20 实施报告](s20-teaching-demo.md)。
- **可归因回归：** `python tools/run_tests.py` 194/194；完整性 194/287/194；全量 unittest 276（较 S19 的 268 增加 8）；语义实验室 15、入口 4、报告视图 14、日志侦探 11、Snake 13、S10 应用 25 均通过；compileall 通过，LWT 行数 246。每条命令及 GUI 未验证项见 [S20 实施报告](s20-teaching-demo.md)。保护的六个 S10/S11 文件相对基线无差异，没有运行会改写原始证据的生成器。
- **分层提交：** `236c54dbe37e59e4fbc1b6e87c9302edbd125a17`（入口和入口测试）、`fea8aff2d4eab3bff61e5c607478d4f3b327c65a`（预测数据/状态与测试）、`5104a8f89b8efe4739bd6e9bb439563a6d716c2d`（Tk 交互）。阶段报告和规划/说明文档作为最后提交；最终阶段 HEAD 见本窗口交接。
- **责任与状态：** S20 在独立阶段分支实施完成，等待主窗口审查；不声称人工 GUI 验收通过。课程 Agent 编写的完整应用仍是 `app/log_report.lwt`；语义实验室是 Python 教学前端。S12 仍未开始。

## S21｜答辩应用桌面验收与可复现缺陷闭环（2026-10-27）

- **实际接收的任务提示：** 用户要求从已审查本地 `main` `fa370f7b7f927b120aee9373c8b4d1e77f5a4917` 创建 `stage/s21-gui-acceptance`，只对语义实验室、LWT 日志侦探工作台/五题挑战及独立 Snake 做真实桌面验收；仅修复可重复的现场缺陷；不得新增功能、合并、推送或开始 S12。要求对照 S10/S11 保护范围，更新完整验收报告和项目状态。
- **基线与环境：** 开工时本地 `main`、HEAD 均符合指定 SHA，`git status -sb` 干净，ahead `origin/main` 76 个提交。同名阶段分支原先不存在，按要求从本地已审查 `main` 创建。只读 `git ls-remote` 得到远端 `main` `de608f7fbf50946715d370df014657169eb8f26d`，没有 fetch/覆盖。Windows 11 Home 中文版 build 26200、Python 3.13.7、Tk 8.6/Tcl 8.6。适配器信息报告 2560×1600，但无法可靠取得桌面缩放比例。
- **真实桌面停止记录：** 启动本阶段自己的 `python -m app.language_lab` 后首次观察目标窗口，看到文件资源管理器覆盖其可操作区域。无法确认鼠标/键盘会落在目标窗口，遂立即停止所有输入，没有激活、切换、连续点击或发送键盘操作，并关闭本阶段启动的目标进程。窗口标题和截图只作为识别遮挡的辅助事实，不计 GUI 通过；未保存含桌面信息的截图。
- **A/B/C 验收状态：** 语义实验室六主题、预测/运行/解释、stdin、RuntimeError、忙碌、重置、关闭、键盘均未验证；工作台 WARN/retry/top=2、过期结果清除、零匹配、文件错误恢复、Unicode 路径、原始报告、缩放以及五题挑战终态/重开均未验证；Snake 按键、反向、暂停、失焦、终态重开和缩放均未验证。相关的无头测试/CLI 契约和只读代码审阅单独列在 [S21 报告](s21-gui-acceptance.md)，不冒充人工 GUI 证据。
- **缺陷与改动：** 因没有执行交互步骤，本轮没有可复现缺陷，也未修改应用/测试代码。准确结论为“未发现可复现缺陷（受遮挡限制，无法执行复现）”。S10 的 `app/log_report.lwt` 实测仍为 246 行有效 LWT；`test_app.py` 定向实跑 25 项通过。相对基线对 `lwt/`、语言规范及六个 S10/S11 保护文件的 `git diff --quiet` 退出码 0；没有运行并发或正式性能生成器。
- **实际检查：** 运行 Python/Tk 版本查询、Windows 版本/适配器查询、`python tools/count_lwt_lines.py app/log_report.lwt`（246）、`python -m unittest discover -s tests -p 'test_app.py' -q`（25 项 OK）和保护路径差异检查（退出码 0）。由于无代码修改，没有运行完整套件、黑盒 runner、完整性工具或 compileall。文档链接/围栏和 `git diff --check` 结果以 S21 报告的最终记录为准。
- **交接与责任：** 新增 [S21 桌面验收报告](s21-gui-acceptance.md)，项目状态、README、路线图、详细规划与总体方案均标为“S21 已完成实施，等待主窗口审查”，并明确桌面验收未能完整完成。`app/README.md` 未修改，因为启动方式和应用行为未变。未合并、未推送；S12 仍未开始。最终阶段提交 SHA 见执行交接。

## S22｜Tk 图形界面交互回归与交付前可靠性提升（2026-10-28）

- **实际接收的任务：** 用户要求在本地 S22 规划基线 `1919861652266edd75ce278736d71958eb90cd62` 上完成三款 Tk 应用的控件级回归。必须使用真实 Tk/Ttk 控件、真实层级和事件循环，涵盖语义实验室、日志工作台/五题挑战及贪吃蛇；保留至少一条真实 LWT CLI 路径，只有不稳定外部依赖边界可注入。不能将合成事件说成人工桌面验收，不改 LWT/语言规范/黑盒矩阵/S10-S11 raw，不合并、推送或开始 S12。
- **基线与分支：** 开工时工作区干净；当前分支为 `stage/s22-gui-regression`，本地 `main`、阶段分支均从指定规划提交继续。S21 最终提交 `d7ca188168cd449027de546b61f78670c29e08ca` 是基线祖先。只读 `git ls-remote origin refs/heads/main` 因 TLS/Schannel 握手失败，远端 tip 和 Actions run 未验证；没有 fetch/pull/push。
- **生成与人工复核：** 新增三款界面的最小 runner/timer 注入点、真实控件/事件测试和 GUI 计数 runner。人工复核重点包括真实 widget 与事件调用、线程仅向 queue 返回结果、关闭后的 poll/after 清理、workbench 条件 revision 丢弃旧结果、Snake 只保留一个活动 tick、CI Linux 条件与矩阵不变。开发过程中修正了对状态文案的测试预期、Notebook 键盘合成前的焦点/选项卡条件及计数脚本仓库导入路径；这些是测试夹具问题，不是产品缺陷。没有降低既有断言，没有发现可复现产品 GUI 缺陷或实施产品逻辑修复。
- **验证状态：** S22 新增 10 项真实 Tk 控件/事件集成测试；语义实验室、日志工作台、五题挑战通过按钮发起真实 `python -m lwt` 子进程，Snake 通过实际按钮/按键事件和受控 timer 驱动。具体逐项映射、全量命令输出/退出码、工作区保护差异和人工 GUI 未验证事项见 [S22 执行报告](s22-gui-regression.md)。Linux CI 新增显示服务探测：若 `xvfb-run` 缺失才安装 `xvfb`/`xauth`；真实远端 workflow 尚未执行。
- **提交与状态：** 代码/测试、CI、报告与状态文档按可审查单元提交；精确提交 SHA 和最终状态以本报告提交后的交接为准。状态为“实施完成，等待主窗口审查”；S21 的人工 A/B/C 检查和 Python 3.10/远端 CI 仍留给 S12。S12 未开始。

## S24｜while/each 的 break 与 continue（2026-10-29）

- **实际接收的任务：** 从已报告的 S23 tip 接续，实现 `while`/`each` 的无标签 `break;` 与 `continue;`；更新语言规范、AST/parser/runtime、公开 CLI 黑盒测试、矩阵、指南和阶段状态。要求循环外及函数自身循环外使用在解析期报错，函数不得继承调用方循环上下文；return/runtime error 保持原传播行为，不改应用、性能证据或 CLI 契约，不合并、不推送、不开始 S12。
- **基线和阶段分支：** S23 tip `999cc7844065336d095b1efe4875313d2ee45da2`，S23 工作区干净；本地 `main` 为 `aadb8f7a2348dad3205c523d4ab1cb4ad5bda063` 且不包含 S23。只读远端 tip `de608f7fbf50946715d370df014657169eb8f26d` 是本地 main 祖先（main ahead 84/behind 0）。S24 在 `stage/s24-loop-control` 执行。第一项独立提交 `aaef11e9df262c5aa3fa5be708da2095f67589a0` 专用于修正 S23 数量文档；后续 AST/parser、runtime、黑盒测试分层提交 SHA 见 S24 阶段报告。
- **实现与人工复核：** 新增带源码位置的 AST 节点，parser 在块/分支传递 loop depth、每个函数体重置该上下文；runtime 使用独立 break/continue 内部信号，由最近 loop 捕获。逐项审阅了嵌套 loop、条件分支、函数边界、each 快照推进、return 穿越 loop、RuntimeError 传播和旧 unsupported 用例替换；lexer 未修改。
- **验证：** Windows CPython 3.13.7、3.11.16 均通过黑盒 217/217、完整性 217 cases/314 links/217 referenced IDs、全量 unittest 297 项和 compileall。Parser 定向 24 项、runtime 定向 7 项通过。S23 固定 seed 性质工具复验 156/156、7 个 CLI 程序，hash 与 S23 相同；隔离变异审计为 9 killed/1 survived，存活项仍是旧的对称参数顺序案例。示例 `python -m lwt examples/loop_control.lwt` 退出码 0，stdout 为 `1\n3\n2\n[1, 2, 3, 4]\n`，stderr 为空。细节与剩余检查见 [S24 执行报告](s24-loop-control.md)。
- **证据边界与状态：** Python 3.10 未安装；Linux、远端 Actions 和人工 GUI 未在本阶段验证。S10/S11 原始数据生成器和正式性能基准未运行；应用 LWT 保持 246 行。S23 未合入本地 main，S24 也不合并或推送；S24 为“实施完成，等待主窗口审查”，S12 仍未开始。

## S25｜可验证的多文件函数模块（2026-10-29）

- **实际接收的任务：** 用户要求在 S24 已审查阶段 tip 上实现声明式静态函数库模块：入口与库文件开头可导入相对路径，采用 alias-qualified 调用；模块禁止顶层可执行语句和 record 声明；路径按 importer 目录解析并 canonical 去重；循环导入拒绝；每文件独立命名空间；模块内编译/运行错误保留真实来源路径。必须同步规范、解释器、公开 CLI 黑盒、矩阵、指南、示例和阶段报告。禁止 Python `eval`/`exec` 执行 LWT，保护 S10/S11 证据，不合并/推送、不开始 S12。
- **基线与分支：** S24 tip `5f899d952bacc91e22e1db99dba6e369153bdbc6`，`stage/s24-loop-control` 工作区干净；从其建立 `stage/s25-modules`。本地 `main` `aadb8f7a2348dad3205c523d4ab1cb4ad5bda063` 不含 S24；只读远端 `origin/main` 为 `de608f7fbf50946715d370df014657169eb8f26d`，是本地 main 祖先。未 fetch/pull/push。
- **实现与人工复核：** 手写 lexer/parser 增加 import token、库文件受限模式和限定调用 AST；限定调用识别不会抢占既有 `record.field`；loader 预构造静态依赖图、严格 UTF-8、canonical 去重和路径链环检测；runtime 为每个文件建立独立函数表/根环境并预链接 alias/member。SourceLocation 的可选 source path 沿 Token/AST 到诊断格式，入口原有路径格式保持。没有改日志分析器、正式性能逻辑或现有 S24 黑盒案例。
- **覆盖和示例：** 增加模块类 30 项配对黑盒，覆盖别名、两层路径、同名命名空间、递归、数组/record 别名、CLI I/O、错误、循环及模块调用结果不可继续调用。另有 9 项 parser/loader/runtime/子进程定向 unittest。新增三文件示例 `examples/modules/`，实际 stdout 为 `demo:2\n`，退出码 0。运行器支持在任意深度忽略 `fixtures/`。新增 `import` 保留字黑盒反例和指南兼容性说明。
- **审计工具调整：** 首次执行 `python tools/audit_semantic_mutants.py` 时两个实参顺序探针因 `CallExpression` 与新 `ModuleCallExpression` 两处出现同一文本而报告 invalid。仅将探针源码锚定到普通调用专属注释，并在隔离副本复跑；结果 9 killed、1 survived、0 invalid。runtime 未为审计工具修改。
- **验证与交接：** Windows CPython 3.13.7 下黑盒最终 247/247、完整性 247 cases/344 links/247 referenced、全量 unittest 308 项、parser/runtime/modules 定向 40 项（其中模块类 9 项）、S10 定向 25 项、compileall 通过。固定 seed 性质检查 156 项通过、7 个 CLI 程序。分层提交：实现/定向测试 `0e769e07e3cc5aa32fddcd48be3dc016fc0c99e5`，黑盒/runner/变异探针 `dab34bfd8c12305fad2b8542407f23a75f196e1e`，阶段报告与状态为最终文档提交（SHA 见执行交接）。有效 LWT 应用仍为 246 行；保护文件差异、完整命令、输出和未验证范围见 [S25 执行报告](s25-modules.md)。Python 3.10、Linux、远端 Actions 未验证；未运行 S10 并发原始数据生成器或 S11 正式性能基准。S25 实施完成，等待主窗口审查；未合并/推送，S12 未开始。

## S26｜可观察、可恢复的运行时错误处理（2026-10-30）

- **实际收到的提示：** 用户要求接续 S25 tip `5e694a22512346d845434824c0785ccecc7c8628`，新增受控 `attempt`/`recover`，只捕获 RuntimeError/3，提供只读不可变 Error 值及稳定显示；更新正式规范、解释器、40 项以上公开 CLI 黑盒、单元测试、矩阵、指南、模块示例、阶段规划和报告。明确要求语法/模块预检错误不可捕获、控制流信号穿过 handler、错误前副作用保留；保护 S10/S11 文件，不推送/合并，不开始 S12。
- **产出：** 在独立 `stage/s26-runtime-recovery` 上修改 lexer、AST、parser、runtime 和 CLI；新增 40 组黑盒配对、parser/runtime/runner 定向测试，以及展示模块函数错误传播和继续处理的 `examples/error_recovery/`。规范第 10 节固定捕获边界、字段和 Error 显示格式。
- **人工复核与修正：** 对照提示逐项审查 LwtError 过滤、return/break/continue 的独立信号、handler 置于自身 try 外、模块 SourceLocation、入口路径回退、Error 字段写入和类型约束。初次定向测试暴露两项既有 composite mutation 测试因测试类插入边界而缺少 helper，补 helper 后定向/全量通过。首次 S23 变异审计发现旧 structural-equality 探针源码锚点被 Error 组合分支扩展影响，更新探针以只变异数组/record 比较、保留 Error 身份规则；复跑 9 killed、1 survived、0 invalid。修订的是隔离审计工具，不是 LWT 行为。
- **真实验证：** Windows 11 build 26200、CPython 3.13.7。黑盒 287/287，完整性 287/384/287，全量 unittest 318 项，parser/runtime/runner 定向 60 项，compileall 通过；固定种子性质检查 156 项通过，变异探针 9 killed/1 survived。错误恢复示例真实 CLI 退出码 0，stderr 空，输出见 [S26 执行报告](s26-runtime-recovery.md)。Python 3.10、Linux、远端 Actions 未验证。未运行并发 raw 或正式性能基准；S10 应用仍为 246 行。最终提交及全部命令、保护路径差异、环境限制见 [S26 执行报告](s26-runtime-recovery.md)。

## S27｜模块感知静态语义检查与机器可读诊断（2026-10-30）

- **实际收到的提示：** 用户要求接续 S26 实际 tip `451f55a4c60dbb50a21f30788a3b79463d9c0b4d`，先将该 SHA 写回 S26 自身提交记录并单独提交，再在 `stage/s27-static-checker` 增加不执行程序的静态检查器与 JSON CLI。要求保持 287 项语言黑盒、正常执行语义和 S10/S11 原始证据不变；更新工具文档、语言规范 CLI 说明及阶段状态；不合并、推送或开始 S12。
- **产出：** S26 报告自包含性修正独立提交 `9006119fc6c98f151244ef06608d72730da1071e`。S27 新增 `lwt/analyzer.py`、`lwt/builtin_signatures.py`、稳定错误夹具 `tests/fixtures/static-checker/undefined-function.lwt` 和 `--check [--format=json]`；复用静态模块图，扫描未调用函数和所有分支。诊断覆盖重复/冲突声明、未知函数/变量/record、调用参数数目、record 字段集合、模块 alias/member 和同作用域重复 let。代码及文档未增加源语言语法。
- **人工复核与修正：** 对照 runtime 环境核对函数局部不能捕获调用者、函数外层 body 与参数共用作用域、each/recover 父作用域、record 仅入口可见、初始化器先于新绑定可见等规则。明确采用保守名字存在检查，不做路径敏感 definite-assignment 或类型推断。共享内置签名避免 checker/runtime arity 名单分叉；静态限定调用与 runtime 预链接复用同一模块解析 helper。JSON 诊断只写 stdout、成功完整加载后才填文件数，读/词法/语法/模块错误沿用原分类和退出码。
- **真实验证：** Windows 11 build 26200、CPython 3.13.7（版本、系统与各命令结果见 [S27 执行报告](s27-static-checker.md)）。新增 checker/CLI 子进程测试 20 项，全量 unittest 和既有语言黑盒的最终实测数见阶段报告；语言黑盒保持 287 项且未添加/修改案例。`test_cli.py` 定向测试实跑 108 项。另复跑固定 seed 20261028 的 156 项性质检查，以及原隔离变异审计 9 killed、1 survived、0 invalid。S27 阶段没有运行 S10 并发数据生成器或正式性能基准。
- **责任与状态：** `examples/modules/main.lwt` 是成功的多模块检查/执行示例；程序输出仍只来自正常执行 CLI，检查器不运行 `emit`、`input()`、`read_text()` 或 `fail()`。`docs/test-matrix.md` 将开发工具测试单列，不计入语言黑盒。S27 实施完成、等待主窗口审查；未合并/推送，S12 未开始。逐条命令、保护文件差异、提交 SHA 和环境限制见 [S27 执行报告](s27-static-checker.md)。

## S28｜LWT 源码级执行追踪、覆盖率统计与可视化（2026-10-30）

- **实际收到的提示：** 用户要求从自包含修正后的 S27 tip `e9fa8f4eaf2289215a53bb6b9e990efd638a23a5` 继续，在 `stage/s28-execution-observability` 增加公开 CLI 可选 profile、基于完整模块 AST 的语句/函数/decision 覆盖率、严格版本化 JSON、离线 HTML 与固定应用证据。明确不增加 LWT 源语言语法、不改变运行结果、不改日志应用/287 项语言黑盒/S10 并发和 S11 性能 raw，不合并/推送，不开始 S12。
- **产出：** 新增显式 observer/profile collector、schema validator、`--profile` CLI、模块 SHA-256、profile merge 与 HTML renderer、两个固定日志场景 runner 和 `test_execution_profile.py`；形成日志应用两场景合并 JSON/HTML 及 `examples/error_recovery` 档案。使用文档把开发工具与语言语义、应用 Python 前端、正式性能实验分开。
- **人工复核与修正：** 人工逐段检查 statement 与 decision hook 只在原有求值/控制分支旁记录，不重复求值、不读取用户值；`attempt` 的 normal edge 放在 finally 以让 return/break/continue 信号按原路径传播；`fail(input())` 的 profile 消息脱敏；模块哈希只在 profile 加载模式计算。renderer 不显示源码，只在本地可定位时验证 hash；所有动态 HTML 文本转义。静态定义 ID 以路径、类别和源码位置生成，不依赖对象地址；复核 normal/app CLI 输出对照测试不触碰并发/性能原始生成器。
- **真实验证：** 本轮 profile 定向测试增至 19 项通过，module 测试 9 项、runtime 测试 11 项；S28 observer hook 插入后，语义变异工具原短路探针因文本锚点不再唯一而初次报告 2 项 invalid。只更新 `tools/audit_semantic_mutants.py` 的隔离探针锚点，让其仍专门改变 AND/OR 短路判断；复跑 9 killed、1 survived、0 invalid。完整测试清单、287 项黑盒、性质/变异、schema 复算、hash、HTML 确定性、Markdown 链接、保护文件和最终 SHA 见 [S28 执行报告](s28-execution-observability.md)。日志默认 stdout 336 bytes（语句 112/173、函数 13/20、decision outcome 55/102），组合筛选 stdout 204 bytes（143/173、18/20、58/102）；输出 stderr 为空、exit 0，merged 档案 297,052 bytes，事件保留为两组独立序列。错误恢复示例 26 events、8/8 语句、1/1 函数、3/4 outcomes。
- **责任与状态：** 执行档案只表明特定输入场景到达的节点，不证明程序正确。记录/渲染会有额外开销，禁止用于 S11 性能对照；S10 并发证据保持既有版本。Python 3.10、Linux 和远端 Actions 只有在实际可用时才报告为通过；本阶段不做 GUI 人工验收、PPT 或最终交付。S28 实施完成、等待主窗口审查；未合并、未推送，S12 未开始。

## S29｜LWT Language Server 与编辑器级静态辅助（2026-10-31）

- **实际收到的任务：** 用户要求接续 S28，并先把 S28 报告补成自包含最终 SHA。随后从 S28 修正 tip 建 `stage/s29-language-server`，实现仅 stdio 的 LSP 子集：文档 open/change/close、静态 diagnostics、document symbols、hover、definition、模块 overlay 和 UTF-16；禁止执行 LWT、禁止扩充语法、禁止第三方依赖和完整 VS Code 扩展。要求 framing/codec、language service、真实子进程测试、smoke 工具及证据，并同步项目文档；保留 S28/S10/S11/287 项黑盒。
- **基线与提交：** S28 原 HEAD `658e37e6c86f0ccb8424055f213f068b482f6826`。先只改 S28 报告，提交自包含性修正 `6aa198a402aaaec1f95806af78548a82abdfd854`；从其建立 S29 分支。S29 实现分层提交：protocol codec `5de21e811de344caa86b032c10fe1409a06a4b33`、overlay language service `68ac07985ff487d08cab94a9eee6bdea764b034d`、LSP lifecycle `7af411b4dfcf8ddcff99ed62b82115c880ac7db7`、real-process smoke/artifact `781c66b96924829eda92fc3fc642f2a483311c6e`、源快照一致性修复 `b4f8338c3e9ac6d92853204a1f96f12e6bb76dd2`、局部绑定定义索引修复 `f829ee5567c69a8ede53db9503cda8cdc67435d7`。
- **实现与人工复核：** 通过可选 `source_overlays` 扩展静态 module loader，普通调用仍省略该参数；服务不导入 runtime。Codec 限制 header/body 大小、拒绝重复 JSON key 和非法 UTF-8；生命周期 capabilities 严格只声明实现项。符号索引复用 AST/module graph/analyzer；变量定义遍历区分参数、显式 block、each 和 recover 作用域。file URI 只接收本地 .lwt；打开文件以内存文本为真、关闭后恢复磁盘版本；UTF-16 位置换算按非 BMP 字符双 code units 计。诊断归属实际模块 URI且去重；parser 首错时清空旧索引。
- **当前验证与交接：** codec/service/server 定向测试分别为 15/16/5 项，共 36 项通过；全量 unittest 为 393 项，语言黑盒 287/287，完整性检查为 287 cases/384 matrix links/287 referenced cases。`python tools/run_lsp_smoke.py` 实际启动 `python -m lwt.lsp_server`，验证 initialize、didOpen、diagnostics、symbols、hover、definition、STC010 错误后修复、didClose、shutdown/exit，进程退出码 0；固定报告的 response ids 为 1–5，诊断序列为无错误、STC010、清空、关闭清空，stderr 无 traceback。其余兼容回归、示例输出、独立 framing 复算、保护路径与文档检查见 [S29 阶段报告](s29-language-server.md)。真实 VS Code/Neovim 等编辑器连接、Python 3.10/Linux/远端 Actions 未在本机验证；S29 等待主窗口审查，不合并/推送，S12 未开始。
