# S42 执行窗口报告：LWT 0.2 语言核心本质性增强

日期：2026-11-07。阶段主题：S42 —— LWT 0.2 语言核心增强（映射类型 `dict`、结构化错误传播 `throw`/`finally`、交互 REPL、运行时画像）。本报告是**执行窗口**的工作报告；按任务书边界，本阶段**不推送、不合并、不打标签**，交主窗口复核。报告中的状态分层：执行实现 / 主窗口审查 / 合入 main / 远端 CI / 现场人工 GUI 验收分别记录，不能由一个推断另一个。

## 1. 阶段与范围

### 1.1 承接在制品的基线裁决（§0.3）

任务书规划窗口记录的工作树快照为 `milestone/final-acceptance @ f1b7fa9…`，但执行窗口开工时**实际状态**为：

- 当前分支 `feature/lwt-core-0.2`（分支名正是任务书 §10 指定的目标），`HEAD = main = origin/main = 5027860efc8a1cce342ca13b1434d7724aeeffc4`，`main..HEAD` 为空；
- 工作树**不干净**：22 个已跟踪文件被修改（+1005/−29 行），并有 `examples/dicts.lwt`、`examples/throw_finally.lwt`、`bench/dict_counts.lwt`、`tests/test_repl.py`、`tests/cases/dict-maps/`（43 对 .lwt/.json）等未跟踪文件；
- `milestone/final-acceptance`（含 S12 收口文档）指向 `f1b7fa9…`，**不在当前工作树 ancestral HEAD 上**。

这是一份**先前执行窗口留下的未提交 S42 在制品**（覆盖 Wave A/B/C 的实现），且文件 mtime 全部停留在当日 01:51–02:19，而执行窗口开工于 10:00 后，确认无并发写入。按 `AGENTS.md`「发现未提交文件须保留现场、不清理/重置/覆盖」与任务书 §0.3「不得在脏工作树上开工、不得重置/覆盖/清理既有未提交文件」，执行窗口**先行停止并请用户裁决**，经明确授权「接手在制品收尾」后，才在该工作树上继续。

**所选基线 SHA：`5027860efc8a1cce342ca13b1434d7724aeeffc4`（即 `main` / `origin/main`）。** 理由：`feature/lwt-core-0.2` 正是从这一已审查主线切出；S12 收口分支 `milestone/final-acceptance` 尚属独立文档收口线，其 4 个 `docs(final)` 提交未合入 `main`，且 S42 是语言核心增强、与 S12 收口文档正交；以 `main` 为基线符合 `repository-workflow.md` 的「从已审查主线创建功能分支」规则，也避免在未审查文档分支上叠加大规模语言改动。本阶段所有提交均在 `feature/lwt-core-0.2` 上累积，**不改写历史、不强推、不 reset**。

### 1.2 范围与未完成项

完成：Wave A（dict）、Wave B（throw/finally）、Wave C（REPL）、Wave D（性能画像，只测量不优化）、应用改造（log_report.lwt 用 dict 且输出字节不变）、S42 报告与文档同步、error() 一致性最小修复。

未完成/未验证（不虚报）：Python 3.10 本机实测、Linux 实测、远端最终 SHA 的 Actions 四格、现场人工 GUI 验收（沿用 S12 收口阶段记录的桌面遮挡与 `cua-driver` 输入归属不清结论；该记录位于独立分支 `milestone/final-acceptance`，不在本基线工作树中，本阶段不改变 GUI 未验证状态）。Wave E（第三个正交应用 / LSP 能力补齐）为 P2 可选，本阶段**未实施**，理由：P0/P1 的规范/实现/测试/画像/应用改造已覆盖五项评分抓手，Wave E 的 LSP 能力或新应用会显著扩大协议与测试面，超出收口风险预算；留作后续阶段或主窗口授权范围。

## 2. Git 状态

