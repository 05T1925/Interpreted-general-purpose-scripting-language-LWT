# S15 日志分析器 GUI 与小游戏执行记录

> 状态：主窗口审查通过，带有明确的 GUI 手工验收遗留，已快进合入本地 `main`。阶段基线：`f6ef8c62737c91a18b793c12658804cba7fca810`；阶段分支：`stage/s15-log-detective-gui`；阶段最终提交：`390d484e2f21a044fcd8c9e8121712c215e1b309`。代码提交：`b8cb5604ba5e8968b099b9b42e52f90fc74ac573`、`5fd6f399814577b5d180905007fb7059ac73cd62`；测试提交：`2c49b356bfc34c3f56ff6b2a22705127dddafa2b`。

## 目标与范围

在保留课程要求的 LWT 日志分析应用主体的前提下，增加一个中文桌面小游戏“LWT 日志侦探”。用户针对默认样例或自行选择的日志回答五道过滤统计题，可以查看得分、反馈和完整分析报告。

`app/log_report.lwt` 继续负责读取日志、拆分记录、过滤、聚合和生成报告。GUI 每题都通过公开 CLI `python -m lwt app/log_report.lwt -- ...` 取得真实结果；Python 只解析报告的唯一 `Matched records: N` 字段，管理题目、窗口和计分。`app/log_report.lwt`、其 246 行有效 LWT、CLI 输出契约、S10 的 25 项应用测试以及并发读取脚本和历史证据均未修改。Tk 工作线程只等待子进程并将结果放入队列，Tk 控件只由主线程更新；这不表示 LWT 支持线程或语言级并发。

## 玩法与题目

默认文件为 `app/fixtures/sample.log`，共五轮：

| 轮次 | 过滤条件 | 样例正确答案 |
|---:|---|---:|
| 1 | `level` 精确等于 `INFO` | 2 |
| 2 | `level` 精确等于 `WARN` | 2 |
| 3 | `message` 包含 `retry` | 1 |
| 4 | `level` 精确等于 `ERROR` | 2 |
| 5 | `level` 等于 `WARN` 且 `message` 包含 `retry` | 1 |

上表答案是对固定样例当前 CLI 输出的记录摘要；运行时分数只采用子进程实际报告解析得到的值。报告按钮显示该日志的完整未过滤 LWT CLI stdout。用户可通过文件选择器换用其他日志；新路径作为单个 argv 元素交给子进程，路径解析基于模块 `__file__` 所在仓库根目录，因此支持空格、Unicode 和从仓库外启动绝对脚本路径。

界面提供开始、作答、正误反馈、下一题、最终得分和重新开始状态；答案可按 Enter 提交。正确/错误反馈同时以文字给出，未依赖颜色。查询异步执行且带有限超时；文件读取失败或 LWT 非零退出会呈现用户可读诊断，并允许重新开始或选择其他文件。

## 代码边界

- `app/log_detective_core.py`：无 Tk 依赖的题目定义、argv 构造、LWT 子进程调用、严格报告字段解析和游戏状态机。
- `app/log_detective_ui.py`：Tk/ttk 视图、事件处理、异步任务队列和报告展示；导入此模块不会创建根窗口。
- `app/log_detective.py`：启动入口；通过自身 `__file__` 解析仓库根目录，只有调用入口时才导入 GUI。
- `tests/test_log_detective.py`：无头状态/协议测试及实际 LWT CLI 集成测试，不进入 S8 的 194 项语言黑盒矩阵。

子进程使用 `sys.executable`、argv 列表、`shell=False`、仓库根目录 `cwd`、UTF-8 解码和 20 秒超时，并捕获 stdout、stderr、退出码。非零退出码、启动失败、超时和缺失/重复/无效报告字段会转换为 `AnalyzerError`。Python 不读取或解析日志文件，也不重新实现 level/keyword 过滤与聚合。

## 启动条件

在仓库根目录可运行：

```powershell
python app/log_detective.py
```

