# LWT 答辩演示脚本（S48 最终候选）

从仓库根目录运行。建议提前打开[系统介绍 PPT](../slides/LWT介绍.pptx)（21 页），准备 Python 3.13 和终端。所有命令均使用公开 CLI；固定证据保持只读。现场按教师要求调整顺序。**主线目标 8–10 分钟**；附录片段按时间取舍。当前状态数字以 [交付清单](delivery-manifest.json) 为唯一来源（400 黑盒 / 721 unittest / 21 页 PPT）。

## 主流程（8–10 分钟）

| 时间 | 操作与讲解 | 命令或证据 |
|---|---|---|
| 0:00–0:40 | 说明课程五项评分与八项提交物；先报当前身份：**LWT 0.3.0**，400 黑盒 / 721 unittest / 21 页 PPT，S42–S49 执行完成、main 已推送，现场人工 GUI A–E 待本人验收。 | `python -m lwt --version`；`python -m lwt --help`；[交付清单](delivery-manifest.json) |
| 0:40–1:30 | 跑最小程序，说明源码经 lexer、parser、AST 和树遍历运行；再演示可定位的除零错误（退出 3）。点出 `record`/`when-otherwise`/`each`/`emit` 的语法特色。 | `python -m lwt examples/guide/hello.lwt`；`python -m lwt examples/language_lab/division_by_zero.lwt` |
| 1:30–2:20 | S42 语言核心增量：dict 插入序与内置、throw/finally 的控制流覆盖；时间紧可只看两条 emit。 | `python -m lwt examples/dicts.lwt`；`python -m lwt examples/throw_finally.lwt` |
| 2:20–3:20 | **测试抓手**：一条命令跑 400 项黑盒并显示分类统计；再用完整性检查证明 400 个用例全部被矩阵链接（unreferenced=0）。不在现场重跑时，展示已记录输出并说明是记录值。 | `python tools/run_tests.py`；`python tools/check_project_integrity.py --require-all-referenced`；[矩阵](test-matrix.md) |
| 3:20–4:20 | **性能抓手**：先给 S11 正式结论（端到端 2.7–5.0×，明确未做优化），再给 S44 附录的分层对照：启动 1.256×/1.224×，纯执行 N=5000 1.45–2.99×；强调端到端仍比 Python 慢、两种口径不混用。 | `python tools/compare_perf.py`；[S11](../reports/performance.md)；[S44](s44-performance.md) |
| 4:20–6:00 | **并发子语言**：多文件每文件一任务并发读取、按输入顺序归并（与串行逐字节等价）；换种子得到另一交错，轨迹可记录/重放；再用 5 秒展示 S46 有界探索（clean 0 违反 / mutant 命中）。 | `python -m lwt app/concurrent_log_report.lwt -- app/fixtures/sample.log app/fixtures/showcase.log`；下方“并发演示片段” |
| 6:00–7:00 | **Agent 应用**：日志分析器 243 行有效 LWT（坏行/等级/关键字/top-k）；并发版 233 行。若桌面可用，再开 LWT Snake；否则说明 GUI 为展示层、规则在 .lwt。 | `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2`；`python tools/count_lwt_lines.py app/log_report.lwt` |
| 7:00–8:00 | **策略证据链**（可选压缩）：S39 原局复核 → S41 自动差异见证 → S40 一步分支；强调同一已验证观察前缀与预算内成立。 | 下方“证据链命令” |
| 8:00–9:20 | **交付自检**：一条命令跑 Git/保护路径/完整性/黑盒/确定性/性能门槛/文档一致性/PPT 静态检查/有界调度探索/提交包，输出 JSON+MD；并说明 Agent 盲测已执行（S48 主口径见报告）、人工 GUI 由本人现场验收。 | `python tools/run_acceptance_selfcheck.py`；`reports/s48-defense/selfcheck/` |
| 9:20–10:00 | 收尾：读 `git status -sb`（干净）与未验证项清单（现场人工 GUI A–E、教师线下验收）；说明 main 已收敛并已推送，CI 四格按精确 SHA 记录。 | `git status -sb`；[S48 报告](s48-defense-readiness.md)；[S47 报告](s47-final-submission.md) |

**取舍**：时间只有 5–8 分钟时，保留 0:00–0:40、0:40–1:30、2:20–3:20、3:20–4:20、4:20–6:00、8:00–9:20，其余口头带过。

## 策略证据链命令

```powershell
python -m app.lwt_snake.arena --verify reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.witness --verify reports/s41-found --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual --explain reports/s41-found/analysis --catalog app/lwt_snake/strategies/strategy-catalog.json
```

