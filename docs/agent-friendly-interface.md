# LWT 的 Agent 友好接口对照（课件 4.4 / 4.5）

> 用途：把课件第 4 章的原则逐条落到 LWT 的真实行为上，每条给“原则 → 实现 → 一条复算命令”。**未实现的原则也如实列出**，不把设计意图写成既有能力。

## 1. 课件原话与对照

课件 4.4「Agent 友好的 CLI」的七条要求（原文摘录见 §3），逐条对照：

| 课件原则（4.4） | LWT 的实现 | 复算命令 |
|---|---|---|
| 机器可读的输出：提供 `--json` 或 `--format` | `--check --format=json` 输出**单行** JSON（`schema_version/ok/files_checked/diagnostics[]`）；`--profile` 与 `--schedule-log` 本身就是 JSON 文件 | `python -m lwt --check --format=json tests/cases/concurrency/check-spawn-undefined.lwt` → `{"schema_version":1,"ok":false,...,"code":"E-SPAWN-001"}`，exit 2 |
| 非交互式运行：默认不提示 | 所有入口默认不读确认；`--check`/`--profile`/`--version` 全程无提示；只有 LWT 源码自己调用 `input()` 时才消费 stdin | `python -m lwt --version` → `lwt 0.3.0`，exit 0（不等待输入） |
| 幂等性：同一命令可安全重复执行 | `--check` **不执行源码**，重复运行结果与退出码一致；`--version`/`--help` 不触碰文件系统；`--profile`/`--schedule-log` 覆盖写同名输出文件，同一输入产出同 schema | 连续两次 `python -m lwt --check tests/cases/dict-maps/dict-items-order.lwt; echo $?` → 两次都是 0 |
| 试运行模式：`--dry-run` | LWT 的等价物是 `--check`：只做模块读取、词法、语法与保守静态检查，**不执行**任何语句 | `python -m lwt --check tests/cases/dict-maps/dict-missing-key-read.lwt` → exit 0（该错误是运行时的，静态检查不误报） |
| 可观测性：`--debug` 输出细节 | 没有 `--debug` 文本开关；可观测性由三样结构化证据承担：`--profile`（`events`/`coverage`/`modules`）、`--schedule-log`（每次调度的 `decisions`）、stderr 的 `file:line:col: Category: message` 诊断 | `python -m lwt --profile %TEMP%/p.json bench/arithmetic.lwt -- 100`（JSON 顶层键含 `schema_version/events/coverage/modules`） |
| 上下文高效：`--fields` 按需输出 | **未实现** `--fields`；现有的省 token 手段是：JSON 单行、`--check` 只报**首个**错误、诊断含稳定 `code` 便于过滤 | —（如实标注未实现） |
| 明确错误码 | 退出码合同：`0` 正常、`2` 语法/静态诊断、`3` 运行时错误、`4` CLI/文件/模块错误；含义写进 `docs/language-spec.md` §7 与 `--help` 摘要 | `python -m lwt tests/cases/dict-maps/dict-missing-key-read.lwt; echo $?` → stderr `...:2:7: RuntimeError: dict has no key "z"`，exit **3** |
| 直接提供 MCP，或至少便于封装：自描述、可发现、结构化输入输出 | `lwt/mcp_server.py` 提供 `initialize`/`tools/list`/`tools/call`（行分隔 JSON-RPC 2.0）；三个工具封装公开 CLI；`--check --format=json` 提供结构化结果 | `printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \| python -m lwt.mcp_server` → 三个工具的 JSON Schema |

## 2. 课件 4.5「接口兼容性」的对照

课件 4.5 的核心是「接口即契约，发布即承诺」与「只增不改」（原文见 §3）。LWT 的三类实例：

