# producer-consumer-channel 盲测报告

## 1. 产物

- 程序：`docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt`
- 本报告：`docs/agent-eval/submissions/producer-consumer-channel/report.md`

程序结构：`produce(ch)` 依次 `send(ch, 1/2/3)` 后 `close(ch)`；主任务先 `spawn` 生产者，再用 `receive` 循环累加到 `null`，输出 `sum 6`；随后 `spawn failer()`（`throw "task failed";`），以 `attempt { join(bad); } recover (p) { emit "caught:" + p.message; }` 捕获并输出 `caught:task failed`。程序不读取 `args()` 与 `input()`。

## 2. 依据文档与小节

| 依据 | 用到的规则 |
|---|---|
| `docs/language-spec.md` §11.2/§11.3 | `spawn` 为目标函数前缀表达式；`spawn` 本身不切换；调度点仅 `yield()`、阻塞 `receive`、阻塞 `join`、任务结束、`read_text` I/O |
| §11.5 | `channel()` 无界 FIFO；`send` 入队尾；队列非空时 `receive` 立即返回；空且未关闭时阻塞；空且已关闭返回 `null`；`close` 幂等 |
| §11.6 | `join` 以原始 category/message/source/line/column 重抛任务错误，可被 `attempt/recover` 捕获 |
| §11.7 | 顶层结束后按编号 join 未完成任务，已完成的 `emit` 保留；本例两个任务均显式 join 或已结束 |
| §10.6 | `throw "…"` 产生 `User` 类别错误，`p.message` 为原字符串 |
| §6 | `channel/send/receive/close/join/spawn` 的预置契约与 `emit` 输出规则 |
| `docs/concurrency.md`「语法」「五个调度点」「错误与收尾」 | 与上表一致的一页速查，确认默认 `fifo` 为真 FIFO 队列、错误在 `join` 处原位置重抛 |
| `docs/developer-guide.md` §1「先运行」「退出码和诊断」、§4「确定性并发」 | 公开入口 `python -m lwt SOURCE`、退出码含义、并发示例写法 |
| `.agents/skills/lwt-app/SKILL.md`「工作流程」「S43 并发子集的使用要点」 | 先 `--check` 再公开 CLI 运行；只用规范支持的能力；不把 `yield` 当锁、不依赖完成顺序输出 |

确定性论证：`spawn` 不切换，主任务在第一次 `receive` 时队列为空且未关闭，按 §11.5 阻塞并成为调度点，生产者因此获得令牌；生产者连续 `send` 与 `close` 之间没有调度点，三个元素与关闭标记一次性就绪，主任务随后每次都命中非空队列（最后一次命中「已关闭且空」）返回 `null`。第二个任务先 `spawn` 后立即 `join`，`join` 是阻塞调度点，错误只在 `join` 调用点重抛，`attempt` 必然捕获。整条路径不依赖调度选择的偶然性，默认 `fifo` 下逐字节一致。

## 3. 命令与实测结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-producer-consumer-channel-s4`

```
python -m lwt --check docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

- 退出码：0
- stdout：`Check passed: 1 source file(s).`
- stderr：空

```
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

- 退出码：0
- stdout（repr）：`b'sum 6\ncaught:task failed\n'`
- stderr（repr）：`b''`

为取原始字节，用 `python -c` 以内置 `subprocess` 调用同一条公开 CLI 并打印 `repr`（仅捕获，不参与任何计算或输出生成）。

### 3.1 默认 fifo 一致性

同一命令连续运行 30 次（stdin 指向 `DEVNULL`），对 `(退出码, stdout, stderr)` 去重：

```
unique results: 1
(0, b'sum 6\ncaught:task failed\n', b'')
```

### 3.2 调度策略旁证

| 命令附加参数 | 退出码 | stdout repr | stderr |
|---|---:|---|---|
| `--schedule=fifo` | 0 | `b'sum 6\ncaught:task failed\n'` | `b''` |
| `--schedule=random:1` | 0 | `b'sum 6\ncaught:task failed\n'` | `b''` |
| `--schedule=random:7` | 0 | `b'sum 6\ncaught:task failed\n'` | `b''` |
| `--schedule=random:42` | 0 | `b'sum 6\ncaught:task failed\n'` | `b''` |

题目只要求默认 fifo 一致；随机种子下输出相同是额外旁证：程序不依赖「谁先完成谁先 emit」。

## 4. 失败与修订次数

- 程序语义/语法修订：**0 次**。`pipeline.lwt` 首次写入即通过 `--check` 与真实 CLI 运行，未再改动。
- LWT 层运行失败：**0 次**（无退出码 2/3/4，无 stderr）。
- 证据采集失败：**1 次**。首次尝试用 shell 把 stdout/stderr 重定向到 `/tmp/out.txt`，Windows 上的 Python 打不开该路径，采集脚本报 `FileNotFoundError`；被重定向的 LWT 进程本身退出码仍为 0。随后改用内置 `subprocess` 捕获原始字节，未改动程序。

## 5. 隔离声明

- 仅阅读 `TASK.md` 与允许的四份文档：`docs/language-spec.md`、`docs/concurrency.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录、其他提交或任何期望输出；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。
- 唯一执行入口为 `python -m lwt`；未用其他语言生成或改写程序输出。
- 仅写入 `docs/agent-eval/submissions/producer-consumer-channel/` 下的两个文件（`pipeline.lwt`、`report.md`）。
