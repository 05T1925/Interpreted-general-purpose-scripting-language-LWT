# cleanup.lwt 盲测报告

## 题目与交付
- 程序：`cleanup.lwt`
- 要求：`charge(n)` 在 `n < 0` 时 `throw error("Validation", "negative amount")`，否则返回 `n * 2`；主程序用 `attempt/recover/finally` 捕获并输出 category、message 与 `cleanup`，之后再 `emit str(charge(4));`。无参数、无 stdin。

## 依据文档与小节
仅阅读 `docs/language-spec.md`：
- §3：`fn` 顶层声明、`throw` 语句、`attempt ... recover (IDENT) ... [finally]` 的 EBNF；块后不写分号。
- §6：`error(category, message)` 预置函数返回 Error，`source/line/column` 取调用点；`str(value)` 格式。
- §4.3：`str`/`emit` 的显示规则（字符串原样、整数十进制）。
- §10.6：throw 语义（字符串包装为 `User`；Error 值原样重抛）、attempt 捕获所有退出码 3 的 LWT 错误、finally 在 handler 之后且至多执行一次。
- §10.3：Error 的 `category`/`message` 只读字段。
- §7：成功退出码 0，未捕获错误 3，词法/语法 2。

## 运行命令
```
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```
工作目录为题目根目录；仅使用公开 CLI 入口，未传 `--` 实参、未提供 stdin。

## 实测结果
- stdout（Python repr）：`b'Validation\nnegative amount\ncleanup\n8\n'`
- stderr（Python repr）：`b''`
- 退出码：`0`

与 §10.6 的语义一致：`charge(-5)` 抛出的 Error 被最近 attempt 捕获，`problem.category` 为 `Validation`、`problem.message` 为 `negative amount`；handler 正常结束后执行 finally 输出 `cleanup`；随后 `charge(4)` 返回 8，输出 `8`。body 中的 `emit str(charge(-5))` 因 throw 立即转移而未产生输出。

## 失败与修订次数
- 程序修订次数：0（首版即通过）。
- 自测过程中的一次工具问题：首次用 shell 重定向到 `/tmp/out.txt` 读取时，Git Bash 的 `/tmp` 与 Windows Python 的路径视图不一致导致文件找不到；改为 `subprocess` 内存捕获后取得上述真实结果。程序本身未改动，不属于程序失败。

## 隔离声明
- 仅阅读 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅用 `python -m lwt <file>` 运行程序；未用其他语言生成或改写程序输出。
- 仅在 `docs/agent-eval/submissions/throw-finally-cleanup/` 下写入 `cleanup.lwt` 与本报告。
