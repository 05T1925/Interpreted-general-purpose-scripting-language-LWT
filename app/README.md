# LWT 日志分析器

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
