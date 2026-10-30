# S28 执行报告：LWT 源码级追踪与覆盖率可视化

**状态：实施完成，等待主窗口审查；S12 未开始。** 本阶段在 S27 静态检查工具之后增加运行时可观察性，不增加 LWT 源语言语法，不修改 LWT 程序的可观察执行结果，不修改日志应用本身或既有语言黑盒用例。

## 1. 基线、分支和提交

- S27 实现 tip：`bf7bb01684144bbc392191cb0c92580dc9e2c416`；报告自包含修正提交：`e9fa8f4eaf2289215a53bb6b9e990efd638a23a5`。修正只补齐 S27 报告中的完整提交表和 S27 阶段 tip，不改写 S27 实现历史。
- S28 从修正后的 S27 tip `e9fa8f4eaf2289215a53bb6b9e990efd638a23a5` 创建分支 `stage/s28-execution-observability`。开工时分支、HEAD 与上述基线一致，工作区干净；执行期间未 fetch、pull、push、merge、rebase、reset、改写 main、打标签或发布。
- S28 实现、测试/证据和一般文档按职责分层提交：

| 提交 | 内容 |
|---|---|
| `f9667325fb6f01fdff4e7c059e884381745bb950` | observer、覆盖静态清单、runtime hook 与 profile-only 模块哈希 |
| `b3043085da977d5841feb86aabb7f9ff1a722936` | `--profile` CLI、原子写入和 schema v1 严格校验 |
| `dfa44b79748ff7cb1685722405f1933fefc18030` | renderer、merge、固定 app runner；修正变异工具短路探针锚点 |
| `e65cb881d9a5304ee268f49c8a2105f037e74cb7` | 19 项 profile 定向测试与固定 JSON/HTML 证据 |
| `a0158762eff25b6e885c5dfb2cfcf3802ef9cba6` | 使用文档、指南、项目状态和 S12 交接规则 |

本报告与路线图 S28 结果段作为最终文档提交，接在上表最后一项之后；最终完整分支 tip SHA 与 clean status 由本次执行交接中的 `git rev-parse HEAD` / `git status -sb` 给出。该报告提交不改写以上历史。

## 2. 实现设计与行为边界

`lwt/observability.py` 从完整且成功加载的 `ModuleGraph` 扫描 AST，生成稳定的静态 ID、函数/语句/decision 分母和运行事件；`ProfileCollector` 只接收解释器显式通知，不检查 Python 帧、不求值额外表达式、不调用 LWT 值显示函数、不序列化局部值。`lwt/runtime.py` 通过可选 observer 参数发出语句、调用/返回、decision、recover、运行错误和程序结束事件。observer 默认为 `None`，未启用时不创建全局状态、不共享跨进程数据。S28 没有使用 `sys.settrace()`：宿主 Python 栈不能准确表示 LWT 模块、浅快照 each、语言函数及 attempt/recover 的控制边界。

`lwt/modules.py` 仅在 profile 模式计算各模块原始 UTF-8 源字节 SHA-256；普通加载不增加散列读取。`lwt/cli.py` 增加 `--profile PROFILE SOURCE [-- PROGRAM_ARGS...]`：档案写入采用同目录临时文件和原子替换；输出路径在执行前检查，不能为 `-` 或入口/依赖模块。成功执行保持原 stdout/stderr 和码 0；未处理 RuntimeError/3 写出已有事件档案后仍返回 3，诊断保持原文；CLI/词法/语法/模块预加载失败发生在执行前，不创建部分档案；profile 写入错误为工具 FileError/4。若程序执行产生副作用后发生不可预见的最终写入故障，工具无法撤销副作用，该限制已写入使用文档。

Schema v1 固定事件序号、路径、类型、字段和覆盖汇总，拒绝重复 JSON key/节点 ID、未知字段、未知版本、绝对路径、错误摘要或事件与静态清单不一致。单次运行事件种类为 `program_start`、`statement`、`function_call`、`function_return`、`decision`、`recover`、`runtime_error`、`program_end`。函数返回分 explicit/natural，不记录返回值；RuntimeError 逸出不伪造 return。档案不存变量、参数、stdin、文件内容、Python 栈、对象地址、绝对路径、时间戳或机器标识；用户通过 `fail(message)` 提供的消息在档案中使用固定脱敏文本，普通 CLI 诊断仍保持原消息。

分母由静态模块 AST 得出：语句包括 let/表达式/emit/return/break/continue/attempt/when/while/each；函数包括所有模块函数；decision outcomes 包括 when then/otherwise、while true/false、each empty/nonempty、and/or short_circuit/evaluate_right 和 attempt normal/recovered。块和声明不计入可执行语句。break 不会冒充 while false，each 的分支依据进入循环时浅快照是否为空。total=0 的 percentage 为 null。覆盖率只说明指定场景经过的节点，不能证明正确性或完整规范覆盖。

