# S49 答辩彩排记录（本地彩排，不是教师验收）

> 生成：2026-11-11T02:49:50Z｜模式：live｜计划 5 条，PASS 4，FAIL 1，TIMEOUT 0，SKIPPED 0。

| 页 | 幻灯片 | 断言 | 结果 | 退出码 | 用时 (s) | 证据 |
|---:|---|---|---|---:|---:|---|
| 11 | 并发记录与开发工具 | `determinism` | FAIL | — | 60.0 | `reports/s48-defense/baseline-determinism.json` |
| 9 | LWT Snake 与策略证据链 | `replay` | PASS | 0 | 1.8 | `reports/s42-schedules/` |
| 10 | S11：新进程端到端性能 | `s11` | PASS | 0 | 0.4 | `reports/performance.md` |
| 10 | S11：新进程端到端性能 | `compare-perf` | PASS | 0 | 0.4 | `reports/s44-performance/` |
| 8 | 日志分析器：公开 CLI 结果 | `diff-eq` | PASS | 0 | 1.4 | `app/concurrent_log_report.lwt` |

## 口径

- 超时记 `TIMEOUT`，命令失败记 `FAIL`，未提交记 `UNRUN`；没有“基本通过”。
- `--dry-run` 只打印计划；`--offline` 不执行命令，只用已提交证据。
- heavy 断言（400 黑盒、全量 unittest、46×10）默认 60 秒会超时，这是时间盒的真实结果；现场应改为只展示已记录证据，或用 `--allow-heavy` 单独排练。
