# producer-consumer-channel 盲测提交报告

## 1. 交付物

| 项 | 值 |
|---|---|
| LWT 源码（相对仓库根目录） | `docs/agent-eval/submissions/producer-consumer-channel/program.lwt` |
| 报告（本文件） | `docs/agent-eval/submissions/producer-consumer-channel/report.md` |
| 运行入口 | 仅 `python -m lwt <file>`（公开 CLI），未使用 `--check` 以外的任何工具，未使用 Python/其他语言生成或改写输出 |

程序结构（`program.lwt`）：

- `fn produce(ch)`：`send(ch, 1)`、`send(ch, 2)`、`send(ch, 3)`、`close(ch)`；
- `fn boom()`：`throw "task failed";`；
- 主任务：`let ch = channel();` → `let producer = spawn produce(ch);` → `let v = receive(ch); while (v != null) { total = total + v; v = receive(ch); }` → `emit "sum " + str(total);`；
- 再 `let t = spawn boom();` → `attempt { join(t); } recover (p) { emit "caught:" + p.message; }`。

形参与 `recover` 变量命名：`produce` 的形参 `ch` 与主任务全局 `ch` 同名（函数局部作用域遮蔽全局，符合规范 §5），`recover (p)` 的 `p` 是 handler 块内的 Error 绑定。

## 2. 依据的文档与具体小节

| 文档 | 小节 | 用于决定什么 |
|---|---|---|
| `docs/language-spec.md` | §3（`spawn_expr`、`attempt_stmt`、`throw_stmt`、块后不写分号、`fn` 仅顶层） | 语法形态；`spawn f(args)` 是前缀表达式，必须带括号；`attempt`/`recover` 不带分号 |
| 同上 | §2.1（`#` 注释、标识符、保留字表） | 注释写法；`spawn`/`throw`/`attempt`/`recover` 为保留字，`channel`/`send`/`receive`/`close`/`join` 为预置函数名而非关键字 |
| 同上 | §4.2（`==`/`!=` 对所有值有定义，类型不同即不等）、§4.3（`+` 字符串拼接、`emit` 显示规则） | `v != null` 在 `v` 为整数时为真、为 `null` 时为假；`"sum " + str(total)` 与 `"caught:" + p.message` 的拼接与显示 |
| 同上 | §6 预置能力表（`channel`/`send`/`receive`/`close`/`join` 行） | `channel()` 无参、`send` 返回 `null`、`receive` 空且未关闭时阻塞且为调度点、空且已关闭返回 `null`、`close` 幂等、`join` 等待并在任务失败时以原始 message 重抛 |
| 同上 | §10.1、§10.3、§10.6 | `attempt` 捕获退出码 3 的 LWT 错误；`throw "task failed"` 产生 `User` 类别、`message` 为原字符串，故 `p.message` 为 `task failed` |
| 同上 | §11.2（`spawn` 语法）、§11.3（`spawn` 本身不切换；五个调度点；任务结束是调度点） | 主任务在 `spawn` 之后继续运行，首个空队列 `receive` 才发生切换 |
| 同上 | §11.4（默认 `fifo` 为真 FIFO 队列，选择是纯函数，不依赖时间/线程 id） | 默认策略下交错唯一 |
| 同上 | §11.5（无界 FIFO 通道语义） | 发送顺序 1、2、3 与取出顺序一致，累加得 6 |
| 同上 | §11.6（`join` 以原始 category/message/source/line/column 重抛，可被 `attempt/recover` 捕获） | `caught:task failed` 的取值来源与可捕获性 |
| 同上 | §11.7（顶层结束后按编号 join 未完成任务） | 未显式 join 的 `producer` 也保证在收尾阶段完成，不会丢失 |
| 同上 | §7（退出码表：成功 0、RuntimeError 3、语法 2、CLI 4） | 预期退出码 0、stderr 空 |
| `docs/concurrency.md` | 「语法（7 个能力）」「五个调度点」「错误与收尾」 | 同上语义的速查确认；反模式 2「不要依赖任务完成顺序输出」——本程序只在主任务里输出，顺序不依赖任务完成次序 |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」；§3「内置函数与输出」；§4「确定性并发（S43）」 | 只用 `python -m lwt SOURCE`；无 `--` 参数、无 stdin；stdout 只含 `emit` 结果 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」第 5–6 步；「语言边界」S43 使用要点 | 先静态检查再公开 CLI 运行，核对 stdout/stderr/退出码；`spawn` 必须带括号、并发只限规范 §11 子集 |

## 3. 运行命令与实测证据

