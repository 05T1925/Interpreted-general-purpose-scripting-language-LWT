# S33 黑盒测试工作台与 VS Code Test Explorer

状态：实施完成，等待主窗口审查。此文记录 `feature/testing-workbench` 上的执行证据；未合并、未推送，S12 尚未开始。

## 基线和提交

- 起始基线：`819d1b0dcfa8015168f146392a048592a0e2262d`（本地 `main` 与实时查询的 `origin/main` 起始点一致）。
- 阶段分支：`feature/testing-workbench`。
- 阶段提交：runner/schema、Test Explorer 和文档分层提交；各提交 SHA 在最终交接中列明（本报告为最后一个报告提交）。

| 层次 | 内容 | 提交 SHA |
|---|---|---|
| Runner/schema | 黑盒运行器选择、inventory/results JSON、进程取消与字节保真 | `86546cb2d15c01fdefb4710e16c557de93dc9c75` |
| Test Explorer/DAP | 官方 Testing API、类别树、运行/调试 profile、Extension Host 回归 | `4b0a9a3e39f9262355a9cda20fed3616e6a4e464` |
| 文档与阶段状态 | README、开发指南和路线图状态 | `72c6916f8b271d31f70890344e243ed587661f4c` |
| 阶段报告 | 本报告和完整验证记录 | 最终报告 SHA 由交接列明 |

## 变更文件

- `tools/run_tests.py`：复用完整 inventory 与 `run_case()` oracle，新增筛选、inventory/results JSON、批量进程取消和原始输出字节编码。
- `tests/test_runner.py`：新增 runner CLI/schema/选择/异常/字节/取消/Unicode 路径及真实类别运行回归。
- `editors/vscode-lwt/src/testing.ts`：Test Explorer 发现、请求展开、执行结果/差异映射、刷新/取消和受限 Debug profile。
- `editors/vscode-lwt/src/extension.ts`、`editors/vscode-lwt/package.json`：扩展生命周期和刷新命令接入、自动激活及测试脚本。
- `editors/vscode-lwt/tests/testing.test.ts`、`tests/manifest.test.ts`、`tests/run-host-tests.ts`、`tests/extension-host/suite/index.ts`：Node parser/workflow 回归和真实 Extension Host/CLI/DAP 集成证据。
- `editors/vscode-lwt/README.md`、`README.md`、`docs/developer-guide.md`：用户工作流、限制和开发入口。
- `project.md`、`docs/s33-testing-workbench-plan.md`、`阶段执行与审查路线图.md`、`LWT大作业总体方案与复检.md`、`详细实施规划.md`：记录 S33 交付状态，保持 S12 为最后阶段。
- `docs/s33-testing-workbench.md`：本阶段契约、决策、缺陷闭环、命令结果和审查边界。

## 架构与事实来源

原有 `tests/cases/**/*.lwt` 与同名 `.json` metadata 仍是唯一黑盒用例来源。`tools/run_tests.py` 在任何筛选前完整调用 `discover_cases()`，复用相同配对、JSON metadata、ID、路径和源码读取验证；筛选不扫描或解析第二套 metadata。每次批量执行只发现一次 inventory，再按稳定顺序调用原有 stdout/stderr/退出码比较 oracle。S33 没有修改 287 组已有用例、metadata、语言规范、LWT 实现或测试矩阵。

默认 `python tools/run_tests.py` 继续逐案打印 `[PASS]/[FAIL]`，以相同 CRLF 规范化规则比较，仅 CRLF 被折成 LF；其他字节、空格和孤立 CR 保持原样。它维持原汇总行形状和成功 `0` / 用例失败 `1` / 配置错误 `2` 的退出码。新增机器 JSON 通道显式写 UTF-8；JSON `actual.stdout_base64` / `actual.stderr_base64` 保存子进程原始字节，比较仍使用旧的 CRLF 规范化字节。该分离避免 Windows 默认控制台编码损坏 Unicode JSON，也不会有损改写黑盒结果。

## Python runner 命令

```powershell
python tools/run_tests.py
python tools/run_tests.py --list-json
python tools/run_tests.py --case args-empty --format json
python tools/run_tests.py --category arrays-records-each --category integrated --format json
python tools/run_tests.py --case args-empty --case split-empty-separator --category builtins-text-io --format json
```

