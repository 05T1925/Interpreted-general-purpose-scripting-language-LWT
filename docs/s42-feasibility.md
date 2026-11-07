# S43 可行性与基线闸门报告（确定性可重放并发）

> 任务书编号为 S42「确定性并发」；用户裁决本阶段记为 **S43**，并叠加在 S42 语言核心增强（`feature/lwt-core-0.2`）之上。文件名沿用任务书验收清单的 `s42-*` 前缀。本文是 **WP0 闸门**的唯一功能外产物；闸门通过后才能进入 WP1 写并发功能代码。

## 1. 基线核对（任务书 §2，实测原文）

在仓库根 `大作业/` 执行：

| 命令 | 结果 |
|---|---|
| `git status -sb` | `## feature/deterministic-concurrency`（建分支前为 `## feature/lwt-core-0.2`，工作区有 WP0 三处修补的未提交改动） |
| `git log --oneline -8` | `a996591`(docs 数字校准)、`3b59f12`(docs 同步)、`aec6076`(app dict)、`125b4db`(画像)、`06fad50`(24 用例)、`35e4b37`(语言核心)、`5027860`(S12 main)、`cb23403` |
| `git branch -vv`（相关） | `feature/lwt-core-0.2 a996591`；`main 5027860 [origin/main]`；`milestone/final-acceptance f1b7fa9 [origin/...]` |
| `git worktree list` | 主树 `大作业/` @ `a996591 [feature/deterministic-concurrency]`；另有 3 个 S9 盲测 detached worktree 和 1 个 s39-agent-strategy worktree（**未触碰**） |
| `git fetch --all --prune` | 退出 0，无输出 |
| `git rev-parse HEAD main origin/main` | `a99659104bc5c4be4109c3b2b318c2e4814e6802` / `5027860efc8a1cce342ca13b1434d7724aeeffc4` / `5027860efc8a1cce342ca13b1434d7724aeeffc4` |
| `git merge-base --is-ancestor main origin/main; echo $?` | `exit=0`（main 未落后远端） |

**基线裁决**：任务书假设"在 `milestone/final-acceptance` 干净树上从 `main` 建分支"，但实测当前在含 6 笔未推送 S42 语言核心提交的 `feature/lwt-core-0.2`。用户裁决「叠加在语言核心之上，记为 S43」。因此从 `a996591` 创建 `feature/deterministic-concurrency`（分支名沿用任务书），保留上一轮 6 笔提交不动。上一轮成果构成本阶段基线：黑盒 **354** 项（非任务书假设的 287），规范已含 §4.4/§8.7/§8.8/§10.6 与 REPL。任务书的 287→332 口径在本阶段统一调整为 **354→399**（354 + 45 并发用例）。`milestone/final-acceptance` 的文档提交（`f1b7fa9`）**未纳入**本基线，单独列为未纳入的文档线。

**未提交改动处置**：建分支前工作区有 WP0 三处修补（`tools/run_tests.py`、`tests/test_runner.py`、`docs/test-matrix.md`），属本 WP0 产物，未清理/未 stash，见第 2 节。

## 2. WP0 阻断修补（不修完不得写并发功能代码）

| # | 修补 | 命令 / 验证 | 结果 |
|---|---|---|---|
| 1 | `VALID_SPEC_REFS` 增加 `11`, `11.1`–`11.9`，保持未知引用报错 | `tools/run_tests.py` 白名单 + `python -m unittest tests.test_runner.CaseInventoryTests.test_concurrency_spec_sections_11_and_11_x_are_valid_references tests.test_runner.CaseInventoryTests.test_unknown_spec_section_12_is_rejected -v` | 两条通过；`11`–`11.9` 被接受，`12` 仍报 `existing language-spec section` 配置错误 |
| 2 | `tests/test_runner.py` 补接受 11.x / 拒绝 12 的回归 | `python -m unittest tests.test_runner -q` | `Ran 34 tests ... OK`（新增 2 条，共 34） |
| 3 | `docs/test-matrix.md` §2.1「§1–§9」→「§1–§11」，新增第 11 节映射表 | Markdown 链接/围栏检查；`python tools/run_tests.py --case args-empty` | 表述已更新；单条黑盒退出 0，配置有效 |

