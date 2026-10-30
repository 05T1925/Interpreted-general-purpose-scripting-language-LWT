# S26 执行报告：运行时错误恢复

**状态：S26 实施完成，等待主窗口审查；未合并、未推送，S12 未开始。**

## 1. 基线与 Git 状态

- 仓库：`C:\Users\28641\Desktop\大三上\程序设计实践\大作业`
- S25 基线：`5e694a22512346d845434824c0785ccecc7c8628`，分支 `stage/s25-modules`；开工时工作区干净、该分支 tip 一致。
- 本地 `main`：`aadb8f7a2348dad3205c523d4ab1cb4ad5bda063`；S25 tip 不是本地 `main` 的祖先，因此本阶段按提示直接以 S25 tip 为父提交。
- S26 分支：`stage/s26-runtime-recovery`。目标分支原先不存在，未覆盖或重建已有分支。
- 本阶段没有 fetch、pull、merge、rebase、reset、push 或发布；远端状态没有在本阶段重新查询，S25 报告中记录的旧远端值不作为本轮实时结果。
- 最终分支 HEAD、提交列表及干净状态见本报告提交后的交接记录；本报告提交 SHA 由最终交接中的 `git rev-parse HEAD` 给出。

## 2. 实现与语义决定

新增 `attempt { ... } recover (name) { ... }`。`attempt`/`recover` 是保留字；recover 必须紧随 attempt body，中间可有空白和注释；两侧都必须是块，整条语句不加分号。recover 变量恰有一个标识符。允许嵌套，不支持 `throw`、可选/多个 handler、类型过滤、`finally`、重试或事务回滚。

运行时只捕获退出码为 3 且类别为 `RuntimeError` 的 LWT `LwtError`。异常可穿过普通块、分支、循环、用户函数和模块函数到达最近的动态 handler。词法、语法、CLI/源文件、导入图和预执行链接错误仍先于普通语句执行，不能被 attempt 捕获；宿主异常、KeyboardInterrupt、SystemExit 也不会被吞掉。return、break、continue 使用原控制流信号穿过捕获逻辑。handler 在捕获 try 块之外执行，因此 handler 的新错误只能由外层 attempt 捕获。

body 与 recover 遵循普通块作用域；错误名只在 recover 期间可见。错误发生前已经完成的输出、赋值、数组/record 修改和输入消费均保留。未捕获错误继续使用既有诊断格式、stderr、退出码 3 和此前 stdout 保留行为。

内部不可变 Error 值由 handler 创建，程序不能伪造。五个只读字段为 `category`、`message`、`source`、`line`、`column`；缺少来源/位置时用 `null`。它以对象身份比较，不能作为记录值、数组索引或 `len` 参数。已知字段赋值产生普通 RuntimeError。显示格式固定为：

```text
Error{category: "RuntimeError", message: "division by zero", source: "math.lwt", line: 2, column: 17}
```

字符串字段使用 LWT 复合字符串的同一转义规则；`str(error)` 与 `emit error;` 一致。示例和完整边界规则已写入规范第 10 节。

## 3. 变更文件

**解释器：**

- `lwt/lexer.py`：增加 `attempt`、`recover` 两个 token/保留字。
- `lwt/ast_nodes.py`：增加带关键字位置的 `AttemptStatement`。
- `lwt/parser.py`：解析 body/recover 块；沿用函数 return 上下文和循环上下文，拒绝缺块、缺 recover、独立 recover、错误参数、末尾分号等无效语法。
- `lwt/runtime.py`：实现限定捕获、handler 作用域、Error 值字段读取/只读赋值/身份相等/格式化、入口源路径回退及 AST 支持检查。
- `lwt/cli.py`：向 runtime 传递入口 CLI 源路径，使捕获值与未捕获诊断来源一致。

**测试与审计：**

- `tests/cases/error-recovery/`：40 组 `.lwt`/`.json` 配对黑盒及两个模块 fixture，覆盖语法、常见错误、Error 字段、模块路径、动态 handler、控制流、副作用、未捕获错误和预检边界。
- `tests/test_parser.py`、`tests/test_runtime.py`、`tests/test_runner.py`：新增 parser/runtime/矩阵条款单元测试；全量 unittest 从 S25 的 308 增至 318（增加 10 项）。
- `tools/run_tests.py`：允许黑盒元数据引用正式规范第 10 节。
- `tools/audit_semantic_mutants.py`：将复合值身份变异探针更新为识别包含 `_ErrorValue` 的身份比较分支，保持对数组和 record 的变异检测有效。