所有命令的工作目录为仓库根目录 `C:/Users/28641/AppData/Local/Temp/lwt-s47-blind-producer-consumer-clarified`，源码路径为相对路径 `docs/agent-eval/submissions/producer-consumer-channel/program.lwt`。全部命令均未提供 `--` 程序实参，也未提供 stdin。

### 3.1 静态检查

```text
python -m lwt --check docs/agent-eval/submissions/producer-consumer-channel/program.lwt
```

- stdout（repr）：`'Check passed: 1 source file(s).\n'`
- stderr（repr）：`''`
- 退出码：`0`

### 3.2 默认（fifo）执行，重复 5 次

```text
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/program.lwt
```

- stdout（repr）：`'sum 6\ncaught:task failed\n'`
- stderr（repr）：`''`
- 退出码：`0`
- 重复性：连续运行 5 次，逐字节 `cmp` 比较，5 次 stdout 两两完全相同、stderr 均为空、退出码均为 0。
- 字节级核对（`od -c`）：`s u m   6 \n c a u g h t : t a s k   f a i l e d \n`，共 0x19 字节，无 CR、无多余空行。

### 3.3 其它调度策略（额外证据，非题目要求）

```text
python -m lwt --schedule=fifo          docs/agent-eval/submissions/producer-consumer-channel/program.lwt
python -m lwt --schedule=random:1      docs/agent-eval/submissions/producer-consumer-channel/program.lwt
python -m lwt --schedule=random:42     docs/agent-eval/submissions/producer-consumer-channel/program.lwt
python -m lwt --schedule=random:1234567 docs/agent-eval/submissions/producer-consumer-channel/program.lwt
```

| 策略 | stdout（repr） | stderr（repr） | 退出码 | 与 3.2 比较 |
|---|---|---|---|---|
| `fifo` | `'sum 6\ncaught:task failed\n'` | `''` | 0 | 逐字节相同 |
| `random:1` | `'sum 6\ncaught:task failed\n'` | `''` | 0 | 逐字节相同 |
| `random:42` | `'sum 6\ncaught:task failed\n'` | `''` | 0 | 逐字节相同 |
| `random:1234567` | `'sum 6\ncaught:task failed\n'` | `''` | 0 | 逐字节相同 |

### 3.4 为什么默认 fifo 下输出唯一（依据 §11.3/§11.4/§11.5）

1. `spawn produce(ch)` 不切换；此时唯一运行的任务是主任务。
2. 主任务首个 `receive(ch)` 时队列为空且未关闭 → 阻塞且是调度点 → 就绪集合只有 `produce` 任务，**没有第二个候选**，选择无歧义。
3. `produce` 在两次调度点之间原子执行 `send×3` + `close`，因此三个值按 1、2、3 入队；任务结束本身是调度点，令牌回到主任务。
4. 此后 `receive` 的队列非空（或已关闭且取尽）→ 不阻塞、不是调度点，主任务一次跑完循环得到 1+2+3=6，并且 `emit "sum 6"` 在 `spawn boom` 之前，输出顺序不依赖任何任务完成次序。
5. `join(t)` 阻塞 → `boom` 运行并 `throw "task failed"` → 任务失败被保存 → `join` 在调用处重抛（§11.6）→ 最近的 `attempt` 捕获，`p.message` 为 `task failed`，输出 `caught:task failed`。

因此任何合法交错下 stdout 都是 `'sum 6\ncaught:task failed\n'`，与 3.3 中随机种子的实测一致。

## 4. 失败尝试与修订次数

- **程序修订次数：0**。首版 `program.lwt` 即通过 `--check` 与全部 5 次默认策略运行、4 种策略运行，未出现词法/语法/运行时错误。
- 失败尝试：**无程序级失败**。仅有一次证据收集方式返工：最初把 stdout 重定向到 `/tmp/out1.txt` 并用 Windows 上的 `python -c` 读取，因 `/tmp` 路径未被 Windows Python 解析而报 `FileNotFoundError`（该命令自身退出码 1）；随后改用提交目录内的临时文件配合 `od -c`/`cmp` 采集证据，临时文件已删除。该项不涉及任何源码改动，也不影响解释器运行结果。

## 5. 隔离声明

- 只读取了允许的 4 个文件：`docs/language-spec.md`、`docs/concurrency.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 另外只执行了目录列举（`ls`）以确认工作目录与提交目录存在，未打开任何其他文件的内容。
- **没有**读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；**没有**访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径；**没有**联网。
- 只写入了 `docs/agent-eval/submissions/producer-consumer-channel/` 下的 `program.lwt`、`report.md` 及运行期间用于采集证据的临时文件（已删除）。运行与观测全部通过 `python -m lwt` 公开入口完成。
