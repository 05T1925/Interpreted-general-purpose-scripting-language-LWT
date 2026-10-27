# LWT：解释型通用脚本语言大作业

本仓库用于实现 LWT 语言、解释器、黑盒测试、性能对比、开发指南和 Agent 编写的应用。S1–S11、S13–S21 已通过主窗口审查并合入本地 `main`；S21 带桌面 GUI 未验证遗留通过，A/B/C 实际交互需在最终演示前的可控桌面预检。S12 是最后阶段，负责新克隆、CI/Python 兼容性、PPT、演示和交付，尚未开始。状态见 [`project.md`](project.md)、[S21 主窗口复核](docs/s21-main-review.md)、[S21 验收报告](docs/s21-gui-acceptance.md)、[S12 最终交付规划](docs/s12-final-delivery-plan.md)和[阶段路线图](阶段执行与审查路线图.md)。

## 阅读入口

1. [作业原文](大作业内容.md)：教师要求与评分项。
2. [总体方案与复检](LWT大作业总体方案与复检.md)：目标、取舍、阶段门槛。
3. [详细实施规划](详细实施规划.md)：语义草案、文件结构、任务和验收方法。
4. [阶段执行与审查路线图](阶段执行与审查路线图.md)：两个聊天窗口的接力方式与阶段门槛；当前下一步为最终收尾 S12。
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
16. [S17 GUI 复检与打磨报告](docs/s17-app-polish.md)：共同主题、响应式排版、Snake 结束态重开修复和逐项验收状态。
17. [S17 主窗口复核](docs/s17-main-review.md)：独立回归、实际桌面交互与剩余边界。
18. [S18 优化规划](docs/s18-optimization-plan.md)：LWT 驱动分析工作台与评分证据增强方向。
19. [S18 主窗口复核](docs/s18-main-review.md)：独立检查、合法 Unicode 边界复现与遗留责任。
20. [S19 优化规划](docs/s19-optimization-plan.md)：阶段目标、范围边界、验收门槛和当前遗留项。
21. [S19 语言实验室工作报告](docs/s19-language-lab.md)：报告拆行修复、语义示例、测试与桌面验收边界。
22. [S19 主窗口复核](docs/s19-main-review.md)：独立测试结果、启动失败退出码遗留及 S20 交接。
23. [S20 优化规划](docs/s20-optimization-plan.md)：预测—运行—解释教学交互、启动契约修复与 GUI 验收收口。
24. [S20 教学演示说明与实施报告](docs/s20-teaching-demo.md)：六例预测流程、CLI 实测、GUI 验收边界、命令结果和分支提交。
25. [S20 主窗口复核](docs/s20-main-review.md)：独立回归、合并结论和未完成 GUI 实测项。
26. [S21 GUI 验收规划](docs/s21-gui-acceptance-plan.md)：现有应用的桌面手测、缺陷闭环与范围边界。
27. [S21 GUI 验收报告](docs/s21-gui-acceptance.md)：本轮桌面遮挡事实、A/B/C 未验证矩阵、只读复核和保护文件结果。
28. [S21 主窗口复核](docs/s21-main-review.md)：独立复核、合入状态、未验证项及 S12 交接。
29. [S12 最终交付规划](docs/s12-final-delivery-plan.md)：评分项证据映射、新克隆/CI、GUI 预检、PPT 与答辩收尾。

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

### S15/S18 日志侦探与交互分析工作台

在支持桌面窗口和 Tkinter 的 Python 环境，从仓库根目录运行：

```powershell
python app/log_detective.py
python -m unittest discover -s tests -p "test_log_detective.py" -v
```

S18 增加“分析工作台”选项卡：可选择日志、输入 Level/Keyword/Top，查看 LWT 生成的摘要、级别与模块图表、前三条示例和此次完整原始报告；五题挑战保留。工作台显示实际 CLI argv，图表只按报告已给计数缩放。Python GUI 负责窗口、构造参数和严格校验报告；日志读取、解析、过滤、统计与排序仍由 `app/log_report.lwt` 经公开 CLI 完成。无桌面环境仍可运行 [确定性演示日志](app/fixtures/showcase.log) 的 CLI 命令和无头测试。操作说明与约三分钟演示顺序见[应用说明](app/README.md)和[S18 展示说明](docs/s18-app-showcase.md)。

