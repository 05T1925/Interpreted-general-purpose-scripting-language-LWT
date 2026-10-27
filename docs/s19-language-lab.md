# S19 执行报告：LWT 语义实验室、报告边界修复与展示增强

**阶段状态：实施完成，等待主窗口审查。** 本阶段在独立分支完成，未合并、未推送；S12 仍未开始。

## 1. 基线和分支

- 仓库：`C:\Users\28641\Desktop\大三上\程序设计实践\大作业`
- 基线：本地已审查 `main`，`c966f97096fd590a77176c9b18f8f45fee5fed31`；开始时工作区干净。
- 阶段分支：`stage/s19-language-lab-robustness`。
- 远端：开工时只读查询 `origin/main` 得到旧提交 `de608f7fbf50946715d370df014657169eb8f26d`。本地 main 已领先多个阶段；本阶段没有从远端取代或覆盖本地基线，也没有推送。
- 基线要求：194 项语言黑盒、256 项 unittest、25 项 S10 CLI 测试、246 行有效 LWT。结束验证保持以上基线，并增加 10 项 unittest。

## 2. 修改文件

### 报告拆行缺陷

- `app/log_report_view.py`：报告协议以 LF 为逻辑分隔符。只去除协议要求的末尾一个 LF，再调用 `split("\n")`；U+0085、U+2028、U+2029、VT、FF 留在报告字段内容中。没有放宽标题、字段、顺序、重复项、计数一致性、Top 截断或示例数量检查。
- `tests/test_log_report_view.py`：新增一项真实 CLI 到报告解析器的 Unicode 回归；并把空报告和额外末尾 LF 加入损坏报告拒绝案例。

### 语义实验室

- `app/language_lab.py`：桌面入口 `python -m app.language_lab`。Tk 无法初始化时返回可读错误，不打印 traceback。
- `app/language_lab_core.py`：固定 6 例白名单、UTF-8 源码读取、稳定预期核对、状态版本和公开 CLI 执行。
- `app/language_lab_ui.py`：只读源码和规范章节/观察点展示；显示本次 argv、工作目录、`--` 后参数或 stdin、stdout、stderr、退出码及预期核对结果。工作在后台线程运行，结果经队列交给 Tk 主线程绘制；重复运行被阻止，切换示例会清空旧结果，窗口关闭时取消轮询并使旧请求失效。
- `examples/language_lab/division_by_zero.lwt`：新增两行确定性除零程序，用于稳定演示运行时诊断位置。
- `tests/test_language_lab.py`：新增 11 项无头测试和真实 CLI 集成测试，覆盖白名单、任意路径拒绝、缺失源码、stdin/CLI 参数、6 例真实输出、错误定位、Tk/Tcl 启动失败、子进程超时/启动失败、异常输出与状态切换/重试。

### 使用与阶段文档

- `app/README.md`：语义实验室启动方法、演示边界和 CLI 后退入口。
- `README.md`：S19 阶段状态、阅读入口和应用说明。
- `docs/developer-guide.md`：新增语义实验室使用说明。
- `docs/agent-dev-log.md`：记录实际任务提示、生成文件、人工复核与修正、真实 CLI 结果和 GUI 未验证边界。
- `docs/s19-optimization-plan.md`：更新交付状态、实际实现范围和桌面未验证项。
- `project.md`：更新 S19 阶段、项目状态和证据入口。
- `详细实施规划.md`、`LWT大作业总体方案与复检.md`、`阶段执行与审查路线图.md`：同步 S19 已实施、待主窗口审查及 S12 尚未开始的状态。
- `docs/s19-language-lab.md`：本报告。

本阶段没有修改 `lwt/`、`docs/language-spec.md`、`tests/test_app.py`、S8 黑盒矩阵、`app/log_report.lwt`、Snake 游戏逻辑或 S10/S11 保护证据。

## 3. 真实缺陷复现与修复证据

复现输入是一条以 LF 结束的 UTF-8 日志记录，消息含合法 U+2028：

