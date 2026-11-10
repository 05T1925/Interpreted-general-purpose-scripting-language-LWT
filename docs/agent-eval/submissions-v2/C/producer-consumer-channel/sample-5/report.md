# 盲测报告：pipeline.lwt（生产者/消费者 + 失败任务）

## 1. 题目与交付物

- 程序：`pipeline.lwt`（本目录）
- 本报告：`report.md`
- 只写入 `docs/agent-eval/submissions/producer-consumer-channel/`。

## 2. 依据文档与小节

仅阅读允许的 `docs/language-spec.md`：

| 需求点 | 依据章节 |
|---|---|
| `spawn` 前缀表达式、不加分号、目标为当前文件函数 | §3（`spawn_expr`）、§11.2 |
| `spawn` 返回 Task，本身不是调度点，任务按编号入就绪队列 | §11.3 |
| `yield`/阻塞 `receive`/阻塞 `join`/任务结束/`read_text` 为唯一调度点，`send` 不是调度点 | §11.3 |
| 无界 FIFO 通道；`send` 返回 `null`；`close` 幂等；关闭后取完余量再返回 `null` | §6 预置函数表、§11.5 |
| 默认 `fifo` 策略：spawn 与让出任务入队尾、队首出队，输出可复现 | §11.4 |
| `throw "task failed"` 产生类别 `User` 的 Error，`message` 为原文 | §10.6、§7 错误表 |
| `attempt { } recover (p) { }` 捕获退出码 3 的 LWT 错误（含 `User`） | §5、§10.1、§10.6 |
| `join` 失败以原始 category/message/source/line/column 重抛，可被 attempt 捕获 | §6 表、§11.6 |
| `+` 只接受两个整数或两个字符串，无隐式转换（因此用 `str(...)`） | §4.2 |
| 收尾只 join“未完成任务”，已 join 的失败任务不再影响退出码 | §11.7 |
| `emit` 输出后接 LF；成功不额外输出，诊断写 stderr | §4.3、§6 |

## 3. 程序结构

1. `fn produce(ch)`：依次 `send(ch, 1..3)` 后 `close(ch)`。
2. 顶层 `let ch = channel();`、`let producer = spawn produce(ch);`。
3. 主任务 `receive` 循环：`while (value != null) { total = total + value; value = receive(ch); }`，随后 `emit "sum " + str(total);`。
4. `fn boom() { throw "task failed"; }`，`let bad = spawn boom();`，用 `attempt { join(bad); } recover (problem) { emit "caught:" + problem.message; }`。

fifo 下的确定性来源：`spawn` 不切换；主任务首次 `receive` 于空且未关闭的通道上阻塞（调度点）→ 生产者独占令牌依次 `send` 三次并 `close`（`send` 不是调度点），任务结束交还令牌 → 主任务连续取到 `1、2、3`（非空 `receive` 不是调度点）后取到 `null`。第二次 `spawn` 后 `join` 阻塞，失败任务运行至结束，`join` 重抛被 `recover` 捕获。

## 4. 运行命令与结果

命令（在仓库根目录执行，仅用公开入口，未传 `--` 之后的程序实参，stdin 为 `/dev/null`）：

```text
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

| 项 | 值 |
|---|---|
| stdout repr | `'sum 6\ncaught:task failed\n'`（25 字节） |
| stderr | 空（0 字节） |
| 退出码 | 0 |

字节级核对（`od -c`）：`s u m   6 \n c a u g h t : t a s k   f a i l e d \n`，换行均为 LF。

## 5. 确定性验证

默认 `fifo` 下连续运行 20 次（stdin 重定向自 `/dev/null`），全部 `exit=0`；20 份 stdout 的 SHA-256 去重后只有
`9ea28f106cd35dbebc59cb6f3f78c5d9f4f03204d7d356bde3af2ebd2ef1c191` 一个值，stderr 均为 0 字节，即每次输出完全一致。

## 6. 失败与修订次数

- 语法/运行时失败次数：0。
- 修订次数：0（首个版本一次运行即通过；未改动任何行）。
- 正式自测运行：1 次 + 确定性重复 20 次，共 21 次，全部退出码 0、stderr 为空。

## 7. 隔离声明

1. 仅阅读 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
2. 未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
3. 仅通过 `python -m lwt <file>` 公开入口运行；未用其他语言生成输出或改写程序。
4. 仅在本目录 `docs/agent-eval/submissions/producer-consumer-channel/` 下写入 `pipeline.lwt` 与本报告。