**示例与文档：**

- `examples/error_recovery/main.lwt`、`examples/error_recovery/math.lwt`：展示模块函数除零、捕获、错误值输出和继续遍历。
- `docs/language-spec.md`、`docs/test-matrix.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`README.md`、`project.md`、`详细实施规划.md`、`LWT大作业总体方案与复检.md`、`阶段执行与审查路线图.md`、`docs/s12-final-delivery-plan.md`、`docs/agent-dev-log.md`：同步语义、覆盖与阶段状态。
- `docs/s26-runtime-recovery.md`：本阶段证据报告。

## 4. 黑盒覆盖

S25 的 247 项基础上增加 40 项错误恢复用例，S26 总数为 287：`arrays-records-each` 32、`builtins-text-io` 43、`cli-errors` 13、`control-functions` 43、`error-recovery` 40、`integrated` 3、`lexer-parser` 52、`modules` 30、`values-operators` 31。282 项执行配对 LWT 源程序；5 项测试 CLI argv override。

新增用例 ID：

- 语法/关键字/正常路径：`attempt-comments-between-blocks`、`attempt-empty-blocks`、`attempt-missing-recover`、`attempt-normal-flow`、`attempt-requires-blocks`、`attempt-reserved-module-alias`、`attempt-reserved-variable`、`attempt-semicolon-rejected`、`recover-parameter-one-only`、`recover-parameter-required`、`recover-reserved-function`、`recover-standalone-rejected`。
- RuntimeError 与 Error 值：`recover-array-bounds`、`recover-division-by-zero`、`recover-error-display-unicode`、`recover-error-fields-display`、`recover-error-identity`、`recover-error-index-type`、`recover-error-len-type`、`recover-error-not-record-type`、`recover-readonly-error-fields`、`recover-type-error`、`recover-undefined-variable`、`recover-unknown-error-field`。
- 动态传播、控制流和副作用：`recover-each-break`、`recover-each-continue`、`recover-handler-error-not-self-caught`、`recover-handler-error-outer`、`recover-nearest-handler`、`recover-preserves-side-effects`、`recover-return`、`recover-user-function`、`recover-variable-scope`、`recover-while-break`、`recover-while-continue`。
- 不捕获的预检错误、模块来源与未处理契约：`recover-import-error-not-caught`、`recover-lex-error-not-caught`、`recover-module-chain-source`、`recover-syntax-error-not-caught`、`recover-unhandled-runtime-keeps-output`。

公开 CLI 案例比较退出码、完整 stdout/stderr、稳定诊断路径/行列和 Error 显示，不用仅检查 Python runtime 单元来替代端到端契约。矩阵完整性实测 `cases=287; matrix_links=384; referenced_cases=287`。

## 5. 示例实测

环境为 Windows 11 build 26200、CPython 3.13.7。命令：

```powershell
python -m lwt examples/error_recovery/main.lwt
```

退出码 0，stderr 为空，stdout 逐字为：

```text
2
division by zero
Error{category: "RuntimeError", message: "division by zero", source: "math.lwt", line: 2, column: 17}
4
remaining values processed
```

`python -m lwt examples/modules/main.lwt` 退出码 0，stdout 为 `demo:2\n`，stderr 为空；`python -m lwt examples/loop_control.lwt` 退出码 0，stdout 为 `1\n3\n2\n[1, 2, 3, 4]\n`，stderr 为空。`python tools/count_lwt_lines.py app/log_report.lwt` 报告 246 行有效 LWT。

## 6. 实际验证结果

| 命令 | 退出码 | 实际结果 |
|---|---:|---|
| `python tools/run_tests.py` | 0 | 287/287 通过、0 失败；`error-recovery=40/40`，其余分类均全通过；36.902 秒。 |
| `python tools/check_project_integrity.py` | 0 | `cases=287; matrix_links=384; referenced_cases=287`。 |
| `python -m unittest discover -s tests -q` | 0 | 318 tests，52.671 秒，OK。 |
| `python -m unittest tests.test_parser tests.test_runtime tests.test_runner -q` | 0 | 60 tests，0.126 秒，OK。 |
| `python -m compileall -q lwt tests tools bench app` | 0 | 编译检查通过。 |
| `python tools/run_semantic_properties.py --seed 20261028 --cases 150` | 0 | 150 个表达式 + 6 个模板 = 156 项性质检查、7 个 CLI 程序通过；oracle SHA-256 `6d4f42d5db1e00ee555f2e915d989d20c6779fa7b467490e352d6b4e03a07ce0`。 |
| `python tools/audit_semantic_mutants.py`（首次） | 1 | 8 killed、1 survived、1 invalid；S26 增加 Error 比较类型后，旧结构相等探针未命中目标源码，属审计器适配问题。 |
| `python tools/audit_semantic_mutants.py`（修订后） | 0 | 9 killed、1 survived、0 equivalent、0 invalid；存活探针仍为旧 `call-arguments-evaluate-right-to-left` 对称效果案例，新不对称案例仍击杀同类变异。 |
| `python -m lwt examples/error_recovery/main.lwt` | 0 | 见第 5 节精确输出。 |
| `python -m lwt examples/modules/main.lwt` | 0 | `demo:2\n`。 |
| `python -m lwt examples/loop_control.lwt` | 0 | `1\n3\n2\n[1, 2, 3, 4]\n`。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0 | 246 行有效 LWT。 |
| `git diff --check` | 0 | 工作区补丁无空白错误。提交后的 `git diff --check 5e694a22512346d845434824c0785ccecc7c8628...HEAD` 也在最终提交后复核。 |
| Markdown 链接/围栏与 Skill frontmatter 检查（12 份本阶段文档） | 0 | 扫描 675 个相对链接，0 断链、0 未配对代码围栏；Skill frontmatter 为 OK。 |
| S10/S11 保护路径对 S25 基线的 `git diff --quiet ... -- <六条路径>` | 0 | `app/log_report.lwt`、`tests/test_app.py`、`reports/app-concurrency.json`、`docs/app-concurrency.md`、`bench/results.json`、`reports/performance.md` 均无差异。 |
| `rg -n "\beval\s*\(|\bexec\s*\(" lwt` | 1 | 无匹配；未新增 Python `eval()`/`exec()` 调用。 |
| `py -0p` | 0 | 本机登记 Python 3.13.7、3.11.16、3.12；无 Python 3.10。实际阶段测试使用 CPython 3.13.7。 |

有一次 S26 初期定向 unittest 因新增测试类边界令两项既有 composite mutation 测试缺少 helper 而失败；补齐测试 helper 后，定向 60 项及全量 318 项均通过。此为测试组织问题，没有改动生产语义来迁就测试。

## 7. 保护范围、实现约束与未验证项

S26 没有修改 `app/log_report.lwt`、`tests/test_app.py`、S10 并发原始记录/报告或 S11 正式性能原始数据/报告。未运行 `tools/run_app_concurrency.py` 或 `tools/benchmark.py`。LWT 执行仍通过手写 lexer/parser/AST/runtime；未新增 `eval()`/`exec()`，也没有更改 Python 全局递归上限。阶段差异以最终基线对比命令为准。

Python 3.10、Linux、远端 GitHub Actions 未在本阶段验证；远端没有重新查询。没有开展 GUI 人工验收，因为本阶段只涉及语言运行时和文档。S12 尚未开始。S26 后建议冻结语言功能；后续只处理审查发现的必要修复和 S12 最终验收/交付。

## 8. 提交与工作区

阶段按实现、测试/审计、规范/指南/示例/状态、最终报告分层提交：

1. `b6715782e195be554a48783c025d2ebc632665de` — `feat: add bounded runtime error recovery`。
2. `682eafe009d23a4f497c34513cada3774d008729` — `test: cover runtime recovery semantics`。
3. `3dfcf84711b2b47ca00acc98939e6cace140bca0` — `docs: specify and demonstrate runtime recovery`。
4. `451f55a4c60dbb50a21f30788a3b79463d9c0b4d` — `docs: record S26 runtime recovery evidence`（S26 最终提交）。

S26 阶段最终 SHA 为 `451f55a4c60dbb50a21f30788a3b79463d9c0b4d`；当时分支 `stage/s26-runtime-recovery` 工作区干净，未合并或推送。
