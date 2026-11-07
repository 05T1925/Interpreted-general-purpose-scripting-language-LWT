# S43 调度探索三态证据（found / absent / tampered）

> 本目录沿用 S38/S40/S41 的「分歧—见证—重放—验真」方法论，把并发调度的每一种交错变成可复现的证据。三态均使用公开 CLI（`python -m lwt --schedule=random:SEED` 与 `--schedule-replay`），不修改黑盒协议、不覆盖保护数据。

## 1. 工具与命令

- `tools/explore_lwt_schedules.py --program PATH --seeds 1..200 --out DIR`：按 seed 批量运行同一程序，按 `(退出码, stdout SHA-256)` 归类，输出 `explore.json` 与每个结果类一个可重放 `trace-*.json`。
- `python -m lwt --schedule=random:SEED --schedule-log=TRACE SOURCE`：记录某一交错的完整轨迹。
- `python -m lwt --schedule-replay=TRACE SOURCE`：按轨迹强制重放，校验所有绑定字段与输出摘要。

## 2. found：`found/lost-update/`（≥2 种结果）

程序 `tests/cases/concurrency/race-lost-update.lwt` 让两个任务各做「读全局计数 → `yield()` → 写回」，在 `random:SEED` 下存在两种结果（丢失一次更新得 `1`；无丢失得 `2`）。

| 项 | 实测 |
|---|---|
| 种子范围 | `1..200`（200 个） |
| 结果类数 | **2** |
| 类 1 | `exit=0`, `stdout_sha256=4355a46b19d3…`, seed 6 首现，96 个种子，trace `trace-1.json` |
| 类 2 | `exit=0`, `stdout_sha256=53c234e5e847…`, seed 1 首现，104 个种子，trace `trace-2.json` |
| 可重放 | 两个类的 trace 均能 `reproduced=True` 重放 |

可复现命令（任务书 §12 一键命令）：

```bash
python -m lwt --schedule=random:7 --schedule-log reports/s42-schedules/found/lost-update/trace-1.json tests/cases/concurrency/race-lost-update.lwt
python -m lwt --schedule-replay reports/s42-schedules/found/lost-update/trace-1.json tests/cases/concurrency/race-lost-update.lwt
```

第一条记录的轨迹、第二条按轨迹重放，stdout 逐字节相同（实测退出码 0、输出 `1`）。说明：同一程序在固定策略下永远同一输出；换种子得到另一交错。

## 3. absent：`absent/ordered-aggregate/`（200 种子 1 种结果）

程序 `absent/ordered-aggregate/program.lwt` 让三个任务只计算并返回，主任务按输入顺序 `join` 并按固定顺序输出——结果不依赖调度。

| 项 | 实测 |
|---|---|
| 种子范围 | `1..200`（200 个） |
| 结果类数 | **1** |
| 唯一类 | `exit=0`, `stdout_sha256=f6d7234415b8…`, 200 个种子全部同类，trace `trace-1.json` |
| 可重放 | `reproduced=True` |

说明：并非所有并发程序都有调度分歧；有序聚合（无共享可变状态的交错敏感点）在 200 个种子下只有一种输出，证明探索工具不会凭空制造分歧。

## 4. tampered：`tampered/`（篡改被拒）

以 `found/lost-update/trace-1.json` 为基线，分别篡改 `chosen`（改成不在 ready 的非法值 999）、`source_sha256`（改全零）、`expected_stdout_sha256`（改全零），三次 `--schedule-replay` 均须 `CliError`/4。

| 篡改字段 | 退出码 | 诊断 |
|---|---:|---|
| `chosen` | 4 | `decision 0: chosen 999 not in ready [1, 2]` |
| `source_sha256` | 4 | `trace binding mismatch: source_sha256` |
| `expected_stdout_sha256` | 4 | `replay mismatch in expected_stdout_sha256: expected '000…', got '…'` |

逐次记录见 `tampered/tampered-log.json`（`all_rejected=true`），三份篡改轨迹 `trace-tampered-*.json` 留档。说明：轨迹与程序字节、策略、决策序列、输出摘要绑定，任何篡改都被拒绝，证据闭环成立。

## 5. 限制

- 探索使用 `random:SEED` 策略；`fifo` 是确定的单结果策略，通常不作为分歧探索对象。
- 200 种子是有限样本：found 说明「存在可观测分歧」，不声称已穷尽所有交错；absent 说明「200 样本内未观察到分歧」，不等于形式化证明无分歧。
- 固定测试向量依赖 splitmix64 自带 PRNG（见规范 §11.4），跨 Python 3.10/3.13、Windows/Linux 一致性由算法保证，但本阶段仅在本机 Windows CPython 3.13.x 实测；其它平台为未验证。
- 本目录是新证据，不覆盖 S10/S11 或任何既有固定 raw。