第一条用全新 LWT 游戏和策略进程重算九局，预期 `Verified 9 matches: game and policy decisions.`；第二条预期 `found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs`；第三条解释 baseline `R/SPACE` 与 BFS `D/FOOD` 在同一局面各自推进一步的真实游戏结果。完整证据见 [S39 结果](../reports/s39-demo/result.json)、[S41 见证](../reports/s41-found/witness.json)与 [S40 分支](../reports/s41-found/analysis/analysis.json)。原结果哈希、策略源码摘要和分支回放均在验真时重新核对。它证明固定输入和当前源码下可复算的决策与一步效果，不认证历史执行主体，也不证明策略整体优劣。

## 篡改拒绝（仅临时副本）

```powershell
$tmp = Join-Path $env:TEMP 'lwt-s12-demo-tamper'
if (Test-Path -LiteralPath $tmp) { throw '目标已存在，请换一个临时目录名' }
Copy-Item -LiteralPath reports/s41-found -Destination $tmp -Recurse
$p = Join-Path $tmp 'agent-feedback.json'
$j = Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
$j.question = 'tampered in temporary copy'
$j | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $p -Encoding UTF8
python -m app.lwt_snake.witness --verify $tmp --catalog app/lwt_snake/strategies/strategy-catalog.json
```

预期退出 3 并指出反馈证据不匹配。若固定 schema 不含 `question` 字段，应改为复制仓库内已提交的 [S41 篡改样例](../reports/s41-tampered/agent-feedback.json)到临时副本同名位置；切勿修改仓库固定证据。演示前实际执行并核对本段命令，不能仅凭文档推测结果。

## REPL 演示片段（S42）

无需桌面即可展示会话式执行；提示符与诊断走 stderr，`emit` 走 stdout，便于管道取纯程序输出：

```powershell
printf 'let d = dict{"Li": 87, "Wu": 56};\nemit d;\nput(d, "Zhao", 73);\nemit keys(d);\nattempt { throw "x"; } recover (p) { emit p.category; } finally { emit "clean"; }\n.exit\n' | python -m lwt --repl
```

stdout 预期依次为 `dict{"Li": 87, "Wu": 56}`、`["Li", "Wu", "Zhao"]`、`User`、`clean`；stderr 含续行提示符与元命令帮助。也可用 `python -m lwt --repl` 进入交互会话（`.help`/`.vars`/`.reset`/`.exit`）。该片段在 S42 执行窗口已实跑核对，见 [S42 执行报告](s42-execution-report.md) 与 [REPL 单测](../tests/test_repl.py)（14 项通过）。REPL 是开发工具，不改变 `python -m lwt SOURCE` 普通执行契约。

## 并发演示片段（S43，约 90 秒）

三步展示「并发可复现」而非「跑得快」。全部用公开 CLI，固定证据只读。

```powershell
# 1) 多文件并发读取，按输入顺序归并；每文件报告块与串行版逐字节相同
python -m lwt app/concurrent_log_report.lwt -- app/fixtures/sample.log app/fixtures/showcase.log

# 2) 同一程序换种子 -> 另一交错（race 有两种结果：丢更新 1 / 无丢失 2）
python -m lwt --schedule=random:1 --schedule-log reports/s42-schedules/found/lost-update/trace-demo.json tests/cases/concurrency/race-lost-update.lwt
python -m lwt --schedule-replay reports/s42-schedules/found/lost-update/trace-demo.json tests/cases/concurrency/race-lost-update.lwt
```

预期：第 1 步输出两个 `=== 路径 ===` 报告块，顺序与参数顺序相同（不依赖哪个文件先读完），块正文与 `python -m lwt app/log_report.lwt -- 单文件` 逐字节相同；第 2 步记录与重放 stdout 一致（同一轨迹逐字复现）。**注意**：`reports/s42-schedules/found/lost-update/trace-demo.json` 是演示临时写入，现场演示后由用户自行删除；不要改动已固定的 `trace-1.json`/`trace-2.json`。篡改演示见 [三态摘要](../reports/s42-schedules/summary.md)（tampered 三种篡改均退出 4），契约见[并发速查](concurrency.md)。本片段命令在 S43 执行窗口已实跑核对（含 4 fixture 差分等价、多文件 10 次一致、一键重放退出 0）。

## 引擎加速演示片段（S44，约 45 秒）

三步展示「快在哪、快多少、为什么」，只读已固定证据，不改任何 S11/S42/S43 原始文件。

