# LWT 答辩逐页讲稿（21 页，S49）

> 用途：现场答辩的逐页口播、追问应答与证据复算入口。**这是本地彩排脚本，不是教师线下验收**；验收是否通过由教师现场判定。
> 唯一数字来源：`docs/delivery-manifest.json`（当前 0.3.0 / 400 黑盒 / 719 unittest / 21 页）。页码与断言映射的机器可读版本见 [`defense-pages.json`](defense-pages.json)，证据台见 [`defense-index.html`](defense-index.html)。
> 标记：**现场跑** = 该页命令必须在现场真实执行；**只展示** = 打开已提交证据，不假装现场重跑；**口播** = 无命令。
> 时间盒：满时约 14 分钟；若限 8 分钟，跳过 9/13/15/19 四张（只讲 17 张），并在第 21 张补一句“细节在证据台”。

## 0. 三条现场纪律

1. **只跑不改**：所有命令只读仓库；需要临时输出的命令写到临时目录，不覆盖 `bench/`、`reports/s42-*`…`reports/s48-*`。
2. **失败照说**：命令失败就报失败与退出码，改说“这一条我现场没跑通，证据在 <路径>”，不解释成“环境问题”糊过去。
3. **口径分离**：本地通过 ≠ CI 通过；`success` 徽章 ≠ 四格通过；彩排 ≠ 教师验收；观察性对照 ≠ 因果结论。

## 1. 逐页表

