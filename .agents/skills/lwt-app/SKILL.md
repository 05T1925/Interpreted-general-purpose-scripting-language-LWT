---
name: lwt-app
description: Use only to create, edit, debug, or validate LWT source programs (.lwt) or the course LWT application in this repository. Do not use for Python/Tkinter apps, interpreter/runtime changes, language-server or debugger implementation, VS Code extension work, or general language-design discussion.
---

# LWT 应用开发

该 Skill 只管编写与验证 LWT 源程序，不定义语言语义，也不代替解释器或编辑器工具开发流程。

## 工作流程

1. 阅读[开发指南](../../../docs/developer-guide.md)。遇到语法、求值、作用域、模块、错误或边界问题时查[正式规范](../../../docs/language-spec.md)；需要核对覆盖时再看[测试矩阵](../../../docs/test-matrix.md)。
2. 先从任务中提取输入、输出、CLI 参数、stdin、文件路径和错误行为。仅在缺失信息会改变结果时提问；其余按规范作简单一致的选择。
3. 只使用规范和当前实现已支持的 LWT 能力。不要把 Python 语法/API 写入 .lwt，也不要用 Python eval/exec 执行 LWT。
4. 多文件程序使用规范定义的静态函数模块；import 路径相对声明文件，库模块只含顶部 import 和函数声明，避免循环依赖。详见[模块示例](../../../examples/modules/main.lwt)。
5. 先运行静态检查，再运行公开 CLI；示例：
   - python -m lwt --check path/to/program.lwt
   - python -m lwt path/to/program.lwt -- arg1 arg2
   - 需要程序输入时，为 CLI 提供对应 stdin；read_text 的相对路径以运行时 cwd 为准。
6. 核对 stdout、stderr、退出码和诊断位置。修正后重跑受影响命令；静态检查通过不代表程序运行成功。
7. 只记录真实运行的命令与结果。若怀疑解释器缺陷，提供最小复现和规范预期；不要在普通应用任务中顺手修改解释器。
8. profile、LSP、CLI debugger 和 VS Code 扩展是独立开发工具。只有任务明确涉及这些工具时才查对应说明；它们不扩大本 Skill 的触发范围。

## 适用与不适用例子

- 适用：“用 LWT 写一个读取参数、统计文本行数并输出摘要的程序。”
- 不适用：“修改 Python Tkinter 界面”“实现新的 LWT 语法”“编写 LWT DAP/debug adapter”“给 VS Code 扩展加命令”或“解释闭包设计”。

## 语言边界

当前 LWT 0.2 支持整数、字符串、布尔/null、数组、record、**dict 映射**、函数、分支循环、each、静态函数模块、基本输入输出、文本内置函数，`attempt/recover` 与 **`throw`/`finally`** 结构化错误传播，以及**规范第 11 节的协作式确定性并发子集**（`spawn`/`join`/`yield()`/通道）。break/continue 只能作用于当前函数中最近的循环。并发仅限该子集：不支持抢占、真实并行 CPU 执行、任务取消/超时、有界通道/背压、`sleep`、条件变量、读写锁、原子变量、多进程共享状态、跨进程通道或网络。也不得使用浮点、类、闭包、函数值、动态模块加载、模块顶层执行或未写入规范的特性。具体边界以正式规范和当前实现为准。

S42 新增能力的使用要点（写 .lwt 时）：

- **dict 映射**：`dict{"k": 1, 2: "two"}` 构造；键必须是整数或字符串（布尔不是合法键），显示与 `keys`/`values`/`items` 都按插入顺序，`d[k]` 读写（缺键读取报错，`d[k] = v` 新键追加），相等性是身份比较。内置：`keys`/`values`/`items`/`has`/`get`/`put`/`delete`，`len(d)` 返回键数。`each` 不直接遍历 dict，用 `each (k in keys(d)) {...}`。详见规范 §4.4、§6 与[示例](../../../examples/dicts.lwt)。注意新增内置名 `keys/values/items/has/get/put/delete/error` 与用户函数共用函数名空间，`fn values()` 等定义会报冲突，应另取名。
- **throw/finally**：`throw "message";` 抛出 `User` 类别错误，`throw error("Category", "message");` 抛出自定义类别；`attempt { ... } recover (problem) { ... } finally { ... }` 的 finally 块无论正常/错误/return/break/continue 都会执行一次，且 finally 自身的错误或控制流会覆盖此前挂起结果；`problem` 只在 recover 块可见。多个 handler、类型过滤、事务回滚**不支持**，可用单个 recover 块内 `when (problem.category == "...")` 分派。详见规范 §10.6 与[示例](../../../examples/throw_finally.lwt)。
- **REPL**：`python -m lwt --repl` 是交互式开发工具（stdout 只含 `emit`，提示符走 stderr），不是 .lwt 程序语法；编写应用仍用普通 CLI。

S43 并发子集的使用要点（写 .lwt 时，详见[并发契约卡](../../../docs/concurrency.md)与规范 §11）：

- **最小示例**：`fn fetch(p){ return read_text(p); } let t = spawn fetch("a.log"); emit str(len(join(t)));` — `spawn` 是唯一新保留字（前缀表达式、必须带括号），`join/yield/channel/send/receive/close` 是预置函数名。
- **五个调度点**：`yield()`、阻塞 `receive`、阻塞 `join`、任务结束、`read_text` 的 I/O 点；两点之间原子完成。并发只在等待型 I/O 上重叠，不加速 CPU 计算（单令牌 + GIL）。`--schedule=random:SEED` 换交错，`--schedule-log`/`--schedule-replay` 记录/重放轨迹（绑定源摘要、实参、策略、决策、输出摘要；篡改以 CliError/4 拒绝）。
- **反模式 1**：把 `yield` 当锁 — 它只是让步点，两个任务「读—yield—写」同一全局变量会丢更新。共享计数请用单任务归并或通道。
- **反模式 2**：依赖任务完成顺序输出 — 调度顺序由策略决定，不是墙钟；用按输入顺序的专属通道或按编号 `join` 收集（见 `app/concurrent_log_report.lwt`）。
- **反模式 3**：为 `--profile`/调试器写并发路径 — 这些工具在执行前以 4 拒绝 `spawn`，不要写「尽力而为」的并发断点或档案逻辑。`--check` 只诊断 `spawn` 目标存在性与实参数量（`E-SPAWN-001/002`），不检查并发正确性。
