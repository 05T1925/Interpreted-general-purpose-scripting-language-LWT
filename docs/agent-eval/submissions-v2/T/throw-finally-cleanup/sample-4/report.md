# 报告：throw / finally 清理（T 组盲测）

## 1. 程序

- 文件：`docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt`
- 结构：顶层 `fn charge(n)`；`n < 0` 时 `throw error("Validation", "negative amount")`，否则 `return n * 2`；主程序为带 `finally` 的 `attempt`，随后 `emit str(charge(4));`。
- 不接收 CLI 参数，不读取 stdin。

## 2. 依据文档与小节

| 文档 | 小节 | 用于确定 |
|---|---|---|
| `docs/language-spec.md` | §3 语法（`attempt_stmt`、`throw_stmt`、`finally`） | attempt 三块无分号、`throw expr;` 语句形式 |
| `docs/language-spec.md` | §5 作用域与函数调用 | 顶层 `fn` 先登记、函数返回值与 `return` |
| `docs/language-spec.md` | §6 预置能力 `error(category, message)` | 构造自定义 category 的 Error，`source/line/column` 取调用点 |
| `docs/language-spec.md` | §7 错误与退出码 | 诊断格式与 0/2/3/4 语义 |
| `docs/language-spec.md` | §10.3 Error 值 | `category`、`message` 为只读字段，handler 中 `problem` 即该 Error |
| `docs/language-spec.md` | §10.6 throw 与 finally | throw Error 值原样重抛并保留 category；finally 在 handler 之后执行且至多一次 |
| `docs/language-spec.md` | §4.3 显示规则 | `emit` 顶层字符串不带引号，`str` 与 `emit` 同一显示形式 |
| `docs/developer-guide.md` | §2「恢复运行时错误」、§3「语义速查」 | attempt/recover 只捕获退出码 3；错误前的输出不回滚 |
| `.agents/skills/lwt-app/SKILL.md` | S42 使用要点（throw/finally 条目） | `throw error("Category","message")` 抛自定义类别；finally 无论正常/错误都执行一次 |

语义推导：`charge(-5)` 走 `throw error(...)`，Error 的 category 为 `Validation`、message 为 `negative amount`；`str(charge(-5))` 的实参求值先抛错，故第一个 `emit` 不产生输出；recover 输出 category 与 message；finally 再输出 `cleanup`；之后 `charge(4)` 返回 8，`str` 后输出 `8`。

## 3. 命令与实测结果

均在本目录（仓库根）执行，仅使用公开入口 `python -m lwt`。

1) 静态检查

```text
python -m lwt --check docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

```text
stdout: Check passed: 1 source file(s).
stderr: (empty)
exit code: 0
```

2) 正式运行

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

```text
stdout repr: b'Validation\nnegative amount\ncleanup\n8\n'
stderr repr: b''
exit code: 0
```

（退出码与字节流由一次只读的 `subprocess.run([...])` 采集，其内部仍只调用 `python -m lwt`，未用任何其他语言生成或改写程序输出。）

3) 无 stdin 复核

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt < /dev/null
```

```text
stdout: Validation / negative amount / cleanup / 8（各一行）
stderr: (empty)
exit code: 0
```

## 4. 失败与修订次数

- 失败次数：0
- 修订次数：0（首版即通过 `--check` 与实跑，未改动程序）

## 5. 隔离声明

- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。
- 只阅读了 TASK.md 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`；另仅列出目录 `docs/agent-eval/submissions/` 以确认写入位置（未读取其中任何内容）。
- 只写入 `docs/agent-eval/submissions/throw-finally-cleanup/` 下的 `cleanup.lwt` 与本报告；未创建其他文件。
- 运行只用 `python -m lwt <file>`（含 `--check` 变体），未使用其他语言生成输出或改写程序。