`--list-json` 只输出 inventory，不启动 LWT 程序，且不能和选择项或 `--format` 合用。可重复 `--case` 与 `--category`：同类选择内部是并集；若同时使用两类选择，则取 case 集合与所选类别并集的交集，按 inventory 原顺序执行。重复 ID/类别、未知 ID/类别和零匹配均为非零配置错误；JSON 模式把配置诊断写 stderr，不往 stdout 混入非 JSON 内容。所有选择前始终验证整份 inventory。

### JSON schema v1

`--list-json` 返回 `schema: "lwt.test-inventory"`、`schema_version: 1`、`case_count`、按类别分组的 `categories` 和完整 `cases`。每个 case 含 ID、类别、仓库相对 `.lwt` 路径、`spec_refs`、`tags`、程序参数、stdin/预期输出 Base64、预期退出码、超时、`cli_args_override` 及经规则计算的 Debug 可用性与原因。

`--format json` 返回 `schema: "lwt.test-results"`、`schema_version: 1`、全批次 `status`、各结果状态计数和每案结果。结果状态为 `passed`、`failed`、`timeout`、`start_failed`、`cancelled`、`not_executed`；`failure_kind` 区分断言差异、运行退出错误、超时和启动失败。包含预期/实际退出码、原始 stdout/stderr Base64、耗时和可读差异。超时没有实际退出码；取消和未执行用例不伪装成通过。运行器处理取消后停止启动后续 case，并终止当前 LWT 子进程；Windows 使用 `taskkill /T /F`，POSIX 终止子进程并等待后升级为 kill。

## VS Code Test Explorer

扩展使用 VS Code 官方 `TestController`、`TestItem`、`TestRunProfile` 和 `TestMessage.diff`。单根 workspace 根目录通过 `tools/run_tests.py`、`lwt/__main__.py`、`tests/cases` 识别，随后以 Python runner `--list-json` 的严格校验结果建立“类别 → 用例”树；每案关联仓库内 `.lwt` URI。非 LWT 根目录、零/多根工作区、Python 启动失败或 inventory 损坏会显示发现错误，不会生成空通过。

运行 profile 由 VS Code 的 include/exclude 选择展开类别和用例、消除重复并按 inventory 顺序执行。每个批次向 runner 一次传入所有选中 case ID，runner 仅完整发现一次。通过、断言失败、运行时退出差异、超时、启动失败、取消和未执行分别映射到 Test Explorer 状态；输出 channel/test message 包含状态、退出码、stdout/stderr 和差异。取消、扩展关闭、发现刷新和去抖文件 watcher 会终止相应 runner 进程树；过期 discovery 不得覆盖新 inventory。

### Debug profile 限制

只有预期退出码为 `0`、标准源码入口（无 `cli_args_override`）、stdin 可严格 UTF-8 解码的案例带 `lwt-debuggable` 标签。Debug 使用已验证 metadata 构造现有 S32 DAP launch 的 program、args、仓库 cwd 和临时 UTF-8 stdin 文件；一次调试一个 case。预期错误、五个 CLI 参数覆盖 case 和非法 UTF-8 stdin case 不显示 Debug。临时文件在 debug session 正常终止、启动失败、取消和扩展停止时清理。Debug session 结束只记为 skipped/unverified 并明确说明没有运行黑盒 oracle；只有正式 runner 的比较可标记通过。

## 验收中发现并修复的问题

Windows Extension Host 第一次读取 `--list-json` 时报告 UTF-8 解码失败。原因是 Python `print()` 按 Windows stdout 默认编码写入含 Unicode metadata 的 inventory。runner 现对两个机器 JSON 模式显式 UTF-8 编码至 `stdout.buffer`；默认人读文本入口未变。修复后同一真实 Host discovery 成功加载全部 287 项。

增加临时 case 触发文件 watcher 时，Extension Host 曾在显式 `refresh()` 返回后读到上一次 287 项 inventory，而最新临时 inventory 应为 289 项。发现刷新现在共享一个有界循环 promise：新 generation 会取消旧查询，调用方等待最新 generation 完成，旧查询不能覆盖新树。Extension Host 后续通过新增/移除 metadata 的真实 runner 刷新检查通过。

Debug 的 Host 断言最初把 `args()` 的展示格式写成了不带空格的 JSON，并只捕获 DAP 的第一个 stdout event。测试修正为按结束前所有 stdout 事件拼接，并与实际格式 `["two words", "雪"]` 比较；没有修改 runtime 输出契约。结果 parser 也会按原有 CRLF 规则核实 Base64 原始输出是否支持其 `passed`/`failed` 声明，阻止相互矛盾的 JSON 状态通过。

