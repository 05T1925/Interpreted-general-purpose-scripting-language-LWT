# report.md —— producer-consumer-channel（C 组，仅语言规范）

## 1. 交付物

- `pipeline.lwt`：题目要求的程序文件（与本报告同目录）。
- 本报告 `report.md`。

## 2. 依据文档与小节

只阅读了 `docs/language-spec.md`（C 组允许的唯一文档），引用的具体小节：

| 需求点 | 规范依据 |
|---|---|
| `spawn` 前缀表达式、目标函数存在性与实参数检查、`spawn` 本身不切换 | §11.2、§11.3 |
| 调度点只有 `yield()`、阻塞 `receive`、阻塞 `join`、任务结束、`read_text` I/O | §11.3 |
| 默认 `fifo` 策略：`spawn` 创建的任务与 `yield()` 让出的任务进队尾，固定策略下同一程序永远同一输出 | §11.4 |
| `channel()` 无界 FIFO；`send` 入队；`receive` 非空立即返回且不是调度点，空且未关闭时阻塞，空且已关闭返回 `null`；`close` 幂等，关闭后先取完余量 | §11.5 |
| 任务内未捕获错误保存在任务结果中，`join` 以原始 category/message/source/line/column 重新抛出，可被 `attempt/recover` 捕获 | §11.6 |
| `throw "task failed";` 产生类别 `User`、消息为字符串本身，可被 attempt 捕获，`p.message` 取值 | §10.6、§7 |
| `+` 只接受两个整数或两个字符串，不做隐式转换，故用 `str(total)` 拼接 | §4.2、§6（`str`） |
| `attempt { } recover (p) { }` 语法与捕获边界；语句后不写分号 | §3、§5、§10.1、§10.2 |
| 顶层 `fn` 在普通语句前一次性登记，允许前向调用 | §5 |

未使用其他任何文档（`static-checker.md`、`concurrency.md`、`s42-*` 等均未打开）。

## 3. 程序设计

```lwt
fn produce(c) { send(c, 1); send(c, 2); send(c, 3); close(c); return null; }
fn boom() { throw "task failed"; }

let ch = channel();
let producer = spawn produce(ch);
```

- `spawn produce(ch)`：按 §11.3 先检查目标存在与实参数（1 个），再求实参 `ch`，把任务 1 放入就绪队列，返回 Task；`spawn` 不切换，主任务继续。
- 主任务 `receive(ch)` 时通道为空且未关闭，阻塞并成为调度点 → 生产者获得令牌，连续 `send` 三个元素后 `close`，任务结束（调度点）。主任务恢复后 `receive` 依次得到 1、2、3（队列非空时 `receive` 不是调度点，故累加过程不会被切开），第 4 次 `receive` 在已关闭且空队列上立即返回 `null`，循环退出。
- 因此累加结果与交错无关：`total = 6`，`emit "sum " + str(total);` 输出 `sum 6`。`join(producer)` 在任务已完成时返回其 `null`。
- `let t = spawn boom();` 后进入 `attempt { join(t); }`：`join` 为阻塞调度点 → `boom` 运行 `throw "task failed"`，任务内未捕获错误按 §11.6 保存在结果中；`join` 以原始类别 `User` 和消息重新抛出，被最近的动态 attempt 捕获，`p.message` 为 `task failed`，拼接输出 `caught:task failed`。
- 程序不调用 `input()` 与 `args()`，不接收参数、不读 stdin。

## 4. 自测（全部为真实 CLI 命令）

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-producer-consumer-channel-s1`

### 4.1 主用例

命令：

```
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

结果：

- stdout（Python `repr(bytes)` 实测）：`b'sum 6\ncaught:task failed\n'`
- 即两行：`sum 6`、`caught:task failed`，末尾各有 LF
- stderr：`b''`（空）
- 退出码：`0`

### 4.2 默认 fifo 下的确定性（连续 5 次）

```
for i in 1 2 3 4 5; do python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt; done
```

5 次全部 `rc=0`，输出均为 `sum 6` + `caught:task failed` 两行，逐字节一致。

### 4.3 附加稳定性检查（非题目要求）

用 `--schedule=random:1 / 7 / 42` 强制其他交错，输出仍为 `sum 6` / `caught:task failed`、`rc=0`，说明结果不依赖调度顺序（通道 FIFO 与关闭后 `null` 语义决定）。

### 4.4 静态检查

```
python -m lwt --check docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

stdout：`Check passed: 1 source file(s).`，退出码 0。

## 5. 失败与修订次数

- 失败次数：0。
- 修订次数：0。首版 `pipeline.lwt` 一次通过全部自测（§4.1–§4.4），未改动任何一行。
- 无调试性输出残留：程序只含题目要求的两次 `emit`。

## 6. 隔离声明

1. 仅阅读了 `TASK.md` 与 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、任何其他题目目录、任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
2. 仅通过公开入口 `python -m lwt <file>`（及规范 §6 记载的 `--check`、§11.4 记载的 `--schedule=` 开发用开关）运行程序；未用其他语言生成或改写程序输出，程序文件全部由本会话按规范手写。
3. 只在本目录 `docs/agent-eval/submissions/producer-consumer-channel/` 下写入 `pipeline.lwt` 与 `report.md`；未修改仓库其他任何文件。
4. 未查看任何隐藏测试、评分脚本或参考实现。