`tools/render_lwt_profile.py` 只用标准库严格验证 profile 并输出确定性、离线 HTML；对可解析到的本地源码校验 SHA-256，不展示源码内容，全部动态文本经过 HTML 转义。`tools/merge_lwt_profiles.py` 要求模块哈希和静态清单一致，累计计数，保留每次运行独立事件序列；顶层 merged events 为空。`tools/run_app_profile_scenarios.py` 使用公开 CLI 固定执行日志应用的默认和组合筛选场景，并逐字比较无 profile / profile 两种模式的 stdout、stderr、退出码。

## 3. 演示档案与逐字输出证据

### 3.1 模块、函数与错误恢复示例

命令：

```powershell
python -m lwt examples/modules/main.lwt
python -m lwt --profile $env:TEMP\lwt-s28-modules-profile.json examples/modules/main.lwt
python -m lwt --profile reports/error-recovery-profile.json examples/error_recovery/main.lwt
python tools/render_lwt_profile.py reports/error-recovery-profile.json --output reports/error-recovery-profile.html
```

两种模块示例命令的 stdout 逐字均为 `demo:2\n`，stderr 为空，退出码 0。错误恢复样例实际 stdout 为：

```text
2
division by zero
Error{category: "RuntimeError", message: "division by zero", source: "math.lwt", line: 2, column: 17}
4
remaining values processed
```

stderr 为空、退出码 0；profile 包含 2 个模块、26 个事件、8/8 语句、1/1 函数及 3/4 decision outcomes。JSON 为 8,161 bytes，HTML 为 9,508 bytes。库函数限定调用、恢复事件与后续语句保留在同一顺序事件序列；样例中有一个未覆盖的 attempt outcome，故 decision 不是 100%。档案当前 SHA-256：入口 `81ab669463e1c24af6a6df4fa5f740ca9d29cd31ac4d490193a5cba2035ebc56`，`math.lwt` `68e17aaf9ccea603699485d882355720f8ceceede9075c551424b5876cd2ed56`。本阶段没有以未运行的 GUI 或 PPT 演示替代 CLI 证据。

### 3.2 LWT 日志分析器固定场景

公开命令为 `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` 和 `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2`；本轮也由独立 runner 在有/无 profile 两种模式下逐字核对输出契约。默认 stdout 为：

```text
LWT log report
Total lines: 7
Valid records: 6
Malformed lines: 1
Matched records: 6
Level counts:
ERROR|2
INFO|2
WARN|2
Top modules:
cache|2
api|1
auth|1
db|1
web|1
Matching examples (first 3):
2026-10-07T10:00:00Z|INFO|auth|login accepted
2026-10-07T10:00:01Z|WARN|cache|eviction started
2026-10-07T10:00:02Z|ERROR|db|connection lost
```

组合筛选 stdout 为：

```text
LWT log report
Total lines: 7
Valid records: 6
Malformed lines: 1
Matched records: 1
Level counts:
WARN|1
Top modules:
cache|1
Matching examples (first 3):
2026-10-07T10:00:03Z|WARN|cache|retry scheduled
```

两场景 stderr 均为空、退出码均为 0。profile runner 本轮实际汇总：默认 stdout 336 bytes，语句 112/173、函数 13/20、decision outcomes 55/102；`WARN + retry + top=2` stdout 204 bytes，语句 143/173、函数 18/20、decision outcomes 58/102。合并档案为 2 次独立运行，JSON 297,052 bytes，HTML 249,837 bytes，事件序列分组保持独立。应用源码 SHA-256 为 `0fb8fff2fee3a4834c5f7fbe774dd178c7461fdf505fdbbd8be05026b3d68572`。

## 4. 测试和机器可复核

执行环境：Windows 11 build 26200，CPython 3.13.7。以下为 S28 最终代码提交后的本轮实际验证；S28 工具测试不计入 287 项 LWT 语言黑盒。

