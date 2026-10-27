# S20：课程演示交互与 GUI 验收收口

**阶段状态：实施完成，等待主窗口审查。** 本报告记录执行窗口实际运行的代码、测试、CLI 和桌面观察；桌面人工 GUI 验收没有完成。S20 没有合并或推送，S12 仍未开始。

## 基线、分支和工作纪律

- 仓库：`C:\Users\28641\Desktop\大三上\程序设计实践\大作业`。
- 指定并实际使用的已审查本地 `main` 基线：`44f85e9b2b3a1c3c12e57f66d0adb286588ffbf6`。
- 阶段分支：`stage/s20-teaching-demo-acceptance`。
- 只读核对到 `origin/main` 为 `de608f7fbf50946715d370df014657169eb8f26d`（`docs: record S4 review and prepare S5`），它是指定基线的祖先；`git rev-list --left-right --count origin/main...44f85e9...` 为 `0 69`，远端跟踪引用落后 69 个提交。本轮未 fetch、推送或用远端重置本地进度。
- `docs/s20-optimization-plan.md` 原先写的基线是 S19 的 `3057df65cef0edcc82ad050462f2fa7991cd28db`，与本轮用户指定的 `44f85e9...` 不同。按用户本轮明确指定的已审查 `main` 基线执行，并在规划文档中修正记录。
- 阶段按层提交：
  1. `236c54dbe37e59e4fbc1b6e87c9302edbd125a17` — `Fix language lab startup exit contract`。
  2. `fea8aff2d4eab3bff61e5c607478d4f3b327c65a` — `Add fixed prediction lessons and outcomes`。
  3. `5104a8f89b8efe4739bd6e9bb439563a6d716c2d` — `Add prediction-first language lab interaction`。
  4. 本报告及阶段状态文档在最后的文档提交中；该提交的完整 SHA 在执行窗口交接回复中给出。

## 交付内容和设计选择

S20 只修改语义实验室入口、固定教学题目/会话状态、Tk 前端、测试和项目说明。未修改 LWT 运行时、正式语言规范、黑盒矩阵、日志分析器的 LWT 统计逻辑或 S10/S11 证据。

语义实验室仍为 Python/Tkinter 教学前端。它展示固定白名单中的 LWT 源码，并通过 `sys.executable -m lwt`、argv 列表、`shell=False`、仓库根目录 cwd、UTF-8 和 12 秒超时执行。没有任意源码输入、`eval`/`exec`、网络、账号或新依赖。课程 Agent 编写的完整 LWT 应用仍是 `app/log_report.lwt`；实验室不是第二个 LWT 应用。

预测答案是固定教学数据。用户必须先选择并提交预测，运行按钮才可使用；运行后分别呈现预测正确性、CLI 是否符合该例的 stdout/退出契约、真实 stdout/stderr/退出码和语言解释。预期运行时错误显示为“按预期报告 RuntimeError”，避免把 exit 3 的诊断描述成普通成功。重新选择或重置会清除旧题目状态；异步结果由会话 revision 拒绝过期回调；关闭时使待处理 revision 失效，worker 线程不操作 Tk 控件。

## P0：入口退出契约修复

此前 Tkinter 导入失败或 Tcl/Tk 初始化失败时只打印诊断，Python 模块入口仍返回成功。现在 `main()` 只捕获预期的 Tk/Tcl 启动失败，输出诊断到 stderr 并返回 1；正常关闭返回 0。意外 UI `RuntimeError` 不会被吞掉，保留回溯供调试；清理根窗口时不使用 `os._exit`。

| 实际子进程场景 | 结果 |
|---|---|
| 注入 `tkinter` 导入失败后经 `runpy.run_module(..., run_name="__main__")` | 非零退出；stdout 为空；stderr 有“LWT 语义实验室不可用 / 无法导入 Tkinter”；无 traceback |
| 注入 `tk.Tk()` 抛 `TclError` | 非零退出；stdout 为空；stderr 含 Tcl 初始化诊断；无 traceback |
| 用隔离 Tk/UI shim 模拟正常主循环结束 | exit 0，stdout/stderr 均为空；不依赖桌面 |
| 注入未预期 UI `RuntimeError` | 非零退出并保留 traceback，不误报为可恢复的 Tk 启动错误 |

