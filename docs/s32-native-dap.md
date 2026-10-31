# S32 执行报告：LWT 原生 VS Code DAP

**状态：实施完成，等待主窗口审查。** 工作保留在 `feature/editor-integration`；S32 未合入 main，未开始 S12。

## 基线、分支和历史

- S32 起点：已审查 S31 合入后的本地 `main` 与 `feature/editor-integration` tip `ddf1759fa4239eabc15488730917daec990da390`。
- S31 原始提交保留：实现 `938d029`、测试 `21506b1`、S31 报告 `d257154`，以及审查窗口文档保护提交 `007c774` 都是集成提交 `ddf1759...` 的祖先；用正常非快进 merge 保留 main/S31 两侧历史，没有 squash、rebase、reset 或强推。
- S31 集成提交：`ddf1759fa4239eabc15488730917daec990da390`。
- S32 分层提交：

| SHA | 内容 |
|---|---|
| `33eca1dc1ab011ffe61dea40ac33f795553ebd4f` | stdio DAP codec/server、共享 debugger control API、VS Code debugger contribution/provider |
| `4ad6422d7ce3e3e06b3b7090ae4897c2b1028b94` | DAP codec/engine/真实子进程测试与 VS Code manifest/workflow/Extension Host 回归 |
| `006e024` | DAP/调试器/扩展使用说明、阶段状态和本报告初稿 |
| 报告状态更正提交 | 记录正常 push 与最终远端读取失败；完整最终 HEAD 由执行交接列出 |

## 实现内容与关键选择

1. **DAP 协议与进程边界。** 新增 `python -m lwt.dap_server` 和严格 stdio framing。`Content-Length` 按 UTF-8 字节计数；header 上限 16 KiB、payload 上限 8 MiB，拒绝非法/重复 header、坏 JSON/UTF-8、超限及半帧 EOF。协议 stdout 只写 DAP 帧；adapter 诊断留在 stderr；LWT 输出通过 DAP `output` event 发送。输出按最多 512 KiB UTF-8 字节分块，避免合法的大程序输出超过 frame 限制。
2. **请求和执行并发。** 一个 reader 线程持续读取协议请求；主线程是唯一 DAP writer；LWT 程序在单独执行线程运行；队列把程序输出和暂停事件交给 writer。因此运行或暂停时仍可请求线程/栈/变量，也能继续、终止或断开。stdin reader 使用直接 fd 读取，避免 Python buffered stdin reader 在线程退出时锁住解释器清理。
3. **复用 S30 语义。** `DebuggerController` 增加显式 start/resume/cancel、断点整批替换和暂停时 frame/locals/globals 访问 API。S30 CLI Debug 仍走原文本命令入口，不从 DAP 解析 CLI 文本，也不注入伪命令。取消在 LWT 语句检查点生效，不强杀 Python 线程；无界循环终止有真实子进程回归。
4. **DAP 能力与引用。** 支持单稳定 thread ID、精确源行断点、threads/stackTrace/scopes/variables、continue/stepIn/next/stepOut、loadedSources、terminate/disconnect。错误行返回 `verified=false`，不会移动断点。恢复后旧 frame ID 和 variablesReference 不再有效；数组、record、Error 可展开，循环引用安全显示。只声明实现的 capabilities；不支持的请求返回标准错误。不支持 Evaluate、Watch、SetVariable、条件/函数断点、logpoints、attach、TCP 或多线程。
5. **VS Code 接入。** 扩展加入 `lwt` debugger manifest、当前文件 launch 初始配置、launch schema、configuration provider 和 `DebugAdapterExecutable` factory。F5 使用当前 Python executable 通过 argv `-m lwt.dap_server` 启动 adapter；程序路径、工作目录、args 和 `stdinFile` 分开传入。DAP stdio 只做协议，程序 `input()` 使用独立 UTF-8 stdin 文件；未配置时按 EOF 处理。S30 终端 CLI Debug 命令保留并改名以区分。
6. **调试事件修正。** S30 内部 step/next/finish 暂停原因按 DAP 标准统一映射为 `stopped.reason="step"`，原始细节保留在 description；断点 reason 为 `breakpoint`。语法/模块预检 launch 失败会显示诊断、拒绝 launch，并发送对应 `exited` 与 `terminated`，文件错误为 exit 4、语法错误为 exit 2；运行时错误仍按真实 LWT exit code 3 报告。

## 验证环境和命令