| 项 | 值 |
|---|---|
| 基线 SHA | `5027860efc8a1cce342ca13b1434d7724aeeffc4`（`main` = `origin/main`） |
| 收口分支 | `milestone/final-acceptance @ f1b7fa9…`（未纳入本阶段基线，独立文档线） |
| 工作分支 | `feature/lwt-core-0.2`（不推送） |
| 提交序列 | 见第 6 节按可运行交付单元分组的提交清单（源码三特性同文件交织，按单元分组而非机械按 Wave；理由见 §6） |
| 远端 | 本阶段**不推送**；候选/基线远端状态以主窗口实时 `git ls-remote` 为准 |
| 工作区 | 每笔提交后 `git status -sb` 干净；保护路径差异为空 |

## 3. 设计决策

1. **dict 语法消歧（R42-02）**：新增 `TokenKind.DICT`，词法器把 `dict` 识别为保留字，parser 在 `atom` 分支先匹配 DICT，产出 `DictExpression`；因此 `dict{...}` 不会被误判为 record 类型名 `dict` 的构造，也不需要匿名 `{...}`。保留字审计（§1.1 与第 4 节）确认基线 `.lwt` 中 `dict/throw/finally/raise/map` 零匹配。
2. **dict 值语义**：插入序、`int`/`str` 键严格区分（`bool` 因 Python 的 `int` 子类型被显式拒绝）、身份相等、缺键读取报错、`each` 不直接遍历映射而用 `keys(d)`；`len` 扩展到映射；新增 `keys/values/items/has/get/put/delete` 七个内置（见规范 §4.4/§6）。
3. **throw/finally 的捕获边界**：attempt 从「仅捕获 `RuntimeError`」扩展为「捕获所有退出码 3 的 LWT 错误」，使 `throw` 字符串（`User` 类别）与 `throw error(...)`（自定义类别）可被同一 recover 捕获；词法/语法/CLI/文件/模块错误仍不可捕获，语义不变。
4. **finally 覆盖优先级（R42-03）**：finally 块置于 runtime 的 Python `try/finally` 子句中执行，利用 Python 在 `finally` 内抛出新异常/控制流信号会替换挂起转移的语义，精确实现「finally 自身抛错或 `return`/`break`/`continue` 覆盖此前挂起结果」；`problem` 只在 recover handler 作用域可见，finally 在父作用域的新子环境中执行故不可见；每个 attempt 的 finally 至多执行一次。无 finally 的旧 attempt 语义零变化。
5. **error() source 一致性最小修复**：执行窗口补齐黑盒用例时发现规范 §6/§10.6 要求 `error(category, message)` 的 `source`「取调用点」，但原实现 `location.source_path` 常为 `None`，使 Error 的 `source` 为 `null`。最小修复为在 `lwt/runtime.py` 的 `error()` 构造处加 `location.source_path or runtime.source_path` 回退（与 attempt 恢复路径已有回退一致）。该修复与 Wave A/B/C 的 `runtime.py` 改动处于同一文件、无法按整文件提交干净拆分，故随 Wave A/B/C 核心提交；但以专门的 `throw-error-builtin-source-fields` 黑盒用例单独验证 `source` 字段符合规范，不触碰保护数据。
6. **REPL 的 I/O 契约**：提示符/诊断/元命令输出走 stderr，stdout 只承载 `emit`；多行判定借鉴 `compile_command` 的不完整返回思想（词法未闭合字符串或 parser 在 EOF 处期待 token 时显示续行）；`.help/.vars/.reset/.exit/.quit` 元命令只在顶层整行生效，源码位置的点开头 token 由 parser 报语法错误；`ReplSession` 复用现有 runtime 的表结构，不新建执行引擎（见规范/指南 REPL 章节）。
7. **画像只测量不优化（R42-07/R42-08）**：`tools/micro_bench.py` 在单进程内解析一次、重复执行，分离 parse 与纯执行；产出 `reports/runtime-profile.{json,md}` 为**独立新证据**，不改 `bench/results.json` / `reports/performance.md`，不在答辩中冒充 S11 性能提升；S42 不实现 VM，S43 VM 门槛与双后端交叉验证优先规则写入报告。
8. **应用改造**：`app/log_report.lwt` 把级别/模块计数从 `Count` 数组的线性 `find_count`（O(n²)）改为 dict 的 O(1) `has/get/put`；输出阶段用 `count_array()` 从 `keys(counts)` 重建 `Count` 数组，沿用原选择排序逻辑，因此显示顺序与输出字节不变（9 组 fixture×参数逐字节比对，`reports/log-report-dict-refactor.json`）。有效 LWT 行 243（≥200）。

