# 盲测报告：producer-consumer-channel（C 组，仅语言规范）

## 1. 交付文件

- `pipeline.lwt`：题目要求的程序（生产者在 spawn 任务中向 `ch` 发送 1、2、3 后 `close(ch)`；主任务 `receive` 循环累加到 `null` 输出 `sum 6`；再 spawn 抛 `throw "task failed";` 的任务，用 `attempt { join(t); } recover (p) { ... }` 捕获并输出 `caught:task failed`）。

## 2. 依据文档与小节

只阅读了允许的 `docs/language-spec.md`，对应依据：

| 需求点 | 依据小节 | 采用的规范结论 |
|---|---|---|
| `spawn f(args)` 前缀表达式、返回 Task、`spawn` 本身不切换 | §3（`spawn_expr`）、§11.2、§11.3 | `let producer = spawn produce();` 合法；派生后主任务继续执行 |
| 调度点仅五类（`yield()`、阻塞 `receive`、阻塞 `join`、任务结束、`read_text` I/O） | §11.3 | 主任务在空通道 `receive` 处阻塞让出；`send`/`close` 不是调度点 |
| 默认 fifo 策略、就绪队列 FIFO | §11.4 | 只有一个就绪任务时选择唯一，输出与时间无关 |
| `channel()` 无界 FIFO；`send` 追加；`receive` 非空立即返回且非调度点，空且未关闭阻塞，空且已关闭返回 `null`；`close` 幂等 | §6 预置能力表、§11.5 | `while (item != null)` 循环在取完 1、2、3 后再拿到 `null` 退出 |
| 函数外层的变量根作用域共享、任务共享全局变量 | §5、§11.1 | 顶层 `let ch = channel();` 可被 `produce` 函数直接读取 |
| `throw` 字符串 → 类别 `User`、message 为原文、位置为 throw 语句 | §7、§10.6 | `p.message` 为 `task failed`，与 `"caught:"` 拼接得 `caught:task failed` |
| `attempt` 捕获所有退出码 3 的 LWT 错误（含 `User`）；`join` 失败按原始 category/message 重抛 | §10.6、§11.6 | `attempt { join(t); } recover (problem) { ... }` 能捕获任务内 throw |
| `emit` 输出显示串 + LF；`str(int)` 为十进制 | §4.3、§6 | `"sum " + str(total)` 输出 `sum 6` |
| 收尾按编号 join 未完成任务 | §11.7 | 两个任务均已完成（生产者正常结束、boom 已 join），收尾不再抛错 |

## 3. 确定性说明（为何每次完全一致）

默认 fifo 下，主任务顺序为：`spawn produce()`（不切换）→ `receive(ch)` 遇空且未关闭 → 阻塞（唯一调度点）；此时就绪集合只有生产者，它执行 `send 1/2/3` 与 `close` 后任务结束（`send`/`close` 均非调度点，不会被打断）；主任务恢复后队列非空，三次 `receive` 都不是调度点，可连续取完，第四次 `receive` 遇空且已关闭立即返回 `null`。随后 `spawn boom()` 不切换，`join(t)` 阻塞时只有 boom 就绪，抛错后 join 重抛。全过程没有"两个任务同时就绪"的时刻，也无时间/线程 id 依赖，因此输出逐字节固定。

## 4. 命令与实测结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-producer-consumer-channel-s2`

```
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

- stdout repr：`b'sum 6\ncaught:task failed\n'`
- stderr repr：`b''`（空）
- 退出码：`0`
- 文本形式：两行 `sum 6`、`caught:task failed`
- stdin 为 `DEVNULL`、未传任何程序实参（程序不调用 `args()` / `input()`）

补充验证：

1. 同一命令连续运行 25 次，按行归并计数为 25 份 `sum 6`、25 份 `caught:task failed`、25 次 `EXIT=0`，无任何差异。
2. `python -m lwt --schedule=fifo docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt` 显式指定默认策略，stdout 同上、stderr 空、退出码 0。

## 5. 失败与修订次数

- 首版 `pipeline.lwt` 一次通过，失败次数 0，修订次数 0（未改动程序文件）。
- 运行中未出现词法/语法/运行时错误，未出现死锁、挂起或非零退出码。

## 6. 隔离声明

1. 仅阅读 `TASK.md` 与允许的 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录，也未查看任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
2. 全程只用 `python -m lwt <file>` 公开入口运行程序（含显式 `--schedule=fifo`）；未用其他语言或工具生成输出、未改写程序。
3. 只在 `docs/agent-eval/submissions/producer-consumer-channel/` 下写入 `pipeline.lwt` 与本 `report.md`，未写入其他路径。
