# S24 执行报告：while/each 的 break 与 continue

**阶段状态：实施完成，等待主窗口审查。** 本报告记录 S24 实施窗口的本地证据，不代表主窗口已批准或合入；没有推送、合并、发布或开始 S12。

## 基线与提交

| 项目 | 实际状态 |
|---|---|
| S24 基线 | S23 阶段 tip `999cc7844065336d095b1efe4875313d2ee45da2`，分支 `stage/s23-test-adequacy`；开工时工作区干净。 |
| 本地 `main` | `aadb8f7a2348dad3205c523d4ab1cb4ad5bda063`，不包含 S23；本轮没有声称 S23 已合入。 |
| 新阶段分支 | `stage/s24-loop-control`，从 S23 已报告最终提交继续建立。 |
| 远端只读核对 | `origin/main` 跟踪值和 `git ls-remote --heads origin main` 均为 `de608f7fbf50946715d370df014657169eb8f26d`；远端是本地 `main` 的祖先，本地 main ahead 84、behind 0。未 fetch、pull、push 或同步远端。 |
| 分层提交 | S23 数量校正文档 `aaef11e9df262c5aa3fa5be708da2095f67589a0`；parser/AST `d3cef2acf38fa7a3dbe0624dd79afb1c957b8703`；runtime `e5bd18e3dea2c519f3c082cecee859bbe3638b10`；黑盒用例、矩阵和示例 `5bb2e7083d8ce46badea9cd99e919933d7dcbecb`；报告及阶段状态文档首个提交 `6c0a02246f8d98baf8d39b45394b195f93bfc6a8`。最后的 SHA 索引修订提交和最终 tip 见执行窗口交接。 |

第一项 S24 提交只校正文档中的 S23 当前数量，保留 S8 于 2026-10-07 在 Python 3.11.16/3.13.7 上通过 194 项的历史结果。S23 快照另列为 195 项、190 个配对 LWT 程序加 5 个 CLI override；没有把 S8 的历史结果改写成 S23 实测。

## 实现与规范决策

- 语法只增加 `break;` 和 `continue;` 两种无标签简单语句，分号必需；它们不是表达式，也不接受标签。
- parser 将循环嵌套深度显式传入语句/块解析。普通块与 `when/otherwise` 延续当前上下文；`while`/`each` 体加一层；每个函数体从零开始，因此不能借用调用者的循环。静态错误在关键字处报 `SyntaxError`/退出码 2；完整解析先于执行。
- AST 使用各自带 `SourceLocation` 的 `BreakStatement`、`ContinueStatement`。lexer 未修改；已有关键字 token 保持不变。
- runtime 用独立 `_BreakSignal`、`_ContinueSignal` 和既有 `_ReturnSignal` 表示控制流。每层循环只捕获自身边界中的 break/continue；while continue 重新测试条件，each continue 前进原浅快照。循环不捕获 return 或 `LwtError`，此前输出照常保留。
- 无标签循环跳转是 S1 初版未纳入的方案扩展，不是课程原文强制使用的关键字。本次明确更新正式规范；不改变词法、CLI 错误码、其他运行时语义、应用或性能证据。

规范、语言指南与仓库 Agent Skill 已同步，详见 [`language-spec.md`](language-spec.md)、[`developer-guide.md`](developer-guide.md) 和 [LWT 应用 Skill](../.agents/skills/lwt-app/SKILL.md)。教学样例为 [`examples/loop_control.lwt`](../examples/loop_control.lwt)。

## 黑盒覆盖

新增 24 个 `.lwt`/JSON 配对案例（12 正常 + 12 语法错误），删除 2 个语义过时的 `break-unsupported`、`continue-unsupported` 配对。新无效上下文和非法形式案例取代旧的笼统 unsupported 反例；旧用例没有被改名后保留过时语义。净增 22 项，矩阵与 runner 一致。

正常案例 ID：`while-break`、`while-continue`、`each-break`、`each-continue-snapshot`、`nested-loop-break`、`nested-loop-continue`、`break-through-when-block`、`continue-through-otherwise-block`、`function-loop-control`、`return-through-while`、`return-through-each`、`loop-normal-completion-continues`。

错误案例 ID：`break-outside-loop`、`continue-outside-loop`、`break-outside-loop-in-function`、`continue-outside-loop-in-function`、`break-no-partial-execution`、`continue-no-partial-execution`、`break-missing-semicolon`、`continue-missing-semicolon`、`break-label-rejected`、`continue-label-rejected`、`break-extra-token`、`continue-extra-token`。

截至本阶段最终验证，黑盒总数为 **217**：`lexer-parser` 52、`values-operators` 31、`control-functions` 43、`arrays-records-each` 32、`builtins-text-io` 43、`cli-errors` 13、`integrated` 3。212 项公开 CLI 执行配对 LWT 源程序，5 项覆盖 CLI argv override。完整性检查为 `cases=217; matrix_links=314; referenced_cases=217`。对应关系见 [`test-matrix.md`](test-matrix.md)。

## 示例实测

从仓库根目录执行：

```powershell
python -m lwt examples/loop_control.lwt
```