## 4. 运行证据

命令均在仓库根目录、Windows Python 3.13.x 执行；证据层级为**本轮 CLI 实测 / 静态审阅**，不冒充人工 GUI 或教师验收。

| 命令 | 退出码 | 关键结果 |
|---|---|---|
| `python tools/run_tests.py`（全量） | 0 | **354/354 通过**，9 类别；`error-recovery` 64/64（含 24 新增）、`dict-maps` 43/43；371.753s |
| `python tools/run_tests.py --category error-recovery` | 0 | 64/64（复核新增用例） |
| `python tools/run_tests.py --category dict-maps --category lexer-parser --category values-operators` | 0 | 126/126（复核 dict 与词法/语法/运算零回归） |
| `python tools/check_project_integrity.py` | 0 | `cases=354; matrix_links=401; referenced_cases=304`（提交 2 在 `test-matrix.md` 补充 7 个 throw/finally 代表用例链接后，由基线 394/297 增至 401/304） |
| `python -m unittest discover -s tests -q`（系统 Python 3.13.7 + Tk） | 1 | `Ran 569 tests ... FAILED (failures=1)`；唯一失败 `test_load_real_s41_witness_with_button_and_reverify`（Tk worker 超时），干净 `main` 基线对照同样失败，与 S42 无关，详见 §7。其余 568 项通过。 |
| `python -m unittest tests.test_lexer tests.test_parser tests.test_runtime tests.test_static_checker tests.test_repl -q` | 0 | 130/130，52.434s |
| `python -m unittest discover -s tests -p test_app.py -q` | 0 | 25/25，43.919s（应用 CLI 契约零回归） |
| `python -m compileall -q lwt tests tools bench app` | 0 | 无诊断 |
| `python -m lwt examples/dicts.lwt` | 0 | 插入序/键类型/内置/`<cycle>` 显示与规范 §8.7 一致 |
| `python -m lwt examples/throw_finally.lwt` | 0 | throw 字符串/Error 重抛、finally 覆盖返回 9、正常流 finally，与 §8.8 一致 |
| `printf 'let x = 1;\nemit x;\n.exit\n' \| python -m lwt --repl` | 0 | stdout 仅 `1`，提示符在 stderr |
| `python tools/micro_bench.py --out reports/` | 0 | 产出 `reports/runtime-profile.{json,md}`；9 组负载×规模输出逐次与 oracle 比对通过 |
| `python -m lwt --check app/log_report.lwt` | 0 | `Check passed: 1 source file(s).` |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0 | 243 有效行（≥200） |
| 应用改造逐字节对比（9 组） | 0 | 全部 stdout/stderr/退出码一致，见 `reports/log-report-dict-refactor.json` |
| `git diff --check` | 0 | 无空白错误 |

### 4.1 基线只读回归与全量 unittest

