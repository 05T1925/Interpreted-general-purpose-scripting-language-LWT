# LWT 日志分析器

## 开发工具提示

S27 为 LWT 提供 `python -m lwt --check app/log_report.lwt`，用于不执行应用源码地检查静态名字、调用参数和 record 构造字段。该命令是解释器开发工具，不替代下方应用 CLI 示例，也不会读取日志；日志分析职责仍由 `app/log_report.lwt` 承担。机器可读方式为 `python -m lwt --check --format=json app/log_report.lwt`，完整范围见 [`docs/static-checker.md`](../docs/static-checker.md)。

`log_report.lwt` 是一个只读的日志统计 CLI 程序。它从一个 UTF-8 文本文件读取记录，在 stdout 输出固定格式的报告，不修改输入文件，也不写其他应用输出文件。

## 运行

从仓库根目录执行：

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log
```

参数形式如下；三个选项可以按任意顺序出现，每种最多一次：

```text
python -m lwt app/log_report.lwt -- INPUT_PATH [--level LEVEL] [--keyword TEXT] [--top N]
```

- `INPUT_PATH` 必须是第一个应用参数，且不能为空。相对路径按**进程当前工作目录**解析；示例命令均从仓库根目录运行。
- `--level LEVEL` 对第二字段作区分大小写的精确匹配。
- `--keyword TEXT` 对第四字段 message 作区分大小写的子串匹配；不检查时间、级别或模块，不能为空。
- 同时给出 `--level` 和 `--keyword` 时使用 AND 条件。
- `--top N` 限制模块排行项数，默认 `5`；只接受 ASCII 数字组成的非负十进制整数。`0` 保留排行标题但不输出排行条目。
- 未知、重复、缺值的选项，额外位置参数、缺少路径、空 keyword 和不合法 top 都通过 LWT `fail()` 给出单行 usage 诊断；stdout 为空、进程以运行时错误退出码 `3` 结束，不产生 Python traceback。为区分选项和值，`--level`、`--keyword`、`--top` 后的参数若以 `--` 开头会按缺少值处理；因此当前 CLI 不接受以 `--` 开头的 level/keyword 字面值。

所有参数错误都在打开文件和打印报告前检查。文件不存在、不可读取或不是有效 UTF-8 时由 `read_text()` 报运行时错误，退出码为 3；这类错误同样不会打印应用报告或 Python traceback。

## 输入记录与坏行

每个逻辑行使用四字段格式：

```text
timestamp|level|module|message
```

时间戳是原样保留的不透明文本，不解析日期；字段不作裁剪。字段数恰好为 4 就是有效记录，空字段允许。字段数少于或多于 4 的行（包括空行，以及 message 含额外 `|` 的行）计为坏行；应用继续分析后续行。其他字段内容不作额外校验。UTF-8 BOM 与 CRLF/CR 按 LWT `read_text()` 规范处理。

空文件有 0 条逻辑行。文本按 LF 切分后，如果最后一个切分元素为空，只去掉这一个元素作为行结束结果。因此一个终止 LF 不增加行数；多个连续终止 LF 中，除最后一个外，之前产生的空逻辑行仍会作为坏行计入。无终止 LF 的最后一行仍参与处理。

默认示例 [`fixtures/sample.log`](fixtures/sample.log) 含 6 条有效记录和 1 条坏记录；完整期望输出在 [`fixtures/sample.expected.txt`](fixtures/sample.expected.txt)。异常样本 [`fixtures/malformed.log`](fixtures/malformed.log) 展示空行、短行和多字段行如何计数。

## 过滤、统计与输出

先统计逻辑行、有效记录和坏行；再对有效记录应用过滤条件。`Matched records`、级别统计、模块排行和匹配示例都只针对匹配记录。级别统计按 level 字符串升序排列；模块先按出现次数降序，次数相同时按模块名升序。匹配示例是原文件顺序中的前三条匹配记录。`--top` 只裁剪模块排行，不影响级别统计和匹配示例。

报告固定包含以下 section，顺序不变；空 section 保留标题且不增加空行：

1. 固定标题 `LWT log report`
2. `Total lines`、`Valid records`、`Malformed lines`、`Matched records`
3. `Level counts:` 及各 `LEVEL|COUNT` 项
4. `Top modules:` 及各 `MODULE|COUNT` 项
5. `Matching examples (first 3):` 及原始记录行

过滤示例：

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2
```