四个子进程契约均由 `python -m unittest discover -s tests -p "test_language_lab_entry.py" -v` 实际验证。

## P1：六个预测案例与公开 CLI 结果

以下命令从仓库根目录执行。应用实际使用当前 `sys.executable`、绝对源文件 argv、`shell=False` 和仓库根 cwd；表内将仓库路径简写为相对路径，避免将机器个人目录写进教学说明。六例均由真实 `python -m lwt` 子进程执行；不是 Python 前端模拟出的输出。

| 主题与预测题 | 正确选项与解释 | 真实 CLI 命令/输入 | 实测结果 |
|---|---|---|---|
| 分支与循环：输出序列是什么？选项 `0 → -1 → 2 → -3`、`0 → 1 → 2 → 3`、`只输出 0` | `0 → -1 → 2 → -3`。`i` 从 0 增至 3；偶数分支输出 `i`，奇数分支输出 `-i`，当 `i=4` 时 while 结束。 | `python -m lwt examples/control_flow.lwt` | exit 0；stdout 为 `0\n-1\n2\n-3\n`；stderr 空。 |
| 函数/递归：在函数声明前调用 `factorial(5)` 会得到什么？选项 `120`、`24`、`声明前报错` | `120`。顶层函数先登记，允许前向调用；递归基例为 `n <= 1`。 | `python -m lwt examples/functions.lwt` | exit 0；stdout 为 `120\n`；stderr 空。 |
| 数组/record/each 浅快照：本轮会访问被替换的 `review` 或新追加的 `late` 吗？选项：`访问 draft、review；不访问 replacement 或 late`、`访问 draft、replacement、late`、`只访问 draft` | `访问 draft、review；不访问 replacement 或 late`。each 遍历开始时保存元素引用的浅快照；替换位置和追加元素不改变本轮序列，但修改快照引用到的 record 可见。 | `python -m lwt examples/collections.lwt` | exit 0；stdout 为 `draft\nreview\n["draft", "review"]\n[Task{name: "draft", done: true}, Task{name: "replacement", done: false}, Task{name: "late", done: false}]\n`；stderr 空。 |
| 文本函数与 CLI 参数：`args()` 有几个元素？选项 `1 个`、`2 个`、`3 个` | `2 个`。`--` 后的相对 fixture 路径和 `preview` 都是程序参数，`args()` 返回两个值。 | `python -m lwt examples/text_tools.lwt -- examples/fixtures/text_tools.txt preview` | exit 0；stdout 为 `2\n[12, "apple", 5]\n[7, "pear", 4]\n`；stderr 空。 |
| stdin：`input()` 返回的正文是否保留 LF？选项 `会保留 LF`、`不会保留 LF`、`返回 null` | `不会保留 LF`。输入行为由语言规范定义；示例读入一行后通过 `emit` 输出正文。 | `python -m lwt examples/basic_io.lwt`；stdin 为 `LWT 输入演示\n` | exit 0；stdout 为 `Enter one line:\nLWT 输入演示\n`；stderr 空。 |
| 运行时错误定位：除零的错误类别、位置和退出码是什么？选项 `exit 0，无诊断`、`exit 2，SyntaxError`、`exit 3，RuntimeError，2:8` | `exit 3，RuntimeError，2:8`。除零在运行时失败，除法运算符的稳定位置为第 2 行第 8 列。 | `python -m lwt examples/language_lab/division_by_zero.lwt` | exit 3；stdout 空；stderr 含 `:2:8: RuntimeError: division by zero`；无 Python traceback。 |

应用在“你的预测”区显示实际所选选项和正确/错误；“CLI 结果”独立显示成功或预期错误诊断，并保留原始 stdout、stderr 和退出码。即使 CLI 意外偏离预期，固定教学预测与 CLI 契约核对也不会混为一个分数。

## 状态与错误恢复证据