从其他工作目录启动时，传入入口脚本的绝对路径即可。GUI 需要有桌面显示能力且当前 Python 安装包含 Tkinter；Tkinter 虽是 Python 标准 GUI 接口，但某些发行包可能不包含该可选模块。[Python 官方 Tkinter 文档](https://docs.python.org/3/library/tkinter.html)（访问日期：2026-10-07）。无 GUI 条件时原有 LWT 命令行分析器仍可独立使用。

## 验证

环境：Windows；CPython 3.13.7；`tkinter` 可导入，Tk 8.6。`python -m tkinter` 诊断窗口实际显示并通过窗口 Quit 关闭。**GUI 手工验收观察：** 初始窗口显示中文标题、默认样例路径、0/5 进度、得分 0、答案输入、开始/下一题/查看报告/选择文件按钮；后续窗口观察到第 4/5 题、错误答案及正确值 2、得分 0 和可用的下一题按钮。桌面期间出现不能归因于执行窗口的用户输入，故观察到的局部状态不记为完整交互测试通过。

| 要求的桌面检查 | 结果 |
|---|---|
| 默认样例及起始窗口 | 已观察到默认 `sample.log`、0/5 及开始按钮；没有可归因的开始点击记录，列为部分观察。 |
| 从仓库外当前目录启动 | 用绝对入口路径和临时目录作为进程 CWD 启动第二个窗口成功；桌面上的其他窗口遮挡了默认路径完整内容，因此只确认窗口创建，路径标签未核实。 |
| 正确答案、得分更新 | 未验证。 |
| 错误反馈和正确值 | 窗口可见错误文字和正确值 2；具体提交者无法确认，列为部分观察。 |
| 下一题及进度更新 | 窗口可见第 4/5 题和下一题按钮；推进操作无法归因，列为部分观察。 |
| 最终结果页面 | 窗口显示“挑战完成”和 0/5；结束过程无法归因，列为部分观察。 |
| 完整 LWT 报告窗口 | 未验证。 |
| 重新开始和计分重置 | 未验证。 |
| GUI 文件选择后调用 LWT | 未验证；无头真实 CLI 集成测试已验证含空格/Unicode 的所选路径参数边界和输出。 |
| GUI 文件错误恢复 | 未验证；无头测试已验证非零退出、timeout 与无效报告的可读错误映射。 |
| Enter 键提交及缩放 | 未验证。 |

无头自动验证：

- 报告解析：有效值以及缺失、重复、负数、非数字/格式异常拒绝。
- 游戏状态：正确/错误计分、不能重复提交、推进、结束和重新开始。
- 命令边界：公开 `python -m lwt` argv、路径空格/Unicode 单参数传递、当前解释器、仓库 `cwd`、UTF-8、有限 timeout 和 `shell=False`。
- 真实 CLI：默认 fixture、单条件、AND 组合过滤和含中文及空格的临时日志路径。
- 错误处理：非零退出、超时和报告格式无效均映射为可读 `AnalyzerError`；真实 GUI 对话框恢复仍待主窗口手工验收。

### 验收命令

| 命令 | 退出码与摘要 |
|---|---|
| `python --version` | 0；Python 3.13.7。 |
| `python tools/check_project_integrity.py` | 0；194 cases、287 matrix links、194 referenced cases。 |
| `python tools/run_tests.py` | 0；语言黑盒 194/194。 |
| `python -m unittest discover -s tests -q` | 0；230 项通过。 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 0；S10 原测试 25 项通过。 |
| `python -m unittest discover -s tests -p "test_log_detective.py" -v` | 0；新增 11 项通过。 |
| `python -m compileall -q lwt tests tools bench app` | 0。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0；246 有效 LWT 行。 |
| 默认 CLI `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 0，stderr 空；6 条匹配、6 条有效、1 条坏行。 |
| AND CLI `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | 0，stderr 空；1 条匹配，`WARN|1`、`cache|1`。 |
| `python tools/run_app_concurrency.py` | 0，在一次性临时 Git worktree（HEAD `5fd6f399814577b5d180905007fb7059ac73cd62`）中运行；1/2/4 进程各 5 轮、共 35 个子进程，warm-up 成功，stdout 全一致、return code 全为 0、stderr 全空；输入 SHA-256 为 `9db070518d4bfa375e62eca0000e84835432e03e4156778b6c204a7a50321214`，试验前后不变。批次时间 ms：1 进程 `[187.911, 172.352, 180.338, 168.139, 195.441]`；2 进程 `[192.580, 200.891, 183.362, 181.600, 181.868]`；4 进程 `[190.779, 206.275, 192.049, 192.046, 199.309]`。脚本生成的临时 raw 随 worktree 删除，仓库原始报告不变；这些时间不用于性能结论。 |
| `git diff --check` / `git diff --check main...HEAD` | 均退出码 0；阶段提交与待提交文档无空白错误。文档暂存后另运行 `git diff --cached --check`。 |

S10/S11 证据保留情况和未验证项也列于 [Agent 开发记录](agent-dev-log.md)。

## 未验证与 S12 交接

没有 Python 3.10 环境或远端 GitHub Actions 实测；由 S12 按既定计划核验。S15 不改语言规范、黑盒覆盖矩阵或解释器；未运行正式性能实验，也未改写 S11 性能原始数据。

## 主窗口审查结果（2026-10-07）

结论：**带非阻断遗留通过，并快进合入本地 `main`。**阶段分支 `stage/s15-log-detective-gui` 从 `f6ef8c62737c91a18b793c12658804cba7fca810` 出发，`main` 为其祖先，工作区干净，`git diff --check main...HEAD` 通过。阶段最终提交 `390d484e2f21a044fcd8c9e8121712c215e1b309` 已快进合入；没有推送远端。

主窗口独立复跑结果：

- `python -m unittest discover -s tests -q`：230 项通过。
- `python tools/run_tests.py`：194/194 黑盒用例通过。
- `python tools/check_project_integrity.py`：194 个用例配对、287 个矩阵链接、194 个引用 ID，检查通过。
- `python -m compileall -q lwt tests tools bench app`：通过。
- `python tools/count_lwt_lines.py app/log_report.lwt`：246 行有效 LWT。
- `git diff --check main...HEAD`：通过。

保留给 S16 第一项的人工 GUI 验收：可归因地操作并核验正确答案得分更新、完整报告窗口、重新开始与分数重置、GUI 文件选择后的查询、文件/CLI 错误恢复、Enter 提交和窗口缩放。S15 已证明窗口可启动并有相关无头状态/CLI 测试，但这些测试不能替代桌面操作记录。S16 需要逐项给出操作步骤和观察结果；若当时没有可用桌面，继续标记未验证，不得将其改写为通过。

S12 仍未开始并继续位于最后阶段，负责新克隆验收、Python 3.10/远端 CI、PPT、最终演示和远端同步。
