# 报告：cleanup.lwt（throw / attempt-recover-finally）

## 1. 交付物

| 文件 | 说明 |
|---|---|
| `cleanup.lwt` | 题目要求的程序文件 |
| `report.md` | 本报告 |

## 2. 依据文档与小节

所有设计判断只来自 TASK.md 允许的三份文档：

| 文档 | 小节 | 采用的点 |
|---|---|---|
| `docs/language-spec.md` | §3 语法（`attempt_stmt = "attempt" block "recover" "(" IDENT ")" block [ "finally" block ]`、`throw_stmt = "throw" expression ";"`） | attempt 三分支写法、块后不写分号、`throw` 后接表达式并带分号 |
| `docs/language-spec.md` | §6 预置能力表 `error(category, message)` | 用 `error("Validation", "negative amount")` 构造自定义 category 的 Error 值；`source/line/column` 取调用点 |
| `docs/language-spec.md` | §10.6 throw 与 finally | `throw` 一个 Error 值时**原样重抛**，保留其 `category/message`，故 `problem.category` 为 `Validation`、`problem.message` 为 `negative amount`；`finally` 在 handler 之后执行且至多一次 |
| `docs/language-spec.md` | §4.3 显示、§5 作用域、§6 `str` | `str(...)` 与 `emit` 同一显示规则；顶层字符串不带引号；函数体 `return n * 2;` |
| `docs/language-spec.md` | §2.1 词法、§7 退出码 | 保留字 `throw`/`finally` 不得作标识符；成功退出码 0，stderr 不混入 stdout |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」、「恢复运行时错误」 | 只用 `python -m lwt SOURCE` 公开入口；源码诊断格式；attempt 语义摘要 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」1/5/6 条、S42 使用要点「throw/finally」 | 先 `--check` 再跑公开 CLI；`throw error("Category","message")` 抛自定义类别；`problem` 只在 recover 块可见；finally 必执行一次 |

## 3. 程序

```lwt
# cleanup.lwt — throw / attempt-recover-finally 演示（LWT 0.3.0 规范 §10.6）

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

要点：

- `charge(n)` 在 `n < 0` 时 `throw error("Validation", "negative amount")`，否则 `return n * 2;`（满足「返回 n 的两倍」）。
- attempt 体里的 `emit str(charge(-5));` 因 `charge` 先抛出，`str` 与外层 `emit` 都不执行，body 无输出。
- `finally` 依据 §10.6 在 handler 正常结束后执行，故 `cleanup` 在 `negative amount` 之后、`8` 之前。
- 程序不读取 `args()` 或 `input()`，无需 CLI 参数与 stdin。

## 4. 真实运行记录

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-throw-finally-cleanup-s5`

### 4.1 静态检查

```
python -m lwt --check docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

- stdout：`Check passed: 1 source file(s).`
- stderr：（空）
- 退出码：0

### 4.2 公开 CLI 执行（主证据）

```
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

原始字节（以 Python `subprocess` 捕获的 `repr` 为准，避免终端转码）：

- stdout repr：`b'Validation\nnegative amount\ncleanup\n8\n'`
- stderr repr：`b''`
- 退出码：`0`

可读形式：

```text
Validation
negative amount
cleanup
8
```

### 4.3 复跑一致性

同一条命令连续执行两次，两次 stdout 均为上文四行、stderr 为空、退出码 0；程序无并发与外部输入，输出确定。

### 4.4 与规范预期的对照

| 断言 | 规范依据 | 实测 |
|---|---|---|
| 类别为 `Validation`（`throw` Error 值保留自定义 category） | §10.6 | `Validation` ✔ |
| 消息为 `negative amount` | §10.6 / §6 `error` | `negative amount` ✔ |
| body 内 `emit str(charge(-5))` 不产生输出（`str` 之前已抛出） | §10.6「throw 立即转移控制」 | 首行即 `Validation` ✔ |
| `finally` 执行一次且在 handler 之后 | §10.6 | `cleanup` 第三行 ✔ |
| 之后继续执行 `emit str(charge(4));` | §10.6 / §5 | `8` ✔ |
| 成功收尾无诊断 | §7 | stderr 空、退出码 0 ✔ |

## 5. 失败与修订次数

- 修订次数：**0**（首版 `cleanup.lwt` 即通过 `--check` 与公开 CLI，语义无改动）。
- 失败次数：**0**（无 LexError/SyntaxError/RuntimeError，无退出码 2/3/4 记录）。
- 过程中唯一一次非程序性波折：首次用重定向把 stdout 写入 `/tmp/s48_out.txt` 后在 Windows 上读取失败（Git Bash 的 `/tmp` 与 CPython 路径映射不一致）。该问题只影响我的取证方式，不涉及 LWT 程序；改用 `subprocess` 内存捕获后取得同样的四行输出。程序本身与运行结果未因此改动。

## 6. 隔离声明

1. 只读了 TASK.md 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
2. 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录，也未访问任何期望输出或 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。
3. 只用 `python -m lwt <file>`（含 `--check` 开发工具入口）运行与自测，未用其他语言实现或改写程序输出。
4. 只写入了 `docs/agent-eval/submissions/throw-finally-cleanup/` 下的 `cleanup.lwt` 与 `report.md`；未创建其他文件。
5. 所有命令与输出均来自本机真实运行，未手工伪造 stdout/stderr。