S15–S18 已通过主窗口审查并合入本地 `main`。S17 主窗口实际操作了两款 GUI 的主路径；S18 的新增操作和剩余边界按“实际点击/无头测试/未验证”分别记录在[阶段报告](docs/s18-workbench.md)，新发现的 Unicode 边界见[主窗口复核](docs/s18-main-review.md)。

### S19–S20 LWT 语义实验室

从仓库根运行 `python -m app.language_lab`。只读 Python/Tkinter 前端展示固定白名单 LWT 示例，并把程序交给 `python -m lwt` 真实执行。S20 加入先选答案并提交、再运行、最后对照预测反馈、实际 CLI 输出和解释的流程；预测正确性与 CLI 契约核对分开显示，预期运行时错误明确标注为诊断。Tkinter/Tcl 启动失败会写入 stderr 并返回非零退出码。它不是第二个 LWT 应用，课程 Agent 应用仍为 `app/log_report.lwt`。详见 [S20 教学演示说明与实施报告](docs/s20-teaching-demo.md)；无头定向测试分别为 `python -m unittest discover -s tests -p "test_language_lab.py" -v` 和 `python -m unittest discover -s tests -p "test_language_lab_entry.py" -v`。

### S16 独立图形化贪吃蛇

S16 已在 `app/snake_game.py` 提供独立启动入口。贪吃蛇是 **Python/Tkinter 附加演示，并非第二个 LWT 应用**；不会替代 `app/log_report.lwt`，也不计入课程要求的 LWT 有效代码行数。S17 为两个 GUI 提取共享主题并修复 Snake 结束态重开；S18 没有改变 Snake 规则。桌面复核状态见[S18 工作报告](docs/s18-workbench.md)。

应用测试经公开 CLI 运行，不纳入 S8 的 194 项语言黑盒矩阵。并发工具使用固定输入分别同时启动 1、2、4 个独立操作系统进程，不代表 LWT 线程支持；原始逐试次结果位于[`reports/app-concurrency.json`](reports/app-concurrency.json)。

## S11 性能实验

S11–S21 已通过主窗口审查并合入本地 `main`；S21 的 A/B/C GUI 交互均受遮挡限制而未验证，详见[主窗口复核](docs/s21-main-review.md)。S12 是最终交付阶段，详见[最终交付规划](docs/s12-final-delivery-plan.md)，当前尚未开始。阶段和性能证据见 [`project.md`](project.md)、[阶段路线图](阶段执行与审查路线图.md)、[S13 综合审计](docs/comprehensive-review.md)、[S14 改进报告](docs/s14-improvements.md)和[S21 GUI 验收报告](docs/s21-gui-acceptance.md)。

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

当前实现标量、变量/块、`emit`、`input()`、`when/otherwise`、`while`、顶层函数/递归/return、可变数组/索引赋值/`push`、record 构造/字段读写和身份相等、`each` 浅快照及循环安全显示，并支持 `args()`、`read_text()`、`len()`、`split()`、`trim()`、`to_int()`、`str()`、`fail()`。空程序返回 0；词法/语法错误返回 2；运行时错误返回 3；CLI/源文件错误返回 4。S8 建立逐条覆盖矩阵、194 项黑盒测试和四格 CI 工作流；S10 日志分析器有 246 行有效 LWT 和 25 项公开 CLI 测试，并有固定输入独立进程读取记录；S11 性能数据和失败计数修复已审查通过。S15–S21 应用/展示阶段已审查并合入本地 `main`。S20 完成启动错误码修复和预测—运行—解释交互；S21 阶段报告与主窗口复核已记录桌面交互限制。S12 最终新克隆、Python/CI、PPT、演示和交付尚未开始，清单见 [S12 最终交付规划](docs/s12-final-delivery-plan.md)。
