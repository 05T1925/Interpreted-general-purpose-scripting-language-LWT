# S29 执行报告：LWT Language Server 与编辑器级静态辅助

状态：**实施完成，等待主窗口审查；S12 未开始。** 本报告记录执行窗口在独立阶段分支中的实现、实测和限制。协议 smoke 证明固定 stdio transcript 可工作，不代表已经连接或验收任何真实编辑器。

## 1. 基线、分支和提交

- S28 原最终 HEAD：658e37e6c86f0ccb8424055f213f068b482f6826。
- 为使 S28 报告包含最终 SHA、分支和干净状态，先在 S28 分支单独提交报告自包含修正：6aa198a402aaaec1f95806af78548a82abdfd854。修正只涉及 docs/s28-execution-observability.md；S29 从该 tip 建立，没有用较旧的远端分支覆盖本地历史。
- S29 分支最终 HEAD：5eaacccd04cb8b2d00865114424099f6983fa13c，分支名为 stage/s29-language-server。该提交后的 S29 工作区干净；本报告不表示 S29 已通过主窗口审查或合入 main。
- 未修改 main，未 fetch/pull/push、合并、变基、重置、打标签或发布。

S29 功能与测试分层提交：

| 提交 | 内容 |
|---|---|
| 5de21e811de344caa86b032c10fe1409a06a4b33 | 有界 stdio framing 与 JSON codec |
| 68ac07985ff487d08cab94a9eee6bdea764b034d | 模块 overlay、文档模型、静态语言服务 |
| 7af411b4dfcf8ddcff99ed62b82115c880ac7db7 | JSON-RPC/LSP 生命周期和子进程测试 |
| 781c66b96924829eda92fc3fc642f2a483311c6e | 真实子进程 smoke 工具和脱敏证据 |
| b4f8338c3e9ac6d92853204a1f96f12e6bb76dd2 | LSP 索引与精确源码快照保持一致 |
| f829ee5567c69a8ede53db9503cda8cdc67435d7 | 局部变量、each/recover 绑定的定义索引 |
| 143b5ad0607bc9019884f37572df5851c05f56ec | ranged 与旧版本 didChange 拒绝回归 |
| ccfaadb354500c42c5d213295e26d985da6bac5d | README、指南、状态和规划同步 |
| 本报告提交 | 本报告及最终状态；当前提交自身构成阶段最终 tip |

## 2. 实现边界和支持能力

入口为 python -m lwt.lsp_server。这是 Python 标准库实现的开发工具，stdio 承载 JSON-RPC/LSP 消息。服务只使用 lexer、parser、AST、模块 loader 和 S27 静态 analyzer；没有导入 runtime，不调用 execute()，不消费被分析程序的 stdin，不触发 emit、input()、read_text() 或 fail()，也不产生 S28 profile。

initialize 只声明以下能力：

| Capability | 固定值 |
|---|---|
| positionEncoding | utf-16 |
| textDocumentSync | openClose: true, change: 1（完整文本同步） |
| hoverProvider | true |
| definitionProvider | true |
| documentSymbolProvider | true |

服务支持 initialize/initialized/shutdown/exit，文档 didOpen/didChange/didClose、push diagnostics、documentSymbol、hover 和 definition。没有声明或实现 completion、formatting、rename、references、semantic tokens、增量 parser、容错 AST、调试协议或网络服务。

### stdio 与 JSON-RPC

- Header 为 ASCII，以 CRLF CRLF 分隔正文；Content-Length 按 UTF-8 正文字节数计算。header 上限 16 KiB，正文上限 8 MiB。
- 正文严格使用 UTF-8 JSON；拒绝重复/缺失/非法长度、非 UTF-8 Content-Type、重复 JSON key、非法 JSON、非对象顶层、截断输入和超限消息。短读会继续读到完整边界；EOF/截断不会无限等待。
- 错误码：Parse error -32700、Invalid Request -32600、Method not found -32601、Invalid params -32602、Internal error -32603、Server not initialized -32002。
- initialize 前业务请求返回 -32002；请求有响应，通知不产生响应；未知通知忽略。shutdown 返回 null 并封闭普通语言请求；shutdown 后 exit 退出码 0，未 shutdown 直接 exit 或未 shutdown EOF 退出码 1；shutdown 后其它请求为 -32600。
- stdout 只输出 LSP frame；错误响应不泄漏异常对象、绝对路径或 traceback。处理为单线程顺序消息循环，不声称异步并发。

### 文档、模块和位置

服务只接收本地 file URI、.lwt 扩展名和 languageId 为 lwt。路径会解码 URI 百分号并规范化后用于 overlay、模块去重和比较；客户端 URI 保持规范化 file URI。中文、空格和 Unicode 路径有测试。

