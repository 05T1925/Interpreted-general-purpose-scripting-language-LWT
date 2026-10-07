# LWT：解释型通用脚本语言大作业

本仓库用于实现 LWT 语言、解释器、黑盒测试、性能对比、开发指南和 Agent 编写的应用。**S1–S6 已审查并合入本地 `main`；S5/S6 尚未推送到 `origin`。**`origin/main` 仍为 S4；本地 `main` 已含 S5、S6 及审查文档提交。

## 阅读入口

1. [作业原文](大作业内容.md)：教师要求与评分项。
2. [总体方案与复检](LWT大作业总体方案与复检.md)：目标、取舍、阶段门槛。
3. [详细实施规划](详细实施规划.md)：语义草案、文件结构、任务和验收方法。
4. [阶段执行与审查路线图](阶段执行与审查路线图.md)：两个聊天窗口的接力方式、S0–S12 阶段门槛和报告格式。
5. [正式语言规范](docs/language-spec.md)：S1 审查通过的 LWT 语法和语义，S2 已将两项审查澄清并入正文。
6. [project.md](project.md)：当前状态、已定决策和下一步，供编程 Agent 复用。

运行 lexer、parser、runtime 与 CLI 阶段性测试。2026-10-07 在 Python 3.13.7 上，S6 阶段分支和主窗口复跑的全套 137 项 unittest 均通过。这些不是最终黑盒测试集：

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
```

`control_flow.lwt` 的实际输出是 `0\n-1\n2\n-3\n`；`functions.lwt` 的实际输出是 `120\n`。`collections.lwt` 在本阶段实测输出如下，展示 `each` 进入时保存浅快照：

```text
draft
review
["draft", "review"]
[Task{name: "draft", done: true}, Task{name: "replacement", done: false}, Task{name: "late", done: false}]
```

当前实现标量、变量/块、`emit`、`input()`、`when/otherwise`、`while`、顶层函数/递归/return、可变数组/索引赋值/`push`、record 构造/字段读写和身份相等、`each` 浅快照及循环安全显示。`args()`、`read_text()`、`len()`、`split()`、`trim()`、`to_int()`、`str()`、`fail()` 仍在执行前以阶段性 `Incomplete`/1 拒绝，且不产生部分 stdout；它们属于 S7。空程序返回 0；词法/语法错误返回 2；运行时错误返回 3；CLI/文件错误返回 4。临时代码 1 不是最终语言行为。S7 尚未开始。
