# S49 答辩彩排记录（本地彩排，不是教师验收）

> 生成：2026-11-11T16:11:14Z｜模式：dry-run｜计划 32 条，PASS 0，FAIL 0，TIMEOUT 0，SKIPPED 0。

| 页 | 幻灯片 | 断言 | 结果 | 退出码 | 用时 (s) | 证据 |
|---:|---|---|---|---:|---:|---|
| 1 | 封面：LWT 可执行语言与可复验应用 | `version` | PLANNED | — | 0.0 | `docs/delivery-manifest.json` |
| 2 | 课程八项交付物 | `help` | PLANNED | — | 0.0 | `docs/language-spec.md` |
| 3 | LWT 语言的特色组合 | `hello` | PLANNED | — | 0.0 | `examples/guide/hello.lwt` |
| 4 | 解释器执行路径 | `check` | PLANNED | — | 0.0 | `docs/developer-guide.md` |
| 5 | 关键语义与可定位错误 | `hello` | PLANNED | — | 0.0 | `examples/guide/hello.lwt` |
| 5 | 关键语义与可定位错误 | `dap` | PLANNED | — | 0.0 | `tests/test_dap_spawn_rejection.py` |
| 6 | 一键黑盒测试与覆盖矩阵 | `blackbox` | PLANNED | — | 0.0 | `tests/cases/` |
| 6 | 一键黑盒测试与覆盖矩阵 | `integrity` | PLANNED | — | 0.0 | `docs/test-matrix.md` |
| 7 | Agent 指南与真实 LWT 应用 | `blind` | PLANNED | — | 0.0 | `docs/s48-agent-eval.md` |
| 8 | 日志分析器：公开 CLI 结果 | `diff-eq` | PLANNED | — | 0.0 | `app/concurrent_log_report.lwt` |
| 9 | LWT Snake 与策略证据链 | `replay` | PLANNED | — | 0.0 | `reports/s42-schedules/` |
| 10 | S11：新进程端到端性能 | `s11` | PLANNED | — | 0.0 | `reports/performance.md` |
| 10 | S11：新进程端到端性能 | `compare-perf` | PLANNED | — | 0.0 | `reports/s44-performance/` |
| 11 | 并发记录与开发工具 | `determinism` | PLANNED | — | 0.0 | `reports/s48-defense/baseline-determinism.json` |
| 12 | 现场演示与交付边界 | `doc-consistency` | PLANNED | — | 0.0 | `docs/delivery-manifest.json` |
| 13 | S43：为什么做确定性并发 | `determinism` | PLANNED | — | 0.0 | `reports/s48-defense/baseline-determinism.json` |
| 14 | S43：调度、轨迹与三态证据 | `replay` | PLANNED | — | 0.0 | `reports/s42-schedules/` |
| 15 | S43：应用与性能实验 | `diff-eq` | PLANNED | — | 0.0 | `app/concurrent_log_report.lwt` |
| 16 | S44：启动与热路径为什么能更快 | `no-concurrency` | PLANNED | — | 0.0 | `lwt/cli.py` |
| 16 | S44：启动与热路径为什么能更快 | `s44-startup` | PLANNED | — | 0.0 | `reports/s44-performance/` |
| 17 | S44：分层证据与诚实口径 | `s44-exec` | PLANNED | — | 0.0 | `reports/s44-performance/` |
| 17 | S44：分层证据与诚实口径 | `compare-perf` | PLANNED | — | 0.0 | `reports/s44-performance/` |
| 18 | S45：八项交付物到证据与一条命令 | `unittest` | PLANNED | — | 0.0 | `reports/s53-mutation/unittest-single-command.json` |
| 18 | S45：八项交付物到证据与一条命令 | `integrity` | PLANNED | — | 0.0 | `docs/test-matrix.md` |
| 19 | S46：有界调度探索抓出抽样漏掉的缺陷 | `s46-clean` | PLANNED | — | 0.0 | `reports/s46-concurrency-model/summary.json` |
| 19 | S46：有界调度探索抓出抽样漏掉的缺陷 | `s46-mutant` | PLANNED | — | 0.0 | `reports/s46-concurrency-model/mutant/` |
| 20 | S47：教师入口与一键提交包 | `bundle-index` | PLANNED | — | 0.0 | `reports/s51-closeout/fresh-clone.json` |
| 20 | S47：教师入口与一键提交包 | `fresh-clone` | PLANNED | — | 0.0 | `reports/s51-closeout/fresh-clone.json` |
| 21 | S48：指南消融与现场可质询验收 | `blind` | PLANNED | — | 0.0 | `docs/s48-agent-eval.md` |
| 21 | S48：指南消融与现场可质询验收 | `blind-ci` | PLANNED | — | 0.0 | `reports/s48-defense/ablation.json` |
| 21 | S48：指南消融与现场可质询验收 | `ppt` | PLANNED | — | 0.0 | `slides/LWT介绍.pptx` |
| 21 | S48：指南消融与现场可质询验收 | `doc-consistency` | PLANNED | — | 0.0 | `docs/delivery-manifest.json` |

## 口径

- 超时记 `TIMEOUT`，命令失败记 `FAIL`，未提交记 `UNRUN`；没有“基本通过”。
- `--dry-run` 只打印计划；`--offline` 不执行命令，只用已提交证据。
- heavy 断言（401 黑盒、全量 unittest、46×10）默认 60 秒会超时，这是时间盒的真实结果；现场应改为只展示已记录证据，或用 `--allow-heavy` 单独排练。