- **改造前基线**（承接工作树）：`python tools/run_tests.py` **330/330**（322.186s）、`check_project_integrity.py` `cases=330; matrix_links=394; referenced_cases=297`、`compileall` 无诊断，起点可用。
- **改造后全量黑盒**：`python tools/run_tests.py` **354/354**（371.753s），`error-recovery` 64/64（含 24 新增）、`dict-maps` 43/43，其余类别零回归；`check_project_integrity.py` `cases=354; matrix_links=401; referenced_cases=304`（提交 2 在矩阵中补充 7 个 throw/finally 代表用例链接后，比基线的 394/297 各增 7）。
- **全量 unittest（权威一次）**：用系统 Python 3.13.7 + Tk 8.6 跑 `python -m unittest discover -s tests -q`，`Ran 569 tests in 1265.982s`，`FAILED (failures=1)`。**唯一失败为 `test_load_real_s41_witness_with_button_and_reverify`**（`Tk worker did not settle within bounded event loop`）。该失败经干净 `main` 基线（5027860，`git worktree` 独立检出）对照重跑，**同样失败**；相关 GUI 源码与策略 LWT 与基线字节一致、`app/lwt_snake/` 无差异，故判定为**桌面环境（多窗口 + `cua-driver`）下的 Tk worker 时序问题，非 S42 回归**。其余 568 项通过。
- **全量 unittest（解释器差异说明）**：Bash 默认 `python` 为 WorkBuddy 内置 3.13.14（**无 tkinter**），用它跑全量会额外出现 `test_language_lab_entry` 的 `ModuleNotFoundError: No module named 'tkinter'` 等环境性 FAIL；该结果不采用。第 4 节 CLI/黑盒/画像实测用 Bash `python` 完成（无 Tk 不影响 CLI），全量 unittest 以系统 Python 为准。
- **失败测试的修复与复验**：基线全量里另有 3 类「新增语言特性导致旧测试断言过期」的问题（13 个 `test_runner` ERROR 源于用例 `spec_refs` 白名单未含 `10.6`；`test_cli` 的 `fn values()` 与新内置冲突；`test_semantic_properties` 模板数量 7→13；`test_runner` 硬编码 `case_count=287`）。均已最小修复并用系统 Python 单独重跑通过（`test_runner` 32/32、`test_cli` 该用例、`test_semantic_properties` 该用例均 OK），属「测试断言随语言演进适配」，不移除断言意图。详见 §7。

### 4.2 保护数据核对

`git diff --stat main...HEAD -- lwt/ docs/language-spec.md tests/cases/ docs/test-matrix.md app/log_report.lwt app/lwt_snake/ bench/results.json reports/performance.md reports/app-concurrency.json reports/app-lwt-profile.json reports/lsp-smoke.json slides/` 中，`bench/results.json`、`reports/performance.md`、`reports/app-concurrency.json`、`reports/app-lwt-profile.*`、`reports/lsp-smoke.json`、`slides/` 差异均为**空**（S10/S11/S28/S29/S12 保护数据未改）；`app/lwt_snake/` 未改。新增画像与对比证据均为 `reports/runtime-profile.*`、`reports/log-report-dict-refactor.json` 新文件。

## 5. 交付位置（需求 → 测试映射）

| 课程评分抓手 | S42 交付 | 文件/证据 |
|---|---|---|
| 解释器（20） | dict + throw/finally + REPL 三个本质增量；保留字/文法/运行时/内置/静态分析同步 | `lwt/{lexer,parser,ast_nodes,runtime,builtin_signatures,analyzer,cli,debugger_core,language_service,observability}.py`；`docs/language-spec.md` §2.1/§3/§4.4/§6/§7/§8.7/§8.8/§10.6；`examples/{dicts,throw_finally}.lwt` |
| 测试（20） | 新增 `dict-maps` 43 项 + `error-recovery` 24 项；STC042/043；REPL 14 项子进程测试；性质检查 6 条 | `tests/cases/dict-maps/`、`tests/cases/error-recovery/`（新增 24 项）、`tests/test_{lexer,parser,runtime,static_checker,repl}.py`、`tools/run_semantic_properties.py` |
| 性能（10） | 单进程微基准 + S28 事件画像 + S43 决策规则（独立证据，不改 S11） | `tools/micro_bench.py`、`reports/runtime-profile.{json,md}` |
| 指南（20） | 规范/指南/演示/Skill 同步；REPL 与 dict/throw 入口 | `docs/language-spec.md`、`docs/developer-guide.md`、`docs/demo-script.md`、`.agents/skills/lwt-app/`、`README.md`、`project.md`、阶段路线图 |
| 应用（30） | log_report.lwt 用 dict 计数，输出字节不变 | `app/log_report.lwt`（243 有效行）、`reports/log-report-dict-refactor.json`、`tools/run_app_concurrency.py` 既有证据未改 |

## 6. 提交清单（按可独立运行的交付单元分组）

