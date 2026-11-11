# S49 答辩彩排记录（本地彩排，不是教师验收）

> 生成：2026-11-11T16:12:01Z｜模式：live｜计划 5 条，PASS 5，FAIL 0，TIMEOUT 0，SKIPPED 0。

| 页 | 幻灯片 | 断言 | 结果 | 退出码 | 用时 (s) | 证据 |
|---:|---|---|---|---:|---:|---|
| 4 | 解释器执行路径 | `check` | PASS | 0 | 0.3 | `docs/developer-guide.md` |
| 16 | S44：启动与热路径为什么能更快 | `no-concurrency` | PASS | 0 | 0.3 | `lwt/cli.py` |
| 10 | S11：新进程端到端性能 | `s11` | PASS | 0 | 0.1 | `reports/performance.md` |
| 12 | 现场演示与交付边界 | `doc-consistency` | PASS | 0 | 0.8 | `docs/delivery-manifest.json` |
| 21 | S48：指南消融与现场可质询验收 | `ppt` | PASS | 0 | 0.2 | `slides/LWT介绍.pptx` |

## 口径

- 超时记 `TIMEOUT`，命令失败记 `FAIL`，未提交记 `UNRUN`；没有“基本通过”。
- `--dry-run` 只打印计划；`--offline` 不执行命令，只用已提交证据。
- heavy 断言（401 黑盒、全量 unittest、46×10）默认 60 秒会超时，这是时间盒的真实结果；现场应改为只展示已记录证据，或用 `--allow-heavy` 单独排练。
