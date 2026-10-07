# S16 应用复检与独立贪吃蛇

日期：2026-10-07。阶段状态：**实施完成，等待主窗口审查**。本报告只记录可核对的文件、操作、命令和结果；未将无法观察的桌面交互记作通过。

## 1. 基线、范围和课程要求

- **仓库与分支：** `stage/s16-app-review-snake`，从本地已审查 `main` 建立。
- **基线：** `09cf5f5eb4d1dded17fd43b84d3e5b48e0dd62b6`。开工时工作区干净，`main` 指向该提交；S15 最终提交 `390d484e2f21a044fcd8c9e8121712c215e1b309` 是其祖先。
- **远端：** 本地 `origin/main` 跟踪值和实时 `git ls-remote origin refs/heads/main` 均为 `de608f7fbf50946715d370df014657169eb8f26d`。本地已审查 `main` 比远端领先 44 个提交；没有以旧远端提交替代本地基线，也未推送。
- **教师要求：** 《大作业内容.md》要求至少一个功能完整、使用 LWT 编写且不少于 200 行的 Agent 应用，并强调关注多线程、并发读取等应用问题。独立 Snake 是 Python/Tkinter 的附加演示，不替代 LWT 应用，不增加 LWT 语言能力，也不计入 LWT 行数。
- **保护边界：** `app/log_report.lwt` 246 行、`tests/test_app.py` 25 项、S8 194 项语言黑盒集、`reports/app-concurrency.json` 与 `docs/app-concurrency.md`、S11 `bench/results.json` 与性能报告均未改。没有执行并发驱动或性能基准。

## 2. S15 GUI 遗留验收

Python 3.13.7 可导入 Tkinter，报告的 `TkVersion` 为 8.6；这只确认模块可用，不代表窗口实际启动或交互通过。此会话的桌面自动化状态返回 `apps: []`，并且 `cua.listApps()` / `cua.listWindows()` 在当前运行时不存在，未提供可操作的原生窗口与输入方法。因此无法把操作归因于执行窗口，以下项目全部保持**未验证**：

| S15 项目 | 结果 | 原因 |
|---|---|---|
| 启动后正确答案反馈、得分增加 | 未验证 | 无可操作桌面窗口 |
| 错误答案、正确值反馈、分数保持 | 未验证 | 无可操作桌面窗口 |
| 下一题、结束页和最终得分 | 未验证 | 无可操作桌面窗口 |
| 已回答题目不能重复计分 | 未验证 | 无可操作桌面窗口 |
| 打开完整 LWT CLI 报告窗口 | 未验证 | 无可操作桌面窗口 |
| 重新开始并重置得分 | 未验证 | 无可操作桌面窗口 |
| 选择含空格与 Unicode 的路径 | 未验证 | 无文件选择窗口可操作；相同路径边界由 CLI 集成测试覆盖 |
| 缺失/无效 UTF-8 文件报错后恢复 | 未验证 | 无可操作桌面窗口；底层 LWT 错误与 GUI 错误映射由自动测试覆盖 |
| Enter 提交 | 未验证 | 无可操作桌面窗口 |
| 窗口缩放 | 未验证 | 无可操作桌面窗口 |

S15 的自动化测试实际复跑，结果为 11/11 通过；S10 LWT CLI 应用测试为 25/25 通过。测试不能代替以上 GUI 手工步骤。

## 3. S10/S15 定向复检

阅读了 `app/log_report.lwt`、`app/log_detective.py`、`app/log_detective_core.py`、`app/log_detective_ui.py`、S10/S15 测试和 fixtures、并发报告与驱动、S15 报告、`app/README.md` 和 Agent 开发记录。

### 检查结果

没有发现可稳定复现的 S10/S15 程序缺陷，因此没有改动既有应用实现或重构。主要证据：

1. **分析职责和 CLI 边界：** 日志读取、解析、筛选、统计与正确答案仍由 `app/log_report.lwt` 经 `python -m lwt` 生成。Python GUI 只解析唯一的 `Matched records: N` 行并维护问题和得分。
2. **子进程配置：** 复核 `build_lwt_command()` 使用 `sys.executable`、参数列表和独立路径参数；`run_lwt_report()` 显式采用仓库根 `cwd`、`shell=False`、UTF-8、20 秒 timeout，并将启动错误、超时、非零退出码和报告字段错误变为 `AnalyzerError`。没有 shell 字符串。
3. **路径和编码：** 定向测试的临时目录和文件名都包含中文与空格，并实际调用公开 CLI 成功；命令构造测试证明完整文件路径和 filter value 保持为单独 argv 项。
4. **线程和 Tk 更新：** 子进程等待在 daemon worker 中进行，通过线程安全队列把结果交给 Tk 的定时轮询；控件更新、对话框和报告窗口都从主线程消息处理回调触发。忙碌期间禁止重复提交、换文件、重开和另起报告查询。
5. **失败后的用户操作：** 题目查询失败会提示错误并保留重新开始和选择文件的入口；没有发现状态机无法恢复的复现路径。测试覆盖非零退出、超时、无效 argv 和缺少计数行的用户可读错误。
6. **证据保护：** 本阶段没有运行会改写 `reports/app-concurrency.json` / `docs/app-concurrency.md` 的 `python tools/run_app_concurrency.py`，因为审计未发现影响既有结论且值得重跑的并发缺陷；没有运行 `python tools/benchmark.py`。

