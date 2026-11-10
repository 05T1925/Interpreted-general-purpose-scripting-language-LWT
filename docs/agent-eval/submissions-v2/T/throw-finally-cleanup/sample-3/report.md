# 盲测提交报告：throw / finally 清理路径（T 组）

## 1. 任务

编写 `cleanup.lwt`：定义 `charge(n)`，`n < 0` 时 `throw error("Validation", "negative amount")`，否则返回 `n` 的两倍；主程序用 `attempt { emit str(charge(-5)); } recover (problem) { ... } finally { emit "cleanup"; }`，随后再 `emit str(charge(4));`。不接收命令行参数与 stdin。

## 2. 依据文档与小节

| 依据 | 用途 |
|---|---|
| `docs/language-spec.md` §3（`fn_decl`、`attempt_stmt`、`throw_stmt`、`emit_stmt` 文法） | 确认 `attempt … recover (p) { … } finally { … }` 与 `throw expr;` 的合法形式、块后不写分号 |
| `docs/language-spec.md` §6 内置函数表 `error(category, message)` | 自定义 category 的 Error 由 `error("Validation", "negative amount")` 构造，`source/line/column` 取调用点 |
| `docs/language-spec.md` §4.3（Error 值字段与显示） | `problem.category`、`problem.message` 为只读字段；`emit` 字符串不带引号 |
| `docs/language-spec.md` §6 `str(value)` 与 `emit` | `emit str(charge(-5))` 与 `emit str(charge(4))` 的显示规则 |
| `docs/language-spec.md` §10.6「throw」「捕获边界扩展」「finally 执行语义」 | throw 的求值/包装规则；attempt 捕获退出码 3 的 `User`/自定义类别错误；finally 在 handler 之后**恰好执行一次**，随后继续 attempt 之后的语句 |
| `docs/language-spec.md` §5（顶层 `fn` 先登记，可前向调用） | `charge` 在顶层普通语句前登记，主程序可直接调用 |
| `docs/language-spec.md` §7 退出码表 | 成功为 0；未捕获的 User/自定义类别为 3、诊断写 stderr |
| `docs/developer-guide.md` §1「先运行」「退出码和诊断」「恢复运行时错误」 | 公开入口 `python -m lwt SOURCE`、先 `--check` 再运行的工作流、stdout 只含 `emit` 输出 |
| `.agents/skills/lwt-app/SKILL.md`「工作流程」第 5、6 条与「S42 新增能力的使用要点」throw/finally 条 | 先静态检查再跑公开 CLI，核对 stdout/stderr/退出码；finally 必执行一次、`problem` 只在 recover 可见、单 handler 内可用 `when (problem.category == "...")` 分派 |

## 3. 程序

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

要点：

- `error("Validation", "negative amount")` 返回 Error 值，`throw` 原样抛出并保留其类别（§10.6）。
- `charge(-5)` 在求 `n * 2` 之前抛出，故 body 中 `emit str(...)` 不产生任何输出；handler 依次输出 `Validation`、`negative amount`。
- finally 在 handler 正常结束后执行，输出 `cleanup`，随后继续 attempt 之后的 `emit str(charge(4))`，输出 `8`。
- 程序不调用 `args()`/`input()`，与「不接收参数与 stdin」一致。

## 4. 命令与真实结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-throw-finally-cleanup-s3`

### 4.1 静态检查

```text
$ python -m lwt --check docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
Check passed: 1 source file(s).
exit 0   stderr: (空)
```

### 4.2 公开入口执行（第 1 次）

```text
$ python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

- stdout（Python repr，由捕获字节 `od -An -c` 核对）：`'Validation\nnegative amount\ncleanup\n8\n'`
- stdout 字节原始转储（37 字节）：`V a l i d a t i o n \n n e g a t i v e   a m o u n t \n c l e a n u p \n 8 \n`
- stderr：空（0 字节）
- 退出码：`0`

### 4.3 复跑一致性（同一次 shell 调用内两次执行，stdout 重定向至文件后 `cmp` 比对）

```text
$ python -m lwt .../cleanup.lwt < /dev/null > r1.out 2> r1.err   # EXIT1=0
$ python -m lwt .../cleanup.lwt < /dev/null > r2.out 2> r2.err   # EXIT2=0
STDOUT_IDENTICAL
OUT_BYTES=37  ERR1_BYTES=0  ERR2_BYTES=0
```

显式关闭 stdin（`< /dev/null`）后输出与退出码不变，验证程序确实不依赖 stdin。

## 5. 语义核对

| 规范预期 | 实测 |
|---|---|
| body 抛出后立即转移控制，`emit str(charge(-5))` 无输出 | 首行为 `Validation`，无多余行 |
| handler 读到自定义类别 `Validation` 与原消息 `negative amount` | 第 1、2 行即为这两个字符串 |
| finally 在 handler 之后、且恰好执行一次 | 第 3 行 `cleanup`，仅一次 |
| finally 后继续 attempt 之后的语句 | 第 4 行 `8`（即 `4 * 2`） |
| 成功路径 stderr 为空、退出码 0 | 0 字节 stderr，exit 0 |

## 6. 失败与修订次数

- 失败次数：**0**
- 修订次数：**0**
- 首版程序在 `--check` 与首次运行即得到上表结果，未做任何改写或重试；无语法、类型、语义类返工。

## 7. 隔离声明

- 只阅读了 TASK.md 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`，外加题目文件 `TASK.md` 本身。
- 未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 执行只用公开入口 `python -m lwt`（`--check` 与普通执行两种子形式），未用其他语言生成或改写程序输出。
- 交付文件仅写入 `docs/agent-eval/submissions/throw-finally-cleanup/`（`cleanup.lwt`、`report.md`）。
- 附带说明：为逐字节核对输出，曾用 shell 重定向把 stdout/stderr 捕获到临时文件（系统临时目录与仓库根下的 `r1.out/r1.err/r2.out/r2.err`，均在同一次命令末尾删除）；`git status` 现仅显示 `?? docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt`（与本报告），仓库根无残留文件，未向其他项目目录写入任何内容。