```text
t|INFO|app|alpha<U+2028>beta<LF>
```

复现命令：

```text
python -m lwt app/log_report.lwt -- <临时 UTF-8 日志路径>
```

修复前，LWT CLI 正常退出（0），stderr 为空，报告中的 `Matching examples` 保留完整消息；工作台使用 Python `str.splitlines()` 却把 U+2028 再拆成两行，因而错误拒绝报告并提示“匹配示例数量与匹配数不符”。日志分析器输出契约本身没有缺陷。

修复后再次通过相同公开 CLI 路径，得到 `Total lines=1`、`Valid records=1`、`Malformed lines=0`、`Matched records=1`，唯一匹配示例仍是完整的 `t|INFO|app|alpha<U+2028>beta`；CLI 退出码为 0，stderr 为空。新增回归在一条消息中同时放入 U+0085、U+2028、U+2029、VT、FF，验证 LWT 报告解析器将其保留为一条记录。损坏报告测试仍拒绝空/缺字段/重复字段/错序/矛盾计数/额外末尾 LF 等输入。

此修复只改变 Python 视图对 LWT 报告分隔符的解释，不修改 `app/log_report.lwt`、日志解析/统计逻辑或 CLI 格式。

## 4. 语义实验室设计和实跑结果

实验室是 **Python/Tkinter 教学与展示前端**，不是第二个“用 LWT 编写的应用”。示例清单固定在代码白名单内；用户不能编辑或指定任意 LWT 文件。每个示例都通过当前 `sys.executable -m lwt`、参数数组、`shell=False`、仓库根 `cwd`、UTF-8 和 12 秒超时执行。Python 只收集并展示进程结果，不重写语言语义。课程 Agent 编写的完整 LWT 应用仍是 `app/log_report.lwt`，日志读取、解析、过滤、统计和排序仍由该 LWT 程序完成。

下面命令均从仓库根执行。表中的 stdout 是本次真实 CLI 捕获的精确文本；空 stderr 记为 `（空）`。源码与规范对应章节也会在界面显示。

| 主题 | CLI 命令 | stdin | 实际 stdout | stderr / 退出码 |
|---|---|---|---|---|
| 分支与循环 | `python -m lwt examples/control_flow.lwt` | 空 | `0\n-1\n2\n-3\n` | 空 / 0 |
| 前向调用与递归 | `python -m lwt examples/functions.lwt` | 空 | `120\n` | 空 / 0 |
| 数组、record、each 浅快照 | `python -m lwt examples/collections.lwt` | 空 | `draft\nreview\n["draft", "review"]\n[Task{name: "draft", done: true}, Task{name: "replacement", done: false}, Task{name: "late", done: false}]\n` | 空 / 0 |
| 文本函数和 CLI 参数 | `python -m lwt examples/text_tools.lwt -- examples/fixtures/text_tools.txt preview` | 空 | `2\n[12, "apple", 5]\n[7, "pear", 4]\n` | 空 / 0 |
| stdin 与 `input()` | `python -m lwt examples/basic_io.lwt` | `LWT 输入演示\n` | `Enter one line:\nLWT 输入演示\n` | 空 / 0 |
| 运行时错误定位 | `python -m lwt examples/language_lab/division_by_zero.lwt` | 空 | 空 | `.../division_by_zero.lwt:2:8: RuntimeError: division by zero` / 3；没有 Python traceback |

自动化集成测试对 6 个示例逐一调用真实 LWT CLI 并精确比较成功输出；错误示例检查退出码 3、stderr 错误类别、行列字段、稳定消息和无 traceback。展示代码保留每次调用实际 stderr，包括动态源文件路径；测试不对临时绝对路径做脆弱的全文比较。

### 三分钟演示顺序

