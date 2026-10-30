# S27 执行报告：模块感知静态检查与机器可读诊断

**状态：实施完成，等待主窗口审查。** 本阶段增加运行前开发工具，不增加 LWT 源语言语法、不执行被检查程序、不开始 S12。

## 1. 基线、分支和提交

- S26 原最终提交：`451f55a4c60dbb50a21f30788a3b79463d9c0b4d`。
- 在 S26 原分支单独补写其自身提交记录中的最终 SHA，提交为 `9006119fc6c98f151244ef06608d72730da1071e`（`docs: make S26 final SHA self-contained`）。该提交只修正 `docs/s26-runtime-recovery.md`，未改写 S26 历史。
- S27 分支：`stage/s27-static-checker`，从更正后的 S26 tip `9006119fc6c98f151244ef06608d72730da1071e` 创建；S27 工作开始时工作区干净。
- S27 分层提交如下；最终报告提交之后的最终 HEAD 以执行窗口交接中的 `git rev-parse HEAD` 为准。

| 提交 | 内容 |
|---|---|
| `9daf5a0b3c8ed908872032a82eaa4e9049781a33` | `feat: add module-aware static checker CLI` |
| `6ac25ed7cae0af565ad8c532490c9f8de05f09ef` | `test: cover static checker and check CLI` |
| `16da1bf541cca818990a52fc737ec08f655e2d7b` | `test: add stable static diagnostic fixture` |
| 后续阶段提交 | 本报告与文档状态同步；SHA 见执行交接的 `git log` |

本阶段没有 fetch、pull、push、merge、rebase 或改写已有提交。远端未同步；S12 未开始。

## 2. 实现范围与诊断契约

`python -m lwt --check SOURCE` 复用严格 UTF-8 读取、lexer、parser 和现有模块图，扫描入口与全部静态导入模块中的完整 AST。`python -m lwt --check --format=json SOURCE` 输出版本 1 JSON。检查器不调用 `runtime.execute()`，不求值 LWT 表达式，不消费程序 stdin，也不运行 `emit`、`input()`、`read_text()`、`fail()` 等操作。普通 `python -m lwt SOURCE [-- PROGRAM_ARGS...]` 继续走原执行分支。

静态码固定为 `STC001`/`STC002`/`STC003`（重复函数、重复 record、函数与内置名冲突）、`STC010`/`STC011`（未知函数、函数/内置/模块函数参数数量）、`STC020`–`STC023`（record 类型与构造字段）、`STC030`/`STC031`（模块 alias/member）、`STC040`/`STC041`（变量可见性、同作用域重复 let）。静态诊断类别为 `StaticError`，severity 为 `error`，退出码 2。加载或语法阶段原错误类别与退出码不变；JSON 稳定码为 `CLI001`、`SRC001`、`LEX001`、`PAR001`、`MOD001`。无错误退出 0，CLI/文件/模块加载错误退出 4。详细诊断消息、位置和 JSON key 顺序见[静态检查器说明](static-checker.md)。

作用域按现有 runtime 规则建立：函数局部不捕获调用者；参数与函数最外层 body 共用一层；显式块另建作用域；each 绑定和 recover 错误名位于其 body 的父作用域；record 类型仅在入口可见。直接 `let` 名称采用保守静态可见集合，初始化表达式隐藏当前待建绑定并继续查找外层。检查器不做类型推断、可达性分析或路径敏感 definite-assignment 证明；“可能尚未执行/初始化”不会被报告成确定错误。

模块限定调用的 alias/member 解析由 `lwt/modules.py` 的共享 helper 提供，正常 runtime 预链接和静态分析共用。内置函数 arity 单独集中在 `lwt/builtin_signatures.py`；runtime 的既有内置名集合从该签名表派生。此处只共享静态链接结果与函数签名，不改变运行时求值顺序或副作用。

## 3. 真实 CLI 结果

从仓库根执行：

