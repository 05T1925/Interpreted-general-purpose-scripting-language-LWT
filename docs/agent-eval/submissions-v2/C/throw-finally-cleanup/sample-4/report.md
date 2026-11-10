# 盲测报告：throw 与 finally 清理（C 组，仅语言规范）

## 1. 命题与实现要点

题目要求：定义 `charge(n)`，`n < 0` 时 `throw error("Validation", "negative amount")`，否则返回 `n` 的两倍；主程序用 `attempt { emit str(charge(-5)); } recover (problem) { emit problem.category; emit problem.message; } finally { emit "cleanup"; }`，随后 `emit str(charge(4));`。

实现依据：

| 依据小节 | 采用的规范内容 |
|---|---|
| §3（`statement`、`attempt_stmt`、`throw_stmt`） | `throw` 只能作语句、后接表达式与分号；`attempt` 必须带 body/recover，`finally` 只能紧跟 recover 块，三者后不写分号 |
| §4.1、§4.3 | `str(value)` 的显示规则；Error 值按对象身份传递 |
| §5（attempt 段） | body/handler 均为普通块作用域，`problem` 仅在 handler 动态执行期绑定 |
| §6（预置表 `error`） | `error(category, message)` 返回 Error 值，`source/line/column` 取调用点 |
| §7（错误表） | throw Error 值保留其类别；被动态 handler 捕获则按 §10 恢复，否则退出码 3 |
| §10.3 | Error 的 `category`/`message` 字段只读，`RuntimeError` 之外的类别（如 `User`、自定义 category）也由 handler 原样给出 |
| §10.6 | `throw` 对字符串包装为 `User`、对 Error 值原样重抛（保留 category/message/身份）；attempt 捕获所有退出码 3 的 LWT 错误；finally **至多执行一次**，在 handler 正常结束后执行，随后继续 attempt 之后的语句 |

关键语义判断：题目用 `throw error("Validation", "negative amount")` 抛的是 **Error 值**，按 §10.6「值为 Error 值时原样重抛（保留其 category/message）」，因此 `problem.category` 为 `Validation` 而不是 `User`；`problem.message` 为 `negative amount`。`finally` 在 recover 正常结束后执行，输出 `cleanup`，之后才执行 `emit str(charge(4));`。`charge(-5)` 的 `emit str(...)` 不发生，故无此行输出。

## 2. 程序文件

`docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt`

```lwt
fn charge(n) {
    when (n < 0) {
        throw error("Validation", "negative amount");
    }
    return n * 2;
}

attempt {
    emit str(charge(-5));
} recover (problem) {
    emit problem.category;
    emit problem.message;
} finally {
    emit "cleanup";
}
emit str(charge(4));
```

不读取 stdin、不使用 `args()`，无 CLI 参数依赖。

## 3. 自测命令与结果

在题目工作目录执行（仅使用公开入口 `python -m lwt`）：

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

- stdout repr：`b'Validation\nnegative amount\ncleanup\n8\n'`
- stderr repr：`b''`
- 退出码：`0`

静态检查（同一公开 CLI 的 `--check` 入口，仅作辅助验证）：

```text
python -m lwt --check docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

输出 `Check passed: 1 source file(s).`，退出码 `0`。

输出与规范预期一致：`Validation`、`negative amount`、`cleanup`、`8` 各占一行；`charge(-5)` 的 `emit` 未执行（throw 立即转移控制），finally 在 handler 之后、attempt 之后语句之前执行。

## 4. 失败与修订次数

- 首次运行即通过，**失败 0 次、修订 0 次**，未改动过程序语义或结构。
- 未出现 `LexError`/`SyntaxError`/`RuntimeError` 诊断。

## 5. 隔离声明

- 只阅读了允许文档 `docs/language-spec.md`（§2–§7、§10 相关小节）；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只通过 `python -m lwt <file>`（及同一入口的 `--check`）运行，未用其他语言生成或改写输出。
- 只在本目录 `docs/agent-eval/submissions/throw-finally-cleanup/` 下写入 `cleanup.lwt` 与本报告；自测时的临时捕获文件已删除。