- 固定清单含六个唯一主题；每题至少两个唯一选项，正确答案必须属于选项，解释非空；测试将正确选项与示例预期 stdout 和退出码固定契约对应。
- 未选题、未选择答案、未提交预测时不能运行；提交后不能改选；已有结果后需重置才能重跑。错误答案和正确答案都经过会话测试。
- 切换题目或重置会清空预测、答案、CLI 结果和错误。旧 revision 完成结果会被拒绝；关闭会话后 pending 结果不能更新状态。
- 超时、子进程无法启动、源文件缺失均转成可读错误；固定白名单没有任意路径执行入口。
- 真实六例 CLI 集成测试核对 stdout、stderr、退出码、stdin、`--` 后参数、cwd、argv、UTF-8、`shell=False` 和有限超时。

## P1：桌面 GUI 验收矩阵

执行窗口用当前 `python -m app.language_lab` 启动了唯一标题为“LWT 语义实验室（Python 教学前端）”的测试窗口并捕获目标窗口状态。截图显示另一应用窗口覆盖着目标窗口，无法把下一步点击/按键归因到本次测试；按 S20 操作纪律立即停止，没有激活、点击、键入或切换其他窗口。随后只清理检查了本轮启动的进程，没有继续桌面输入。因此，启动窗口和获取截图**不作为 GUI 交互通过**。

| 场景 | 实际点击/键盘观察 | CLI/无头测试支持 | 代码审阅 | 当前结论 |
|---|---|---|---|---|
| 语义实验室六主题、题目/源码切换、源码只读 | 未操作；目标窗口被遮挡后停止 | 六例 manifest、源码白名单和六例 CLI 均有测试 | Tk 主线程构造控件；固定源只读展示 | GUI 未验证 |
| 正确/错误预测、提交后才运行、输出与解释 | 未操作 | 会话模型核验预测、提交、正确/错误反馈、运行契约独立 | 按钮状态依赖提交/运行状态；显示 `describe_outcome` | GUI 未验证 |
| 运行时错误、重置/重试、关闭和异步过期 | 未操作 | exit 3 错误集成测试；reset/retry/revision/close 状态测试 | worker 只写队列，Tk 更新在轮询回调 | GUI 未验证 |
| 工作台 WARN+retry+top=2、旧结果清除、原始报告、零匹配、无效路径恢复、Unicode 路径、缩放 | 未操作 | `test_log_report_view.py` 的真实 CLI、边界和状态测试 14 项通过 | S18 Python 前端仍只展示 LWT 报告；没有改变其代码 | S20 手工项未验证 |
| 日志侦探第五题结束页、重开、Enter | 未操作 | `test_log_detective.py` 11 项含结束/重开状态和公开 CLI 测试通过 | 只审阅了现有实现 | S20 手工项未验证 |
| Snake 方向键/WASD、Space/R、失焦暂停恢复、终态重开、焦点/缩放 | 未操作 | `test_snake_game.py` 13 项无头状态测试通过 | 只审阅了现有实现 | S20 手工项未验证 |

### 留给主窗口/稳定桌面的手工复验步骤

1. 在无其他窗口遮挡的桌面运行 `python -m app.language_lab`；逐个切换六主题，确认源码只读。
2. 对分支例先故意选错并提交，再运行；查看预测标记、stdout、exit 0 和解释。重置后选对再跑；运行除零例确认 exit 3 的 RuntimeError 与源码位置，无 traceback。
3. 运行途中关闭窗口或切换案例（若按钮可操作），确认无旧结果覆盖、销毁控件 Tcl 异常或 UI 卡死；测试 timeout/启动失败后通过重置恢复。
4. 打开日志侦探，在工作台执行 `WARN + retry + top=2`，对照摘要、条形图、匹配示例和完整原始报告；再检查零匹配、缺失文件恢复、空格/Unicode 路径、条件切换和窄窗口。
5. 在五题挑战中完成第五题并重开，检查 Enter 路径；在 Snake 检查方向键/WASD、Space、R、失焦暂停/恢复、终态重开和窗口缩放。若输入法拦截快捷键，只记录按钮路径可用，不声称快捷键覆盖。

无头测试和代码审阅只能支持状态/CLI 契约，不能替代以上人工观察。