```text
python -m lwt --check examples/modules/main.lwt
exit: 0
stdout: Check passed: 3 source file(s).\n
stderr: <empty>

python -m lwt --check --format=json examples/modules/main.lwt
exit: 0
stdout: {"schema_version":1,"ok":true,"files_checked":3,"diagnostics":[]}\n
stderr: <empty>

python -m lwt --check app/log_report.lwt
exit: 0
stdout: Check passed: 1 source file(s).\n
stderr: <empty>

python -m lwt examples/modules/main.lwt
exit: 0
stdout: demo:2\n
stderr: <empty>
```

稳定错误夹具为 [`tests/fixtures/static-checker/undefined-function.lwt`](../tests/fixtures/static-checker/undefined-function.lwt)。公开 CLI 的精确结果：

```text
python -m lwt --check tests/fixtures/static-checker/undefined-function.lwt
exit: 2
stdout: <empty>
stderr: tests/fixtures/static-checker/undefined-function.lwt:1:6: StaticError[STC010]: undefined function 'missing'\n

python -m lwt --check --format=json tests/fixtures/static-checker/undefined-function.lwt
exit: 2
stdout: {"schema_version":1,"ok":false,"files_checked":1,"diagnostics":[{"code":"STC010","severity":"error","category":"StaticError","message":"undefined function 'missing'","source":"tests/fixtures/static-checker/undefined-function.lwt","line":1,"column":6}]}\n
stderr: <empty>
```

另外使用临时源文件真实启动文本和 JSON 两种模式；文本诊断退出 2、stdout 空，stderr 指向临时源的 `:1:6` 并带 `StaticError[STC010]`；JSON 诊断退出 2、stderr 空，stdout 是完整 schema 1 对象。`test_static_checker.py` 进一步断言固定夹具两种模式的完整字节输出，以及 lex/syntax/file/CLI/import 错误分类、位置和退出码。

## 4. 修改文件

本阶段提交修改：

| 文件 | 内容 |
|---|---|
| `lwt/analyzer.py` | 独立、无副作用 AST/模块图分析器及确定排序 |
| `lwt/builtin_signatures.py` | 十个内置函数的名字/参数数目签名 |
| `lwt/cli.py` | `--check`、文本诊断与紧凑 JSON schema；普通执行维持原路径 |
| `lwt/modules.py` | 提供共享模块限定调用解析 helper |
| `lwt/runtime.py` | 复用内置签名和模块 alias/member 解析；不改 evaluator 语义 |
| `tests/test_static_checker.py` | 20 项静态分析、CLI 子进程、作用域/模块/JSON/无执行测试 |
| `tests/fixtures/static-checker/undefined-function.lwt` | 稳定 STC010 文本/JSON CLI 夹具 |
| `docs/static-checker.md` | 能力范围、稳定码、作用域、非目标和 JSON schema |
| `docs/language-spec.md` | 仅补充 CLI 开发工具及其与源语言语义的边界 |
| `docs/developer-guide.md` | 加入运行前检查工作流 |
| `README.md` | 阶段状态、CLI 示例、工具说明索引 |
| `app/README.md` | 将应用 CLI 与不执行应用源码的检查命令区分 |
| `.agents/skills/lwt-app/SKILL.md` | Agent 先检查再运行的推荐流程 |
| `docs/test-matrix.md` | 单列工具 unittest；明确不计入 287 项语言黑盒 |
| `project.md` | S27 待审查状态、检查命令和 S12 前置关系 |
| `阶段执行与审查路线图.md` | 增加 S27，并把审查顺序更新为 S23–S27 后进入 S12 |
| `详细实施规划.md` | 文件结构、阶段状态和 S27 工具范围 |
| `LWT大作业总体方案与复检.md` | 更新收尾阶段与静态检查工具的位置 |
| `docs/s12-final-delivery-plan.md` | 将 S27 审查列为 S12 前置，并加入新克隆检查命令 |
| `docs/agent-dev-log.md` | 记录 S27 任务、实现、复核和本轮验证证据 |
| `docs/s27-static-checker.md` | 本阶段执行报告 |

S26 独立修正提交唯一修改文件为 `docs/s26-runtime-recovery.md`，将实际已核实的 S26 tip `451f55a4c60dbb50a21f30788a3b79463d9c0b4d` 写入其自有提交记录。