## 4. 独立贪吃蛇实现

### 文件和职责

- `app/snake_game.py`：独立启动入口，从脚本位置加入仓库根路径；Tkinter 或桌面环境缺失时输出简明错误并以 4 退出。
- `app/snake_game_core.py`：纯规则/状态模块，不导入 Tkinter，不打开窗口。随机数源可注入以确定食物位置。
- `app/snake_game_ui.py`：Tkinter Canvas 棋盘、分数/状态、控件、按键、焦点处理和单个 `after` 定时器。
- `tests/test_snake_game.py`：无头规则和模块导入测试，不加入 LWT 黑盒矩阵。

### 已冻结玩法

- 默认棋盘为 24×18 格，初始蛇长 3 格，面向右；分数从 0 开始。状态为准备、运行、暂停、结束或胜利。
- 每 140 毫秒通过 Tk `after` 移动一格。任何时刻至多保留一个待执行 tick；暂停、重开和关窗会取消当前 tick，不使用忙等或睡眠循环。
- 方向键与 WASD 移动；Space 在准备时开始、运行时暂停、暂停时继续；R 与“重新开始”按钮重置棋盘和得分。
- 长度大于 1 时拒绝立即反向。撞墙或撞到非尾部身体部分即结束，碰撞 tick 不移动蛇。
- 不增长的一步允许蛇头进入本步将离开的旧尾格；若本步吃到食物，尾格保留，此时不能撞入身体。
- 吃到食物后增长一格、增加 10 分。新食物在所有空格中均匀选择，不会生成在蛇身；占满整个棋盘时 `food` 变成 `None`，游戏进入胜利状态。
- 窗口失焦后在焦点切换完成时自动暂停；焦点返回不会自动继续，玩家按 Space 或“继续”恢复。焦点变化处理延迟到 `after_idle`，避免同一窗口控件之间切换焦点时误暂停；规则状态的失焦暂停行为由无头测试覆盖。

无桌面环境的运行说明：

```powershell
python -m unittest discover -s tests -p "test_snake_game.py" -v
```

具备 Tk 桌面的机器从仓库根目录运行：

```powershell
python app/snake_game.py
```

## 5. 实际验证

执行环境：Windows，CPython 3.13.7；Tkinter 可导入，Tk 版本 8.6。以下是本分支实际命令结果：

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p "test_snake_game.py" -v` | 11 项通过。覆盖初始化、合法移动、拒绝反向、增长计分/新食物、墙碰撞、自碰撞、可进入即将离开的尾格、暂停/继续/失焦暂停、重开、满盘胜利、核心导入不加载 Tkinter。 |
| `python -m unittest discover -s tests -p "test_log_detective.py" -v` | 11 项通过，含公开 LWT CLI 查询、组合过滤、Unicode/空格文件路径和错误映射。 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 25 项通过；S10 应用既有测试全部通过。 |
| `python -m unittest discover -s tests -q` | 241 项通过。 |
| `python tools/run_tests.py` | 194/194 语言黑盒通过，分类分别为数组/record/each 32、内置文本 I/O 43、CLI 错误 13、控制/函数 30、集成 3、词法/语法 42、值/运算 31。 |
| `python tools/check_project_integrity.py` | 通过：194 个配对用例、287 个矩阵链接、194 个被引用 ID。 |
| `python -m compileall -q lwt tests tools bench app` | 通过，退出码 0。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | `Effective LWT lines: 246`。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 退出码 0；6 条匹配、6 条有效、1 条坏行。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | 退出码 0；1 条匹配，模块 `cache|1`，匹配样例为 `retry scheduled`。 |
| `git diff --check` / `git diff --check main...HEAD` | 均通过；当前 Windows Git 对 LF 文件显示其将规范化为 CRLF 的提示，不是空白错误。暂存差异与最终提交差异均完成检查。 |
| Markdown 本地链接/代码围栏检查 | 20 个 Markdown 文件、439 个本地链接；缺失链接 0、未闭合围栏 0。 |

一次早期测试把 4×1 的“撞墙”棋盘用作普通移动案例，但该盘上的下一格正好是最后空格，正确规则会先触发满盘胜利。将测试棋盘改为 4×2、使食物位于蛇行路径外后，墙碰撞测试按预期通过；游戏规则没有为适应测试而改变。

## 6. 未验证、风险与阶段交接

- S15 图形界面的全部人工交互，以及 Snake GUI 的实际窗口显示、按键、缩放和焦点切换仍未现场验证。Python/Tkinter 可导入和代码编译不能替代桌面验收。主窗口如有桌面操作能力，可按本报告表格补测并追加结果。
- 本阶段未在 Python 3.10、Linux、无 Tk 安装环境或真实 Windows 桌面运行 Snake GUI；不声称跨平台 GUI 已验证。
- LWT 194 项语言黑盒矩阵不变；没有测试 Snake Python 代码作为 LWT，也没有改正式规范、解释器、CLI 或运行时。
- S10 并发和 S11 性能 raw 未重跑、未覆盖、未编辑。
- 阶段分支保持独立，未推送或合并。S16 **实施完成，等待主窗口审查**；S12 仍未开始，必须等 S16 审查通过后再进入。