Windows CPython 3.13.7 实际 stdout：

```text
1
3
2
[1, 2, 3, 4]
```

stderr 为空，退出码为 0。while 循环跳过 `i == 2` 并在 `i == 4` 停止；each 循环在遍历初始快照时跳过首项、新追加的 `4` 不进入快照，并在 `3` 时停止。

## 实际验证

环境：Windows 11 build 26200，CPython 3.13.7；另有可调用的 CPython 3.11.16。`py -0p` 没有列出 Python 3.10，因此 3.10 未验证；Linux 和远端 Actions 未运行。首个 Python 3.11 命令尝试因 PowerShell 未使用调用运算符而在 shell 解析阶段失败，随后改用 `& '<python.exe>' ...` 原样重跑成功；失败没有进入 Python，也没有触发代码改动。

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p test_parser.py -v` | 退出码 0；24 项通过。新增 loop context、函数边界、AST 节点位置与非法分号/标签/额外 token 检查。 |
| `python -m unittest discover -s tests -p test_runtime.py -v` | 退出码 0；7 项通过。新增 continue 不吞 return、循环内 RuntimeError 传播且保留既有 stdout 两项。 |
| `python tools/run_tests.py`（CPython 3.13.7） | 退出码 0；217/217；各类 52/31/43/32/43/13/3，0 失败。 |
| `python tools/check_project_integrity.py`（CPython 3.13.7） | 退出码 0；217 cases、314 matrix links、217 referenced cases。 |
| `python -m unittest discover -s tests -q`（CPython 3.13.7） | 退出码 0；297 项，OK。 |
| `python -m compileall -q lwt tests tools bench app`（CPython 3.13.7） | 退出码 0，无诊断。 |
| `python tools/run_semantic_properties.py --seed 20261028 --cases 150` | 退出码 0；150 个表达式 + 6 个语义检查，共 156 检查、7 个公开 CLI 程序；oracle SHA-256 `6d4f42d5db1e00ee555f2e915d989d20c6779fa7b467490e352d6b4e03a07ce0`，与 S23 记录一致。 |
| `python tools/audit_semantic_mutants.py` | 退出码 0；10 个探针：9 killed、1 survived、0 equivalent、0 invalid。存活项仍是旧的参数顺序对称案例；新的不对称副作用案例击杀同一逆序变异。工具只用临时副本，未修改正式 runtime。 |
| `python -m lwt examples/loop_control.lwt` | 退出码 0；stderr 为空，stdout 如上。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 退出码 0；246 行有效 LWT。 |
| Python 3.11.16 下同一黑盒、完整性、全量 unittest 与 compileall 命令 | 使用 `& 'C:\Users\28641\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none\python.exe' <arguments>` 调用；四项均退出码 0，黑盒 217/217，完整性 217/314/217，unittest 297 项 OK，compileall 无诊断。 |
| `git diff --check` | 退出码 0；工作区改动无 whitespace error。Git 提示若干 LF 文件在未来触及时可能转成 CRLF，不影响检查结果。 |
| `git diff --check 999cc7844065336d095b1efe4875313d2ee45da2...HEAD` | 退出码 0、无诊断；在报告与状态文档提交后再次执行，覆盖完整 S24 阶段差异。 |
| Markdown 链接/围栏检查（PowerShell here-string 驱动的 Python 检查器） | 覆盖 12 份变更 Markdown/Skill 文档，检查 587 个相对链接并对百分号编码路径先 URL 解码；所有目标存在，代码围栏成对，退出码 0。首次检查未解码 `%20`，把两个指向课程 PDF 的合法链接误报为缺失；加入 `urllib.parse.unquote` 后检查通过。 |
| S10/S11 保护路径 Git 差异检查 | `git diff --quiet 999cc7844065336d095b1efe4875313d2ee45da2 HEAD -- app/log_report.lwt tests/test_app.py reports/app-concurrency.json docs/app-concurrency.md bench/results.json reports/performance.md` 退出码 0；这些路径未变化。 |

手工语义对照：若把 break 错当 continue，while/each break 案例会多输出并触发后续循环；若把 continue 错当 break，while/each continue 案例会丢掉后续快照项；嵌套案例验证内层循环只消费自己的信号；each 快照案例验证 continue 仍推进到原快照的下一元素。该分析是测试设计审阅，不声称运行了新增 S24 变异探针。

## 文件范围、保护证据与遗留

实现改动仅涉及 `lwt/ast_nodes.py`、`lwt/parser.py`、`lwt/runtime.py`；未改 lexer、CLI、正式应用 `app/log_report.lwt`、性能 raw 或性能报告。S10 并发原始记录和 S11 性能数据按 S24 基线进行 Git 差异核验，结果列于最终交接。正式语言规范、黑盒用例、覆盖矩阵是本阶段预期修改内容。

S24 没有修改应用 GUI，因此没有新增桌面验收；S21 的人工 GUI 遗留继续由 S12 现场预检。Python 3.10、Linux 和远端 Actions 状态未验证。S23、S24 都须等待主窗口审查；本分支没有合并/推送，S12 未开始。