该命令匹配一条记录：级别为 `WARN|1`，模块为 `cache|1`，示例行为 `2026-10-07T10:00:03Z|WARN|cache|retry scheduled`。正常报告不包含输入路径、当前时间或耗时，因此对同一输入和参数重复运行会产生相同输出。

## 实现限制与复杂度

应用一次性用 `read_text()` 读取整个文件，并在内存中保存逻辑行和解析出的匹配 record；它不适合超大日志流式处理。没有字典数据类型，级别与模块通过数组线性查找聚合。若 `R` 条有效记录都匹配、`M` 是不同模块数、`L` 是不同级别数，聚合最坏约为 `O(R × (M + L))`；关键字拆分另随 message 长度增长。级别排序约 `O(L²)`；模块排行每选出一项扫描候选数组，输出 `K = min(M, top)` 项时约 `O(M × K)`。空间复杂度包含整个输入、行数组、记录数组和 `O(M + L)` 聚合项。

## 独立进程读取验证

可运行：

```powershell
python tools/run_app_concurrency.py
```

工具用同一个 [`fixtures/concurrency.log`](fixtures/concurrency.log)、同一命令和当前应用文件，分别并发启动 1、2、4 个独立 `python -m lwt` 操作系统进程；每组先做 warm-up，再进行 5 个计时试次，逐字节核对 stdout、空 stderr 和退出码。Python 线程池只负责同时调度子进程，**这不是 LWT 线程、语言级并发或并行加速结论**。原始数据和解释见 [`../docs/app-concurrency.md`](../docs/app-concurrency.md) 与 [`../reports/app-concurrency.json`](../reports/app-concurrency.json)。

固定 fixture 的完整行为通过 `tests/test_app.py` 经公开 CLI 测试；该应用测试不加入 S8 的 194 项语言黑盒覆盖矩阵。

## 日志侦探：分析工作台与五题挑战（S15、S18）

在具备桌面显示能力且 Python 包含 Tkinter 的环境中，从仓库根目录启动：

```powershell
python app/log_detective.py
```

也可以从其他当前工作目录使用入口脚本的绝对路径启动。游戏默认读取 [`fixtures/sample.log`](fixtures/sample.log)，提供五道 `level`、`keyword` 和组合过滤题；玩家输入匹配记录数，可按 Enter 提交，查看正误反馈、当前进度和最终得分。选择日志文件后会将完整路径作为单独参数传给 LWT CLI。游戏内“查看完整 LWT 报告”显示未过滤 CLI 的完整标准输出。

S18 在原五题挑战之外增加“分析工作台”选项卡。它可选择日志、设置 Level、Keyword 与 Top，显示 LWT 报告给出的总览数字、级别条形图、模块排行和前三条匹配示例。点击级别统计行会填入 Level；再次点击“运行 LWT 查询”才会发出新请求。模块排行只读。当前筛选条件与实际 CLI argv 在界面可见；“查看此次原始报告”打开同一次查询的完整 stdout。改变条件会使旧结果失效，零匹配与错误均可继续查询。五题挑战、Enter 提交、计分、重开和未过滤完整报告入口保留。

Python/Tkinter 负责窗口、题面、会话、得分、构造参数、校验固定报告格式与展示；日志读取、记录解析、过滤、统计、排序与正确答案仍由 `log_report.lwt` 通过 `python -m lwt` 完成。GUI 调用使用当前 Python、argv 参数列表、`shell=False`、仓库根工作目录、UTF-8 和 20 秒超时；后台线程只等待 CLI，Tk 控件更新限于主线程。GUI 不改变 LWT 的语言能力或 CLI 契约。

