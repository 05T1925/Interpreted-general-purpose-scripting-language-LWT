# LWT：解释型通用脚本语言大作业

本仓库用于实现 LWT 语言、解释器、黑盒测试、性能对比、开发指南和 Agent 编写的应用。S1–S11、S13–S16 已通过主窗口审查并合入本地 `main`；S17 应用复检与界面打磨待开始。S15 GUI 全流程与 Snake 桌面交互受当前桌面接口限制仍未验证，S17 将先尝试补测并继续完善两个 GUI。S12 新克隆验收、Python 3.10/远端 CI、PPT、演示和最终交付仍未开始，并按用户要求保持最后阶段。状态见 [`project.md`](project.md)、[S14 执行报告](docs/s14-improvements.md)、[S15 GUI 执行报告](docs/s15-app-gui.md)、[S16 应用复检与贪吃蛇报告](docs/s16-app-review-snake.md)和[阶段路线图](阶段执行与审查路线图.md)。

## 阅读入口

1. [作业原文](大作业内容.md)：教师要求与评分项。
2. [总体方案与复检](LWT大作业总体方案与复检.md)：目标、取舍、阶段门槛。
3. [详细实施规划](详细实施规划.md)：语义草案、文件结构、任务和验收方法。
4. [阶段执行与审查路线图](阶段执行与审查路线图.md)：两个聊天窗口的接力方式、S0–S17 阶段门槛和报告格式；当前顺序为 S16 审查通过 → S17 → 最终收尾 S12。
5. [正式语言规范](docs/language-spec.md)：S1 审查通过的 LWT 语法和语义，S2 已将两项审查澄清并入正文。
6. [project.md](project.md)：当前状态、已定决策和下一步，供编程 Agent 复用。
7. [人类/Agent 开发指南](docs/developer-guide.md)：从运行 CLI 到语言语义和示例的操作说明。
8. [Agent Skill](.agents/skills/lwt-app/SKILL.md)：仓库内 LWT 应用编写/调试工作流；是否被其他 Agent 平台自动发现取决于该平台。
9. [S9 独立盲测记录](docs/agent-blind-test.md)：三道新上下文盲测、可复现命令、结果和路由评估限制。
10. [S10 日志分析器说明](app/README.md)：输入格式、CLI 契约、报告语义和实现限制。
11. [并发读取报告](docs/app-concurrency.md)：1/2/4 个独立 LWT 进程的一致性和计时记录。
12. [S13 全项目复检报告](docs/comprehensive-review.md)：课程要求追踪、规范/实现/测试映射、应用与性能原始证据审计、环境限制和 S12 交接。
13. [S14 改进报告](docs/s14-improvements.md)：完整性门禁、权限错误回归、平台实测和未验证事项。
14. [S15 GUI 与小游戏报告](docs/s15-app-gui.md)：GUI/LWT 架构边界、玩法、自动及桌面验证状态。
15. [S16 应用复检与贪吃蛇报告](docs/s16-app-review-snake.md)：S15 GUI 验收限制、应用审计、贪吃蛇规则与验证证据。
16. S17 将复查并打磨日志侦探与贪吃蛇两个独立 Tkinter 应用；S12 仍是最终交付阶段。

运行仓库结构完整性检查：

```powershell
python tools/check_project_integrity.py
```

该命令复用黑盒 runner 的配对/metadata/ID 校验，并检查覆盖矩阵中的测试文件链接。它证明库存与链接结构完整，不替代黑盒执行和人工语义覆盖复核。

运行完整 LWT CLI 黑盒测试集：

```powershell
python tools/run_tests.py
```

语义用例以 `.lwt` 源程序经 `python -m lwt` 执行，同名 `.json` 精确记录退出码、stdout、stderr、参数、stdin 和超时；CLI argv 专项用例使用显式 override。格式、发现规则、逐条规范覆盖及实测状态见[覆盖矩阵](docs/test-matrix.md)。当前共有 194 项黑盒用例，其中 189 项执行配对 LWT 程序、5 项专测 CLI 参数契约。S14 本轮在 Windows Python 3.13.7 和 WSL Ubuntu 24.04 / Linux Python 3.12.3 各测得 194/194，全量 unittest 各为 219 项通过。完整性检查当前报告 194 个配对用例、287 个矩阵链接和 194 个被引用 ID。GitHub Actions 尚未远端运行，Python 3.10 格仍未验证。

运行 lexer、parser、runtime、CLI 和黑盒 runner 的开发辅助 unittest：

```powershell
python -m unittest discover -s tests -v
```

可选地编译检查 Python 源码：

```powershell
python -m compileall -q lwt tests tools
```

项目目标支持 Python 3.10+ 标准库；S14 本轮实际运行 Windows Python 3.13.7 和 Ubuntu 24.04 / Linux Python 3.12.3。`.github/workflows/tests.yml` 在 push、pull request 和手动触发时运行 Python 3.10/3.13 × Ubuntu/Windows 矩阵，并先运行新增的完整性检查，再执行黑盒、unittest 和 compileall。Python 3.10 与远端 workflow 尚未实际运行，不能据此声称四格 CI 已通过。

运行示例：

```powershell
python -m lwt examples/basic_io.lwt
```

输入一行后，基础示例会回显该行。控制流、函数和集合示例可分别运行：

```powershell
python -m lwt examples/control_flow.lwt
python -m lwt examples/functions.lwt
python -m lwt examples/collections.lwt
python -m lwt examples/text_tools.lwt -- examples/fixtures/text_tools.txt preview
```

`control_flow.lwt` 的实际输出是 `0\n-1\n2\n-3\n`；`functions.lwt` 的实际输出是 `120\n`。`collections.lwt` 在本阶段实测输出如下，展示 `each` 进入时保存浅快照：