`tools/check_project_integrity.py` 复用 runner 的 metadata 校验，无需重复修改；WP3 落地 11.x 用例后统一核对数字。

## 3. 七个新名字全仓扫描（任务书 §5.9 破坏性变更审计）

命令（在 `大作业/`，对 `main` 与当前 HEAD 两个 tree 都跑）:

```bash
for n in spawn join yield channel send receive close; do
  git grep -c -w "$n" main -- '*.lwt' | awk -F: '{s+=$2} END{print "'$n' : " s+0}'
done
git grep -n -w -E 'spawn|join|yield|channel|send|receive|close' main -- '*.lwt'
```

结果（`main` 与 `HEAD` 的 `.lwt` 完全相同）:

| 名字 | main | HEAD | 名字 | main | HEAD |
|---|---:|---:|---|---:|---:|
| `spawn` | 0 | 0 | `receive` | 0 | 0 |
| `join` | 0 | 0 | `close` | 0 | 0 |
| `yield` | 0 | 0 | `channel` | 0 | 0 |
| `send` | 0 | 0 | | | |

`git grep -n -w -E ... main -- '*.lwt'` 无输出（零匹配）。结论：`spawn` 新保留字与 6 个新内建名（`join/yield/channel/send/receive/close`）**不与现有 `.lwt` 标识符冲突**，任务书 §5.9 的破坏性变更在现有用例上风险为零。规范 §11.9 仍须写明该变更（沿用 S25 `import`、S26 `attempt/recover` 的写法）。注意：任务书旧的 R42-01 延伸提醒——新内建名会与既有**用户函数定义**冲突（如上一轮 `fn values()` 与新内建 `values` 冲突），但本轮扫描的 6 个名字在 `.lwt` 中零出现，故无此类冲突。

## 4. 基线性能剖析

见 `docs/s42-baseline-profile.txt`（`cProfile -s cumtime` 与 `-X importtime` 的原始前 15/10 行）。相对热点：`_evaluate` 累计 0.394s、`isinstance` 1,272,726 次 0.120s；导入热点为 `encodings`/`importlib` 与标准库。该剖析仅作 S43 的相对定位，**不与 S11 绝对值比较**，本阶段不是优化任务。

## 5. 调度器原型与三闸门（WP0 核心）

原型位于 Git 工作树**之外**的 `<workspace>/tmp/s42_scheduler_probe.py`，用**协作式 generator 模型**严格验证调度算法（同一进程、单线程驱动各任务 generator，调度点显式 yield）。理由见第 6 节的可行性发现。

命令：`python ../tmp/s42_scheduler_probe.py`（cwd = 仓库根）。完整 JSON 见本文件末尾附录。

| 闸门 | 判据 | 实测 | 结论 |
|---|---|---|---|
| G1 交替 yield 10 次一致 | 10 个 sha256 全部相同 | fifo `df38d4ee…b83858e57b` ×10；random:7 `63a7b1f5…ea07b113a` ×10 | 通过 |
| G2 稳定丢更新 | 固定策略下 counter 稳定且 < 2 | `[1]×10`（两个任务读—yield—写，稳定丢 1 次） | 通过 |
| G3 死锁不挂死 | 双 block 时状态=deadlock 且进程退出 | `{"status":"deadlock","deadlock":true}`，退出 0 | 通过 |
| G4 PRNG 跨种子可复现 | seed 1/7/42 各 10 向量稳定且互异 | 三组 10 向量互异；无 `random` 模块、无字典迭代依赖 | 通过 |
| G5 无 spawn 基线计时 | ≥5 次 | `bench/arithmetic.lwt -- 5000` 5 次：median 521.422ms、min 506.447、max 548.494 | 已记录 |