> 提交 SHA 在每笔 `git commit` 后填写；本阶段**不推送**。

**与任务书 §10「每 Wave 一个独立提交」的偏差及理由**：承接的在制品把 Wave A（dict）、Wave B（throw/finally）、Wave C（REPL）的源码改动**交织在 `lwt/runtime.py`、`parser.py`、`ast_nodes.py`、`analyzer.py` 等同一文件的多个 hunk 中**，且相互依赖（如 `runtime.py` 的 attempt 分支同时含 finally 钩子与 Error 重抛；`ast_nodes.py` 同时新增 `DictExpression`/`ThrowStatement`/`finally_body`）。用 `git add -p` 机械按 Wave 拆 hunk 会产生**无法独立 import/运行的中间提交**（例如 parser 引用了尚未在同一提交加入的 AST 节点），反而违背「便于独立审查/回滚」的目的。因此按**可独立运行、可独立验证的交付单元**分组，每个提交后代码均可正常执行；这保留了任务书的分提交审查精神，同时保证每笔提交的自洽性。SC 特性在提交 1 的事务中一次落地，其测试补强（Wave B 的 24 用例）则独立成提交 2。

| 提交 | 标题 | 内容与可运行性 |
|---|---|---|
| 1 | `feat(lwt-0.2): add dict, throw/finally and REPL core` | 全部 `lwt/*.py` 源码（含 error() source 修复）、`examples/{dicts,throw_finally}.lwt`、`bench/dict_counts.lwt`、`tests/cases/dict-maps/`（43 对）、`tests/test_{lexer,parser,runtime,static_checker,repl}.py`、`tests/test_{cli,semantic_properties,runner}.py` 断言适配、`tools/{run_tests,run_semantic_properties}.py`、`docs/language-spec.md`/`static-checker.md`。提交后 330 用例 + REPL/单测可跑。 |
| 2 | `test(errors): add 24 verified throw/finally black-box cases` | `tests/cases/error-recovery/` 新增 24 对 N/B/E 用例（每条先实测并断言语义后记录 expected）、`docs/test-matrix.md` 数字 330→354 与覆盖说明。提交后全量 354 用例可跑。 |
| 3 | `perf(profile): add single-process micro-benchmark` | `tools/micro_bench.py`、`reports/runtime-profile.{json,md}`（独立证据，不改 S11）。 |
| 4 | `feat(app): refactor log_report counting with dict` | `app/log_report.lwt` dict 计数改造、`reports/log-report-dict-refactor.json`（9 组逐字节对比）。 |
| 5 | `docs: sync guides, demo, skill, status and S42 report` | `docs/{developer-guide,demo-script}.md`、`README.md`、`.agents/skills/lwt-app/SKILL.md`、`project.md`、阶段路线图、`docs/s42-execution-report.md`。 |
| 6 | `docs: correct integrity link counts` | 提交后抽检发现改造后完整性链接数应为 `matrix_links=401; referenced_cases=304`（提交 2 在矩阵补充 7 个代表用例链接后增长），把报告/`project.md`/路线图中「改造后」数字的 394/297 更正为实测值；改造前基线的 330/394/297 是历史事实，保留不变。仅文档，不重跑全量。 |

SHA 与最终 `git status -sb` 在提交后回填（见第 10 节）。

## 7. 已知问题与「未验证」清单

