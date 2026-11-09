# LWT 有界调度探索工具（S46）

> 一句话：对**小型** LWT 并发程序枚举调度选择树，在有界预算内检查通道/关闭/join/死锁/收尾等不变量；违反时最小化调度前缀并生成可重放的 `--schedule-replay` 轨迹。**这是有界系统化探索（bounded systematic schedule exploration），不是形式化模型检验，不证明"所有调度都正确"。**

## 1. 为什么需要它

S45 发现并修复了 `send` 的重复投递缺陷：值既入队又注入阻塞接收者，下一次 `receive` 又拿到同一元素（违反规范 §11.5"每个元素只投递一次"）。该缺陷在 **46 项并发黑盒 + 200 个随机种子**下都没暴露——因为既有用例都没有"阻塞接收者后再收一次"的形状，随机抽样也不保证覆盖特定交接时序。

随机种子回答的是"这些采样里有没有分歧"，有界探索回答的是"在给定深度/预算内，**每一条**可选调度路径有没有违反不变量"。后者对小型程序更接近穷尽，且失败时给出可复现的最小前缀。

## 2. 术语与边界

| 术语 | 含义 |
|---|---|
| 调度点 | 规范 §11.4 的五个：`yield()`、阻塞 `receive`、阻塞 `join`、任务结束、`read_text` 的 I/O 点 |
| 决策 | 一次调度点上的选择：`{index, ready[], chosen}`，与轨迹 schema 完全一致 |
| 前缀 | 前 N 个决策强制取给定任务 id 的序列；N 之后的决策回退到 `fifo` |
| 就绪集 `ready` | 该决策点的候选任务 id 的**排序快照**（与轨迹一致，顺序无关） |
| 预算 | `--max-runs`（每个程序最多执行次数）、`--max-decisions`（前缀深度上限）、`--time-budget`（整次调用墙钟秒数） |

**不做的事**：不枚举堆状态、不做状态去重（只做前缀去重）、不覆盖非调度不确定性（墙钟、磁盘完成顺序已由批次屏障固定）、不分析多程序组合、不对无限循环做硬超时（corpus 是受信小程序；死锁由调度器自身检测）。

## 3. 算法

```
queue = [()]                       # 空前缀 = 默认 fifo
seen  = {()}
while queue and runs < max_runs and now < deadline:
    prefix = queue.popleft()
    result = execute(program, schedule_choices=prefix)   # 新跑一次
    runs += 1
    记录 outcome (exit, stdout_sha256, stderr_sha256) 与首个 witness
    若 outcome 不满足 .model.json → 记 violation(prefix)
    对 result.decisions 的每个 j（len(ready) > 1）:
        base = decisions[:j] 的实际 chosen 序列
        对每个 alt != chosen: 入队 base + (alt,)，前缀去重、深度 ≤ max_decisions
```

- **解析一次**：`load_module_graph` 只做一次；每次执行用同一 AST/模块图新建运行时。
- **结果分类**：`(exit_code, stdout_sha256, stderr_sha256)`；每个新类保留首个 witness。
- **非法前缀**：强制选择不在 `ready` 中 → `ScheduleReplayMismatch` → `CliError`/4，标记 `INVALID_PREFIX` 并跳过，**不视为程序失败**。工具自身生成的前缀都取自 `ready`，因此正常探索不会产生非法前缀；该路径由测试固定。
- **预算耗尽**：队列未空或触及任一上限 → `BUDGET_EXHAUSTED`。**预算耗尽绝不写成 PASS**；`--require-clean` 下返回非零。

### 最小化

对违反前缀做两轮贪心：

1. **删除**：逐位尝试去掉一个选择，若仍违反则保留删除（从头重试直到稳定）。
2. **替换**：逐位尝试把选择替换为当前 `ready` 的第一个 id，若仍违反则保留；再做一轮删除。

结果是"仍能触发违反的最短前缀"，并重新执行该前缀取输出/决策用于轨迹。空前缀是合法的最小结果（默认 fifo 就能触发时）。

### 轨迹与重放

violation/outcome witness 写入 `trace.json`，字段与 `lwt-schedule-trace/1` 完全一致（`source`、`source_sha256`、`program_args`、`policy`、`expected_*`、`decisions`）。

- **clean witness**：`python -m lwt --schedule-replay=trace.json PROGRAM`，逐字节比对 stdout 与退出码。
- **mutant witness**：故障是合成注入、不存在于产品，干净进程无法复现；因此用**同一个 CLI 入口** + 工具内故障注入的 replay harness 重放，证据里 `replay.mode` 标为 `tool-harness-duplicate-delivery`。工具绝不把 mutant 注入到产品路径。

## 4. 不变量格式

每个程序旁边一个 `<stem>.model.json`：

