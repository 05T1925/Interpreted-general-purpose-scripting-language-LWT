# 盲测报告：producer-consumer-channel

## 1. 题目与交付

- 程序：`pipeline.lwt`（本目录）。
- 要求：`spawn` 生产者向通道 `ch` 依次发送 1、2、3 后 `close(ch)`；主任务 `receive` 循环累加到 `null`，输出 `sum 6`；再 `spawn` 一个 `throw "task failed";` 的任务，用 `attempt { join(t); } recover (p) { emit "caught:" + p.message; }` 输出 `caught:task failed`。默认 fifo 策略下输出完全一致，不接收参数与 stdin。

## 2. 依据（仅语言规范）

只依据 `docs/language-spec.md`：

- §2.1、§3：`spawn` 是保留字/前缀表达式；`join`、`yield`、`channel`、`send`、`receive`、`close` 是预置函数名，按普通调用解析。
- §11.3：`spawn f(args)` 先解析目标并检查参数，再求实参；`spawn` 本身不切换；调度点只有 `yield()`、阻塞的 `receive`、阻塞的 `join`、任务结束、`read_text` 的 I/O 点。
- §11.5：`channel()` 创建无界 FIFO；`send` 追加；队列非空时 `receive` 不阻塞、不是调度点；关闭后先取完余量再返回 `null`。
- §11.6：任务失败的错误保存在任务结果中，`join` 以原始 category/message/source/line/column 重新抛出，可被 `attempt/recover` 捕获；重复 join 返回同一错误。
- §10.1、§10.6：`attempt` 捕获从 body 逸出、退出码 3 的 LWT 错误；`throw` 字符串的类别为 `User`，`problem.message` 为原字符串。
- §6：`join(task)` 等待任务完成并返回/重抛；`emit` 输出一行。
- §11.4：默认 `fifo` 使用先进先出队列，同一程序每次输出一致。

## 3. 程序结构

1. `let ch = channel();` 建立进程内共享通道。
2. `fn produce(ch)`：`send(ch, 1/2/3)` 后 `close(ch)`；`spawn produce(ch);` 派生生产者（`spawn` 不切换）。
3. 主任务 `receive(ch)`：队列空且未关闭时阻塞（调度点），生产者运行至结束（任务结束是调度点）；此后队列已关闭且含 1、2、3，非空 `receive` 不是调度点，主任务一次连续取完 3 个元素，第 4 次得到 `null` 退出循环，`emit "sum " + str(total);` 输出 `sum 6`。
4. `fn boom()`：`throw "task failed";`。`spawn boom();` 后 `attempt { join(t); }`：`join` 阻塞（调度点），boom 抛错并结束，`join` 重抛原始 `User` 错误；recover 中 `p.message` 为 `task failed`，输出 `caught:task failed`。
5. 顶层结束按 §11.7 收尾 join 未完成任务，此时均已完成。

## 4. 命令与实测结果

工作目录：仓库根目录。仅使用公开入口 `python -m lwt <file>`。

```bash
python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt
```

- 退出码：`0`
- stdout（精确 repr）：`b'sum 6\ncaught:task failed\n'`
- stderr（精确 repr）：`b''`
- 未使用 `--` 传入程序参数，未向 stdin 提供内容（运行时不读取 stdin）。

确定性复跑（5 次，stdin 重定向为 `/dev/null`，合并 stdout/stderr 后取 SHA-256 前 16 位）：

```bash
for i in 1 2 3 4 5; do
  out=$(python -m lwt docs/agent-eval/submissions/producer-consumer-channel/pipeline.lwt < /dev/null 2>&1)
  printf 'run%s exit=%s sha=%s\n' "$i" "$?" "$(printf '%s' "$out" | sha256sum | cut -c1-16)"
done
```

实测 5 次均为 `exit=0`、`sha=fd0b4fe4ab44f65a`，即每次输出逐字节一致。

## 5. 失败与修订

- 程序失败次数：0；代码修订次数：0（首版即通过，未改过程序）。
- 输出捕获过程中曾因 Windows 下 Git Bash 的 `/tmp` 与 Python 看到的路径不一致，读取捕获文件失败一次；改用仓库内临时重定向文件后成功。该问题只影响测量步骤，不影响 `pipeline.lwt` 的运行结果；临时文件已删除。

## 6. 隔离声明

- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 语言依据只有 `docs/language-spec.md`；另外在开始时读过仓库根目录 `AGENTS.md`（仅协作/流程规则，无语言语义、测试或本题答案），`TASK.md` 为任务说明。
- 未用其他语言生成或改写输出；所有运行均通过 `python -m lwt` 公开入口。
- 交付文件只写在 `docs/agent-eval/submissions/producer-consumer-channel/`（`pipeline.lwt`、`report.md`）；运行输出捕获所用的临时重定向文件位于仓库根目录，读取后立即删除，未改动仓库其他文件或 git 状态。