## 5. 实际验证

环境：Windows 11 build 26200，CPython 3.13.7。以下命令均在本轮实际运行，逐项退出码与摘要如下；Python 3.10、Linux 和远端 Actions 未在本环境验证。

| 命令 | 退出码 | 本轮结果 |
|---|---:|---|
| `python -m unittest discover -s tests -q` | 0 | 338 项通过，53.282 秒；包含 S27 定向测试 |
| `python tools/run_tests.py` | 0 | S26 原语言黑盒 287/287；S27 工具测试不加入此集 |
| `python tools/check_project_integrity.py` | 0 | `cases=287; matrix_links=384; referenced_cases=287` |
| `python -m compileall -q lwt tests tools bench app` | 0 | 无编译错误 |
| `python -m unittest discover -s tests -p "test_static_checker.py" -v` | 0 | 20 项通过 |
| `python -m unittest discover -s tests -p "test_cli.py" -q` | 0 | 108 项通过 |
| `python tools/run_semantic_properties.py` | 0 | seed `20261028`；150 个表达式 + 6 项语义性质，156 checks / 7 个 CLI 程序通过 |
| `python tools/audit_semantic_mutants.py` | 0 | 9 killed、1 survived、0 equivalent、0 invalid；存活项仍是既有对称参数顺序探针，不是 S27 造成的变化 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0 | 246 行有效 LWT |
| `git diff --check` | 0 | 无 whitespace error；Git 仅提示工作副本 LF 将规范为 CRLF |

文档自检：对本阶段所有已修改或新增 Markdown 执行相对链接存在性与代码围栏配对检查，结果为 11 个文件、618 个相对链接、120 个围栏标记，缺失链接 0、未闭合围栏 0。保护路径相对 S27 基线 `9006119fc6c98f151244ef06608d72730da1071e` 执行 `git diff --quiet BASE -- app/log_report.lwt tests/test_app.py reports/app-concurrency.json docs/app-concurrency.md bench/results.json reports/performance.md tests/cases`，退出码 0、无差异。

`python -m lwt --check examples/modules/main.lwt`、JSON 模式、`app/log_report.lwt` 检查和上节示例均由公开 CLI 实际运行。最后的报告版本会记录所有命令的最终复跑结果、修改后的 Markdown 链接/代码围栏检查、S27 基线保护路径差异及最终 `git diff --check`。

## 6. 回归及保护范围

- 原语言黑盒目录 `tests/cases/` 未修改，完整性工具仍报告 287 个配对案例、384 个矩阵链接、287 个引用案例；新测试位于 unittest 和 `tests/fixtures`。
- `app/log_report.lwt` 实际统计仍为 246 行有效 LWT；`tests/test_app.py` 未改。S10 并发原始记录/报告和 S11 性能 raw/报告未改，也未运行 `tools/run_app_concurrency.py` 或正式 benchmark。
- `lwt/runtime.py` 仅把已有内置名表改为共享签名集合，并让既有模块预链接复用新的 alias/member helper。全量语言黑盒及旧 CLI 测试作为执行/求值行为回归；未改解释求值函数、AST、parser、语言语义或黑盒结果。
- `docs/language-spec.md` 只说明检查 CLI 是开发工具，不是静态类型系统或语言语义扩展。
- 检查器诊断边界见 §2：不推断类型、不证明 definite assignment、不判断可达性或动态值。通过只表示列出的静态问题未发现。

## 7. 未验证项与交接

本轮只在 Windows CPython 3.13.7 实测。Python 3.10、Linux、远端 GitHub Actions 未运行；没有制作 PPT、没有同步远端、没有进行 GUI 验收，也没有开始 S12。S23/S26 固定 seed 性质与变异工具已在本轮复跑，保留 1 个原存活变异的事实，不将其改写为 S27 缺陷。

最终阶段报告的提交 SHA 和提交后工作区状态由执行交接中的 `git rev-parse HEAD`、`git log` 与 `git status -sb` 给出；阶段分支保持 `stage/s27-static-checker`，不合并、不推送。
