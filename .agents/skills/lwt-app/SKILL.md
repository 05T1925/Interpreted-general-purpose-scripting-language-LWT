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

当前 LWT 支持整数、字符串、布尔/null、数组、record、函数、分支循环、each、静态函数模块、基本输入输出、文本内置函数及有限 attempt/recover。break/continue 只能作用于当前函数中最近的循环。不得使用浮点、字典、类、闭包、函数值、动态模块加载、模块顶层执行、线程或未写入规范的特性。具体边界以正式规范和当前实现为准。