```json
{
  "id": "channel-exactly-once",
  "spec_refs": ["§11.5", "§11.7"],
  "max_decisions": 30,
  "tags": ["channel", "exactly-once"],
  "expected": {"exit": 0, "stdout": "7\nnull\n"}
}
```

判定规则：

- `expected.stdout`：stdout 逐字节（UTF-8 文本）相等；
- `expected.stderr_contains`：stderr 包含子串（用于死锁诊断）；
- `expected.exit`：退出码相等（缺省 0）；
- `expected.allowed_outcomes`: 列表，任一 `{exit, stdout}` 匹配即通过。用于记录**允许的分歧**（如 `lost-update` 的 1/2 两种结果），不把"有两种结果"误报为 bug。

## 5. corpus（`tests/concurrency-model/`）

| 程序 | 不变量 | 规范 |
|---|---|---|
| `channel-exactly-once` | 阻塞接收者先得 7，下一次 `receive` 得 `null`；每个元素只投递一次 | §11.5/§11.7 |
| `channel-fifo-three` | 1,2,3 按 FIFO 输出 `123` | §11.5/§11.7 |
| `channel-close-drain` | 关闭后先取完余量，再 `null` | §11.5/§11.7 |
| `join-error-origin` | `join` 重抛原始 category/message，可被 `attempt/recover` 捕获 | §11.6/§11.9 |
| `deadlock-two-receivers` | 两个任务阻塞在不同空通道、主任务 join → `deadlock detected`（退出 3），不挂死 | §11.8 |
| `nested-spawn-drain` | 顶层结束后按编号收尾所有后代任务 | §11.9 |
| `lost-update` | 允许 `1`/`2` 两种结果；用于展示分歧与 witness，**不作为违规** | §11.3/§11.4 |
| `channel-blocked-then-queued` | 阻塞接收者 + 后续入队值保持 FIFO（S45 回归） | §11.5/§11.7 |

corpus 故意**不放入** `tests/cases/`：黑盒计数保持 400，S46 的模型用例单独计。

## 6. 故障注入自测

`--mutant duplicate-delivery` 在**工具进程内**把 `Scheduler.wake_receiver` 包装为"先正常交接、再把同一值 append 到 `channel.items`"，复现 S45 的缺陷形状；退出即恢复，产品路径不受影响。

- clean：`channel-exactly-once` → 0 violation；
- mutant：4 个通道程序各 ≥1 violation，最小前缀 `[]`（fifo 下主任务先阻塞在 `receive`，已能触发），`--schedule-replay` 在 harness 下复现 `7\n7\n`；
- 这证明检查器能抓到"随机抽样漏掉"的交接时序缺陷，而**不是**声称当前产品有 bug。

## 7. 输出与读法

`--out DIR` 生成：

- `summary.json`：`mode`（mutant/预算/耗时）、`programs[]`（runs、prefixes、decision points、max depth、outcomes、violations、minimized prefix、replay、budget 状态）、`totals`、`all_pass`；
- `summary.md`：同内容的表格 + 每个 outcome 的 `exit/stdout/count/first_prefix`；
- `witnesses/<id>/outcome-<n>-trace.json`、`violation-<n>-trace.json`：可直接 `--schedule-replay`。

读 witness：先看 `minimized_prefix`（长度越小越易解释），再看 `decisions` 中该前缀位置前后的 `ready` 变化，最后用 trace 重放确认 stdout/exit。

## 8. 限制（必须如实说明）

1. **有界不等于证明**：只覆盖 `max_runs × max_decisions` 内的前缀；报告状态为 `COMPLETE` 也仅表示"已发现的全部前缀都跑完"，不是所有可能调度的形式化证明。
2. **无堆状态去重**：相同前缀只跑一次，但不同前缀到达同一程序状态时会重复执行；大程序会指数爆炸（预算兜底）。
3. **单程序、单入口**：不支持多模块组合、外部 I/O 内容变化、环境差异。
4. **受信 corpus**：进程内执行依赖调度器自身的死锁检测；不设每 run 硬超时（避免为不可中断的 Python 线程制造假安全感）。
5. **mutant 重放口径**：mutant witness 只在工具 harness 下可复现，不能当作产品 CLI 的独立复现。

## 9. 运行

```bash
# clean corpus（CI 同参数）
python tools/model_check_concurrency.py --corpus tests/concurrency-model \
    --max-runs 300 --time-budget 90 --require-clean \
    --out reports/s46-concurrency-model

# 故障注入自测（期望找到违反；成功条件是有违反且 witness 可重放）
python tools/model_check_concurrency.py --corpus tests/concurrency-model \
    --max-runs 200 --time-budget 60 --mutant duplicate-delivery --expect-violation \
    --out reports/s46-concurrency-model/mutant
```

一键自检包也包含该步骤（`tools/run_acceptance_selfcheck.py`，`--model-budget` 控制），预算耗尽记为 `BUDGET_EXHAUSTED`/FAIL，不写成 PASS。