## 完整回归命令与结果

所有下列命令均在本阶段分支工作目录中实际运行，退出码均为 0。

| 命令 | 实际结果 |
|---|---|
| `python tools/run_tests.py` | 194/194 黑盒通过，0 失败；分类：arrays-records-each 32/32、builtins-text-io 43/43、cli-errors 13/13、control-functions 30/30、integrated 3/3、lexer-parser 42/42、values-operators 31/31。 |
| `python tools/check_project_integrity.py` | `OK; cases=194; matrix_links=287; referenced_cases=194`。 |
| `python -m unittest discover -s tests -q` | `Ran 276 tests ... OK`；S19 基线 268，本轮新增 8 项。 |
| `python -m unittest discover -s tests -p "test_language_lab.py" -v` | 15 项通过；包含六例真实 CLI、预测契约、错误/正确答案、重置/重跑/过期/关闭状态。 |
| `python -m unittest discover -s tests -p "test_log_report_view.py" -v` | 14 项通过。 |
| `python -m unittest discover -s tests -p "test_log_detective.py" -v` | 11 项通过。 |
| `python -m unittest discover -s tests -p "test_snake_game.py" -v` | 13 项通过。 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 25 项通过；S10 CLI 契约测试未改动。 |
| `python -m unittest discover -s tests -p "test_language_lab_entry.py" -v` | 4 项入口子进程契约通过。S20 定向合计 19 项（实验室 15 + 入口 4）。 |
| `python -m compileall -q lwt tests tools bench app` | 退出码 0，无语法编译错误。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | `Effective LWT lines: 246`。 |
| `git diff --check main...HEAD` | 在最终文档提交后复跑；结果写入执行窗口最终报告。 |

在汇总前另实际重跑了六个固定示例，均满足白名单预期：前五例 exit 0、stderr 空；分支 stdout `0/-1/2/-3`，递归 stdout `120`，集合 stdout 包含 `draft`/`review`/最终数组，文本/参数 stdout 含参数数 `2` 和两行处理结果，stdin 输出中文输入行；除零例 exit 3、stdout 空、stderr 为 `RuntimeError` 且位置 `2:8`。

## 保护范围核对

逐个与 S20 基线 `44f85e9...` 对比，下列六个文件无差异：

- `app/log_report.lwt`
- `tests/test_app.py`
- `reports/app-concurrency.json`
- `docs/app-concurrency.md`
- `bench/results.json`
- `reports/performance.md`

没有运行并发/性能证据生成器；没有修改 `lwt/`、正式语言规范、语言黑盒测试/矩阵、日志报告计算逻辑；没有制作 PPT、新克隆验收、远端 Actions/Python 3.10 最终核验、推送、标签或发布。S12 保持未开始。GUI 手工验收仍是本阶段最主要未完成证据；桌面窗口被遮挡导致无法取得可归因输入，不应把本报告的无头通过解释为 GUI 已验收。

## 变更文件

代码与测试：

- `app/language_lab.py`：预期 Tk/Tcl 启动失败的非零退出契约。
- `app/language_lab_core.py`：六个固定预测、预测会话状态、实际 CLI 结果摘要。
- `app/language_lab_ui.py`：先预测后运行的键盘可达交互、反馈/解释、错误诊断标签和状态清理。
- `tests/test_language_lab.py`：预测契约、状态、六例真实 CLI 和结果摘要测试。
- `tests/test_language_lab_entry.py`：四项真实模块入口子进程测试。

说明与状态：

- `docs/s20-teaching-demo.md`（本报告）
- `docs/s20-optimization-plan.md`
- `README.md`
- `app/README.md`
- `docs/developer-guide.md`
- `docs/agent-dev-log.md`
- `project.md`
- `阶段执行与审查路线图.md`
- `详细实施规划.md`
- `LWT大作业总体方案与复检.md`

最终阶段 SHA、最终 `git status -sb`、链接/围栏检查和 `git diff --check main...HEAD` 结果由执行窗口交接回复给出。主窗口审查完成前，状态保持“实施完成，等待主窗口审查”；主窗口通过后再冻结应用范围并派发 S12。
