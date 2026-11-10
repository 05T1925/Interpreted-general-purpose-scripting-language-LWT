# producer-consumer-channel 盲测报告

## 1. 产物

| 文件 | 说明 |
|---|---|
| `docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt` | 题目要求的 LWT 程序 |
| `docs/agent-eval/submissions/producer-consumer-channel/report.md` | 本报告 |

程序内容：

```lwt
# pipeline.lwt — deterministic producer/consumer over an unbounded FIFO channel,
# followed by a join/recover demo for a failing task.

let ch = channel();

fn produce() {
    send(ch, 1);
    send(ch, 2);
    send(ch, 3);
    close(ch);
}

fn explode() {
    throw "task failed";
}

let producer = spawn produce();

let sum = 0;
let value = receive(ch);
while (value != null) {
    sum = sum + value;
    value = receive(ch);
}
emit "sum " + str(sum);

let t = spawn explode();
attempt {
    join(t);
} recover (p) {
    emit "caught:" + p.message;
}
```

## 2. 依据文档与小节

- `docs/language-spec.md` §3（`spawn` 前缀表达式语法、`attempt/recover` 语法、`while`）、§6 预置能力表（`channel/send/receive/close` 的阻塞与关闭后语义、`join` 的原位置重抛）、§10.6（`throw "..."` 产生类别 `User`、`message` 为原字符串）、§11.3（`spawn` 不切换、五个调度点、任务结束是调度点）、§11.5（无界 FIFO 通道；非空 `receive` 不是调度点；空且关闭返回 `null`）、§11.6（失败任务经 `join` 以原始 message 重抛、可被 `attempt/recover` 捕获）、§11.7（收尾只 join 未完成任务）。
- `docs/concurrency.md`（语法速查、默认 `fifo` 真 FIFO 队列、通道语义、join 错误重抛、任务结束是调度点）。
- `docs/developer-guide.md` §4「确定性并发（S43）」（`spawn`/`join`/`yield`/通道的最小用法与默认 `fifo`）。
- `.agents/skills/lwt-app/SKILL.md`「S43 并发子集的使用要点」（只使用已支持的 LWT 能力、先 `--check` 再公开 CLI 实测、记录真实命令与结果）。

设计要点：`ch` 是顶层 `let` 绑定，函数经文件级变量根作用域访问它；`send`/`close` 不是调度点，生产者从启动到任务结束不会被切走，主任务阻塞 `receive` 后按 FIFO 拿到全部 4 个调度结果（1、2、3、`null`），累加与输出顺序固定。`explode` 的 `throw "task failed";` 产生 `User` 类别、message 为 `task failed`，`join` 在 `attempt` 内原位置重抛，`p.message` 拼接后输出 `caught:task failed`。

## 3. 自测命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-producer-consumer-channel-s3`

### 3.1 静态检查

```text
$ python -m lwt --check docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
Check passed: 1 source file(s).
exit=0
```

### 3.2 默认 fifo 执行（题目验收命令）

```text
$ python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
stdout:
sum 6
caught:task failed
exit=0
```

- stdout 精确 repr：`'sum 6\ncaught:task failed\n'`
- 字节视图（`od -c`）：`s u m   6 \n c a u g h t : t a s k   f a i l e d \n`
- stderr：空（`''`，0 字节）
- 退出码：`0`
- 未传 `--` 参数；程序不调用 `input()`，标准输入未被读取。

### 3.3 重复运行一致性（默认 fifo）

连续执行 10 次，逐次保存 stdout/stderr 并计算 stdout 的 SHA-256：

```text
run=01..10  exit=0  sha256=9ea28f106cd35dbebc59cb6f3f78c5d9f4f03204d7d356bde3af2ebd2ef1c191（10 次完全相同）
所有 stderr 合计 0 字节
```

### 3.4 换交错交叉验证

用公开 CLI 的 `--schedule=random:SEED` 换调度交错（不属于题目验收条件，仅用于确认输出不依赖某一交错）：

```text
seed=1  exit=0 sha256=9ea28f106cd35dbebc59cb6f3f78c5d9f4f03204d7d356bde3af2ebd2ef1c191
seed=7  exit=0 sha256=9ea28f106cd35dbebc59cb6f3f78c5d9f4f03204d7d356bde3af2ebd2ef1c191
seed=42 exit=0 sha256=9ea28f106cd35dbebc59cb6f3f78c5d9f4f03204d7d356bde3af2ebd2ef1c191
```

三个种子与默认 fifo 的 stdout 完全相同，stderr 均为空。

## 4. 失败与修订次数

- 失败次数：0（`--check` 首次通过；首次运行即得到期望输出与退出码 0）。
- 修订次数：0（提交的 `pipeline.lwt` 未经修改）。

## 5. 隔离声明

- 只阅读了 TASK.md 允许的四份文档：`docs/language-spec.md`、`docs/concurrency.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 未联网。
- 运行只使用公开入口 `python -m lwt <file>`（含 `--check` 与 `--schedule=random:SEED` 公开开关）；未用其他语言生成输出或改写程序。
- 只写入 `docs/agent-eval/submissions/producer-consumer-channel/` 下的 `pipeline.lwt` 与 `report.md`。
