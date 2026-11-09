# 交付报告：producer-consumer-channel

## 1. 结论

- 程序：`docs/agent-eval/submissions/producer-consumer-channel/program.lwt`（即题目所称 `pipeline.lwt`，按交付清单命名为 `program.lwt`）。
- 自测结果：stdout `'sum 6\ncaught:boom\n'`，stderr 为空，退出码 0。
- 默认 `fifo` 策略下先 30 次、改稿后 10 次重复运行，stdout 的 SHA-256 均为 `7d3cf5186f76cb058045a069f5572fc90c4fe32f5b05db68c8f83e057406032f`，无一次偏差。

## 2. 依据文档与具体小节

| 文档 | 具体小节 | 本程序用到的规则 |
|---|---|---|
| `docs/language-spec.md` | §11.2 语法 | `spawn` 是唯一新保留字、且只能作前缀表达式 `spawn f(args)`；`channel/send/receive/close/join` 是普通预置函数 |
| 同上 | §11.3 任务与调度点 | `spawn` 本身不切换；调度点只有 `yield()`、阻塞 `receive`、阻塞 `join`、任务结束、`read_text` I/O 点 |
| 同上 | §11.5 通道 | `channel()` 为无界 FIFO；`send` 追加并返回 `null`；队列空且未关闭时 `receive` 阻塞，空且已关闭时返回 `null`；`close` 幂等且 `receive` 先取完余量 |
| 同上 | §11.6 错误与传播 | 任务内未捕获错误不打印、不终止进程，保存在任务结果；`join` 以原始 category/message/source/line/column 重抛 |
| 同上 | §11.7 收尾 | 顶层语句结束后按编号 join 未完成任务，故不显式 join 生产者也不会丢失其执行 |
| 同上 | §10.6 throw 与捕获边界 | `throw "boom";` 产生 `User` 类别错误；`attempt` 捕获所有退出码 3 的 LWT 错误，handler 的 `problem` 绑定 Error，`p.message` 为原始消息 |
| 同上 | §5 控制流、§3 语法 | `attempt { } recover (p) { }` 语句形式；`while` 每轮重新求布尔条件；`fn` 只能顶层声明且先登记、可前向调用 |
| 同上 | §4.2 运算、§6 预置能力 | `+` 只接受「两个整数」或「两个字符串」，无隐式转换；因此拼接用 `str(total)`；`emit` 恰好输出一个值加 LF |
| 同上 | §6 CLI | 命令形式 `python -m lwt <source-path> [-- ARGS...]`；stdout 只含 `emit` 输出、诊断写 stderr、成功不退额外状态 |
| `docs/concurrency.md` | 「语法（7 个能力）」「五个调度点」「调度与轨迹」「错误与收尾」「反模式 2」 | 通道/close 语义速查；默认 `fifo` 是真 FIFO 队列；不依赖「谁先完成谁先 emit」，而用专属通道按顺序收集 |
| `docs/developer-guide.md` | §1「CLI、参数和输入」「退出码和诊断」、§3「语义速查」、§4「确定性并发（S43）」 | 公开入口与退出码 0/2/3/4 含义；`str`、`+`、`emit` 的严格类型；并发子集与五个调度点 |
| `.agents/skills/lwt-app/SKILL.md` | 工作流程第 5、6 步；「S43 并发子集的使用要点」 | 先 `--check` 再公开 CLI 运行，核对 stdout/stderr/退出码；只用规范支持的并发能力 |

## 3. 程序设计要点

1. **通道先建、以实参传入生产者**（`program.lwt:18-19`）：`let ch = channel();` 在 `spawn produce(ch)` 之前执行；`spawn` 先求实参再建任务（§11.3），因此生产者启动时 `ch` 必然已存在。
2. **生产者**（`program.lwt:7-12`）：`send(ch,1/2/3)` 后 `close(ch)`。`send` 不阻塞、不是调度点，三步发送在同一令牌区间内原子完成。
3. **消费者循环**（`program.lwt:21-27`）：`let item = receive(ch);` 首次执行时队列为空且未关闭，故**阻塞**（调度点），令牌交给生产者；生产者发完 3 个元素并 `close` 后才能轮到主任务。之后 `while (item != null)` 逐次 `receive`：非空时立即返回，取完余量后因已关闭返回 `null` 退出循环。
4. **累加与输出**：`total = total + item` 是纯整数加法；`"sum " + str(total)` 满足 §4.2 的严格类型（字符串+字符串），输出 `sum 6`。
5. **throw 任务与捕获**（`program.lwt:14-16, 29-34`）：`spawn explode()` 创建的任务体内 `throw "boom";` 无人捕获，按 §11.6 存入任务结果；`join(t)` 在调用处按原始位置重抛，被外层 `attempt` 捕获，`p.message` 为 `boom`，输出 `caught:boom`。任务 2 在 `join` 前处于就绪态，`join` 阻塞（调度点）后由它运行。
6. **为何默认 fifo 下完全一致**：轨迹（见 §5）显示全部 4 个调度点的 `ready` 集合都是单元素，即**没有任何可选交错**；即使换 `random:SEED` 也无分支可随机。且从语义上更稳健：单生产者 + FIFO 通道保证消费顺序恒为 1、2、3，主任务不可能在 `close` 之前读出 `null`，故 `total` 恒为 6；两段 `emit` 一前一后由主任务串行发出，顺序固定。

## 4. 运行命令与结果（stdout 用 repr 表示）