```powershell
# 1) 启动惰性化：非 spawn 程序不加载并发模块（约 10 秒）
python -m lwt --help                      # S45 起该路径正常退出 0（S44 时代是 exit 4 错误路径）
python -c "import sys, lwt.cli; print('concurrency loaded:', 'lwt.concurrency' in sys.modules)"   # False

# 2) 一键对照 before/after 门槛（只读 reports/s44-performance/ 的新 JSON）
python tools/compare_perf.py             # 文本表：启动 --help 1.256× / hello 1.224×；纯执行 N=5000 1.45–2.99×

# 3) S11-v2 分层：端到端 vs 纯执行分开看
python tools/benchmark_v2.py --help        # 协议说明；正式结果见 reports/s44-performance/benchmark-v2.md
```

预期：第 1 步 `lwt.cli` 导入后 `lwt.concurrency` 不在 `sys.modules`（P0-1 惰性化）；第 2 步 `compare_perf.py` 对启动两项与纯执行三负载均报 PASS，退出码 0；第 3 步展示分层报告，说明端到端 LWT/Python 倍率（约 1.48–1.79×）与纯执行提升（1.45–2.99×）是**不同口径**，不混用。**注意 S44 的 `--help` 测量是 exit 4 的历史证据，不能与 S45 的 exit 0 数字直接相减比较**；S45 启动重测见 `reports/s45-acceptance/startup.md`。完整方法、环境、逐项台账与未验证项见 [S44 执行报告](s44-performance.md)、[性能计划](s44-performance-plan.md) 与 [优化台账](s44-optimization-ledger.md)。

## 有界调度探索片段（S46，约 50 秒）

```powershell
# 1) clean：8 个小程序、32 次执行、0 违反（约 5-10 秒）
python tools/model_check_concurrency.py --corpus tests/concurrency-model --max-runs 300 --time-budget 90 --require-clean --out reports/s46-concurrency-model

# 2) 故障注入：把 S45 的重复投递装回工具进程，检查器应报 4 个违反并给最小前缀
python tools/model_check_concurrency.py --corpus tests/concurrency-model --max-runs 200 --time-budget 60 --mutant duplicate-delivery --expect-violation --out reports/s46-concurrency-model/mutant

# 3) 读 witness：最小前缀与重放（clean 用公开 CLI；mutant 用工具 harness）
python -c "import json;d=json.load(open('reports/s46-concurrency-model/mutant/summary.json'));v=[p for p in d['programs'] if p['id']=='channel-exactly-once'][0]['violations'][0];print(v['minimized_prefix'],repr(v['stdout']),v['replay']['mode'],v['replay']['matches'])"
```

讲解词：**有界探索不是形式化证明**——只覆盖 `max_runs × max_decisions` 内的前缀；预算耗尽写 `BUDGET_EXHAUSTED`，不写 PASS。mutant 是**合成故障注入**，证明检查器能抓到 S45 那种抽样漏掉的交接时序，不是说当前产品有 bug。clean 的 lost-update 会给出 `1`/`2` 两种结果，那是 `allowed_outcomes`，不是违规。

## 教师视角收尾片段（S48，约 40 秒）

```bash
# 1) 打开教师入口：8 项提交内容 → 路径/命令/证据
cat SUBMISSION.md

# 2) 现场随机抽一条可质询断言并复算（也可 --list / --random 3）
python tools/run_defense_probe.py --claim blind

# 3) 看包索引：bundle 截止 SHA、最终 tip、允许的 lag 白名单
cat reports/s48-defense/package-index.json

# 4) 从 bundle 新克隆并跑 400 黑盒（验证交付可达）
python tools/verify_fresh_clone.py --package-index reports/s48-defense/package-index.json
```

讲解词：`SUBMISSION.md` 是教师第一眼入口；现场用 `run_defense_probe.py --claim <id>` 复算任一断言；`package-index.json` 明确写出 bundle 截止 SHA 与最终 tip 的差异白名单（自引用无法把“记录包的那一笔”打进包内）；新克隆在空目录重跑 400/400，不依赖本工作区未跟踪文件。

## 无 GUI 后退

无需桌面、网络或第三方 GUI 库即可运行上面的 CLI。展示游戏规则时使用 `python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-parent.json`；展示语言模块时使用 `python -m lwt examples/modules/main.lwt`。GUI/Tk 自动测试证明控件回调集成，不能代替现场真实鼠标、键盘、焦点和视觉检查。

## S49：逐页讲稿与排练（不在主流程内，供答辩前自用）

- 逐页口播/追问/断言/命令：`docs/defense-runbook.md`（21 页，与 PPT 一一对应）。
- 随机抽问排练：`python tools/rehearse_defense.py --random 5 --timeout 60`；只走口播：`--dry-run`；无网络/无 GUI：`--offline`。
- 现场证据台：`docs/defense-index.html`（离线单文件，按页码或断言 id 跳转）。
- 口径：排练是本地演练，不是教师验收；heavy 断言（400 黑盒/全量 unittest/46×10）不要塞进 60 秒时间盒，改为只展示已记录证据。
