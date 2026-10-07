# LWT：解释型通用脚本语言大作业

本仓库用于实现 LWT 语言、解释器、黑盒测试、性能对比、开发指南和 Agent 编写的应用。**S1–S10 已通过主窗口审查并合入本地 `main`；S11 性能实验和 S12 答辩交付尚未开始。**本地 `main` 比 `origin/main` 领先 24 个提交；`origin/main` 仍为 S4，本地阶段进度尚未推送。

## 阅读入口

1. [作业原文](大作业内容.md)：教师要求与评分项。
2. [总体方案与复检](LWT大作业总体方案与复检.md)：目标、取舍、阶段门槛。
3. [详细实施规划](详细实施规划.md)：语义草案、文件结构、任务和验收方法。
4. [阶段执行与审查路线图](阶段执行与审查路线图.md)：两个聊天窗口的接力方式、S0–S12 阶段门槛和报告格式。
5. [正式语言规范](docs/language-spec.md)：S1 审查通过的 LWT 语法和语义，S2 已将两项审查澄清并入正文。
6. [project.md](project.md)：当前状态、已定决策和下一步，供编程 Agent 复用。
7. [人类/Agent 开发指南](docs/developer-guide.md)：从运行 CLI 到语言语义和示例的操作说明。
8. [Agent Skill](.agents/skills/lwt-app/SKILL.md)：仓库内 LWT 应用编写/调试工作流；是否被其他 Agent 平台自动发现取决于该平台。
9. [S9 独立盲测记录](docs/agent-blind-test.md)：三道新上下文盲测、可复现命令、结果和路由评估限制。
10. [S10 日志分析器说明](app/README.md)：输入格式、CLI 契约、报告语义和实现限制。
11. [并发读取报告](docs/app-concurrency.md)：1/2/4 个独立 LWT 进程的一致性和计时记录。

运行完整 LWT CLI 黑盒测试集：

```powershell
python tools/run_tests.py
```

语义用例以 `.lwt` 源程序经 `python -m lwt` 执行，同名 `.json` 精确记录退出码、stdout、stderr、参数、stdin 和超时；CLI argv 专项用例使用显式 override。格式、发现规则、逐条规范覆盖及实测状态见[覆盖矩阵](docs/test-matrix.md)。当前共有 194 项黑盒用例，其中 189 项执行配对 LWT 程序、5 项专测 CLI 参数契约。执行窗口在 Windows Python 3.11.16、3.13.7 各测得 194/194；主窗口补充“空测试集必须失败”的检查后，在 Python 3.13.7 重跑 194/194，174 项 unittest 通过，且从临时目录启动黑盒运行器也通过。GitHub Actions 尚未远端触发，Python 3.10/Linux 结果未验证。

运行 lexer、parser、runtime、CLI 和黑盒 runner 的开发辅助 unittest：

```powershell
python -m unittest discover -s tests -v
```

可选地编译检查 Python 源码：

```powershell
python -m compileall -q lwt tests tools
```

项目目标支持 Python 3.10+ 标准库；当前本地实测环境为 Windows Python 3.11.16 和 3.13.7。`.github/workflows/tests.yml` 在 push、pull request 和手动触发时运行 Python 3.10/3.13 × Ubuntu/Windows 矩阵，并执行同一黑盒命令以及 unittest/compileall。Python 3.10、Linux 和远端 workflow 尚未实际运行，不能据此声称 CI 已通过。

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

应用测试经公开 CLI 运行，不纳入 S8 的 194 项语言黑盒矩阵。并发工具使用固定输入分别同时启动 1、2、4 个独立操作系统进程，不代表 LWT 线程支持；原始逐试次结果位于[`reports/app-concurrency.json`](reports/app-concurrency.json)。

当前实现标量、变量/块、`emit`、`input()`、`when/otherwise`、`while`、顶层函数/递归/return、可变数组/索引赋值/`push`、record 构造/字段读写和身份相等、`each` 浅快照及循环安全显示，并支持 `args()`、`read_text()`、`len()`、`split()`、`trim()`、`to_int()`、`str()`、`fail()`。空程序返回 0；词法/语法错误返回 2；运行时错误返回 3；CLI/源文件错误返回 4。当前规范允许的程序不再使用阶段临时代码 `Incomplete`/1。S8 已审查通过并合入本地 `main`，包含逐条覆盖矩阵、194 项黑盒测试和四格 CI 工作流。S9 开发指南、仓库 Skill 和三项独立盲测已审查通过并合入本地 `main`；Skill 自动路由仍不可观测。S10 日志分析器有 246 行有效 LWT，25 项公开 CLI 测试通过；1/2/4 个独立进程各 5 轮读取结果一致，阶段经主窗口审查并快进合入本地 `main`。S11 尚未开始。