1. **0:00–0:25**：启动语义实验室，说明这是 Python 前端，展示固定 LWT 源码、规范章节和“观察点”；指出课程主应用仍是 `app/log_report.lwt`。
2. **0:25–0:55**：选择“分支与循环”，先预测输出，再运行并核对 stdout。
3. **0:55–1:20**：运行递归 factorial，观察声明前调用及结果 `120`。
4. **1:20–1:55**：运行 collections 示例，观察 each 的浅快照：本轮继续访问快照中的 `review`，记录对象字段修改可见，数组追加项留到下轮。
5. **1:55–2:25**：运行文本示例并展示 `--` 后两个参数；再运行 stdin 示例并输入一行中文。
6. **2:25–3:00**：运行除零程序，展示 stdout、stderr、退出码 3 和 `2:8` 定位；最后说明相同示例可在终端直接用公开 CLI 运行。

### 没有图形桌面时的后退命令

```powershell
python -m lwt examples/control_flow.lwt
python -m lwt examples/functions.lwt
python -m lwt examples/collections.lwt
python -m lwt examples/text_tools.lwt -- examples/fixtures/text_tools.txt preview
python -m lwt examples/basic_io.lwt
python -m lwt examples/language_lab/division_by_zero.lwt
python -m unittest discover -s tests -p "test_language_lab.py" -v
```

## 5. 桌面验收矩阵

**本轮没有进行可归因的人工点击验收。** 启动 GUI 检查时桌面被其他应用占据/遮挡，不能确认输入会落到本次窗口；因此停止操作并关闭本轮启动的进程。没有保存截图。本表将 CLI/无头支持和人工观察分开，不以代码审阅或自动化测试宣称 GUI 已通过。

| 项目 | CLI / 无头支持 | 实际点击观察 | 状态 |
|---|---|---|---|
| 工作台 `WARN + retry + top=2` | `test_combined_filter_is_parsed_from_real_cli` 及样例 CLI 验证 LWT 结果为 1 条、`WARN|1`、`cache|1`；未点击工作台 | 无 | GUI 未验证 |
| 更改条件后清除旧结果 | S18 `WorkbenchSession` 状态测试验证旧请求结果被丢弃 | 无 | GUI 未验证 |
| 完整原始报告入口 | 代码保留同一次 CLI 查询的完整 stdout | 无 | GUI 未验证 |
| 零匹配、无效文件与恢复 | S18 报告模型测试覆盖零匹配、缺失文件和失败后旧报告清除 | 无 | GUI 未验证 |
| Unicode/空格路径 | `test_unicode_space_path_uses_public_cli` 通过真实 CLI | 无 | GUI 未验证 |
| 640×500 或更小尺寸及缩放 | 本轮没有通过桌面观察布局；自动测试不提供尺寸证明 | 无 | 未验证 |
| 日志侦探第五题结束页、计分和重开 | 全量 unittest 包含既有状态测试 | 无 | GUI 未验证 |
| Snake 方向键/WASD、Space/R、失焦暂停恢复、终态重开 | 全量 unittest 包含既有 Snake 状态测试 | 无 | GUI 未验证 |
| 语义实验室源码/输出布局与选择/运行/关闭 | 核心白名单、状态切换、启动失败/超时和 CLI 集成测试通过；Tk 控件未手动操作 | 无 | GUI 未验证 |

“代码与无头测试支持”仅说明相应逻辑有测试，不代表窗口尺寸、主题、键盘焦点、文件对话框和真实用户流程已人工验收。主窗口可在稳定可操作桌面继续检查上述项目。

## 6. 实际运行的验证命令

