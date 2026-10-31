# S31 规划：VS Code 扩展与统一开发工作流

状态：S31 实施完成并经主窗口复核通过（带明确未验证项），尚未合入 main。该计划记录 S31 原始范围；S31 不实现 DAP。S32 原生 DAP 作为编辑器集成大阶段的后续提案，见 [S32 规划](s32-native-dap-plan.md)。

## 目标

通过一个可本地打包的 VS Code 扩展，关联 `.lwt` 文件、提供与 lexer 一致的基础着色，并复用 S29 Language Server、S27 `--check`、普通 CLI 和 S30 源码级 CLI 调试器。统一路径和参数处理，保留 CLI 的标准输出、错误码与 stdin 行为。

## 资料依据

- 项目需求：[`大作业内容.md`](../大作业内容.md)及当前正式规范 [`language-spec.md`](language-spec.md)。
- S29：[`language-server.md`](language-server.md) 的 stdio transport、诊断、document symbols、hover、definition 能力表。
- S27/S30：[`static-checker.md`](static-checker.md)、[`debugger.md`](debugger.md) 的参数和 I/O 契约。
- VS Code 官方 Language Server 扩展指引与 Extension Test Host 文档，见[扩展使用说明](vscode-extension.md#依据)。
- `vscode-languageclient` 11.0.0 包元数据声明 VS Code `^1.91.0`；manifest 版本固定，开发依赖锁在 `editors/vscode-lwt/package-lock.json`。

## 设计决策

1. 使用 VS Code `vscode-languageclient` Node client，以 direct executable/args/options 配置启动 `python -m lwt.lsp_server`。LSP stdout/stderr 不被应用任务复用；诊断日志走独立 `LWT` Output Channel。server cwd 固定为单一 workspace 根。
2. 只支持一个 workspace folder。扩展不能从任意文件推断可导入的 `lwt` 包根；要求打开项目根并明确报出零/多根限制。
3. Run/Check/Debug 均由 `ProcessExecution` 创建进程型任务；不传 shell 命令字符串。Run 和 Debug 将参数数组追加到 `--` 之后；Check 单独调用 `-m lwt --check SOURCE`，不继承程序参数。
4. Run/Debug 任务显示并聚焦终端以支持程序 `input()` 和 S30 调试命令。Debug 的程序 stdin 只通过单独 `--program-stdin FILE` 配置；未指定沿用 S30 的 EOF 规则。
5. `lwt.pythonPath` 是可执行文件字段，不解析可执行路径中的额外参数。`workingDirectory` 空值用 workspace 根，配置的相对路径从 workspace 根解析。`programArgs` 是字符串数组。
6. TextMate grammar 仅做词法着色，不替代 lexer 诊断；保留精确 LWT 标识符/关键字/字面量/注释规则。Snippets 只生成现有语法。没有注册 completion、formatting、rename、semantic tokens 或 Debug Adapter。
7. `vscode-languageclient` 固定到官方 npm 包 11.0.0；本地实测 VS Code 为 1.144.0，扩展最低 engine 与同版 `@types/vscode` 对齐为 `^1.144.0`，并通过 vsce 的版本一致性门槛。Node 开发依赖限于扩展目录，并提交 lockfile。VSIX 本地生成后验证，不提交二进制或发布 Marketplace。
8. 通过 Extension Host 导出的 task-construction seam 检查 VS Code API 创建的 `ProcessExecution`；Host 中 Run/Check 另真实启动任务并检查退出码。CLI 行为单独用真实 Python 子进程验证。Headless terminal 的 PTY/输入不作为人工终端体验证据。

## 范围与非目标

- 扩展只是开发工具入口，LWT runtime、静态语义、Language Server、CLI 退出码、S27 JSON schema 和 S30 调试语义保持原样。
- 不实现 DAP，不声称原生断点、Variables、图形单步或 VS Code debugger UI 已连接。
- 不实现补全、格式化、重命名、包管理、语言生成能力、解释器或 Python 日志业务逻辑。
- 不添加 Python 第三方依赖，不发布 Marketplace，不提交用户路径/机器信息。
- S12 新克隆、Python/Actions 矩阵、PPT、人工桌面演示和最终交付不属于 S31。

## 验收矩阵

| 目标 | 证据 | 限制 |
|---|---|---|
| manifest、语言 ID、命令、设置、grammar、snippets、lockfile 一致 | Node 单测读取实际 manifest、lexer 关键字表和配置文件 | 静态/包级证据，不是用户视觉验收。 |
| Python argv、`--`、cwd、含空格/Unicode 路径 | workflow 单测和真实 CLI 子进程；Extension Host 检查 `ProcessExecution` | host 任务终端测试不代表人工键盘/终端交互。 |
| LSP 真实编辑器 client 连接 | 隔离 VS Code Extension Host 中启动真实 `python -m lwt.lsp_server`，验证诊断新增/修复清除、hover、definition、设置 Python 路径、Unicode/空格 workspace | 不代表所有 VS Code 版本/平台；没有人工编辑器目测时单列。 |
| Run/Check/Debug 使用正确公开入口 | Extension Host Run/Check 任务 + task seam；真实 CLI Run stdin、Check 无执行输出、S30 debugger 固定脚本 | Extension Host 无头 Debug 终端 EOF 情况单列。 |
| 本地可安装包 | `npm ci`、TypeScript 构建、`vsce package`、检查 VSIX 内容 | 不代表 Marketplace 发布或跨平台安装验收。 |

阶段报告记录实际命令、OS/Node/npm/VS Code/Python 版本、证据层次、保护路径差异、未验证项和 S12 交接。
