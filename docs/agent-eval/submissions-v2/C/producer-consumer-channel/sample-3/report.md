# pipeline.lwt 交付报告

## 1. 依据

- 仅阅读 `docs/language-spec.md`（C 组消融：仅语言规范）。相关小节：
  - §11.2 语法：`spawn f(...)` 为前缀表达式；`join/yield/channel/send/receive/close` 为预置函数。
  - §11.3 调度点：`spawn` 本身不切换；调度点仅有 `yield()`、阻塞 `receive`、阻塞 `join`、任务结束、`read_text` I/O。
  - §11.5 通道：`channel()` 无界 FIFO；`send` 尾插；`receive` 非空立即返回（非调度点），空且未关闭时阻塞，空且已关闭返回 `null`；`close` 幂等。
  - §11.6 错误传播：任务内未捕获错误存入任务结果，`join` 以原始 category/message 重新抛出，可被 `attempt/recover` 捕获。
  - §11.7 收尾：顶层语句结束后按编号回收未完成任务，已完成任务的 `emit` 输出保留。
  - §10.6 `throw`：字符串值包装为 `User` 类别的 Error，`message` 即原文；`p.message` 可取回。
  - §4.2：`!=` 对所有值有定义（整数与 `null` 类型不同故不等）。
  - §6：`emit` 输出一个值加 LF；`str` 用于整数转字符串拼接。

## 2. 程序结构

- `produce(ch)`：依次 `send(ch, 1/2/3)`，随后 `close(ch)`。
- 主任务：`channel()` 建通道 → `spawn produce(ch)`（不切换）→ `receive` 循环，值非 `null` 时累加 → `emit "sum " + str(sum)`。
- `boom()`：`throw "task failed";`。
- `spawn boom()` 后执行题面指定形式 `attempt { join(t); } recover (p) { emit "caught:" + p.message; }`。

确定性来源：`spawn` 不切换，主任务首次 `receive` 在空且未关闭通道上阻塞，才轮到生产者；生产者无调度点，一次连续发完 3 条并关闭；此后 `receive` 每次都能非阻塞取到元素或 `null`。累加与元素顺序无关，因此在任何交错下输出相同。程序不调用 `args()`、`input()`，不读 stdin。

## 3. 实测（均在仓库根目录，仅用 `python -m lwt`）

命令：

```
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

- stdout（`od -c` 原始字节）：`sum 6\ncaught:task failed\n`
  - repr：`'sum 6\ncaught:task failed\n'`
- stderr：空（0 字节）
- 退出码：0

### 3.1 默认 fifo 重复性

连续运行 5 次，每次均为 `exit=0`、stderr 0 字节、stdout 完全相同的两行（`'sum 6\ncaught:task failed'`）。

### 3.2 附加交叉验证（非题目要求，仍走公开 CLI）

`--schedule=random:0/1/7/42` 四个种子下均为 `exit=0`，输出同为 `sum 6` 与 `caught:task failed`，说明结果不依赖交错。

## 4. 失败与修订

- 失败运行次数：0。
- 代码修订次数：0（首版一次通过全部检查）。

## 5. 隔离声明

- 只阅读了 `TASK.md`、`AGENTS.md`（仓库协作规则，未提供语言细节）与本任务允许的 `docs/language-spec.md`；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 运行只用 `python -m lwt <file>`（及同一入口的 `--version`、`--schedule=...` 选项）；未用其他语言生成输出或改写程序。
- 只写入 `docs/agent-eval/submissions/producer-consumer-channel/` 下的 `pipeline.lwt` 与本报告。