| 页 | 标题 | 口播要点（≤3 句） | 追问与一句话回答 | 断言 | 现场命令 / 降级证据 | 模式 |
|---|---|---|---|---|---|---|
| 1 | 封面：LWT 可执行语言与可复验应用 | 我做的是一个可执行语言 LWT：规范、解释器、400 项黑盒、指南、应用、Git 与 PPT 八项齐全。今天每一页都配一条可当场复算的命令。 | Q：一句话说清它是什么？ A：带 record/dict/throw-finally/协作式并发子语言的解释型脚本语言，实现与证据同仓。 | `version` | `python -m lwt --version`；降级：`docs/delivery-manifest.json` | **现场跑** |
| 2 | 课程八项交付物 | 八项交付物对应课程五个评分项：解释器 20、测试 20、性能 10、语法+指南 20、应用 30。入口是 `SUBMISSION.md`，每项一行命令。 | Q：哪一项最弱？ A：性能只做到端到端 2.7–5.0×，比 Python 慢，这是结构性成本，不美化。 | `help` | `python -m lwt --help`；降级：`SUBMISSION.md` | 口播 |
| 3 | LWT 语言的特色组合 | 语言特色是 `record` 字段访问、`each` 浅快照、`when/otherwise` 与 `emit` 的输出模型。下面跑最小程序。 | Q：和 Python 差在哪？ A：静态记录形状 + 显式错误分类 + 可调度并发的确定性，不是通用库生态。 | `hello` | `python -m lwt examples/guide/hello.lwt`；降级：`examples/guide/hello.lwt` | **现场跑** |
| 4 | 解释器执行路径 | 源码经 lexer、parser 到 AST，再由树遍历执行；`--check` 只做静态检查不执行。 | Q：为什么不用字节码？ A：课程目标是语义与可验证性，树遍历更容易保证错误定位与轨迹一致。 | `check` | `python -m lwt --check examples/modules/main.lwt`；降级：`docs/developer-guide.md` | **现场跑** |
| 5 | 关键语义与可定位错误 | 除零会带行列与类别退出 3；错误分类让 `recover` 能按 category 分流。DAP 侧对 `spawn` 直接拒绝，避免调试器与调度器语义冲突。 | Q：DAP 为什么拒绝 spawn？ A：调试暂停点与调度点无法同时保证确定性，宁可拒绝也不静默降级。 | `hello` `dap` | `python -m unittest tests.test_dap_spawn_rejection -q`；降级：`tests/test_dap_spawn_rejection.py` | **现场跑** |
| 6 | 一键黑盒测试与覆盖矩阵 | 一条命令跑 400 项黑盒，按类别统计；完整性检查证明 400 项全部被矩阵引用、无孤儿用例。 | Q：400 项够吗？ A：覆盖五类语法与 46 项并发，且每项都能被矩阵追溯；不足在“真实程序规模”，用应用与差分等价补。 | `blackbox` `integrity` | `python tools/run_tests.py`（约 4 分钟）；降级：`tests/cases/`、`docs/test-matrix.md` | **现场跑** |
| 7 | Agent 指南与真实 LWT 应用 | 指南 + Skill 让 Agent 能独立写出 243 行日志分析器与 233 行并发版；S48 用 60 个会话做了 T/C 消融。 | Q：指南真有用吗？ A：本样本下没测出增量（T−C 区间含 0），我不把“能写出来”说成指南的因果功劳。 | `blind` | `python tools/run_defense_probe.py --claim blind`；降级：`docs/s48-agent-eval.md` | 口播 |
| 8 | 日志分析器：公开 CLI 结果 | 日志分析器支持坏行、等级、关键字与 top-k；并发版按输入顺序归并，与串行版逐字节等价。 | Q：并发版快吗？ A：并发是为确定性与结构，不是提速；性能对照见第 15 页，不宣称 CPU 加速。 | `diff-eq` `replay` | `python -m lwt app/concurrent_log_report.lwt -- app/fixtures/sample.log`；降级：`app/concurrent_log_report.lwt` | **现场跑** |
| 9 | LWT Snake 与策略证据链 | Snake 的规则层是 LWT，GUI 只是展示层；策略证据链给出同一观察前缀下的分支与预算。 | Q：GUI 能现在演示吗？ A：桌面演示属人工 GUI 验收项（A–E），我今天按 CLI 降级轨给等价证据，不冒充已验收。 | `replay` | 只展示：`docs/s41-gui-acceptance.md`；`reports/s42-schedules/` | 只展示 |
| 10 | S11：新进程端到端性能 | S11 的正式口径是端到端 2.7–5.0×（LWT 慢于 Python），未做解释器优化时的原始数据。 | Q：为什么不用纯执行数字？ A：两种口径不能混用；纯执行在 S44 附录单列，端到端仍慢就说慢。 | `s11` `compare-perf` | `python tools/compare_perf.py`；降级：`reports/performance.md` | 只展示 |
| 11 | 并发记录与开发工具 | 并发子语言有记录/重放、`--profile` 与调试器边界；46 项并发用例 ×10 次逐字节稳定。 | Q：确定性怎么保证？ A：默认 fifo 调度 + 记录调度点 + 重放校验；不确定性只允许出现在显式 random 策略。 | `determinism` | `python tools/run_concurrency_determinism.py --repeat 10 --out <临时目录>/d.json`；降级：`reports/s48-defense/baseline-determinism.json` | **现场跑** |
| 12 | 现场演示与交付边界 | 现场只演示能复算的部分；GUI、教师验收、跨平台 CI 分开写状态，不互相推断。 | Q：哪些没验？ A：现场人工 GUI A–E 与教师线下验收未发生，报告里就是 NOT_RUN。 | `doc-consistency` | `python -m unittest tests.test_doc_consistency -q`；降级：`docs/final-acceptance-checklist.md` | 口播 |
| 13 | S43：为什么做确定性并发 | 并发不是为了跑得快，是为了“同一程序同一输入结果可复现”，并能把交错记录成轨迹。 | Q：和线程有什么区别？ A：调度点显式、默认确定性、可记录可重放；线程的自由交错在这里是缺陷来源。 | `determinism` | 只展示：`docs/s42-deterministic-concurrency.md` | 口播 |
| 14 | S43：调度、轨迹与三态证据 | 三种状态：found（200 种子找到两类交错）、absent（200 种子未出现）、tampered（三处篡改均 exit 4）。 | Q：轨迹能伪造吗？ A：轨迹带源码摘要绑定，篡改即拒绝；旧 trace 因 CRLF 入库，改用现场记录→重放 round-trip。 | `replay` | `python tools/run_defense_probe.py --claim replay`；降级：`reports/s42-schedules/` | **现场跑** |
| 15 | S43：应用与性能实验 | 并发日志应用 4 组 fixture 与串行逐字节等价；性能实验给 Amdahl 上限，不宣称加速。 | Q：那并发有什么用？ A：结构化并发 + 确定性 + 可回放，工程上可验证，而不是拿核数换速度。 | `diff-eq` | `python tools/run_defense_probe.py --claim diff-eq`；降级：`reports/concurrency-performance.md` | **现场跑** |
| 16 | S44：启动与热路径为什么能更快 | 启动惰性化：非 spawn 程序不加载并发模块；热路径减少分派与临时对象。启动 1.256×/1.224×。 | Q：为什么端到端还是慢？ A：解释器分派、对象分配与包导入是结构性成本，局部优化只能削一部分。 | `no-concurrency` `s44-startup` | `python tools/run_defense_probe.py --claim s44-startup`；降级：`reports/s44-performance/` | **现场跑** |
| 17 | S44：分层证据与诚实口径 | 纯执行 N=5000 是 1.454×/1.552×/2.992×；与端到端分列，不混口径。 | Q：2.992× 是不是挑出来的？ A：三负载全列，dict_counts 最高，arithmetic 最低，都写进报告。 | `s44-exec` `compare-perf` | `python tools/compare_perf.py`；降级：`reports/s44-performance/` | 只展示 |
| 18 | S45：八项交付物到证据与一条命令 | 八项交付物各有入口命令与证据；一条自检命令把 Git、保护路径、完整性、黑盒、确定性、性能门槛、文档一致性、PPT 全跑一遍。 | Q：自检能造假吗？ A：每步记录真实退出码与输出到 JSON；任一步 FAIL 就整体 FAIL，不写“基本通过”。 | `unittest` `integrity` | `python tools/run_acceptance_selfcheck.py`（约 8 分钟）；降级：`reports/s48-defense/selfcheck/` | **现场跑** |
| 19 | S46：有界调度探索抓出抽样漏掉的缺陷 | 工具枚举调度点、按前缀重跑、分类结果；clean corpus 0 违反，mutant 注入后 4 违反且最小前缀为空。 | Q：这是形式化证明吗？ A：不是，是有界探索；预算耗尽写 BUDGET_EXHAUSTED，不写 PASS。 | `s46-clean` `s46-mutant` | `python tools/run_defense_probe.py --claim s46-mutant`；降级：`reports/s46-concurrency-model/` | 只展示 |
| 20 | S47：教师入口与一键提交包 | `SUBMISSION.md` 是教师入口；包由 `build_submission.py` 生成，索引记录 bundle 截止 SHA 与允许的差异白名单。 | Q：bundle 里有没有最终提交？ A：自引用做不到；索引显式声明 X、Y 与白名单，并断言 `X..Y` 只含白名单文件。 | `bundle-index` `fresh-clone` | `python tools/run_defense_probe.py --claim bundle-index`；降级：`reports/s48-defense/package-index.json` | **现场跑** |
| 21 | S48：指南消融与现场可质询验收 | 60 个独立会话：T 30/30、C 29/30，T−C=+0.033，95% 区间 [−0.031,+0.098] 含 0。结论是本样本未测得指南增量，且这是观察性对照。证据台 24 条断言可随机抽一条复算。 | Q：区间含 0 是不是白做了？ A：不是——它把“指南有效”从断言降级为可复算的观察，并暴露天花板效应与 n=5 的限制。 | `blind` `blind-ci` `ppt` `doc-consistency` | `python tools/run_defense_probe.py --random 3`；降级：`docs/s48-agent-eval.md`、`docs/defense-index.html` | **现场跑** |