打开的文档以内存文本为真，模块图中的未打开依赖从磁盘严格 UTF-8 读取；导入解析、循环检测和去重继续复用正式 loader。didChange 只接受一个完整文本且无 range 的变更，version 必须严格增加；旧版本、range 更新、未知文档更新和重复打开不会覆盖当前 overlay。关闭文档会清空该 URI 的诊断、移除 overlay，并按磁盘内容重分析仍打开的入口。LSP loader 可保留 parser 实际读取的源码文本，保证 AST 和索引使用同一份 source snapshot。

LWT 位置是一基行/码点列，LSP 位置是零基行/UTF-16 code unit 列；非 BMP 标量按两个 code unit 计。range end 排他；token 使用真实宽度，EOF 错误可用零宽末尾范围。CRLF/LF/CR 由文档位置层一致处理。

### Diagnostics、symbols、hover 和 definition

- 文档打开或更新后发布该模块 URI 的诊断。S27 STC* 稳定码原样保留；lexer、parser、module 和 source 读取错误分别使用既有映射码 LEX001、PAR001、MOD001、SRC001。诊断 severity 为 error，source 为 lwt；相同诊断去重并稳定排序，修复后发送空数组清旧诊断。
- 词法/语法首错继续遵循当前 parser 模型；语法无效时丢弃过期 AST 特性，symbols 返回空、hover/definition 返回 null，不做容错恢复。
- documentSymbol 列出 import alias、record、function 和顶层 let，记录字段与函数参数作为子符号。hover 提供关键字、十个内置函数、当前作用域变量、函数、record、模块 alias 与限定函数的静态描述，不推断动态类型或运行时值。
- definition 支持变量（含赋值目标）、函数、record、模块 alias 和 alias.function(...)；遵守参数/函数体、block、each、recover、遮蔽和独立模块命名空间规则。动态字段访问没有足够静态类型信息，故不猜测其 record 定义；不唯一可靠时返回 null。

## 3. Smoke 与真实协议证据

命令：python tools/run_lsp_smoke.py。它通过 argv 启动当前 Python 的真实 python -m lwt.lsp_server 子进程，指定仓库根 cwd、shell=False 和超时；自行校验 stdout framing，检查 stderr 不含 traceback。实际摘要：

    LSP smoke passed: 11 protocol steps, 3 symbols, diagnostics clear after repair
    exit code: 0

固定 transcript 依次覆盖 initialize、initialized、didOpen、documentSymbol、hover、definition、制造 STC010 的 didChange、修复错误、didClose、shutdown、exit。文档列出 3 个符号 stats、Batch、batch；hover 为 fn summarize(batch)；definition 指向仓库相对 examples/modules/stats_utils.lwt。诊断发布序列为 []、[STC010]、[]、[]；请求响应 id 顺序为 1–5，stderr 无 traceback，正常 exit 为 0。脱敏摘要位于 reports/lsp-smoke.json，没有用户绝对路径、时间戳、PID、机器名或对象地址。

另以独立小型 framing 解析器再次启动服务，发送 initialize/initialized/shutdown/exit，解析到两个且仅两个请求响应（id 1、2），逐 frame 按原始 UTF-8 正文字节复算 Content-Length，一致；进程退出 0，stderr 0 bytes。独立 UTF-16 复算将“😀target”中 target 起点映射为 character 2，和 UTF-16LE 字节数除以 2 的结果相符。smoke 再运行到系统临时目录，报告字节与已提交 JSON 完全相同，SHA-256 为 2e86126394729f81b41998614a907d429ac08017e95605f7fbeeeb5184c56958。

## 4. 验证结果

环境为 Windows 11 10.0.26200、CPython 3.13.7、AMD64。下表命令在本轮实际执行；退出码均为 0，除特别说明外全部通过：

| 命令 | 实际结果 |
|---|---|
| python -m unittest discover -s tests -p "test_lsp_protocol.py" -v | 15/15 passed |
| python -m unittest discover -s tests -p "test_language_service.py" -v | 16/16 passed |
| python -m unittest discover -s tests -p "test_lsp_server.py" -v | 5/5 passed；含真实子进程生命周期、错误码、overlay 和 shutdown/exit |
| 三个 LSP 定向测试合计 | 36/36 passed |
| python -m unittest discover -s tests -q | 393 tests，全部通过 |
| python tools/run_tests.py | 287/287 语言黑盒通过，0 failed；原有黑盒文件未删改 |
| python tools/check_project_integrity.py | OK：287 cases、384 matrix links、287 referenced cases |
| python -m compileall -q lwt tests tools bench app | 通过，退出码 0 |
| python tools/count_lwt_lines.py app/log_report.lwt | 246 行有效 LWT |
| python tools/run_semantic_properties.py | 固定 seed 20261028，156 checks、7 programs，通过 |
| python tools/audit_semantic_mutants.py | 10 probes：9 killed、1 survived、0 equivalent、0 invalid；幸存探针为普通参数逆序探针，既有独立“不同副作用参数逆序”探针已 killed，保留此审计结果不作掩盖 |
| python -m unittest discover -s tests -p "test_static_checker.py" -v | 20/20 passed |
| python -m unittest discover -s tests -p "test_execution_profile.py" -v | 19/19 passed |
| python -m unittest discover -s tests -p "test_modules.py" -q | 9/9 passed |
| python -m unittest discover -s tests -p "test_runtime.py" -v | 11/11 passed，含错误恢复、循环控制和错误值 |
| python -m unittest discover -s tests -p "test_cli.py" -q | 108/108 passed |
| python -m unittest discover -s tests -p "test_app.py" -q | 25/25 passed |
| python tools/run_lsp_smoke.py | 11 protocol steps 成功；退出码 0 |

