# LWT 原生调试器（DAP）

LWT VS Code 扩展通过标准输入/输出 Debug Adapter Protocol 启动真实的 LWT 源码调试会话。Python adapter 入口为 `python -m lwt.dap_server`；它复用 S30 的 AST/runtime 调试钩子，不解析 CLI 调试器的文字输出，也不实现第二套 LWT 执行逻辑。DAP 是开发工具，不增加 LWT 语法，也不会把课程应用 `app/log_report.lwt` 改写为 Python。

## 在 VS Code 中启动

1. 在 VS Code 打开包含 `lwt/` 包的仓库根目录，并只使用一个 workspace folder。
2. 安装本地扩展包（构建步骤见 [VS Code 扩展说明](vscode-extension.md)），打开一个已保存的 `.lwt` 文件。
3. 在编辑器左侧 gutter 点击可执行源码行设置断点；按 F5 或从 **Run and Debug** 启动 `LWT: Debug Current File`。
4. 在标准调试工具栏使用 Continue、Step Into、Step Over、Step Out。Call Stack 展示 LWT 调用帧；Variables 展示当前暂停点的 Locals 和 Globals。数组、record 和 Error 值可以展开。

默认 launch 配置使用当前已保存文件。要显式配置参数和程序输入，可在 `.vscode/launch.json` 中加入：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "lwt",
      "request": "launch",
      "name": "LWT: Debug Current File",
      "program": "${file}",
      "python": "${config:lwt.pythonPath}",
      "cwd": "${workspaceFolder}",
      "args": [],
      "stdinFile": ""
    }
  ]
}
```

`program` 是已保存的 LWT 源文件；`python` 是 Python 可执行文件，不带 shell 参数；`cwd` 是程序工作目录；`args` 是字符串数组，作为 LWT `args()` 返回的值；`stdinFile` 是可选程序输入文件路径。相对 `program` 路径以 workspace 根解析；相对 `stdinFile` 路径以 `cwd` 解析。调试 adapter 使用扩展配置的 Python 可执行文件，并以 workspace 根启动 `lwt.dap_server`。

LWT `input()` 从 `stdinFile` 读取 UTF-8 字节；未设置时输入立即到达 EOF 并得到语言规定的 EOF 值。DAP 的 stdio 永远只承载协议帧，不能作为 LWT 程序输入。LWT `emit` 输出作为调试器的 stdout output event 展示，诊断作为 stderr output event 展示。

## DAP 能力与限制

当前支持单进程、单 LWT 执行线程，稳定 thread ID 为 1。断点按精确源码行设置；无可执行语句或来源不在已加载模块图时会返回 `verified: false`，不会移动到邻近行。导入模块使用真实本地路径，支持含空格和 Unicode 的路径。

Continue、Step Into、Step Over/Next、Step Out 均由共享调试控制层执行。Variables 只读；每次恢复后，旧 frame ID 和 variablesReference 失效。协议 reader 在 LWT 运行或暂停期间仍接收请求；DAP 帧由一个 writer 顺序写入。LWT runtime 错误以 stderr output event 和实际退出码报告；源码语法/模块预检错误会使 launch 失败，并显示对应诊断及退出码。

不支持 attach、远程/TCP、多线程、条件/函数断点、logpoints、Evaluate/Watch、SetVariable、变量赋值、Debug Console 交互式 `input()`、时间回溯或 Marketplace 发布。扩展的 `LWT: Debug Current File in Terminal` 仍保留为 S30 CLI 调试后退入口；它不是 DAP。

## 命令行后退方式

不使用 VS Code 时，可用 S30 的可复现命令脚本运行相同 LWT 调试钩子：

```powershell
python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt
```

程序 stdout 与调试 stderr 分离；预期程序 stdout 为 `demo:5`。更完整的命令和作用域规则见 [源码级调试器说明](debugger.md)。

## 验证边界

阶段实现报告分别列出 DAP codec、控制层、真实 DAP 子进程、VS Code Extension Host、打包、远端 CI 和人工 GUI 证据。Extension Host 证明 VS Code API 与 adapter 的自动集成路径；它不代替用户桌面上的人工安装/视觉验收。