## 2. 抽问彩排

- 现场随机质询：`python tools/run_defense_probe.py --random 3`（每条默认 60 秒超时，失败写 FAIL）。
- 逐页彩排：`python tools/rehearse_defense.py --pages 1-21`；只走口播不执行命令：`--dry-run`；无网络/无 GUI：`--offline`。
- 彩排证据：`reports/s49-rehearsal/rehearsal-<UTC>.{json,md}`（页码、断言、起止时间、真实退出码、是否超时）。

## 3. 三条最容易被问倒的问题

| 问题 | 回答骨架 |
|---|---|
| 你的指南到底有没有用？ | 60 会话 T/C 对照，T 30/30、C 29/30，差值 +0.033，区间含 0 → **本样本未测得增量**；限制是天花板效应、n=5、单平台；不写成因果。 |
| CI 四格按哪个 SHA？ | 按最终推送 SHA 逐格记录；`724dc7c` 四格失败（文档一致性抓到过期的分支状态表述）、`446ed4d` 与 `0df0e40` 四格通过；不用徽章推断。 |
| 现场 GUI 没做怎么办？ | 直说 `REGISTERED 0/5`、A–E 为 NOT_RUN；给 CLI 降级证据（[`gui-acceptance-quickref.md`](gui-acceptance-quickref.md)），不拿自动测试或旧截图冒充人工验收。 |
