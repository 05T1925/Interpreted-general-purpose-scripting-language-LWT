# 报告：throw / finally 清理（cleanup.lwt）

## 1. 任务
编写 `cleanup.lwt`：函数 `charge(n)` 在 `n < 0` 时 `throw error("Validation", "negative amount")`，否则返回 `n` 的两倍；主程序用 `attempt { emit str(charge(-5)); } recover (problem) { ... } finally { emit "cleanup"; }`，随后 `emit str(charge(4));`。不接收参数与 stdin。

## 2. 依据文档与章节
只阅读 `docs/language-spec.md`。

| 设计点 | 依据 |
|---|---|
| `fn` 顶层声明、`return`、`when/otherwise` 分支 | §3（`fn_decl`、`when_stmt`）、§5（顶层函数一次登记、前向调用） |
| `throw expr;` 与 `attempt … recover (p) { … } finally { … }` 的语法、无分号 | §3 `attempt_stmt` / `throw_stmt`、§10.1 |
| `error(category, message)` 返回 Error，`source/line/column` 取调用点 | §6 预置能力表 `error` 行 |
| `throw` 一个 Error 值时**原样重抛**、保留 `category/message/…` 与身份 | §10.6「throw」段 |
| attempt 捕获体 3 类错误（含 `User` 与自定义 category） | §10.6「捕获边界扩展」 |
| `problem.category` / `problem.message` 只读字段与取值 | §10.3 Error 值字段表 |
| finally 在 handler 正常结束后执行、至多一次、`problem` 在 finally 不可见（本题未引用） | §10.6「finally 执行语义」 |
| throw 立即转移控制，`emit str(charge(-5))` 不产生输出 | §10.6、§8.8 规范示例 |
| `str(整数)` 显示为十进制、`emit` 追加 LF、顶层字符串不带引号 | §4.3、§6 `str` |
| 严格无隐式转换、`n < 0` 只接受整数 | §4.2 |

语义推断要点：`charge(-5)` 在求 `str(...)` 实参时即抛出，故 body 的 `emit` 不执行，stdout 不以 `-10` 开头；`throw error(...)` 抛的是 Error 值而非字符串，因此 `problem.category` 是 `"Validation"` 而不是 `"User"`。

## 3. 程序
文件：`docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt`

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

## 4. 运行命令与可观察结果
工作目录为题目根目录；仅通过公开入口运行，无程序实参、stdin 为空：

```
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

- stdout（repr）：`'Validation\nnegative amount\ncleanup\n8\n'`
- stderr：空（0 字节）
- 退出码：`0`

字节级校验（`od -c`）末字节为 `8 \n`，无 CR、无 BOM、无额外输出；stderr 文件长度 0。

## 5. 失败与修订次数
- 失败次数：0
- 修订次数：0（首版一次通过；第二条命令仅用于分离捕获 stdout/stderr 与字节核对，未改动程序）
- 未使用 `--check`、`--profile` 等其它入口，未借用其它语言计算结果。

## 6. 隔离声明
- 只读了 `docs/language-spec.md` 与 `TASK.md`；未打开 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅用 `python -m lwt <file>` 公开入口执行；未用其他语言生成或改写输出。
- 仅写入 `docs/agent-eval/submissions/throw-finally-cleanup/`（`cleanup.lwt`、`report.md`）。
