# producer-consumer-channel 盲测报告

## 1. 产物

- 程序：`docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt`
- 行为：生产者任务向通道 `ch` 依次发送 1、2、3 后 `close(ch)`；主任务用 `receive` 循环累加到 `null`，输出 `sum 6`；随后派生一个执行 `throw "task failed";` 的任务，用 `attempt { join(t); } recover (problem) { ... }` 捕获并输出 `caught:task failed`。

## 2. 依据文档与小节

- `docs/language-spec.md`
  - §3：`spawn` 前缀表达式语法；`while`/`break`；`attempt/recover` 语句形式。
  - §4.2、§4.3：`+` 只接受两个整数或两个字符串，无隐式转换（整数求和、字符串拼接分别使用 `+`，整数转字符串用 `str`）。
  - §5：顶层 `fn` 先登记后按源码顺序执行顶层语句；块作用域与 `break` 归属最近循环；`attempt` 捕获动态逸出的运行时错误。
  - §6：`channel()`、`send`、`receive`、`close`、`join`、`str` 的参数/返回与边界（`receive` 空且未关闭时阻塞，空且已关闭返回 `null`；`join` 失败时按原始 category/message/source/line/column 重抛）。
  - §7：成功退出码 0，诊断走 stderr。
  - §10.6：`throw "..."` 产生 `User` 类别 Error，`problem.message` 为原始消息。
  - §11.2–§11.7：`spawn` 本身不切换；五个调度点；默认 fifo 为真 FIFO 队列；通道为无界 FIFO；任务内未捕获错误保存在任务结果中，`join` 重抛且可被 `attempt/recover` 捕获；收尾按编号 join 未完成任务。
- `docs/concurrency.md`：七个并发能力的最小写法；五个调度点与两点间原子性；fifo 策略；`join` 原位置重抛；"不要依赖任务完成顺序输出"的反模式。
- `docs/developer-guide.md`：公开 CLI 形式 `python -m lwt SOURCE`、stdout 只含 `emit`、诊断写 stderr、退出码表、`attempt/recover` 示例。
- `.agents/skills/lwt-app/SKILL.md`：先静态核对语义再跑公开 CLI；并发子集边界与"用专属通道/按编号 join 收集"的写法。

## 3. 设计与确定性说明

- 通道 `ch` 在顶层 `let` 中创建，生产者函数通过共享的全局根作用域访问它；`spawn produce()` 只创建任务，不切换。
- 主任务首次 `receive(ch)` 时队列为空且未关闭，构成阻塞调度点，令牌交给唯一就绪的生产者；生产者 `send` 三次并 `close`，其间没有调度点，直到任务结束才交还令牌。
- 主任务随后连续 `receive` 取完 1、2、3，再取到 `null` 退出循环；`join(producer)` 确认生产者已正常结束，然后输出 `sum 6`。
- 第二个任务 `boom` 执行 `throw "task failed";`，任务内未捕获错误存入任务结果；`join(t)` 以原始消息重抛，`recover` 的 `problem.message` 为 `task failed`，输出 `caught:task failed`。
- 两行输出的先后完全由主任务语句顺序决定；生产者不产生 stdout，唯一交错点为阻塞的 `receive`/`join`，因此默认 `fifo` 下可重复。
- 程序不调用 `args()` 或 `input()`，不需要命令行参数或 stdin。

## 4. 运行证据

工作目录：仓库根目录（`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-producer-consumer-channel-s5`）。

命令（唯一使用的运行入口）：

```text
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

实测结果：

| 项目 | 值 |
|---|---|
| stdout（Python repr） | `'sum 6\ncaught:task failed\n'` |
| stdout 的 sha256 | `9ea28f106cd35dbebc59cb6f3f78c5d9f4f03204d7d356bde3af2ebd2ef1c191` |
| stderr（Python repr） | `''` |
| 退出码 | `0` |

一致性自测：同一命令连续运行 10 次，将 stdout、stderr 合并并追加退出码标记后逐次取摘要，10 次摘要均为 `c543c95da4b11730`（sha256 前 16 位），逐字节一致；stdout 哈希与上表相同。

## 5. 失败与修订次数

- 失败运行：0 次（首版即通过）。
- 修订：1 次，仅为把第二个任务的变量名 `failing` 改为题目片段中的 `t`（纯命名对齐，无语义变化）；改名后重新执行 10 次，结果一致。
- 未遇到词法、语法、运行时错误或死锁。

## 6. 隔离声明

- 只阅读了允许清单中的 `docs/language-spec.md`、`docs/concurrency.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 为定位提交目录，仅对仓库根与 `docs/`、`docs/agent-eval/submissions/` 做过目录列举，未打开清单外文件的内容。
- 仅使用 `python -m lwt <file>` 公开入口运行程序，未用其他语言生成输出或改写程序。
- 仅写入 `docs/agent-eval/submissions/producer-consumer-channel/` 下的 `pipeline.lwt` 与 `report.md`。