- **未验证**：Python 3.10 本机实测、Linux 实测、远端最终 SHA 的 Actions 四格、现场人工 GUI 验收（A–E 项沿用 S12 桌面限制）、Wave E 未实施（见 §1.2）。
- **设计边界（非缺陷）**：try/finally 采用单一 recover handler 内 `when (problem.category == ...)` 分派；不支持多个 recover 子句、类型过滤 handler、事务回滚、`finally` 之外的新控制结构；REPL 是开发工具，不改变普通 CLI 契约；画像观测有额外开销，只用于结构占比不用于计时。
- **已修复**：error() 的 source 字段一致性（§3 决策 5，随核心提交、专门用例验证）。
- **调试器/DAP/--profile/LSP**：为 dict/finally 补了 AST 遍历以保证不崩溃、不丢事件；**未新增** throw/finally 专属调试语义，按任务书要求仅保证兼容。
- **新增内置名与既有用户函数的冲突（R42-01 延伸）**：保留字审计只覆盖 `dict/throw/finally/raise/map`，但 S42 新增的**内置函数名** `keys/values/items/has/get/put/delete/error` 也进入函数命名空间。既有 `tests/test_cli.py` 的 `fn values()` 因此报「function name 'values' conflicts with a built-in」。该冲突是「用户函数不能覆盖预置函数」既有规则在新内置名上的必然结果（类似 S25 新增保留字对旧程序的影响），非实现缺陷。最小修复为把该 S6 测试里的辅助函数改名为 `values_snapshot`（断言意图不变：`each` 空数组 iterable 只求值一次、迭代作用域独立）。规范/指南/Skill 已记录新内置名约束（见 §3 决策与 `.agents/skills/lwt-app/SKILL.md`）。复现证据：`fn values() { return 1; }` 退出 3、诊断「conflicts with a built-in」；`main` 基线 `builtin_signatures.py` 无 `values` 内置，确认由 S42 引入。
- **测试断言随语言演进的适配（3 项，均已单独验证）**：① `tests/test_runner.py` 两处硬编码 `case_count == 287` 改为对 `len(self.cases)` 动态断言（新增 43+24 用例后总数为 354，硬编码会失效；动态断言保留「inventory 完整」意图）；② `tests/test_semantic_properties.py` 固定模板从 7→13 条（在制品新增 6 条确定性 dict/throw 性质检查），断言 `programs=13 checks=24`；③ 上述 `fn values()` 改名。三项均只用系统 Python 3.13.7（带 Tk）单独重跑通过，属「新增语言特性导致旧测试断言过期」的必要适配，不移除任何断言意图。
- **Python 解释器差异（证据层级）**：本机 Bash 的 `python` 是 WorkBuddy 内置 3.13.14（**无 tkinter**），而系统 Python `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe` 是 3.13.7（**Tk 8.6**）。第 4 节 CLI 实测与黑盒用 Bash 的 `python`（无 Tk 不影响 CLI）；**全量 unittest 以系统 Python 3.13.7 为准**，因 Tk GUI 测试需要 tkinter。用无 Tk 的解释器跑全量会额外产生 `test_language_lab_entry` 的 `ModuleNotFoundError: No module named 'tkinter'` 环境性 FAIL，与 S42 无关。
- **S41 Tk GUI 测试基线既有 FAIL（非本轮回归）**：`test_load_real_s41_witness_with_button_and_reverify` 报 `Tk worker did not settle within bounded event loop`。用 `git worktree` 从干净 `main`（5027860，无任何 S42 改动）检出对照树单独重跑，**同样失败**；且 `app/lwt_snake/counterfactual_ui.py`、`tests/test_lwt_snake_counterfactual_gui.py`、`app/lwt_snake/strategies/mobility-lookahead.lwt` 与基线字节一致、`app/lwt_snake/` 无差异。判定为桌面环境（多窗口 + `cua-driver`）下的 Tk worker 时序问题，与 S42 无关；本轮不修改 GUI 测试或 S41 产物。
- **版本标识（非阻断，未纳入本轮）**：`lwt/*.py` 文件头 docstring 与规范标题仍写「LWT 0.1」，S42 新增内容在章节级标注「S42 / 0.2」。属历史标识，不影响语义，留待主窗口决定是否在后续统一版本表述。
- **测试遗留的清理**：多次全量 unittest（部分被工具级中断）在保护路径 `app/lwt_snake/strategies/` 下残留 4 个 0 字节 `test-<uuid>.lwt` 文件，来源为 `tests/test_lwt_snake_workshop.py` 的临时符号链接测试（`addCleanup` 在中断时未执行）。执行窗口将其移动到 `%TEMP%\lwt_s42_test_leftovers_backup\`（可恢复，**非删除**），使 `app/lwt_snake/` 工作树干净；这些文件未加入任何提交，保护数据差异为空。

## 8. Agent 开发记录

- **提示与授权**：规划窗口给出 S42 任务书；执行窗口发现工作树与快照不符（脏树 + 在制品），按 `AGENTS.md` 与 §0.3 停止写入并请用户裁决；用户选择「接手在制品收尾」后继续。
- **审计与基线**：只读通读在制品的 lexer/parser/ast/runtime/analyzer/cli/工具链改动与规范新增章节，确认依赖符号齐全、`finally` 借 Python `try/finally` 实现覆盖优先级正确；复核保留字零匹配；跑基线回归 330/330、完整性 330/394/297。
- **产出**：补齐 24 个 throw/finally 黑盒用例（每条先用公开 CLI 实测并断言语义，才写入 expected，避免盲目录入）；修正 test-matrix 虚报（原声称「已加入」但实际 0 项）；发现并最小修复 error() 的 source 偏差（随核心提交、专门用例验证）；实现 micro_bench 与画像报告；用 dict 重构 log_report 并固化 9 组逐字节对比证据。
- **人工审查与修正**：执行窗口发现自身两处预期值笔误（`finally-nested-once` 应为 111 而非 110；`error()` source 字段暴露的实现偏差），前者修正预期、后者修复实现并重跑核验；两处均在报告中留痕，不掩盖。

## 9. 状态分层

- **执行实现**：完成（本窗口，证据见第 4 节）——但**待主窗口复核**。
- **主窗口审查**：未开始（本报告交主窗口）。
- **合入 main**：未发生（本阶段不推送、不合并）。
- **远端 CI（最终 SHA）**：未查询（本阶段不推送，无远端最终 SHA；候选 `e1249f5` 的历史四格成功不外推到本阶段）。
- **现场人工 GUI 验收**：未验证（沿用 S12 桌面限制，本阶段未改变）。
- **教师验收 / 最终评分**：不属于本执行窗口，不声称。

## 10. 提交后记录（本窗口完成后回填）

| 项 | 值 |
|---|---|
| 工作分支 | `feature/lwt-core-0.2`（从基线 `5027860efc8a1cce342ca13b1434d7724aeeffc4` 创建，**不推送**） |
| 提交序列（按 §6 分组） | ① `35e4b37a99b2da8d48719eda31080c6e4792e99e` `feat(lwt-0.2): add dict, throw/finally and REPL core`；② `06fad50aa97e3bc894cd5e969417c94449bf81ba` `test(errors): add 24 verified throw/finally black-box cases`；③ `125b4db5f6e34eac8b98810d0e5865e65c320901` `perf(profile): add single-process micro-benchmark and runtime profile`；④ `aec6076f67a945dcbddc0e56c907c34f3d5a5dcc` `feat(app): refactor log_report counting with dict`；⑤ `3b59f12e277a9d47869e2fa4b80094d1cd3b5c94` `docs: sync guides, demo, skill, status and S42 report`；⑥ 数字校准提交（`docs: correct integrity link counts`，即包含本报告的最终笔，把改造后完整性链接数从基线的 394/297 更正为实测 401/304；SHA 由主窗口以 `git log -1 feature/lwt-core-0.2` 核对，本正文不预写自身 SHA）。 |
| 最终 `git status -sb` | `## feature/lwt-core-0.2`，工作区干净；`git diff --check` 0、Markdown 667 链接全解析、保护路径差异为空。 |
| 远端 | **未推送**；无远端最终 SHA，Actions 未查询，不沿用候选旧 SHA。 |
| 全量 unittest（系统 Python 3.13.7 + Tk 8.6） | `Ran 569 tests in 1265.982s`，`FAILED (failures=1)`；唯一失败为基线既有环境性 Tk worker 超时（干净 `main` 对照同样失败），其余 568 项通过。 |

> 本阶段执行窗口到此停止写入，交主窗口复核。推送、合入、精确 SHA 的远端 CI、Python 3.10/Linux 实测与现场人工 GUI 验收由主窗口按仓库工作流另行处理；本窗口不声称其中任何一项已完成。