| 命令/检查 | 退出码 | 本轮结果 |
|---|---:|---|
| `python -m unittest discover -s tests -q` | 0 | 357 项通过，66.157 秒 |
| `python -m unittest discover -s tests -p "test_execution_profile.py" -v` | 0 | 19 项通过 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 0 | 原 S10 应用契约 25 项通过 |
| `python -m unittest discover -s tests -p "test_modules.py" -q` | 0 | 9 项通过 |
| `python -m unittest discover -s tests -p "test_runtime.py" -q` | 0 | 11 项通过 |
| `python tools/run_tests.py` | 0 | 287/287；各类数量为 32/43/13/43/40/3/52/30/31，elapsed 48.282 秒 |
| `python tools/check_project_integrity.py` | 0 | `cases=287; matrix_links=384; referenced_cases=287` |
| `python -m compileall -q lwt tests tools bench app` | 0 | 编译通过 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0 | 246 行有效 LWT |
| `python tools/run_semantic_properties.py` | 0 | seed `20261028`，150 表达式 + 6 项语义性质，156 checks、7 个 CLI 程序通过；hash `6d4f42d5db1e00ee555f2e915d989d20c6779fa7b467490e352d6b4e03a07ce0` |
| `python tools/audit_semantic_mutants.py` | 0 | 9 killed、1 survived、0 equivalent、0 invalid；保留 S23 的一个对称参数顺序存活探针 |
| `python tools/run_app_profile_scenarios.py` | 0 | default 336-byte stdout，112/173 语句、13/20 函数、55/102 outcomes；组合筛选 204-byte stdout，143/173、18/20、58/102；stderr 空、exit 0；合并 JSON 297,052 bytes、HTML 249,837 bytes，2 组事件序列分离 |
| `python -m lwt examples/modules/main.lwt` 与 `python -m lwt --profile <temp> examples/modules/main.lwt` | 0/0 | 两者 stdout 均为 `demo:2\n`，stderr 均空；逐字 byte tuple 相等 |
| `python -m lwt --profile reports/error-recovery-profile.json examples/error_recovery/main.lwt` | 0 | 26 events；stdout 与 §3.1 完全一致；stderr 空 |
| 临时源码公开 CLI 未处理 RuntimeError 档案复现 | 3 | stdout 空，原诊断 `RuntimeError: division by zero`，profile 状态/码为 `runtime_error`/3，含 4 个事件且无 traceback |
| 独立 profile 复算脚本 | 0 | app 与 recovery JSON 均通过 schema；节点 ID 唯一、每组序号连续、hit/call/outcome 计数与 events 一致、覆盖摘要重算一致，所有模块 SHA-256 与当前源字节匹配 |
| 对两个固定 JSON 重新渲染 HTML 并逐字节比较 | 0 | 两份 HTML 均确定；app SHA-256 `0959f83dd43ef4b263dcc37d6d0a4dc84f4dac23cac1cdb4abc9c00a93af29c0`，recovery SHA-256 `bf93b8083927dabe12ca06bc23b62869212592e65e12dc08a6d1a2718818c83d` |
| 修改/新增 Markdown 相对链接与围栏检查 | 0 | 检查 11 个 Markdown 文件、632 个本地链接；无缺失目标、无未闭合围栏 |
| S28 基线保护路径 `git diff --quiet e9fa8f4... -- <protected paths>` | 0 | 无差异 |
| `git diff --check e9fa8f4...` | 0 | 无空白错误；仅有 Git 的 LF→CRLF 提示 |

HTML renderer 与 merge 共用严格 validator。安全性测试还核对重复 JSON key、错误 JSON、未知 schema、重复节点 ID、计数矛盾、可用源 hash 不匹配和 HTML 特殊字符转义；profile 收集器构造/序列化异常通过 CLI 单行返回 FileError/4，不泄漏内部异常文本或 traceback。profile 文件不含临时绝对路径或 `fail(message)` 用户文本；普通与 profile 模式应用 stdout/stderr/退出码由固定 scenario runner 逐字比较。

## 5. 修改文件

本阶段最终修改的 28 个文件如下（与 S28 基线比较；生成报告为确定性固定产物）：

| 分组 | 文件 |
|---|---|
| runtime observer 与 CLI/schema | `lwt/observability.py`、`lwt/profile_schema.py`、`lwt/cli.py`、`lwt/modules.py`、`lwt/runtime.py` |
| 工具 | `tools/render_lwt_profile.py`、`tools/merge_lwt_profiles.py`、`tools/run_app_profile_scenarios.py`、`tools/audit_semantic_mutants.py` |
| 测试 | `tests/test_execution_profile.py` |
| 固定 profile 证据 | `reports/app-lwt-profile.json`、`reports/app-lwt-profile.html`、`reports/error-recovery-profile.json`、`reports/error-recovery-profile.html` |
| 使用/实现文档 | `docs/execution-profile.md`、`README.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/test-matrix.md`、`docs/language-spec.md`、`app/README.md` |
| 阶段状态与记录 | `docs/s28-execution-observability.md`、`docs/s12-final-delivery-plan.md`、`docs/agent-dev-log.md`、`project.md`、`阶段执行与审查路线图.md`、`详细实施规划.md`、`LWT大作业总体方案与复检.md` |

## 6. 保护范围、限制与交接

相对 S28 基线逐项核对且保持不变：`app/log_report.lwt`（246 行有效 LWT）、`tests/test_app.py`（25 项 S10 CLI 契约）、`reports/app-concurrency.json`、`docs/app-concurrency.md`、`bench/results.json`、`reports/performance.md`、`tests/cases/`、`lwt/` 以外正式黑盒/规范相关文件。没有运行并发原始记录生成器或正式 benchmark。

profile 记录与写盘会产生显著额外开销，绝不用于 S11 性能结论；S11 原始测量不与 profile 模式混合。profile 的计数模型不含 MC/DC、路径覆盖和隐式异常边。Python 3.10、Linux 和远端 Actions 是否运行均需以本环境能否实际调用为准；没有实测时会明确列为未验证。S10 并发证据保持历史状态。S28 不做桌面 GUI 人工验收，不制作 PPT，不合并/推送，不开始 S12。

阶段完成后停止在 `stage/s28-execution-observability`，保持工作区干净，结论为“实施完成，等待主窗口审查”。S12 仍未开始。
