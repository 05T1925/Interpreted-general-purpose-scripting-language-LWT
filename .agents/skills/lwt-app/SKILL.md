---
name: lwt-app
description: Use when creating, editing, debugging, or validating an LWT `.lwt` program or small application in this repository. Do not use for language-design questions, interpreter implementation changes, or ordinary Python programs.
---

# LWT 应用开发

当用户要求在本仓库新建、修改、调试或验证 LWT `.lwt` 程序/小型应用时，按此流程工作。单纯讨论 LWT 概念或语言设计、修改 Python 解释器、编写普通 Python 程序时不使用此应用开发流程。

## 工作步骤

1. 阅读[开发指南](../../../docs/developer-guide.md)。涉及语法、值、作用域、内置函数、错误或边界语义时，查阅[正式语言规范](../../../docs/language-spec.md)。需要确认现有黑盒覆盖时，再读[测试覆盖矩阵](../../../docs/test-matrix.md)。不要把计划文档当作比正式规范更高的语义依据。
2. 先确认用户要求的输入、输出、文件、CLI 参数、stdin 和错误行为。只有缺失信息会改变实现结果时才询问；其他细节按规范选择简单一致的方案。
3. 只用仓库中已实现且有规范/测试依据的 LWT 能力设计程序。`break;`/`continue;` 只可处于当前函数自身的 while/each 循环体，目标是最近循环；each 的 continue 使用进入循环时的浅快照。不要把 Python 语法、标准库 API 或未实现特性写入 `.lwt`。
4. 在用户指定的路径创建或修改 `.lwt` 文件；有需要时添加最小 fixture。不要无理由修改解释器、正式规范或 S8 测试。不要通过 Python `eval`/`exec` 执行 LWT。
5. 使用公开 CLI 运行程序：`python -m lwt path/to/program.lwt`。如程序需要输入，提供 stdin；如需要程序参数，使用 `python -m lwt path/to/program.lwt -- arg1 arg2`。从实际工作目录核对相对文件路径。
6. 检查 stdout、stderr、退出码和报错行列位置；将实际结果与任务预期逐项比较。修正后重新运行受影响的命令；不要只依赖静态阅读，也不要声称未运行的验证通过。
7. 最终报告列出改动文件、实际执行的命令及结果、尚未验证的环境或边界。若怀疑解释器缺陷，保留最小复现及规范预期；除非用户当前明确派发解释器修复任务，不要在应用任务里改变解释器语义。

## 边界

- LWT 0.1 不支持浮点、字典、类、闭包、函数值、模块、异常捕获、带标签循环跳转、语言级线程或 REPL。无标签 `break;`/`continue;` 已支持，受最近循环和函数边界规则限制。只有规范和当前实现确认的功能才可使用。
- `read_text(path)` 的相对路径以进程工作目录为基准；`args()` 只返回 CLI `--` 后参数。
- 不要无条件安装依赖；仓库解释器和测试使用 Python 标准库。
- 不要绕过 `python -m lwt`，不要把 LWT 源码输入宿主 Python 执行器。

## References

- [人类/Agent 开发指南](../../../docs/developer-guide.md)
- [LWT 0.1 语言规范](../../../docs/language-spec.md)
- [黑盒覆盖矩阵](../../../docs/test-matrix.md)