**零退化闸门的处理**：WP0 尚无可执行的 `spawn` 语法，无法在同一个解释器上做"加/不加 spawn"的端到端对比。为**避免假证据**，本阶段只记录无 spawn 基线（G5），把"有/无 spawn 无可测退化"的判定**推迟到 WP2**（接线后同一解释器上真实对比 5 次）。这是诚实的分期，不是跳过。

## 6. 可行性发现与 WP2 缓解（关键）

1. **fifo 语义必须精确化（写进规范 §11.4）**：任务书 §5.4 字面写「fifo 选择任务编号最小的就绪任务」。原型证明：若把 yield 后的任务放回一个就绪**集合**并每次取最小编号，则低编号任务会持续自我调度、饥饿其它任务（第一次原型因此挂住）。**必须**把 fifo 定义为**先进先出队列**：`spawn` 与 `yield` 的任务入队尾、队首出队；任务书说的"编号最小"只在**同一批初始 spawn 入队时按编号排序**体现。这样既保持纯函数性（不依赖时间/线程 id/字典序），又避免饥饿。该偏离将在 WP1 写进规范 §11.4 并在阶段报告「语义决策与偏离」列出。
2. **真实线程 Condition 移交有唤醒丢失风险（WP2 缓解）**：第一次原型用 `threading.Condition` + `notify_all()` 作令牌移交，在本机 Windows Python 3.13.x 上出现间歇挂起（带诊断打印改变时序时可正常交替，去掉打印后稳定挂住），符合 lost-wakeup 竞态特征。WP2 的生产调度器**不得**直接照搬该骨架，须改用**每个任务一个 `threading.Event` 的显式令牌移交** + 有界 `wait(timeout)` 兜底；I7「线程不泄漏」必须在 `tests/test_concurrency.py` 中对正常返回 / RuntimeError / 死锁三条路径用 `threading.enumerate()` 断言。本协作式原型证明**调度算法本身**确定可复现，但**不宣称**线程化实现已被 WP0 证明；那是 WP2 的验证责任。
3. **I/O 批次屏障与死锁的边界**：增强版任务书要求「任务 A 阻塞 join + 任务 B io_pending + 任务 C 可运行」不得误判死锁。WP2 的状态机须区分 `blocked`（真等待）与 `io_pending`（批次等待）：`ready` 空但存在 `io_pending` 时等待当前批 I/O 完成后按任务编号放回就绪，**不**按死锁处理。协作式原型用 `("io", …)` 调度点建模，WP2 用 `ThreadPoolExecutor` 实现。

## 7. 闸门结论

**WP0 闸门通过**（原型 G1–G5 全部成立），可进入 WP1。附带的三项语义/实现决策（fifo 队列精确化、线程 Event 移交、I/O 批次屏障）为 WP1/WP2 的强制约束，已记录在第 6 节与阶段报告「偏离」栏。若 WP2 的线程化实现无法满足"10 次逐字节一致"或"线程不泄漏"，按任务书 §10 停止规则交修复报告；若确认单令牌 + 宿主线程架构在本平台不可稳定复现，执行附录 A 的 Plan B（不改语言语义的并行后端）。

## 附录：原型完整输出（摘录）

```json
{
  "schema": "s43-feasibility-probe/1",
  "model": "cooperative generators (algorithmic determinism)",
  "yield_fifo_sha256_unique": 1,
  "yield_random7_sha256_unique": 1,
  "lost_update_fifo": [1,1,1,1,1,1,1,1,1,1],
  "deadlock": {"status": "deadlock", "deadlock": true},
  "prng_vectors_seed_1": [27,44,18,53,33,82,10,74,31,1],
  "prng_vectors_seed_7": [19,86,75,67,48,59,92,96,53,63],
  "prng_vectors_seed_42": [42,6,54,6,58,88,38,91,22,15],
  "timing_no_spawn_baseline": {"repeats":5,"median_ms":521.422,"min_ms":506.447,"max_ms":548.494},
  "gates": {"deadlock_detected":true,"lost_update_stable":true,"lost_update_witness":true,
            "no_spawn_baseline_recorded":true,"prng_distinct_seeds":true,
            "yield_fifo_stable":true,"yield_random7_stable":true}
}
```
