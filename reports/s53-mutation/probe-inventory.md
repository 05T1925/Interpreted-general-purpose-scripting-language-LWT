# S53 变异探针清单

> 目的：回答“400 项黑盒到底有没有判别力”，不是证明解释器正确。有限探针的 killed 比例**不是总体正确率**（`docs/s23-test-adequacy-plan.md` 的口径）。

## 1. 方法与隔离

| 项 | 做法 |
|---|---|
| 隔离 | `tools/audit_semantic_mutants.py` 为每条探针建两个 `TemporaryDirectory` 项目副本（baseline / mutant），主工作树从不写入；运行前后各查一次 `git status --porcelain`，必须为空 |
| 锚定 | 补丁片段必须在目标源文件中**唯一匹配**（`patch target must occur once`），否则记 `invalid` 而不是 `killed` |
| 基线 | 先在正确副本上跑同一用例，必须原本是绿的；否则记 `invalid`（避免把“本来就红的用例”当成判别力） |
| 目标文件 | `lwt/runtime.py`（核心语义、dict、finally、throw、join）或 `lwt/concurrency.py`（通道与调度） |
| 证据 | 每条记录 `patch_sha256` + 变异后每个目标用例的 exit/stdout/stderr |

## 2. S23 的 10 条（历史快照与 S53 处置）

| 探针 | 语义点 | 锚定方式 | S53 处置 / 结果 |
|---|---|---|---|
| `division-truncates-toward-zero` | 整除向零截断 | `runtime.py` 的 `//` 分支 | 保持不变，killed |
| `modulo-loses-divisor-sign` | 取模符号 | `return left % right` | 保持不变，killed |
| `and-evaluates-skipped-right-side` | `and` 短路 | 去掉 false-left 早退 | 保持不变，killed |
| `or-evaluates-skipped-right-side` | `or` 短路 | 去掉 true-left 早退 | 保持不变，killed |
| `composite-values-use-structural-equality` | 复合值按身份相等 | `_EQUALITY_OPERATORS` 分支 | **S53 重锚**：S42 把 `_DictValue/_TaskValue/_ChannelValue` 加进 isinstance 元组，旧锚点匹配数为 0（已退化为 invalid）；重锚后 killed |
| `each-iterates-live-array` | `each` 用入口快照 | `snapshot = list(iterable)` | 保持不变，killed |
| `call-arguments-reversed` | 实参从左到右求值 | `for argument in expression.arguments` | **S53 合并**：原为两条同补丁探针（`...-evaluate-right-to-left` 与 `...-reversed-distinct-effects`），合并为一条、保留两个目标；killed（仅 distinct-effects 判红） |
| `and-accepts-host-truthiness` | `and` 左操作数严格布尔 | 去掉类型检查 | 保持不变，killed |
| `len-counts-utf8-bytes` | `len` 数字符而非字节 | `len(value.encode("utf-8"))` | 保持不变，killed |

### 2.1 两条历史问题的处理（不掩饰）

- **invalid 的那条**不是“新增失败”，而是 S42 改了源码后旧锚点失效。S23 的“9 killed / 1 survived”是当时的真实结果；S53 复跑得到 `invalid=1`，说明**探针本身需要跟着语义演进维护**。
- **survived 的那条**（`argument-evaluation-order`）在对称副作用下无法判别参数顺序：交换两个实参的求值顺序，输出仍是 `[1, 2]`。同一补丁在 `argument-evaluation-order-distinct-effects` 上被杀。因此不是等价变异，而是**目标用例过弱**——正是课件 5.5 提醒的“弱断言”陷阱。报告用 `passed_targets` 保留这条证据。

## 3. S53 新增 9 条（覆盖 S42/S43 新语义）

| 探针 | 区域 | 语义点 | 判红用例 |
|---|---|---|---|
| `dict-display-reverses-insertion-order` | dict | 显示按插入序（§4.4） | `dict-literal-display-order`、`dict-nested-display`、`dict-put-update-keeps-position` |
| `dict-get-missing-returns-null` | dict | 缺键必须报运行时错误 | `dict-missing-key-read` |
| `dict-delete-missing-reports-true` | dict | 删不存在的键返回 false | `dict-delete-missing` |
| `finally-runs-only-on-unrecovered-error` | finally | finally 在正常/return/break 路径都执行（§10.6） | `finally-on-normal-flow`、`finally-return-in-body-runs-first`、`finally-break-passes` |
| `throw-rethrow-loses-category` | throw | 重抛保留 category | `uncaught-throw-error-category` |
| `channel-receive-is-lifo` | concurrency | 通道 FIFO（§11.5） | `channel-fifo` |
| `send-skips-blocked-receiver` | concurrency | send 必须交接给已阻塞的接收者（S45 缺陷形状） | `channel-block-receive` |
| `scheduler-picks-last-ready` | concurrency | 就绪队列 FIFO（§11.4） | `fifo-order`、`yield-three-tasks` |
| `join-returns-before-completion` | concurrency | join 必须阻塞到目标完成（§11.6） | `spawn-join-return`、`join-preserves-output` |

## 4. 三个“目标用例单独不判别”的观测

| 探针 | 未判红的目标用例 | 说明 |
|---|---|---|
| `call-arguments-reversed` | `argument-evaluation-order` | 对称副作用，交换顺序输出不变 |
| `throw-rethrow-loses-category` | `throw-error-rethrow` | 该用例没有断言 category（只断言重抛后的消息/身份），属弱断言 |
| `send-skips-blocked-receiver` | `channel-multi-producer` | 多生产者用例的接收顺序恰好不依赖交接路径 |

这三条不是探针失败：同一变异各有另一条用例判红。它们记录的是**单个用例的判别力差异**，可用于后续补强。

## 5. 一个真实盲区：按 key 排序的显示

先试过 `dict-display-sorts-keys`（按 key 文本排序输出）：**survived**。原因是所有显示类用例的键恰好按字典序插入（`dict{"a": 1, "b": 2}`、`dict{"arr": ..., "sub": ...}`），排序前后输出一致。

- 这说明 400 项黑盒在“键序”上只覆盖了“插入序=字典序”的情形；
- 该变异未被纳入正式探针集（否则会以 killed 数量换一个假象），替换为可在同一批用例上观察的逆序变异；
- 若后续允许扩充用例，最小补强是新增一条“非字典序插入 + 显示”的用例（会改变 400 计数，S53 不做）。

## 6. 复现

```bash
python tools/audit_semantic_mutants.py --out-dir reports/s53-mutation
```

输出 `mutation-report.json`（机器可读）与 `mutation-report.md`（人读）。
