# 盲测提交报告：producer-consumer-channel

## 1. 任务与交付

- 源程序：`docs/agent-eval/submissions/producer-consumer-channel/program.lwt`
- 目标行为：生产者任务经 `spawn` 启动，向通道 `ch` 依次 `send` 1、2、3 后 `close(ch)`；主任务 `receive` 循环累加至 `null`，输出 `sum 6`；随后再启动一个 `throw "task failed"` 的任务，由 `attempt { join(t); } recover (p) { emit "caught:" + p.message; }` 捕获并输出 `caught:task failed`。
- 程序不调用 `args()` / `input()`，不依赖 CLI 实参或 stdin。

## 2. 依据文档与小节

| 设计点 | 依据 |
|---|---|
| `spawn f(args)` 为前缀表达式，必须带括号，返回 Task；`spawn` 本身不切换 | `docs/language-spec.md` §3（EBNF `spawn_expr`）、§11.2、§11.3 |
| `channel()` 无参创建无界 FIFO 通道；`send(ch, v)` 返回 `null`；`close(ch)` 幂等关闭 | 规范 §6 预置能力表、§11.5；`docs/concurrency.md`「语法（7 个能力）」 |
| 队列空且未关闭时 `receive` 阻塞（调度点）；空且已关闭返回 `null` | 规范 §6、§11.3、§11.5 |
| 任务结束、阻塞 `receive`/`join` 均为调度点；两点之间原子完成 | 规范 §11.3；`docs/concurrency.md`「五个调度点」 |
| 任务内未捕获错误存入任务结果；`join` 以原始 category/message 重抛，可被 `attempt/recover` 捕获 | 规范 §11.6；`docs/concurrency.md`「错误与收尾」 |
| `throw "task failed"` 产生 `User` 类别 Error，`problem.message` 为原文；attempt 捕获所有退出码 3 的 LWT 错误 | 规范 §10.6、§10.1、§10.3 |
| 默认 `fifo` 为真 FIFO 队列，固定策略下输出一致 | 规范 §11.4；`docs/concurrency.md`「调度与轨迹」 |
| `+` 仅接受两个整数或两个字符串，需显式 `str(sum)` | 规范 §4.2、§6 `str` 行 |
| 分号必需、`while`/`when` 块后不写分号 | 规范 §2.1、§3 |
| CLI 用法与退出码 | `docs/developer-guide.md` §1「CLI、参数和输入」「退出码和诊断」、§4「确定性并发（S43）」 |
| 工作流：先 `--check` 再公开 CLI，只记录真实运行结果 | `.agents/skills/lwt-app/SKILL.md`「工作流程」第 5–7 条、S43 使用要点 |

## 3. 程序结构（简述）

`fn produce(ch)` 依次 `send(ch, 1)`、`send(ch, 2)`、`send(ch, 3)` 并 `close(ch)`；主流程 `channel()` 后 `spawn produce(ch)`，用 `receive` + `while (item != null)` 累加并 `emit "sum " + str(sum)`。`fn boom()` 执行 `throw "task failed";`，`spawn boom()` 后在 `attempt` 内 `join(t)`，`recover (p)` 输出 `"caught:" + p.message`。两次 `spawn` 与 `attempt` 的先后顺序保证输出顺序为 `sum 6` 在前、`caught:task failed` 在后。

## 4. 命令与实测结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-producer-consumer-channel-s2`

### 4.1 静态检查

```text
python -m lwt --check docs/agent-eval/submissions/producer-consumer-channel/program.lwt
```

- stdout：`Check passed: 1 source file(s).`
- stderr：空
- 退出码：0

### 4.2 正式运行

```text
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/program.lwt
```

- stdout（repr）：`'sum 6\ncaught:task failed\n'`
- stdout（原始字节核对）：`s u m   6 \n c a u g h t : t a s k   f a i l e d \n`，共 25 字节
- stderr：空（0 字节）
- 退出码：0

### 4.3 默认 fifo 一致性

同一命令连续运行 5 次，stdout 的 SHA-256 均为
`9ea28f106cd35dbebc59cb6f3f78c5d9f4f03204d7d356bde3af2ebd2ef1c191`，
每次 stderr 0 字节、退出码 0。

### 4.4 无 stdin / 无参数

```text
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/program.lwt < /dev/null
```

- stdout 与 4.2 基线逐字节相同；stderr 0 字节；退出码 0。未传 `--` 实参，程序也未读取 stdin。

## 5. 失败与修订次数

- 失败次数：0（首版即通过静态检查与全部运行验证）。
- 修订次数：0（未修改过程序内容）。

## 6. 隔离声明

- 仅阅读了允许的 T 组文档：`docs/language-spec.md`、`docs/concurrency.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅通过公开入口 `python -m lwt` 执行程序，未使用其他语言生成输出或修改程序。
- 写入范围仅限本目录 `docs/agent-eval/submissions/producer-consumer-channel/`（`program.lwt`、`report.md`）。
