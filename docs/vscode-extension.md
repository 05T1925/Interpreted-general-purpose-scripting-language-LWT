# LWT VS Code 扩展使用说明

扩展位于 [`editors/vscode-lwt/`](../editors/vscode-lwt/)，语言 ID 为 `lwt`，仅关联 `.lwt` 文件。它是 Python/TypeScript 开发工具与调用入口；LWT 解释器和课程应用主体仍分别是 `lwt/` 与 [`app/log_report.lwt`](../app/log_report.lwt)。扩展不增加作业语言功能，不是第二个 LWT 应用，也不计入课程应用评分。

## 能力范围

扩展复用仓库已有入口，不实现另一套语言语义：

| VS Code 能力 | 实际入口 | 行为 |
|---|---|---|
| 静态编辑服务 | `python -m lwt.lsp_server`，stdio | 诊断、文档符号、hover、definition；不执行 LWT。 |
| `LWT: Run Current File` | `python -m lwt SOURCE [-- ARGS...]` | 执行当前已保存文件；进程型任务显示集成终端，允许程序调用 `input()`。 |
| `LWT: Check Current File` | `python -m lwt --check SOURCE` | 静态检查，不执行程序，不向程序传递 `programArgs`。 |
| `LWT: Debug Current File in Terminal` | `python -m lwt.debugger [--program-stdin FILE] SOURCE [-- ARGS...]` | 在集成终端运行 S30 源码级 CLI 调试器；调试命令从终端输入。 |

LSP 只注册其现有 diagnostics、document symbols、hover 和 definition 能力。基础 TextMate 语法着色使用与 lexer 一致的关键字、双引号字符串、十进制整数字面量和 `#` 行注释。Language Configuration 提供括号匹配、自动闭合和简单块缩进。少量 snippets 只生成规范中已有语法。

本扩展不提供补全、格式化、重命名、语义 tokens、类型推断、DAP、VS Code gutter 断点、Variables 面板或图形单步界面。Debug 命令是 S30 CLI 调试器的终端任务，不是 VS Code 原生 debugger。

## 本地构建与安装

要求 Node.js 22+、npm 和 VS Code。仓库 Python runtime 本身仍只用 Python 标准库；Node 依赖仅用于此扩展开发与打包。

```powershell
Set-Location editors/vscode-lwt
npm ci
npm test
npm run package
code --install-extension .\lwt-language-tools-0.1.0.vsix
```

`npm test` 运行 manifest/grammar/launch 单元测试和隔离 VS Code Extension Host 测试。若 VS Code 安装在非标准位置，先设置：

```powershell
$env:VSCODE_EXECUTABLE_PATH = 'C:\Path With Spaces\Microsoft VS Code\Code.exe'
npm test
```

Extension Host 使用临时 workspace、user-data 和 extension 目录，不加载个人配置。`npm run package` 只生成本地 `.vsix`，不发布或上传 Marketplace；VSIX 是可再生成的构建产物，不纳入仓库提交。

## 开始使用

1. 安装 VSIX 后，在 VS Code 中打开 **LWT 仓库根目录**作为单一 workspace folder。
2. 打开或新建 `.lwt` 文件。扩展启动 `python -m lwt.lsp_server`，LSP 子进程以仓库根为 cwd；LSP stdin/stdout 专用于协议，扩展日志写到 `LWT` Output Channel。
3. 在命令面板运行 `LWT: Run Current File`、`LWT: Check Current File` 或 `LWT: Debug Current File in Terminal`。命令要求当前编辑器是已保存的 `.lwt` 文件；执行前扩展保存当前文档。
4. Run/Debug 显示并聚焦集成终端，便于输入。Check 为非执行路径，终端显示静态检查结果。

## 设置