环境：Windows 11 家庭中文版，build 26200；CPython 3.13.7；Node.js 24.18.0；npm 11.13.0；VS Code 1.144.0（`E:\APP\VS编译\VS code\Microsoft VS Code\Code.exe`）。Extension Host 使用隔离临时 workspace/profile。

| 实际命令 | 结果 |
|---|---|
| `python tools/run_tests.py` | exit 0；黑盒 `287/287`，failed 0；类别：arrays-records-each 32、builtins-text-io 43、cli-errors 13、control-functions 43、error-recovery 40、integrated 3、lexer-parser 52、modules 30、values-operators 31；50.161 秒 |
| `python tools/check_project_integrity.py` | exit 0；cases 287、matrix_links 384、referenced_cases 287 |
| `python -m unittest discover -s tests -q` | exit 0；442 tests，78.015 秒 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | exit 0；S10 CLI 契约测试 25/25 |
| `python -m unittest discover -s tests -p "test_debugger.py" -v` | exit 0；S30 CLI 调试器回归 28/28 |
| `python -m unittest tests.test_dap_protocol tests.test_dap_engine tests.test_dap_subprocess -q` | exit 0；S32 DAP 定向 21/21：codec 7、控制层 5、真实 `python -m lwt.dap_server` 子进程 9 |
| `python -m compileall -q lwt tests tools bench app` | exit 0 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | exit 0；有效 LWT 行数 246 |
| 固定 S30 调试示例：`python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt` | exit 0；程序 stdout 为 `demo:5`，调试记录在 stderr |
| 扩展目录 `npm test`（`VSCODE_EXECUTABLE_PATH` 指向上述 Code.exe） | exit 0；Node 单测 11/11；Extension Host 4/4；skip 0。Host 真实启动 adapter，验证 gutter source breakpoint、停点、Call Stack/Variables、Continue、stdout 和退出事件 |
| 扩展目录 `npm run package` | exit 0；生成本地 `lwt-language-tools-0.1.0.vsix`，391 个归档项、701,993 bytes；归档抽查测试文件 0 个，扩展入口存在 |
| `git diff --check` | exit 0，无空白错误 |
| 修改 Markdown 的相对链接/代码围栏检查（16 个变更文档） | exit 0；相对链接均可解析，代码围栏成对 |

Extension Host 有少量上游 VS Code agent-host/PTY 日志噪声；它不影响用例结果。VSIX 打包有两条工具警告：扩展目录没有 LICENSE 文件；扩展 182 个 JavaScript 文件未 bundle。S32 未增加依赖，也未将 VSIX、`out/`、`node_modules/` 纳入提交。

### DAP 子进程覆盖

九项真实子进程测试发出真实 `Content-Length` DAP 帧并解析 adapter stdout，覆盖：含空格/Unicode 的入口和导入模块路径；source breakpoint 验证与同 source 整批替换；递归 LWT stack、局部遮蔽及 locals/globals；数组/record/Error 与自引用展开；变量/frame 引用恢复后失效；args、cwd、程序 stdin 文件与 EOF；continue、stepIn、next、stepOut 的标准事件 reason；程序输出和运行时错误 exit 3；launch 语法错误 exit 2、缺源文件 exit 4；畸形协议只写 stderr 且退出；512 KiB 输出分帧；terminate 无界循环。所有子进程均无挂起、stdout 协议帧可完整解码、stderr 无 Python traceback。

### Extension Host 与人工界面证据

真实 Extension Host 通过 VS Code debug API 启动 manifest 注册的 `lwt` launch，并实际创建 gutter `SourceBreakpoint`。adapter 对该行回复 `verified=true`，随后 stopped reason 为 breakpoint；Host 从 session 请求 threads、stackTrace、scopes、variables，Continue 后收到 `42\n` stdout、exit 0 和 terminated。另三项 Host 回归覆盖语言服务诊断/hover/definition 与 Run/Check 真实 CLI process task。

这属于真实 VS Code Extension Host 自动集成证据，不是用户桌面上的人工视觉验收。本轮未手工安装 VSIX，也未用真实鼠标/键盘检查 F5、窗口、焦点和断点 gutter 视觉效果；交由 S12 现场预检。VS Code `--version` 在本执行环境没有输出文本，版本通过 `Code.exe` 文件属性确认是 1.144.0。

## GitHub 与远端状态