真实 CLI 兼容路径也已实际执行：

| 命令 | 关键输出/退出码 |
|---|---|
| python -m lwt examples/modules/main.lwt | stdout demo:2；exit 0 |
| python -m lwt --check --format=json examples/modules/main.lwt | {"schema_version":1,"ok":true,"files_checked":3,"diagnostics":[]}；exit 0 |
| python -m lwt examples/error_recovery/main.lwt | 输出 2、division by zero、稳定 Error 描述、4、remaining values processed；exit 0 |
| python -m lwt app/log_report.lwt -- app/fixtures/sample.log | 默认报告：总行 7、有效 6、坏行 1、匹配 6；ERROR/INFO/WARN 均为 2；exit 0 |
| python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2 | 匹配 1；WARN\|1、cache\|1，示例为 2026-10-07T10:00:03Z\|WARN\|cache\|retry scheduled；exit 0 |

这些运行/检查输出只证明现有 CLI 路径能在本分支继续使用；不构成性能测量。profile 定向测试验证普通模式、--check 不创建 profile 且 profile JSON 确定性。保护文件对比相对 S29 基线 6aa198a402aaaec1f95806af78548a82abdfd854 进行：S10 app/log_report.lwt、25 项 tests/test_app.py、tests/cases/、S10 并发记录/报告、S11 bench/results.json/性能报告及四份 S28 固定 profile 均无差异；lwt/runtime.py、CLI、lexer、parser、AST、analyzer 和 profile collector/schema 无差异。S29 只改 lwt/modules.py 的可选静态 source overlay/source snapshot 能力，并新增 LSP 工具模块，没有改 LWT runtime 或源语言语义。

## 5. 修改文件清单

### LSP 实现与验证

- lwt/lsp_protocol.py：有界 framing、严格 UTF-8/JSON 读取和写入。
- lwt/lsp_documents.py：file URI、文档版本/overlay、CRLF/LF/CR、UTF-16 转换和 token range。
- lwt/modules.py：可选 overlay 和 source snapshot 参数；普通 CLI 默认调用路径不变。
- lwt/language_service.py：静态模块图、diagnostics、symbols、hover、definition 与词法作用域定义索引。
- lwt/lsp_server.py：stdio server、JSON-RPC 生命周期、文档通知和请求分派。
- tests/test_lsp_protocol.py、tests/test_language_service.py、tests/test_lsp_server.py：codec、service、真实子进程与事件边界测试，共 36 项。
- tools/run_lsp_smoke.py、reports/lsp-smoke.json：真实 server transcript 和固定脱敏证据。

### 使用、阶段状态和规划

- docs/language-server.md：启动、协议子集、配置示意、UTF-16、overlay、能力限制和 smoke 说明。
- docs/s29-language-server.md：本阶段完整执行报告。
- README.md、docs/developer-guide.md、.agents/skills/lwt-app/SKILL.md：开发工具入口和使用说明。
- docs/language-spec.md：仅增加 Language Server 属于开发工具、不改语言语义/执行的说明。
- docs/test-matrix.md：把 LSP 工具测试与 287 项语言黑盒明确分开。
- docs/agent-dev-log.md：记录收到的任务、实现提交、复核修正和本轮验证。
- project.md、阶段执行与审查路线图.md、详细实施规划.md、LWT大作业总体方案与复检.md、docs/s12-final-delivery-plan.md：同步 S29 状态、范围和 S12 依赖顺序。

## 6. 文档和审查边界

已对本阶段 Markdown 检查相对链接存在性与代码围栏闭合，并运行 git diff --check；最终结果和退出码列于执行交接。运行时语义、正式语言规则、287 项黑盒和性能结论没有改写。没有真实连接 VS Code、Neovim 或其它编辑器；Python 3.10、Linux 和远端 GitHub Actions 也没有在本机实际验证。未执行正式性能基准、S10 并发原始数据生成器或 S28 profile 档案生成器。

S29 是开发工具，不是第二个 LWT 应用或完整 IDE 插件。它不提供补全，也不运行被分析程序。主窗口审查通过后才进入 S12；本阶段没有合并或推送，也未开始 S12。