| 设置 | 默认值 | 说明 |
|---|---|---|
| `lwt.pythonPath` | `python` | Python 可执行文件路径，用于 LSP 与命令任务。可填写含空格的完整路径；这里只接受 executable，不接受带参数的 shell 命令字符串。 |
| `lwt.workingDirectory` | 空字符串 | 空值使用 workspace 根目录。相对路径以 workspace 根解析，绝对路径也可用。该 cwd 用于 Run/Check/Debug 任务；Language Server 固定使用 workspace 根。 |
| `lwt.programArgs` | `[]` | 字符串数组，只传给 Run/Debug，并逐项放在 LWT 源文件后的 `--` 之后。数组项里的空格、Unicode 和以 `--` 开头的值都作为单个参数传入。 |
| `lwt.programStdin` | 空字符串 | 仅供 Debug 使用。可填绝对路径或相对于任务 cwd 的 UTF-8 文件路径，扩展会把完整路径作为单独参数传给 `--program-stdin`。未指定时，被调程序按 S30 规则遇到 EOF；它不占用调试命令 stdin。 |

Python 和任务通过 VS Code 的 `ProcessExecution` / Language Client executable 启动，工作目录作为独立 cwd 设置，参数使用数组。没有 shell 拼接。当前只支持一个 workspace folder；零个或多个 folder 时会提示打开单一项目目录。

相对源码路径以该 LWT CLI 进程 cwd 为基准。若把 `lwt.workingDirectory` 改到仓库之外，需确保该环境仍能导入 LWT 包并访问程序的相对输入文件。推荐初次使用时保留默认 workspace cwd。

## 命令结果与错误

Run、Check 和 Debug 在终端中显示子进程输出。扩展 Output Channel `LWT` 记录实际 argv、cwd、语言服务生命周期和任务退出码。退出码解释仍由现有 CLI 决定：成功 0、词法/语法错误 2、未捕获运行时错误 3、CLI/文件错误 4；S30 调试会话取消/命令 EOF 的额外状态见[调试器说明](debugger.md)。

静态检查通过只表示 S27 checker 的静态规则通过，不表示程序已运行。启动子进程成功也不代表 LWT 程序退出码为 0。Language Server 启动失败时，扩展会显示一次可读消息，在 Output Channel 写明错误；不会无限自动重启。修复 `lwt.pythonPath`、打开仓库根目录后执行 `Developer: Reload Window`。

## 故障排查

- 找不到 `lwt` 模块：将 workspace 打开到含 `lwt/` 包的仓库根目录；确认使用的 Python 可导入该工作树。不要用 shell 拼接命令来“补救”路径。
- Python executable 路径含空格：直接把完整 executable 路径填入 `lwt.pythonPath`，不要加引号或额外参数；扩展按一个进程字段传递。
- 文件修改后 diagnostics 不更新：确认文件扩展名为 `.lwt`、VS Code 语言模式为 LWT，并检查 `LWT` Output Channel 的 server 生命周期记录。
- `input()` 无响应：Run/Debug 会显示并聚焦任务终端；确认焦点在集成终端并在程序提示后输入。Check 不会执行或等待输入。
- Debug 程序需要输入：设置 `lwt.programStdin` 为 UTF-8 文件。调试命令仍在终端输入；不要把调试命令脚本或程序 stdin 混为一项。
- 多根 workspace：当前明确不支持；关闭额外根目录，单独打开 LWT 项目。

## 命令行后退路径

不安装扩展也可使用相同功能：

```powershell
python -m lwt.lsp_server
python -m lwt --check examples/modules/main.lwt
python -m lwt examples/basic_io.lwt
python -m lwt.debugger examples/debugger/main.lwt
```

调试器可复现会话（从仓库根目录执行）：

```powershell
python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt
```

## 依据

- [VS Code Language Server Extension Guide](https://code.visualstudio.com/api/language-extensions/language-server-extension-guide)
- [VS Code Extension Test](https://code.visualstudio.com/api/working-with-extensions/testing-extension)
- [Microsoft vscode-languageclient 11.0.0 manifest](https://registry.npmjs.org/vscode-languageclient/11.0.0)
- [LWT Language Server 能力与协议边界](language-server.md)
- [LWT S30 调试器 I/O 与退出码契约](debugger.md)