- S31 合流 tip `ddf1759...` 的 `feature/editor-integration` Actions run `41190959253` 已成功，4/4 个矩阵 job 完成；[run 41190959253](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41190959253)。该验证发生在 S32 修改前。
- S32 完成后新一次 `git ls-remote --heads origin main feature/editor-integration stage/s31-vscode-extension` 失败：`fatal: unable to access 'https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT.git/': schannel: failed to receive handshake, SSL/TLS connection failed`。没有改 TLS 校验设置，也没有以旧 SHA 假装已重新核实。
- 文档分层提交后实际执行 `git push origin feature/editor-integration`，同样因上述 Schannel TLS 握手错误失败。随后再次只读执行 `git ls-remote --heads origin main feature/editor-integration stage/s31-vscode-extension`，仍得到相同错误。没有改变 TLS 校验、强推或切换传输方式。
- 最近一次成功核实的远端 `main` 和 `feature/editor-integration` 是 S32 开始前的 `ddf1759...`；当前远端 tip 无法从本执行环境确认。S32 未取得远端 SHA，也没有可绑定到 S32 SHA 的 Actions run；S31 的成功 Actions 不能外推到 S32。

## 保护范围核对

相对 S32 基线 `ddf1759...` 的保护路径 `git diff --exit-code` 退出码为 0，差异为空：

- `app/log_report.lwt`、`tests/test_app.py`（S10 契约仍 25 项）；
- S10 并发原始记录 `reports/app-concurrency.json`、`docs/app-concurrency.md`；
- S11 性能原始记录/报告 `bench/results.json`、`reports/performance.md`；
- S28 固定 profile `reports/app-lwt-profile.json`、`.html`；
- S29 固定 smoke `reports/lsp-smoke.json`；
- `lwt/runtime.py`、正式语言规范、黑盒矩阵和 `tests/cases/`。

没有运行 S10 并发证据生成器或正式性能基准。允许的 `lwt/` 改动仅为 DAP server/codec 与 S30 debugger control API；未改变解释器 runtime 或用户可观察语言语义。

## S32 修改文件

**实现（6）：** `lwt/dap_protocol.py`、`lwt/dap_server.py`、`lwt/debugger_core.py`、`editors/vscode-lwt/package.json`、`editors/vscode-lwt/src/extension.ts`、`editors/vscode-lwt/src/workflow.ts`。

**测试（6）：** `tests/test_dap_protocol.py`、`tests/test_dap_engine.py`、`tests/test_dap_subprocess.py`、`editors/vscode-lwt/tests/manifest.test.ts`、`editors/vscode-lwt/tests/workflow.test.ts`、`editors/vscode-lwt/tests/extension-host/suite/index.ts`。

**文档/项目状态：** `docs/dap.md`、`docs/debugger.md`、`docs/vscode-extension.md`、`editors/vscode-lwt/README.md`、`README.md`、`project.md`、`AGENTS.md`、`docs/agent-dev-log.md`、`docs/repository-workflow.md`、`docs/s32-native-dap-plan.md`、`docs/s31-vscode-extension-plan.md`、`docs/s12-final-delivery-plan.md`、`LWT大作业总体方案与复检.md`、`详细实施规划.md`、`阶段执行与审查路线图.md`、`docs/s32-native-dap.md`。

## 开发期间的测试调整记录

几项早期失败均为测试预期与实际接口/语义未对齐，已修正后复跑：Node manifest 测试最初假定 adapter argv 必须直接字面写在 extension 文件，实际由 workflow builder 集中构造；测试改为断言 provider 使用该 builder。首轮 Extension Host DAP 测试因 stopDebugging 清理取消掩盖了前序失败，增强 tracker 覆盖 client/server 两向消息、等待 configurationDone，并让清理取消不遮盖原始错误；之后完整 `npm test` 通过。预检语法测试最初预期 `ParseError`，实际稳定诊断类别是 `SyntaxError`；断言修正后通过。递归测试最初错误期望入口 frame 有局部函数参数，改为只检查实际可见的函数帧 locals。上述为测试修订，没有放宽现有产品/语言断言。

## 遗留和 S12 交接

- 等待主窗口审查后，才按已授权集成流程处理 S32；本执行窗口不合入 main。
- S32 正常 push 和只读远端核验均因 TLS 握手失败，远端 SHA/Actions 未验证；不得把 S31 的 run 外推到 S32。
- 用户桌面安装 VSIX、实际 F5、视觉可读性和真实硬件键鼠仍未验证；S12 现场预检时记录可归因步骤。
- S23–S30 不是每阶段都有独立主窗口审查记录；不因本轮回归把这些历史缺口改写为“全部审查通过”。
- S12 新克隆、Python 3.10/CI 矩阵、PPT、最终答辩和发布继续保留；本阶段未开始这些工作。