## 实际验证

基线已实测：黑盒 `287/287`，完整性 `287 cases / 384 matrix links / 287 referenced cases`，Python unittest `442` 项。本轮最终验证在 Windows 11、Python 3.13.7、Node 24.18.0、npm 11.13.0、VS Code 1.144.0 执行：

| 证据层 | 实际命令/环境 | 实际结果 |
|---|---|---|
| 默认公开黑盒 | `python tools/run_tests.py` | exit 0；287/287；9 类全通过（32/43/13/43/40/3/52/30/31）；53.264s |
| 完整性 | `python tools/check_project_integrity.py` | exit 0；287 cases / 384 matrix links / 287 referenced cases |
| Python 全量 | `python -m unittest discover -s tests -q` | exit 0；454 项通过；105.695s |
| Runner 定向 | `python -m unittest discover -s tests -p "test_runner.py" -v` | exit 0；32 项通过；包含真实类别 CLI JSON 批次和 Unicode/空格路径 |
| S30 CLI debugger | `python -m unittest discover -s tests -p "test_debugger.py" -v` | exit 0；28 项通过 |
| S32 DAP 回归 | `python -m unittest tests.test_dap_protocol tests.test_dap_engine tests.test_dap_subprocess -q` | exit 0；21 项通过 |
| Python 编译 | `python -m compileall -q lwt tests tools bench app` | exit 0 |
| 有效 LWT 行数 | `python tools/count_lwt_lines.py app/log_report.lwt` | exit 0；246 行 |
| Extension 单测 | `npm run test:unit` | exit 0；18 项通过，0 失败/跳过 |
| Extension Host | `VSCODE_EXECUTABLE_PATH=<本机 Code.exe> npm run test:host` | exit 0；6 项通过，0 失败/跳过；包括 287 项发现、单项/批量执行、失败、取消、刷新、源码打开和 DAP 断点/stdin/args/output |
| 扩展总测试 | `$env:VSCODE_EXECUTABLE_PATH='E:\APP\VS编译\VS code\Microsoft VS Code\Code.exe'; npm test` | exit 0；Node 单测 18 项、Extension Host 6 项通过；Host 进程正常退出 |
| VSIX 打包 | `npm run package -- --out C:\Users\28641\AppData\Local\Temp\lwt-s33-45db30016baa492491c8c0b2eb5e21e3.vsix` | exit 0；392 files / 696.84 KB。vsce 发出未提供 LICENSE 文件和未 bundle 的性能警告；未擅自选择许可证或改打包架构。临时包已清理；原有 `.vsix` 未覆盖 |
| 文档/差异 | `git diff --check`；9 份 Markdown 链接/围栏检查 | exit 0；所有扫描到的相对链接存在、围栏平衡；最终范围 `main...HEAD` 提交后复验 |

Extension Host 自动化是真实 VS Code Extension Host 和真实 runner/LWT/DAP 子进程证据，不是人工鼠标/键盘操作；真实编辑器 Test Explorer 视觉布局、用户键盘/焦点和鼠标操作未在本阶段手工验收。远端 Actions 未对 S33 SHA 运行（本阶段不推送），记为未验证。`package.json` 保留原 `UNLICENSED`；打包警告如实记录，未选择新许可证、引入 bundler 或宣称 Marketplace 发布。扩展目录在开工前已有一个同名 `.vsix`，打包改用唯一临时输出路径并清理新生成包，没有覆盖已有文件。

## 保护范围和未决事项

- `app/log_report.lwt` 继续为 246 行有效 LWT。
- 287 组黑盒源码与 metadata、`tests/test_app.py` 原 25 项 CLI 契约、S10 并发证据、S11 性能原始数据、S28 固定 profile、S29 smoke、`lwt/`、正式语言规范和 `docs/test-matrix.md` 与起始基线逐项检查，未纳入改动。
- 测试 UI/扩展用 Python、TypeScript 编写，是开发工具；课程 Agent 编写的 LWT 应用仍是 `app/log_report.lwt`。
- 不声称远端 CI、VSIX 安装、Marketplace 发布、人工编辑器交互已完成。主窗口需审查分层提交、runner JSON v1 契约和 Debug profile 的 Test Explorer 体验；随后才进入 S12。