| 兼容做法 | LWT 证据 | 复算命令 |
|---|---|---|
| 只增不改：新能力用新键/新编号追加 | `VALID_SPEC_REFS` 增量注册：S43 追加 `11.1–11.9`，S52 追加 `8.1–8.6`、`9.1–9.5`、`10.1–10.5`；旧编号一个未删 | `python -m unittest tests.test_runner -q`（含“未知编号 12 仍被拒绝”的回归） |
| 默认参数扩展：不传时用默认值，旧调用不变 | `--format` 只在 `--check` 下生效且默认仍是文本；`--schedule` 默认 `fifo`；`--profile` 的 `-- ARGS` 可省略 | `python -m lwt --check tests/cases/dict-maps/dict-items-order.lwt`（不带 `--format`）→ 文本诊断，行为与 S27 一致 |
| 旧证据键保留，新键追加 | `reports/s49-rehearsal/ci-cells.json` 保留 `f3e209c/496ccc0/8a5f2a1/f36ebe0/5ab9e5a`，S52 只追加 `5ab9e5a`；`delivery-manifest.json` 只加 `evidence.s5x_*`，不删旧键 | `python -c "import json;print(sorted(json.load(open('reports/s49-rehearsal/ci-cells.json'))['runs']))"` |
| 兼容等级（4.5 分级） | 源码兼容：Python 3.10+ 标准库，无第三方运行时依赖；CLI 旧用法（`SOURCE [-- ARGS]`）在 S43/S45 加参数后未变 | `python -m lwt examples/guide/hello.lwt` |

## 3. 课件原文摘录（用于答辩时对照）

- 4.4 CLI：「人类友好的同时，提供 Agent 友好的选项（一个工具同时服务人和 Agent）」；「机器可读的输出：提供 `--json` 或 `--format` 选项，输出结构化数据」；「非交互式运行」；「幂等性」；「试运行模式：提供 `--dry-run`」；「可观测性：提供 `--debug`」；「上下文高效：提供 `--fields`」；「明确错误码：命令失败时返回明确错误码」。
- 4.4 MCP：「直接提供 MCP 接口，或者至少提供便于 MCP 封装的接口」；「自描述」「可发现」「结构化输入输出…使用 JSON Schema 明确定义类型和约束」。
- 4.4 结论：「格式稳定、错误码可检索、文字朴素：这些传统的『好日志』标准，恰好也是 Agent 友好的标准。」
- 4.5：「接口即契约，发布即承诺」；兼容做法「**只增不改**：已有字段的编号、类型保持原样，新字段用下一个编号追加」；函数增加有默认值的参数属源码兼容。

## 4. MCP 实现状态

- 课件 4.3 把 MCP 作为 Agent 接口的正式形态（JSON-RPC 2.0 over stdio、`initialize`、`tools/list`、`tools/call`）。
- LWT 已有 `lwt/lsp_protocol.py` / `lwt/lsp_server.py`（290 行，Content-Length 封帧）与 DAP 经验；MCP 用**行分隔 JSON**，封帧方式不同，**没有**直接复用 LSP 的帧解析。
- **已实现**：`lwt/mcp_server.py`（标准库，无 SDK），实现 `initialize` / `tools/list` / `tools/call` 三个方法，暴露三个工具：

| 工具 | 作用 | 复算命令 |
|---|---|---|
| `lwt_check` | 静态检查，返回 `--check --format=json` 的同一份 JSON | `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \| python -m lwt.mcp_server` |
| `lwt_run` | 执行程序，返回 `exit_code/stdout/stderr` | 同上，`tools/call` + `{"name":"lwt_run","arguments":{"path":"examples/guide/hello.lwt"}}` |
| `lwt_profile` | 跑 `--profile` 并返回 schema/事件数/覆盖键摘要 | 同上，`lwt_profile` |

- **边界（必须如实说）**：只做了**协议级**测试（8 项：握手、工具清单、真实执行、静态诊断、profile 摘要、未知工具/方法/路径的 JSON-RPC 错误）。**没有**接入真实 MCP 宿主做端到端演示，所以不能声称“已在 Claude/Cursor 等宿主中验证”。
- 不改变任何既有 CLI 行为：MCP 是独立入口 `python -m lwt.mcp_server`，内部只调用公开 CLI。

## 5. 一句话总结

LWT 的 CLI 不是“专门为 Agent 设计的接口”，但它满足课件 4.4 里最关键的几条：**退出码合同 + 数据/诊断分流 + 结构化 JSON + 可重复执行**，并通过 `python -m lwt.mcp_server` 提供了协议级可用的 MCP 入口。仍然缺的是 `--fields` 与 `--debug` 两个开关，以及“在真实 MCP 宿主里端到端跑过”的证据；这些在本文与答辩卡里都标注为未实现/未验证，不计入“已完成”。
