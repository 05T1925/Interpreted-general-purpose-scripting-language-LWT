# S53 语义变异探针报告

> 本报告只说明**这些探针**能否被既有黑盒用例判红。有限探针的 killed 比例**不是总体正确率**，也不是质量保证；等价变异与测试缺口需要人工判断（S23 计划的口径，见 `docs/s23-test-adequacy-plan.md`）。

## 1. 目标、基线与停手判据

- **目标**：每处最小语义变异都必须被至少一个既有黑盒用例判红；用来量化 400 项黑盒的判别力，而不是证明解释器正确。
- **基线**：S23 的 10 条探针（9 killed / 1 survived / 0 invalid 的历史快照）；S53 复跑时发现 1 条补丁锚点因 S42 改动失效（invalid），另 1 条 survived 与另一条探针同补丁。
- **停手**：任何探针出现 invalid、或补丁锚点不再唯一匹配、或工作树被改动，立即停止并修正；不为了 killed 数量伪造用例。

## 2. 隔离与还原核验

- 每个探针只修改 `TemporaryDirectory` 中的项目副本，主工作树从不写入；运行前 `git status --porcelain` 为空：**True**；运行后仍为空：**True**。
- 补丁只有在源码片段**唯一匹配**时才应用（`patch target must occur once`）；基线副本先跑同一用例确认原本是绿的，否则记为 invalid 而不是 killed。

## 3. 探针结果

| 区域 | 探针 | 状态 | 判红用例 | 未判红的目标用例 |
|---|---|---|---|---|
| core | division-truncates-toward-zero | **killed** | `negative-floor-division-modulo` | — |
| core | modulo-loses-divisor-sign | **killed** | `negative-floor-division-modulo` | — |
| core | and-evaluates-skipped-right-side | **killed** | `short-circuit-and` | — |
| core | or-evaluates-skipped-right-side | **killed** | `short-circuit-or` | — |
| core | composite-values-use-structural-equality | **killed** | `record-instance-identity`, `arrays-identity-equality` | — |
| core | each-iterates-live-array | **killed** | `each-snapshot-replacement` | — |
| core | call-arguments-reversed | **killed** | `argument-evaluation-order-distinct-effects` | `argument-evaluation-order` |
| core | and-accepts-host-truthiness | **killed** | `boolean-left-is-strict` | — |
| core | len-counts-utf8-bytes | **killed** | `len-unicode-codepoints` | — |
| dict | dict-display-sorts-keys | **killed** | `dict-display-insertion-order` | — |
| dict | dict-display-reverses-insertion-order | **killed** | `dict-literal-display-order`, `dict-nested-display`, `dict-put-update-keeps-position` | — |
| dict | dict-get-missing-returns-null | **killed** | `dict-missing-key-read` | — |
| dict | dict-delete-missing-reports-true | **killed** | `dict-delete-missing` | — |
| finally | finally-runs-only-on-unrecovered-error | **killed** | `finally-break-passes`, `finally-on-normal-flow`, `finally-return-in-body-runs-first` | — |
| throw | throw-rethrow-loses-category | **killed** | `uncaught-throw-error-category` | `throw-error-rethrow` |
| concurrency | channel-receive-is-lifo | **killed** | `channel-fifo` | — |
| concurrency | send-skips-blocked-receiver | **killed** | `channel-block-receive` | `channel-multi-producer` |
| concurrency | scheduler-picks-last-ready | **killed** | `fifo-order`, `yield-three-tasks` | — |
| concurrency | join-returns-before-completion | **killed** | `join-preserves-output`, `spawn-join-return` | — |

合计：**19** 条探针，killed **19**、survived **0**、equivalent **0**、invalid **0**。

## 4. 覆盖到的新语义

| 区域 | 语义点 | 为什么此前没有验证 |
|---|---|---|
| dict | 插入序 / 缺键 / delete 返回值 | S42 引入 `dict`，S23 的探针集早于它 |
| finally | finally 在正常、return、break 路径上的执行 | S42 引入 `finally`（§10.6） |
| throw | 重抛保留 category | S42 引入 `throw` |
| concurrency | 通道 FIFO、send 交接、就绪队列 FIFO、join 阻塞 | S43 引入 §11；46 项并发用例从未被变异验证 |

## 5. 边界（必须与数字一起读）

- 探针是**人工挑选的有限语义点**，不是对 `lwt/` 的穷举变异；killed 比例不能外推为“解释器正确率”，也不能当作“测试充分”的证明（Just et al., ICSE/FSE 2018 指出变异测试受等价变异与测试集规模影响）。
- 等价变异不存在于本报告：每条 survived 都必须写出书面理由；S53 的处理是把同补丁的重复探针合并，并在 `passed_targets` 里保留“这条用例单独不判别”的证据。
- 探针只跑**目标用例**，不跑全量 400；因此它回答“是否至少有一条用例能判红”，不回答“有多少条能判红”。

## 6. 复现

```bash
python tools/audit_semantic_mutants.py --out-dir reports/s53-mutation
```
