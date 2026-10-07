# LWT：解释型通用脚本语言大作业

本仓库用于实现 LWT 语言、解释器、黑盒测试、性能对比、开发指南和 Agent 编写的应用。**S1–S7 已审查并合入本地 `main`；S7 提交为 `4f11b80`。**本地 `main` 比 `origin/main` 领先 9 个提交；`origin/main` 仍为 S4，这些本地进度尚未推送。

## 阅读入口

1. [作业原文](大作业内容.md)：教师要求与评分项。
2. [总体方案与复检](LWT大作业总体方案与复检.md)：目标、取舍、阶段门槛。
3. [详细实施规划](详细实施规划.md)：语义草案、文件结构、任务和验收方法。
4. [阶段执行与审查路线图](阶段执行与审查路线图.md)：两个聊天窗口的接力方式、S0–S12 阶段门槛和报告格式。
5. [正式语言规范](docs/language-spec.md)：S1 审查通过的 LWT 语法和语义，S2 已将两项审查澄清并入正文。
6. [project.md](project.md)：当前状态、已定决策和下一步，供编程 Agent 复用。

运行 lexer、parser、runtime 与 CLI 阶段性测试。2026-10-07 在 Python 3.13.7 上，主窗口独立复跑 S7 合入后的全套 157 项 unittest，全部通过。这些不是 S8 要建立的最终黑盒测试集：

```powershell
python -m unittest discover -s tests -v
```

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

当前实现标量、变量/块、`emit`、`input()`、`when/otherwise`、`while`、顶层函数/递归/return、可变数组/索引赋值/`push`、record 构造/字段读写和身份相等、`each` 浅快照及循环安全显示，并支持 `args()`、`read_text()`、`len()`、`split()`、`trim()`、`to_int()`、`str()`、`fail()`。空程序返回 0；词法/语法错误返回 2；运行时错误返回 3；CLI/源文件错误返回 4。当前规范允许的程序不再使用阶段临时代码 `Incomplete`/1。S7 已审查通过；完整黑盒测试集、覆盖矩阵和 CI 是 S8 的待办。