新增确定性 UTF-8 演示日志 [`fixtures/showcase.log`](fixtures/showcase.log) 有 12 行，其中有效 11、坏行 1；包含 Unicode、多级别、多模块和两条 WARN/retry 命中：

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/showcase.log
python -m lwt app/log_report.lwt -- app/fixtures/showcase.log --level WARN --keyword retry --top 2
```

前一命令得到匹配 11，级别 DEBUG/ERROR/INFO/WARN 分别为 1/3/4/3；后一命令得到匹配 2、WARN|2、cache|2。完整演示与教师要求对应表见 [S18 展示说明](../docs/s18-app-showcase.md)；阶段实测见 [S18 工作报告](../docs/s18-workbench.md)。

Tkinter 是 Python 标准 GUI 接口，但可能作为可选模块缺省；先检查 `python -m tkinter` 并确认有可用桌面。没有 Tkinter 或桌面时继续使用上面的 CLI；无需安装第三方 GUI 依赖。运行无头逻辑及 CLI 集成测试：

```powershell
python -m unittest discover -s tests -p "test_log_detective.py" -v
python -m unittest discover -s tests -p "test_log_report_view.py" -v
```

设计边界、实测观察、自动测试和未验证事项见 [`../docs/s15-app-gui.md`](../docs/s15-app-gui.md)。

## LWT 语义实验室（S19–S20）

从仓库根目录运行：

```powershell
python -m app.language_lab
```

实验室是 Python/Tkinter 制作的只读教学前端，并通过真实的 `sys.executable -m lwt` CLI 执行固定白名单中的示例。每例先显示一道固定预测题：选择并提交后才可运行；运行后同时显示学生选项与正确性、实际 stdout/stderr/退出码，以及预测题解释。预测答案与 CLI 契约状态是两项不同结果。成功样例核对精确 stdout；预期运行时错误明确显示“按预期报告 RuntimeError”，不把诊断误标为普通成功，也不隐藏真实 CLI 输出。源码不可编辑，也不接受任意路径或用户程序。网络和第三方依赖均不需要。

示例复用 `examples/control_flow.lwt`、`examples/functions.lwt`、`examples/collections.lwt`、`examples/text_tools.lwt` 与 `examples/basic_io.lwt`；错误定位使用 `examples/language_lab/division_by_zero.lwt`。无图形桌面时可直接运行示例 CLI；逐例命令和预期输出见 [`../docs/s20-teaching-demo.md`](../docs/s20-teaching-demo.md)。无头定向测试：

```powershell
python -m unittest discover -s tests -p "test_language_lab.py" -v
python -m unittest discover -s tests -p "test_language_lab_entry.py" -v
```

语义实验室是**Python 教学/展示前端**，通过公开 CLI 运行 LWT 示例，不是第二个“用 LWT 编写的应用”。课程 Agent 编写的完整 LWT 应用仍是 `app/log_report.lwt`，日志读取、解析、过滤、统计和排序仍由 LWT 实现。Tkinter/Tcl 缺失或启动失败时，模块入口在 stderr 给出诊断并返回非零退出码；其他未预期程序异常仍保留回溯供调试。S20 三至五分钟演示步骤、CLI 实测结果和人工 GUI 未验证项见 [`../docs/s20-teaching-demo.md`](../docs/s20-teaching-demo.md)。

LWT 现在也支持静态函数库模块。日志分析器仍按现有单文件 CLI 契约实现；想查看独立的多文件语言示例，可从仓库根目录运行 `python -m lwt examples/modules/main.lwt`，规范和源文件路径语义见 [`../docs/language-spec.md`](../docs/language-spec.md#9-静态函数库模块s25)。

## 独立贪吃蛇（S16；S17 复检与界面打磨）

贪吃蛇是独立的 **Python/Tkinter 附加演示，并非第二个 LWT 应用**；不调用 LWT 日志分析器，也不计入 `app/log_report.lwt` 的课程代码行数。从仓库根目录启动：

```powershell
python app/snake_game.py
```

方向键或 WASD 控制移动；Space 在准备状态开始、运行时暂停、暂停时继续；R 或“重新开始”按钮重置棋盘与得分。游戏结束或胜利时，主按钮变为“再来一局”，点击后会重置并立即开始；R 仍将棋盘重置到准备状态。方向键在按钮获得焦点时仍可控制蛇。游戏使用固定 140 毫秒事件间隔。窗口失去焦点后自动暂停，回到窗口后按 Space 或“继续”恢复。

蛇碰墙或撞到非尾部蛇身时结束。长度大于 1 时拒绝直接反向；若本步不吃食物，蛇头可以进入本步将离开的尾格。吃到食物后长度增加一格、得分增加 10 分，食物从剩余空格中均匀选择。填满棋盘即胜利。核心状态与规则位于不依赖 Tkinter 的 `snake_game_core.py`，界面与定时器在 `snake_game_ui.py`；导入核心不会打开窗口。

无头规则测试可在没有显示器的环境中运行：

```powershell
python -m unittest discover -s tests -p "test_snake_game.py" -v
```

Tkinter 可能未随 Python 安装；若启动时报 Tk 或桌面不可用，核心测试仍可运行。S17 为两款 GUI 统一了配色、间距和系统默认字体回退；日志侦探的题面、反馈与所选路径随窗口宽度调整，Snake 棋盘缩小时收敛网格细节，结束提示按棋盘尺寸排版。S17 主窗口已实际操作两款 GUI 主路径；S18 工作台的实测与尚未验证项见 [阶段报告](../docs/s18-workbench.md)，S17 原有审查记录见 [主窗口复核](../docs/s17-main-review.md)。

## S22 控件级交互回归

从仓库根目录运行真实 Tk 控件/事件集成测试：

```powershell
python -m unittest discover -s tests -p "test_gui_integration.py" -v
python tools/run_gui_integration.py --require-no-skips
```

测试使用真实应用窗口、Tk/Ttk 控件和事件循环；边界测试只注入受控 runner/timer，不替代主要 CLI 路径。语义实验室、工作台与五题挑战包含真实 `python -m lwt` 调用。Windows 上需要可用 Tk 桌面；无显示时测试会逐项标记 skip。Linux CI 会检查/按需安装 Xvfb，以虚拟显示运行 GUI 定向测试和完整 unittest。合成事件只证明控件与回调集成，不代表物理鼠标键盘、输入法、窗口管理器或人工视觉验收通过。S21 留下的人工 A/B/C 检查仍交由 S12 现场预检；完整映射、结果和限制见 [S22 执行报告](../docs/s22-gui-regression.md)。

## S28 LWT 执行档案演示

日志分析仍完全由 `app/log_report.lwt` 解析、过滤和汇总。可从仓库根目录运行固定 profile 场景：

```powershell
python tools/run_app_profile_scenarios.py
```

该 runner 使用公开 `python -m lwt --profile ...` 子进程，固定执行默认样例和 `WARN + retry + top=2`，逐字比较普通模式与 profile 模式的 stdout、stderr、退出码，再合并两次独立运行并渲染 HTML。预生成的 [档案 JSON](../reports/app-lwt-profile.json) 与[离线 HTML](../reports/app-lwt-profile.html) 可直接查看。profile 是解释器开发工具，不属于 LWT 应用能力；额外开销使其不适合作为 S11 性能测量模式，也不刷新 S10 并发记录。数据结构和证据细节见 [执行档案说明](../docs/execution-profile.md) 与 [S28 报告](../docs/s28-execution-observability.md)。

## S34 LWT 驱动贪吃蛇

运行 `python -m app.lwt_snake`。窗口明确标为“LWT 驱动贪吃蛇”；游戏状态来自单个长期 `python -u -m lwt app/lwt_snake/game.lwt` 子进程。方向键/WASD 转向，Space 开始、暂停或继续，R/“重新开始”复位；终局主按钮先回到准备状态，再点击开始。失去窗口焦点自动暂停，恢复焦点后手动继续。等待响应时忽略普通输入，TICK 不重叠；规则进程故障后点击“重试引擎”。

默认棋盘 24×18、种子 1。RESET 重放同一初始食物序列。固定命令脚本 `app/lwt_snake/demo.commands` 在 4×1 小棋盘演示吃食物并获胜，预期逐行输出见 [demo.expected](lwt_snake/demo.expected)。跨平台 CLI 后退演示：

```powershell
python -c "import subprocess,sys,pathlib; p=subprocess.run([sys.executable,'-u','-m','lwt','app/lwt_snake/game.lwt'],input=pathlib.Path('app/lwt_snake/demo.commands').read_bytes()); sys.exit(p.returncode)"
```

新游戏规则由 LWT 编写，Python bridge/GUI 仅负责进程、输入事件、响应校验和绘图。原 Python Snake 入口及规则保持独立；完整协议、状态与错误行为见 [冻结文档](lwt_snake/protocol.md)。定向回归：`python -m unittest discover -s tests -p "test_lwt_snake*.py" -v`。Tk 用例使用真实控件与合成事件，不能替代人工键鼠/输入法/视觉验收；证据与限制见 [S34 报告](../docs/s34-lwt-snake.md)。

## S35 保存、验证、复盘与接管

在同一 LWT Snake 窗口点击“保存本局”，通过工作线程事务边界保存完整前缀；文件对话框可能引发的 PAUSE 同样按真实响应录制。取消对话框不会保存。文件只写到玩家明确选择的位置，不自动加入 Git 或上传。达到 5000 条录制上限会提示仅保留前缀，原子写失败不会破坏已有目标。

点击“载入记录”会先回收实时引擎，再启动新的公开 LWT CLI 逐条验证；验证成功后才能上一条/下一条或播放，速度为慢/中/快。位置按事务计数，TURN、PAUSE、RESET、ERR 也占位置，不保证每条都移动。视觉暂停不发 PAUSE。可以取消验证、连续载入另一记录或返回实时游戏。

选定非终态位置后点击“从此接管”，系统再从 INIT 重执行到该前缀，保留随机状态和待转向状态。READY 等待开始，PAUSED 等待继续，RUNNING 在明确接管后恢复游戏时钟；终态需选较早位置或返回实时新局。新子局含完整前缀及后续事务，另选文件保存即可独立验证，父文件不变。

```powershell
python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-parent.json
python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-child.json
python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-divergent.json
```

前两条成功退出 0（10/12 笔）；第三条故意篡改，退出 3 并报告第 3 笔 TICK 分数不同。文件/版本/源码不兼容退出 2。工具退出码不改变 LWT CLI。完整[格式说明](../docs/snake-replay-format.md)与[实际验证记录](../docs/s35-replay.md)说明 16 MiB/5000 条上限、固定可信源码、超时/取消及自动/人工边界。S34 时钟已改为独立截止时间，持续转向不会重设移动时间。

## S36 LWT 策略提示与自动驾驶

仍从 `python -m app.lwt_snake` 进入。在 RUNNING 状态点击“提示 / 关闭提示”，独立长驻 `strategy.lwt` 计算方向箭头及 FOOD（食物路线）、SPACE（优先空间）或 TRAPPED（没有合法步）。提示只显示在棋盘下方文字区，不改游戏状态、不写游戏事务；计算中停手动时钟，返回后恢复，下一次快照会清除旧提示。PAUSED 时先“继续”再查询；关闭提示或手动转向可取消。策略是固定 U/R/D/L 平局序的单步 BFS 启发式，不保证最优或胜利。

点击“自动驾驶：关”启用后，手动定时器停用，每链串行执行“LWT 策略 → 必要 TURN → TICK → 新快照”，链间至少 140ms，响应慢时不补发。手动方向键退出自动并接管。暂停、失焦、重置、保存/载入对话框、复盘、接管、关闭均取消旧策略；恢复焦点或继续游戏不会自行恢复自动。策略错误会停止定时推进并保留已确认状态，可重试策略或手动接管；不会回退到 Python 寻路。两个 LWT 进程的 PID、序号与生命周期独立。

自动驾驶真实 TURN/TICK 沿用 S35 录制器，保存时先停止自动并请求 PAUSE，在一致事务边界保存；即使取消文件选择，也不会自动续跑。保存文件可用上述 replay CLI 在全新游戏进程内验证，再选 RUNNING 前缀接管、手动转向并另存子局。固定 S35 样例、game.lwt、原 Python Snake 均保持不变。

无 GUI 的确定性后退演示（仓库根目录）：

```powershell
python -m lwt --check app/lwt_snake/strategy.lwt
python -c "import subprocess,sys,pathlib; p=subprocess.run([sys.executable,'-u','-m','lwt','app/lwt_snake/strategy.lwt'],input=pathlib.Path('app/lwt_snake/strategy-demo.commands').read_bytes()); sys.exit(p.returncode)"
python -m unittest tests.test_lwt_snake_strategy -v
```

三条响应依次为 `MOVE|R|FOOD`、`MOVE|L|SPACE`、`NONE|-|TRAPPED`；完整预期见 [strategy-demo.expected](lwt_snake/strategy-demo.expected)。两分钟展示：开始并手动转向（20s）→提示及 LWT 算法边界（20s）→自动数步（20s）→保存并用 replay CLI 验证（30s）→载入、选前缀、接管手动分支（30s）。这是可执行演示顺序，未声称人工演示已完成。[冻结协议](../docs/snake-strategy-protocol.md)、[阶段报告](../docs/s36-strategy.md)与[本机时延数据](../reports/s36-strategy-latency.json)说明测试、上限和未验证项；S12 仍未开始。

## S37 双 LWT 策略擂台

从仓库根目录执行；输出须是尚不存在的目录，已有目录一律拒绝覆盖：

```powershell
python -m app.lwt_snake.arena --seeds 4,7,11 --max-ticks 12 --workers 1 --output my-arena-result
python -m app.lwt_snake.arena --verify my-arena-result/result.json
python -m app.lwt_snake.replay --verify my-arena-result/replays/bfs-4.json
```

第一条运行 `baseline`（优先保持合法当前方向，否则首个合法方向）与 `bfs`（S36 静态 BFS），各自都是 LWT 源程序；每局独立启动 LWT 游戏与策略子进程。结果按策略和 seed 固定排序。第二条对现行 v2 结果用全新 LWT 游戏与策略进程分别复核游戏回放及决策链；第三条可单独打开某局的 S35 游戏回放。控制台打印每局分数、步数、停止原因及两个证明标志，也打印每策略完成局的 median/min/max。S37 初版范围和历史结果见[原契约](../docs/s37-arena-contract.md)、[六局 v1 结果](../reports/s37-demo/result.json)与[阶段报告](../docs/s37-arena.md)。

**S38 证据口径：** 现行命令生成 v2 结果，额外保存逐步 LWA1 决策证据；`--verify` 分别核对 `game_verified` 和 `policy_verified`。旧 S37 固定结果保持原样，不能证明每步来自所标策略；须显式运行 `python -m app.lwt_snake.arena --game-only --verify reports/s37-demo/result.json`，输出会标注 `strategy decisions unverified`；普通 `--verify` 对 v1 退出 3。新固定样例及可解释命令：

```powershell
python -m app.lwt_snake.arena --verify reports/s38-demo/result.json
python -m app.lwt_snake.arena --explain reports/s38-demo/result.json --case bfs/4 --step 3
```

解释命令先双层验真，再显示真实查询前快照、LWT 建议、TURN/TICK 和分数变化。固定样例见[结果](../reports/s38-demo/result.json)、[v2 契约](../docs/s38-policy-proof-contract.md)及[实施报告](../docs/s38-policy-proof.md)。无桌面或断网时可直接使用以上 CLI。SHA-256 标识文件字节一致性及当前源码的确定性重算，不能认证历史执行者。

离线 2–3 分钟演示：展示两份 `.lwt` 决策源码（30 秒）→运行固定三 seed 的有界命令（约 1 分钟，实际耗时依设备）→查看结果表（20 秒）→独立验证一局回放（20 秒）→复制到临时目录篡改一笔 score，验证非零退出并定位事务（30 秒）。该顺序是准备材料，人工现场演示尚未完成。相同 seed 仅固定初始随机状态，不保证两策略后续食物完全一致；这个小样本不能证明算法优越性。Python 汇总统计与展示不代算方向、碰撞或得分；无需 GUI 或网络。S12 仍未开始。

## S39 Agent 可编写 LWT 策略工作坊

把[策略模板](lwt_snake/strategies/strategy-template.lwt)复制到同目录新文件，按 [策略 SDK](../docs/strategy-sdk.md)编写无 `import` 的 LWA1 长驻 LWT 程序，并在[可信本地目录](lwt_snake/strategies/strategy-catalog.json)添加 ID、单文件路径、规范化源码 SHA-256 与协议版本。内置 `baseline,bfs` 仍无需 catalog；自定义策略必须显式 `--catalog`，路径限制和超时**不是安全沙箱**，只运行自己信任的本地源码。

```powershell
python -m app.lwt_snake.arena --check-strategy mobility-lookahead --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.arena --catalog app/lwt_snake/strategies/strategy-catalog.json --strategies baseline,bfs,mobility-lookahead --seeds 4,7,11 --max-ticks 6 --workers 2 --output 新目录
python -m app.lwt_snake.arena --verify 新目录/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.arena --explain 新目录/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json --case mobility-lookahead/4 --step 1
```

第三策略 `mobility-lookahead.lwt` 由独立上下文 Agent 根据公开文档提交，以局部两步出口数、直接食物与距离做确定性选择；这不是 BFS，也不保证更高分。上面命令生成 v3 结果；验证与解释必须再提供同一可信 catalog，不能从结果文件自动运行路径。固定[九局 v3 证据](../reports/s39-demo/result.json)、[Agent 产出链](../docs/s39-agent-record.md)和[阶段报告](../docs/s39-strategy-workshop.md)可供离线复查。S37 v1 仍仅 game-only，S38 v2 六局仍可不带 catalog 双层验真。无 GUI/断网时本节就是完整后退路径；人工现场演示待 S12。

## S40 同一观察轨迹的单步反事实实验

从仓库根目录运行以下命令。S40 只接受已双层验真的 S39 v3 结果，候选策略对同一原局观察序列逐次响应；每个 MOVE 都在新 LWT 游戏进程里只推进一步，再由另一个新进程验证。Python 不计算移动、碰撞或分数。`--catalog` 必须显式指定可信本地目录，时间与路径限制不是陌生源码沙箱。

```powershell
python -m app.lwt_snake.counterfactual --analyze reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json --case baseline/4 --step 2 --strategies baseline,bfs,mobility-lookahead --output 新目录
python -m app.lwt_snake.counterfactual --verify 新目录 --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual --explain 新目录 --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual_ui
```

固定[方向分歧实验](../reports/s40-divergence/analysis.json)对比 baseline 的 R 与 BFS、新策略的 D；[第 1 步样例](../reports/s40-demo/analysis.json)展示同方向、不同原因，[故意篡改样例](../reports/s40-tampered/analysis.json)必须验真失败。Tk 入口仅是 Python 只读教学界面；没有 GUI 时上述 CLI 能完成全部验真和解释。证据边界见[冻结契约](../docs/s40-counterfactual-contract.md)和[阶段报告](../docs/s40-counterfactual-lab.md)。

## S41 自动寻找可复验方向分歧

从可信 S39 v3 结果中按 seed、咨询步和挑战者 ID 固定顺序搜索。参考与挑战者都是各自长驻的 LWT 进程，接收相同的真实观察前缀；最多扫描 32 次参考咨询。找到后调用 S40 生成并重验一步分支。预算内无分歧是正常结果，不能推断策略等价。可信本地目录与超时不是安全沙箱。

```powershell
python -m app.lwt_snake.witness --result reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json --reference baseline --challengers bfs,mobility-lookahead --max-observations 32 --output 新目录
python -m app.lwt_snake.witness --verify 新目录 --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual --explain 新目录/analysis --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual_ui
```

Tk 只读查看器的“加载见证目录”按钮可显式选择本地 S41 结果并在后台重新验真；固定 S40 演示仍可用。离线答辩可用[已发现见证](../reports/s41-found/witness.json)、[预算 1 无见证](../reports/s41-none/witness.json)、[篡改反馈](../reports/s41-tampered/agent-feedback.json)复现成功、边界和拒绝路径。冻结含义见[契约](../docs/s41-witness-contract.md)，实测与限制见[阶段报告](../docs/s41-witness-discovery.md)。

S12 候选的 5–8 分钟系统演示与无 GUI 命令见[演示脚本](../docs/demo-script.md)，八项提交物与现场尚待确认的操作见[最终验收清单](../docs/final-acceptance-checklist.md)。