| 命令 | 结果 |
|---|---|
| `python tools/run_tests.py` | 退出码 0；语言黑盒 194/194。分类：数组/record/each 32/32、内置函数与 I/O 43/43、CLI 错误 13/13、控制流/函数 30/30、集成 3/3、词法/语法 42/42、值与运算符 31/31。 |
| `python tools/check_project_integrity.py` | 退出码 0；194 cases、287 matrix links、194 referenced cases。 |
| `python -m unittest discover -s tests -q` | 最终重跑退出码 0；268 项通过（35.094 秒），较 256 项基线新增 12 项。 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 退出码 0；S10 既有 25 项 CLI 契约测试通过。 |
| `python -m unittest discover -s tests -p "test_log_report_view.py" -v` | 退出码 0；14 项通过，含 U+2028 等真实 CLI 报告回归。 |
| `python -m unittest discover -s tests -p "test_language_lab.py" -v` | 最终定向运行退出码 0；11 项通过，含 6 个真实 CLI 示例和 Tk/Tcl 初始化失败处理。 |
| `python -m unittest discover -s tests -p "test_log_detective.py" -v` | 退出码 0；11 项通过，覆盖既有挑战状态、CLI 边界与真实报告集成。 |
| `python -m unittest discover -s tests -p "test_snake_game.py" -v` | 退出码 0；13 项通过，覆盖 Snake 状态、方向变更、失焦暂停和终态重开逻辑；不代表桌面按键已人工验收。 |
| `python -m compileall -q lwt tests tools bench app` | 退出码 0。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 退出码 0；246 行有效 LWT。 |
| Markdown 本地链接与围栏检查 | 退出码 0；28 个 Markdown 文件、520 个本地相对链接、围栏平衡。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 退出码 0、stderr 空；7 总行、6 有效、1 坏行、6 匹配，ERROR/INFO/WARN 各 2。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | 退出码 0、stderr 空；1 匹配，`WARN|1`、`cache|1`，示例为 `retry scheduled`。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/showcase.log` | 退出码 0、stderr 空；12 总行、11 有效、1 坏行、11 匹配；DEBUG/ERROR/INFO/WARN 为 1/3/4/3。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/showcase.log --level WARN --keyword retry --top 2` | 退出码 0、stderr 空；2 匹配，`WARN|2`、`cache|2`，两条 retry 示例均显示。 |
| `git diff --check main...HEAD` | 最终阶段提交后复跑，退出码 0；无空白错误。 |

没有运行 `tools/run_app_concurrency.py`、正式性能基准或会改写并发/性能原始证据的生成器。S19 没有以 GUI 响应速度得出解释器性能结论。

## 7. 保护文件、规划差异和风险

### 分层提交

| 顺序 | 提交 | 内容 |
|---:|---|---|
| 1 | `0aa34ad28166fe7df716f951bc7fb41ac63a4c9e` | 报告按 LF 协议拆行与真实 CLI Unicode 回归。 |
| 2 | `4e48f40bd1473971dd126ba68b37bdc6fe753154` | 语义实验室核心、Tk 界面、入口、错误示例与初版 9 项测试。 |
| 3 | `fd7972246191da40e6f57c448440f5791301b9fb` | Tkinter 缺失/Tcl 初始化失败转为可读错误，并新增两项测试。 |
| 4 | `2a4f319` | 保留空报告与额外末尾 LF 的严格拒绝回归。 |
| 5 | 文档阶段提交 | 本报告、状态文档、应用说明和 Agent 开发记录；最终 SHA 由执行窗口交接时列出。 |

- 与本阶段基线比较，六个保护文件没有差异：`app/log_report.lwt`、`tests/test_app.py`、`reports/app-concurrency.json`、`docs/app-concurrency.md`、`bench/results.json`、`reports/performance.md`。
- 相对原规划，语义实验室落地为六个例子，而非原先概念阶段提出的“五个卡片”；覆盖面更明确地包括分支/循环、递归、集合快照、文本/参数、stdin 和错误定位。没有增加语言语法或运行时能力。
- GUI 人工验收受桌面遮挡影响，所有所列 GUI 操作仍需主窗口在可归因的桌面环境检查；本轮没有声称通过。
- Python 3.10、远端 Actions、新克隆验收、PPT、最终答辩和远端同步仍属于 S12，未提前开始。
- 本报告及相关阶段文档在阶段文档提交中；源代码提交 SHA、最终 HEAD、干净工作区及最终 diff/链接检查结果由执行窗口在交接消息中列出。
