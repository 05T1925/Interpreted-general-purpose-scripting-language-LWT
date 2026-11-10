# producer-consumer-channel 盲测提交报告

## 1. 依据的文档与小节

只读了题目允许的四份文档，未读任何被禁目录/文件的内容。

| 文档 | 具体小节 | 用到的结论 |
|---|---|---|
| `docs/language-spec.md` | §2.1 词法（保留字 `spawn`，预置名 `join/yield/channel/send/receive/close`） | 确认 `spawn` 是唯一新保留字、其余为普通预置函数名 |
| 同上 | §3 语法（`spawn_expr`、`attempt_stmt`、`throw_stmt`、块后不写分号） | `spawn f(args)` 必须带括号；`attempt { } recover (p) { }` 与 `throw expr;` 的写法 |
| 同上 | §4.2 运算与比较 | `"sum " + str(sum)` 走字符串 `+`；`v != null` 对跨类型合法（类型不同即不等） |
| 同上 | §6 预置能力表（`channel`/`send`/`receive`/`close`/`join` 行） | `receive` 队列非空时立即返回且**不是**调度点；空且已关闭返回 `null`；`close` 幂等；`join` 以原始 category/message/source/line/column 重抛 |
| 同上 | §10.3 Error 值 | `p.message` 读取被捕获错误的 `message` 字段 |
| 同上 | §10.6 throw 与 finally | `throw "task failed";` 产生类别 `User`、message 为原文；被 `attempt` 捕获 |
| 同上 | §11.3 调度点 | 五类调度点；`spawn` 本身不切换；`send` 非调度点；任务结束是调度点 |
| 同上 | §11.4 fifo 策略 | 默认 fifo 为真 FIFO 队列，输出可复现 |
| 同上 | §11.5 通道 | 无界 FIFO；关闭后 `receive` 先排空再返回 `null`，关闭后 `send` 才报错 |
| 同上 | §11.6/§11.7 错误与收尾 | 任务内未捕获错误不打印不终止，由 `join` 重抛；收尾按编号 join 残留任务 |
| `docs/concurrency.md` | 「语法（7 个能力）」「五个调度点」「错误与收尾」「反模式 2」 | 同上速查；不依赖任务完成顺序输出，改用通道数据顺序 |
| `docs/developer-guide.md` | §1「CLI、参数和输入」「退出码和诊断」「运行前静态检查」；§3「内置函数与输出」；§4「确定性并发（S43）」 | 只用 `python -m lwt SOURCE` 公开入口；先 `--check` 再运行；`emit` 写 stdout、诊断写 stderr |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」第 5–7 条；「S43 并发子集的使用要点」 | 先静态检查再跑公开 CLI；只记录真实命令与结果 |

## 2. 脚本相对路径

- 程序：`docs/agent-eval/submissions/producer-consumer-channel/program.lwt`
- 本报告：`docs/agent-eval/submissions/producer-consumer-channel/report.md`

以下命令的工作目录均为仓库根 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-producer-consumer-channel-s1`。

## 3. 程序设计要点

- 先 `spawn produce(ch)`：`spawn` 不切换，主任务继续执行到首个阻塞 `receive`（调度点），此时通道为空未关闭，主任务让出令牌。
- 生产者任务连续 `send` 1、2、3 再 `close(ch)`；`send`/`close` 都不是调度点，故三条消息与关闭在同一时间片内完成，随后任务结束（调度点）交还令牌。
- 主任务按 FIFO 顺序收到 1、2、3，最后在「空且已关闭」时收到 `null` 结束循环，累加得 6，输出 `sum 6`。数据顺序由通道 FIFO 保证，不依赖任何任务完成顺序（`docs/concurrency.md` 反模式 2）。
- 再 `spawn boom()` 并 `attempt { join(t); } recover (p) { ... }`：`join` 阻塞是调度点，任务抛出 `User` 类错误后结束；`join` 原位置重抛，`p.message` 为 `task failed`，输出 `caught:task failed`。
- 程序不调用 `args()`/`input()`，无参数、无 stdin，因此输出与外部输入无关。

## 4. 真实运行记录

### 4.1 静态检查

命令：

```
python -m lwt --check docs/agent-eval/submissions/producer-consumer-channel/program.lwt
```

- stdout：`'Check passed: 1 source file(s).\n'`
- stderr：`''`
- 退出码：`0`

### 4.2 首次运行（默认 fifo）

命令：

```
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/program.lwt
```

- stdout（repr）：`'sum 6\ncaught:task failed\n'`
- stderr：`''`
- 退出码：`0`

字节级核对（`od -c`，25 字节）：

```
s u m   6 \n c a u g h t : t a s k   f a i l e d \n
```

### 4.3 默认策略重复运行 5 次（确定性）

命令（`i` = 1..5，各自重定向到临时文件后比较）：

```
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/program.lwt > /tmp/out_$i.txt 2> /tmp/err_$i.txt
```

| 次数 | 退出码 | stdout 字节数 | stderr 字节数 | stdout sha256 前缀 |
|---|---:|---:|---:|---|
| 1 | 0 | 25 | 0 | `9ea28f106cd35dbe` |
| 2 | 0 | 25 | 0 | `9ea28f106cd35dbe` |
| 3 | 0 | 25 | 0 | `9ea28f106cd35dbe` |
| 4 | 0 | 25 | 0 | `9ea28f106cd35dbe` |
| 5 | 0 | 25 | 0 | `9ea28f106cd35dbe` |

每次 stdout 均为 `'sum 6\ncaught:task failed\n'`，stderr 均为 `''`，退出码均为 `0`。

### 4.4 其它调度策略下的一致性（补充证据，非题目要求）

命令（`SEED` = 1、7、42、123）：

```
python -m lwt --schedule=random:SEED docs/agent-eval/submissions/producer-consumer-channel/program.lwt > /tmp/r_$SEED.txt 2> /tmp/re_$SEED.txt
```

| SEED | 退出码 | stdout sha256 前缀 | stderr 字节数 |
|---|---:|---|---:|
| 1 | 0 | `9ea28f106cd35dbe` | 0 |
| 7 | 0 | `9ea28f106cd35dbe` | 0 |
| 42 | 0 | `9ea28f106cd35dbe` | 0 |
| 123 | 0 | `9ea28f106cd35dbe` | 0 |

说明输出只取决于通道 FIFO 语义，与具体交错无关；默认 fifo 下自然同样恒定。

## 5. 失败尝试与修订次数

- 失败尝试：0 次。
- 修订次数：0 次。
- `program.lwt` 首版即通过 `--check`，首次运行即得到题目要求的 stdout、空 stderr、退出码 0；后续只做重复性与跨策略的一致性核对，未改动源码。

## 6. 隔离声明

- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径。
- 仅通过 `ls` 列目录时看到过仓库根目录与 `docs/` 目录的**文件名清单**（其中包含上述被禁目录的名字），未打开其中任何文件。
- 所有写入仅发生在 `docs/agent-eval/submissions/producer-consumer-channel/` 下（`program.lwt`、`report.md`）；自测用的 stdout/stderr 重定向文件写在仓库外的系统临时目录 `/tmp/`，未修改仓库任何其它文件。
- 全部执行只用公开入口 `python -m lwt`（含 `--check` 与 `--schedule=random:SEED` 两种既有开关），未用 Python 或其它语言生成输出或改写程序。
