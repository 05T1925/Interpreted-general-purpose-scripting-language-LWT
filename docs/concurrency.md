# LWT 确定性并发契约卡（S43）

> 一页速查。权威语义见[正式规范第 11 节](language-spec.md)；人用说明见[开发指南](developer-guide.md)。设计目标：**每一次交错都可复现、可断言、可探索**，不是加速 CPU 计算。

## 语法（7 个能力）

```lwt
let t = spawn f(a, b);        # 当前源文件函数；也可 spawn m.f(...) 模块限定
let r = join(t);              # 等待任务、返回值或原位置重抛错误
yield();                      # 显式让步调度点
let ch = channel();           # 无界 FIFO 通道
send(ch, value);              # 追加到队尾，返回 null
let v = receive(ch);          # 队列空且未关闭时阻塞；空且已关闭返回 null
close(ch);                    # 幂等关闭；关闭后 send 报错
```

`spawn` 是唯一新保留字（前缀表达式，必须带括号）；其余六个是预置函数名，不是关键字。`yield` 仍可作变量名，但不能声明同名用户函数。

## 五个调度点

`yield()`、阻塞的 `receive`、阻塞的 `join`、任务结束、`read_text` 的 I/O 点。两个调度点之间所有 LWT 操作原子完成：`emit` 不半行、`x = x + 1` 不中途被切。任务共享模块全局变量根作用域、数组/record 引用、stdout、文件系统、`args()`；任务局部作用域独立。任务内 `input()` 是 `RuntimeError`。

## 调度与轨迹

- 默认策略 `fifo`：真 FIFO 队列，`spawn`/`yield` 入队尾、队首出队（不是"每次选最小编号"——那会让低编号任务饥饿其它任务，见规范 §11.4）。
- `random:SEED`：自带 splitmix64 PRNG，对排序后的就绪快照等概率选择；每个调度点消耗一次随机数；跨 Python 3.10/3.13、Windows/Linux 逐位复现。测试向量见规范 §11.4。
- `--schedule-log=FILE` 记录轨迹；`--schedule-replay=FILE` 强制重放。轨迹绑定 `source` + `source_sha256`、`program_args`、`policy`、`expected_exit_code`、`expected_stdout_sha256`、`expected_stderr_sha256`、每条 `decisions[i].{index,ready,chosen}`。任何不符 → `CliError`/4（消息指出第几个决策点或哪个绑定字段）。
- `--schedule-log` 与 `--schedule-replay` 互斥；对 `--repl`/`--check`/`--profile` 传调度开关是 `CliError`/4。

## 错误与收尾

任务内未捕获 `RuntimeError` 不打印、不终止进程，保存在结果中；`join` 以**原始 category/message/source/line/column** 重抛（可被 `attempt/recover` 捕获）。无人 `join` 的失败任务在程序收尾按编号抛出。就绪集为空、无 `io_pending`、仍有未完成任务 → `RuntimeError: deadlock detected`（退出 3），不挂死、不留后台线程。收尾按任务编号 join 所有未完成任务，含任务内再 `spawn` 的后代。

## I/O 边界（重要）

`read_text` 在存在其它任务时把读取提交给内部线程池，任务转 `io_pending`、交还令牌；就绪集空但有 `io_pending` 时等待当前批 I/O 全部完成，再按任务编号放回就绪（批次屏障），确定性不依赖磁盘完成顺序。**只对普通文件保证重叠**；FIFO、设备文件、网络挂载的终止性不在契约内，测试只用普通文件。CPU 计算不因 `spawn` 变快（GIL + 单令牌），重叠只在等待型 I/O。

## 工具边界

| 工具 | 遇 spawn |
|---|---|
| `--check` | 诊断 `E-SPAWN-001`（目标不存在）/`E-SPAWN-002`（实参数量），文本与 JSON 均含；不执行、不检查并发正确性 |
| `--profile` | 执行前 `CliError`/4，不产生部分档案 |
| CLI debugger / DAP | 执行前 `CliError`/4，不产生半真断点 |
| LSP | 补 `SpawnExpression` 节点遍历，不崩溃；语义不变 |

## 三条反模式

1. **把 `yield` 当锁**：`yield()` 只是让步点，不提供互斥；两个任务 `读—yield—写` 同一全局变量会稳定丢更新（规范 §11.3/§11.4 的 `lost-update` 见证）。需要共享计数请用单任务归并或通道。
2. **依赖任务完成顺序输出**：调度顺序由策略决定，不是墙钟；用输入顺序的专属通道或按编号 `join` 收集，别用"谁先完成谁先 emit"。
3. **在 `--profile`/调试器下期望并发**：这些工具明确拒绝 `spawn`（退出 4），不要为它们写"尽力而为"的并发断点路径——那会产生不可信证据。

## 模型检查工具（S46）

`tools/model_check_concurrency.py` 对小型程序做**有界**系统化调度探索：枚举每个调度点的 `ready` 备选，强制前缀重跑，检查 corpus 的 `.model.json` 不变量（通道精确一次/FIFO/close 排空、join 错误重抛、死锁、后代收尾）。违反时贪心最小化前缀并写 `--schedule-replay` 轨迹。

- **不是形式化证明**：只覆盖 `--max-runs`/`--max-decisions`/`--time-budget` 内的路径；预算耗尽写 `BUDGET_EXHAUSTED`，不写 PASS。
- corpus 在 `tests/concurrency-model/`（**不在** `tests/cases/`，黑盒计数仍 400）；`lost-update` 的两种结果是 `allowed_outcomes`，不是违规。
- `--mutant duplicate-delivery` 仅在工具进程内复现 S45 缺陷，用于证明检查器能抓到随机抽样漏掉的交接时序；产品路径不变。
- 算法、预算、witness 读法与限制见[模型检查说明](concurrency-model-check.md)；S46 实测见[S46 验证报告](s46-concurrency-verification.md)。

## 完整示例

见 `app/concurrent_log_report.lwt`（233 行）：每文件 `spawn` 一个任务读取，专属通道按输入顺序收集，坏文件用 `attempt/recover` 降级为 unavailable；`docs/s42-app-dev-log.md` 有差分等价契约。三态证据见 `reports/s42-schedules/summary.md`。