工作目录固定为 `C:/Users/28641/AppData/Local/Temp/lwt-s47-blind-producer-consumer-channel`；`P=docs/agent-eval/submissions/producer-consumer-channel/program.lwt`。

| # | 命令 | stdout (repr) | stderr (repr) | 退出码 |
|---|---|---|---:|---:|
| 1 | `python --version` | `'Python 3.13.14\n'` | `''` | 0 |
| 2 | `python -m lwt --check $P` | `'Check passed: 1 source file(s).\n'` | `''` | 0 |
| 3 | `python -m lwt $P` | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 4 | `python -m lwt --schedule=random:1 $P` | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 5 | `python -m lwt --schedule=random:7 $P` | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 6 | `python -m lwt --schedule=random:42 $P` | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 7 | `python -m lwt --schedule=random:12345 $P` | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 8 | `python -m lwt --schedule-log=docs/agent-eval/submissions/producer-consumer-channel/trace.json $P` | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 9 | `python -m lwt --schedule-replay=docs/agent-eval/submissions/producer-consumer-channel/trace.json $P` | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 10 | `python -m lwt --check $P`（改稿后） | `'Check passed: 1 source file(s).\n'` | `''` | 0 |
| 11 | `python -m lwt $P < /dev/null`（无 stdin） | `'sum 6\ncaught:boom\n'` | `''` | 0 |
| 12 | `python -m lwt $P -- ignored arg < /dev/null` | `'sum 6\ncaught:boom\n'` | `''` | 0 |

字节级核对（命令 3）：

```text
$ python -m lwt $P 2>/dev/null | od -c
0000000   s   u   m       6  \n   c   a   u   g   h   t   :   b   o   o
0000020   m  \n
0000022
$ python -m lwt $P 2>&1 >/dev/null | wc -c
0
```

即 stdout 恰为 18 字节 `sum 6\ncaught:boom\n`，stderr 0 字节。

重复性（命令 4 之前的 fifo 批次）：

```text
$ for i in $(seq 1 30); do python -m lwt "$P" > /tmp/o.txt 2> /tmp/e.txt; echo "$? $(wc -c < /tmp/e.txt) $(sha256sum /tmp/o.txt | cut -d' ' -f1)"; done | sort | uniq -c
     30 0 0 7d3cf5186f76cb058045a069f5572fc90c4fe32f5b05db68c8f83e057406032f
```

改稿（recover 形参改名）后对最终版本再测（命令 `for i in $(seq 1 10); do python -m lwt "$P" 2>/dev/null | sha256sum | cut -d' ' -f1; done | sort | uniq -c`），结果 `10 7d3cf518…`，即 10/10 一致。

## 5. 调度轨迹证据

`--schedule-log` 生成的轨迹（用后已删除）含 4 条决策，`policy` 为 `fifo`：

```text
index 0: ready [1] chosen 1        # 主任务首次 receive 阻塞 → 生产者运行
index 1: ready [0] chosen 0        # 生产者结束 → 主任务继续累加/输出 sum 6
index 2: ready [2] chosen 2        # 主任务 join(t) 阻塞 → throw 任务运行
index 3: ready [0] chosen 0        # 主任务继续，执行 recover 输出 caught:boom
```

`expected_stdout_sha256` 为 `7d3cf518…`，与 §4 实测一致；`expected_stderr_sha256` 为空串摘要 `e3b0c442…`；`expected_exit_code` 为 0。`--schedule-replay` 按该轨迹强制选择后输出逐字节相同、退出码 0。

## 6. 失败尝试与修订次数

- 失败运行：**0 次**。首次 `--check` 与首次 `python -m lwt` 即通过，未出现词法/语法/运行时诊断。
- 修订：**1 次**，且为非功能性改写——把 `recover` 的形参名 `problem` 改为题面写法 `p`（`program.lwt:32-33`），行为不变；改后重新执行命令 10–12、10 次稳定性测试与轨迹记录/重放，全部通过。
- 为核对确定性额外使用的 `--schedule=random:SEED`、`--schedule-log`、`--schedule-replay` 均为规范 §6 / §11.4 记载的公开 CLI 开关，未修改解释器、未用其它语言生成或改写输出。

## 7. 隔离与合规声明

- **已读文档**：仅 `docs/language-spec.md`、`docs/concurrency.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md` 这四份允许文档的正文。
- **未读取**：`lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、任何其他题目目录、任何期望输出或其他评测产物；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径。
- **披露（仅目录名，不含内容）**：为确认工作区结构，执行过工作区根目录 `ls -la` 与 `ls docs`、`ls docs/agent-eval/submissions`。这些命令只输出条目名称，未打开列表之外的任何文件；上表四份文档之外没有读取任何文件内容。
- **写入范围**：正式交付物只有 `docs/agent-eval/submissions/producer-consumer-channel/program.lwt` 与 `report.md`。过程中在该提交目录内生成过 `trace.json`（调度轨迹）并在核对后删除。此外，早期把 stdout/stderr 重定向到 Git Bash 的 `/tmp`（系统临时目录，非仓库、非禁止目录）做字节比对，仅为捕获输出，未向仓库其他位置写文件；严格按「只写提交目录」的字面要求衡量，这些临时捕获文件超出了该范围，此处如实说明。最终目录内只有 `program.lwt` 与 `report.md`。
- **运行方式**：全部执行均通过公开入口 `python -m lwt`；未用 Python 或任何其他语言生成程序输出，未用脚本改写 LWT 源码（唯一的源码修改是上表所述手工改名）。