```text
draft
review
["draft", "review"]
[Task{name: "draft", done: true}, Task{name: "replacement", done: false}, Task{name: "late", done: false}]
```

`text_tools.lwt` 从仓库根目录运行；`read_text` 的相对路径也以进程工作目录为基准。`args()` 收到数据文件路径和 `preview` 两个参数，stdout 为：

```text
2
[12, "apple", 5]
[7, "pear", 4]
```

## S10 日志分析器

从仓库根目录运行默认固定样例或过滤示例：

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log
python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2
```

完整参数和坏行规则见[应用说明](app/README.md)，实际开发过程见[Agent 开发记录](docs/agent-dev-log.md)。运行应用 CLI 集成测试和有效 LWT 行数统计：

```powershell
python -m unittest discover -s tests -p "test_app.py" -v
python tools/count_lwt_lines.py app/log_report.lwt
python tools/run_app_concurrency.py
```

### S15 日志侦探图形化小游戏

在支持桌面窗口和 Tkinter 的 Python 环境，从仓库根目录运行：

```powershell
python app/log_detective.py
python -m unittest discover -s tests -p "test_log_detective.py" -v
```

小游戏每题通过公开 LWT CLI 获取真实报告；Python GUI 负责题面、窗口、进度和得分。无桌面环境仍可运行无头逻辑与 CLI 集成测试。入口条件、玩法和 S15 验收限制见[应用说明](app/README.md)及[S15 执行报告](docs/s15-app-gui.md)。

S15 已通过自动化审查并合入本地 `main`。S16 检查时当前计算机使用接口没有提供可操作窗口清单或原生输入能力，因此正确计分、报告窗、重开、图形文件选择/错误恢复、Enter 和缩放等桌面操作仍明确标为未验证；S15 自动化测试已实际复跑。

### S16 独立图形化贪吃蛇

S16 已在 `app/snake_game.py` 提供独立启动入口。贪吃蛇是 Python/Tkinter 附加游戏，与日志侦探和 LWT 分析器分开；不会替代 `app/log_report.lwt`，也不计入课程要求的 LWT 有效代码行数。无头状态逻辑 11 项测试覆盖移动、计分、碰撞、暂停/失焦、重开和满盘胜利。S16 的自动化审查已通过；Snake 桌面人工验收仍未完成，S17 将优先尝试补测。启动说明和逐项证据见[应用说明](app/README.md)与[S16 报告](docs/s16-app-review-snake.md)。

应用测试经公开 CLI 运行，不纳入 S8 的 194 项语言黑盒矩阵。并发工具使用固定输入分别同时启动 1、2、4 个独立操作系统进程，不代表 LWT 线程支持；原始逐试次结果位于[`reports/app-concurrency.json`](reports/app-concurrency.json)。

## S11 性能实验

S11 已通过主窗口审查并快进合入本地 `main`，审查修正了失败进程与无效配对重复计数。S13 全项目审计、S14 质量保障升级、S15 日志侦探 GUI 和 S16 贪吃蛇均已通过审查并合入本地 `main`。S17 接续处理两个 GUI 的桌面验收遗留与视觉/交互打磨；S12 最后收尾仍未开始。阶段与性能证据见 [`project.md`](project.md)、[阶段路线图](阶段执行与审查路线图.md)、[S13 综合审计](docs/comprehensive-review.md)、[S14 改进报告](docs/s14-improvements.md)、[S15 GUI 报告](docs/s15-app-gui.md)和[S16 应用报告](docs/s16-app-review-snake.md)。

从仓库根目录运行正式 LWT/Python 成对实验：

```powershell
python tools/benchmark.py
```

默认对 `arithmetic` 和 `array_scan` 两组负载各用 N=100、1000、5000，每个语言/负载/规模进行 10 次独立新进程计时，共 120 个正式子进程，另有 12 个经输出验证但不计时的 warm-up。固定 seed 交错配对运行；计时是包含解释器启动和 LWT 词法/语法分析的端到端墙钟时间，不代表纯运行时速度。原始逐次记录和校验值追加到 [`bench/results.json`](bench/results.json)，可复算的报告在 [`reports/performance.md`](reports/performance.md)。

先做不进入正式统计的校准：

```powershell
python tools/benchmark.py --calibration
```

校准数据仍保存在 JSON 中并标注 `calibration`；不会纳入正式表格。更多协议、环境、源文件哈希和限制见[性能报告](reports/performance.md)。

当前实现标量、变量/块、`emit`、`input()`、`when/otherwise`、`while`、顶层函数/递归/return、可变数组/索引赋值/`push`、record 构造/字段读写和身份相等、`each` 浅快照及循环安全显示，并支持 `args()`、`read_text()`、`len()`、`split()`、`trim()`、`to_int()`、`str()`、`fail()`。空程序返回 0；词法/语法错误返回 2；运行时错误返回 3；CLI/源文件错误返回 4。当前规范允许的程序不再使用阶段临时代码 `Incomplete`/1。S8 建立逐条覆盖矩阵、194 项黑盒测试和四格 CI 工作流；S9 开发指南、仓库 Skill 和三项独立盲测已审查通过，Skill 自动路由仍不可观测；S10 日志分析器有 246 行有效 LWT 和 25 项公开 CLI 测试，并有固定输入独立进程读取记录；S11 性能数据和失败计数修复已审查通过。S13 综合审计和 S14 完整性门禁/权限错误回归均已通过主窗口审查并合入本地 `main`。S15 日志侦探 GUI 与 S16 贪吃蛇均已审查通过并合入本地；两个 GUI 的桌面人工验收仍受限，S17 将先尝试实测并继续打磨视觉与交互。S12 仍未开始，负责新克隆验收、Python 3.10/远端 CI、PPT、演示和最终交付。
