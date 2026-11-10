# 盲测提交报告：throw / attempt / recover / finally 清理语义

## 1. 依据的文档与具体小节

只阅读了任务允许的 T 组三份文档：

| 文档 | 使用到的小节 | 取用的规则 |
|---|---|---|
| `docs/language-spec.md` | §2.1 保留字表 | `attempt`/`recover`/`finally`/`throw` 均为保留字；`error` 是预置函数名，不是关键字 |
| `docs/language-spec.md` | §3 语法（`attempt_stmt`、`throw_stmt`、`fn_decl`） | `attempt block recover (IDENT) block [finally block]`，三个块后均不写分号；`throw expression;` 带分号；`fn` 只能顶层声明 |
| `docs/language-spec.md` | §5 作用域与函数 | 顶层 `fn` 在执行前登记；函数体末尾 `return expr;` 返回值；`problem` 仅在 handler 动态执行期间可见 |
| `docs/language-spec.md` | §6 预置能力表 `error(category, message)` 行 | 两字符串参数，返回 `source/line/column` 取调用点的 Error 值，用于构造自定义 category |
| `docs/language-spec.md` | §10.1 捕获边界 | attempt 捕获从 body 逸出、退出码 3 的 LWT 错误，含 `throw` 的 `User`/自定义类别 |
| `docs/language-spec.md` | §10.3 Error 值 | `category`、`message` 只读字段；`message` 为不含类别/路径/行列前缀的原始消息 |
| `docs/language-spec.md` | §10.6 throw 与 finally（核心依据） | `throw expr;` 值为字符串时 category 为 `User`；此处用 `error("Validation", ...)` 得到 category `Validation`；throw 的 Error 值原样重抛；**finally 至多执行一次**，body 正常 → 跳过 handler 后执行 finally；body 抛可恢复错误 → 执行 handler、handler 正常结束后执行 finally、再继续之后语句 |
| `docs/language-spec.md` | §4.3 显示规则 | 顶层字符串 `emit` 不带引号，`str(value)` 与 `emit` 同规则 |
| `docs/developer-guide.md` | §1「先运行」/「CLI、参数和输入」 | 运行方式 `python -m lwt SOURCE`；不需要 `--` 与参数 |
| `docs/developer-guide.md` | §1「退出码和诊断」 | 成功退出码 0；stdout 只放 `emit` 结果，stderr 为空 |
| `docs/developer-guide.md` | §1「运行前静态检查」 | 建议工作流：先 `--check`，再跑公开 CLI |
| `docs/developer-guide.md` | §1「恢复运行时错误」 | `attempt/recover` 捕获后继续执行 attempt 之后的语句；`problem.category`/`problem.message` 各占一行 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」1/5/6/7 条 | 先读开发指南、查规范；先 `--check` 再 `python -m lwt`；核对 stdout/stderr/退出码；只记录真实运行的命令 |
| `.agents/skills/lwt-app/SKILL.md` | 「语言边界」S42 段（throw/finally 要点） | `throw error("Category","message")` 抛自定义类别；finally 无论正常/错误都执行一次；`problem` 只在 recover 块可见 |

## 2. 交付物与脚本相对路径

- 程序：`docs/agent-eval/submissions/throw-finally-cleanup/program.lwt`
- 本报告：`docs/agent-eval/submissions/throw-finally-cleanup/report.md`
- 所有命令的工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-throw-finally-cleanup-s1`（仓库根；下文命令中的相对路径均以此为基准）

题目文字称程序为 `cleanup.lwt`，交付清单要求文件名为 `program.lwt`，故按交付清单命名为 `program.lwt`，程序内容与 `cleanup.lwt` 的要求一致。

程序正文：

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

## 3. 执行记录（全部为真实运行的命令）

### 3.1 环境

命令：

```text
python --version
python -m lwt --version
```

- `python --version`：stdout `'Python 3.13.14\n'`，stderr `''`，退出码 0
- `python -m lwt --version`：stdout `'lwt 0.3.0\n'`，stderr `''`，退出码 0

### 3.2 静态检查

命令：

```text
python -m lwt --check docs/agent-eval/submissions/throw-finally-cleanup/program.lwt
```

- stdout：`'Check passed: 1 source file(s).\n'`
- stderr：`''`
- 退出码：`0`

### 3.3 公开 CLI 运行（第 1 次）

命令：

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/program.lwt
```

- stdout：`'Validation\nnegative amount\ncleanup\n8\n'`
- stderr：`''`
- 退出码：`0`

### 3.4 公开 CLI 运行（第 2 次，stdin 显式关闭，确认不读 stdin）

命令：

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/program.lwt < /dev/null
```

- stdout：`'Validation\nnegative amount\ncleanup\n8\n'`（37 字节）
- stderr：`''`（0 字节）
- 退出码：`0`
- 逐行：`['Validation', 'negative amount', 'cleanup', '8']`

### 3.5 输出与题目要求的对照

| 顺序 | 期望来源 | 实际输出 |
|---|---|---|
| 1 | `recover` 中 `emit problem.category`，throw 的 `error("Validation", ...)` 使 category 为 `Validation` | `Validation` |
| 2 | `emit problem.message`，即 `negative amount` | `negative amount` |
| 3 | `finally` 块 `emit "cleanup"`，在 handler 正常结束后执行一次 | `cleanup` |
| 4 | attempt 之后的 `emit str(charge(4))`，`4*2=8` | `8` |

`charge(-5)` 在 `str()`/`emit` 之前就抛错，因此 body 不产生任何输出；这与 §10.6「body 抛出可恢复错误 → 执行 handler」一致。stderr 为空、退出码 0 表明错误被 recover 完整捕获，未升级为退出码 3 的诊断。

## 4. 失败尝试与修订次数

- 程序修订次数：**0**。首版 `program.lwt` 即通过 `--check` 与两次公开 CLI 运行，未修改源码。
- 失败尝试：**1 次**，且属测试脚手架问题，不是程序或语言语义失败。
  - 命令：`python -m lwt .../program.lwt > /tmp/out.txt 2> /tmp/out.err`，随后用 `python -c` 读取 `/tmp/out.txt`。
  - 现象：`FileNotFoundError: [Errno 2] No such file or directory: '/tmp/out.txt'`，该读取步骤退出码 1（同一 shell 行中 `echo "exit=$?"` 打印的是程序自身的 0）。
  - 原因：Git Bash 的 `/tmp` 与 Windows 原生 Python 看到的路径不一致，重定向文件落在 MSYS 侧临时目录。
  - 修订：改为把 stdout/stderr 重定向到提交目录内的相对路径文件再读取（即 §3.3、§3.4 的做法），未改动 `.lwt` 源码。证据文件读取完成后已删除，目录内只保留 `program.lwt` 与 `report.md`。

## 5. 隔离合规声明

- 只阅读了 `docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md` 三份 T 组文档。
- **未**读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、`examples/`、其他题目目录，也未读取任何期望输出文件；目录列表（`ls`）只用于确认提交目录存在，未展开这些目录的内容。
- **未**访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径。
- **未**联网。
- 只通过公开入口 `python -m lwt` 运行程序；`python -c` 仅用于把已捕获的 stdout/stderr 字节解码为 `repr` 以便写入本报告，未用于生成或改写程序输出。
- 写入范围仅限 `docs/agent-eval/submissions/throw-finally-cleanup/` 下的 `program.lwt`、`report.md`（以及已删除的临时重定向文件）。
