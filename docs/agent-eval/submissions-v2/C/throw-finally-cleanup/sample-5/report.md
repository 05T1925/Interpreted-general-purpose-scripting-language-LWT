# 盲测报告：throw + finally 清理

## 程序

`cleanup.lwt`（与本报告同目录）：

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

## 依据（仅 docs/language-spec.md）

| 需求 | 依据小节 | 要点 |
|---|---|---|
| `charge` 定义、`when` 分支、`return` | §3（`fn_decl`/`when_stmt`/`return_stmt`）、§5 | 顶层 `fn` 先登记，普通语句按序执行 |
| `throw error("Validation", "negative amount")` | §10.6「throw」、§6 `error(category, message)` 行 | `error` 返回 Error，`source/line/column` 取调用点；`throw` Error 值原样重抛并保留 `category/message` |
| `attempt … recover (problem) … finally …` | §3 `attempt_stmt`、§10.6「捕获边界扩展」「finally 执行语义」 | 捕获所有退出码 3 的 LWT 错误（含 `throw` 的自定义类别）；`problem` 仅 handler 内可见；finally 至多执行一次且在 handler 之后 |
| 未被捕获的非法 `throw` 类型 / `problem` 字段读取 | §10.6、§10.3 | 本程序不涉及；字段读取 `problem.category`、`problem.message` 为只读字符串字段 |
| 输出格式 | §4.3、§6 `emit` 行 | `emit` 输出显示字符串 + 一个 LF；顶层字符串不带引号 |
| `str` | §6 `str(value)` 行 | 整数显示为十进制 |

要点：`str(charge(-5))` 中 `charge(-5)` 先抛错，`str` 与 `emit` 均不执行，故 body 无输出；handler 输出自定义类别 `Validation` 与原消息；finally 随后输出；attempt 之后 `charge(4)` 正常返回 8。

## 运行命令与结果

环境：Windows 11，Python 3.13.14，工作目录为题目目录根。仅使用公开入口 `python -m lwt <file>`。

命令：

```
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

- stdout repr：`'Validation\nnegative amount\ncleanup\n8\n'`
- stderr repr：`''`
- 退出码：`0`

带显式捕获复核（同样只调用 `python -m lwt`）：

```
python -c "import subprocess,sys; p=subprocess.run([sys.executable,'-m','lwt','docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt'],capture_output=True); print(p.returncode, repr(p.stdout.decode()), repr(p.stderr.decode()))"
```

输出：`0 'Validation\nnegative amount\ncleanup\n8\n' ''`

逐行核对规范预期：

1. `Validation` —— `throw` 的 Error 值 category 被 handler 读到（§10.6 保留原类别，而非笼统 `RuntimeError`）。
2. `negative amount` —— `problem.message` 为原始消息。
3. `cleanup` —— finally 在 handler 正常结束后执行（§10.6）。
4. `8` —— `charge(4)` 返回 `4 * 2`，`str` 后由 `emit` 输出。

程序不读取 `args()`、不调用 `input()`，无参数与 stdin 依赖；重复运行结果一致。

## 失败与修订

- 失败运行次数：0
- 修订（改源码）次数：0
- 说明：按 §10.6 一次性写成 `throw error(...)` 形式（而非 `throw "..."`），首次运行即得到上述输出与退出码 0。

## 隔离声明

- 只阅读了 `docs/language-spec.md`（及题目与仓库协作说明文件），未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只用 `python -m lwt <file>` 公开入口运行程序；未用其他语言生成输出，未改写运行结果。
- 仅写入 `docs/agent-eval/submissions/throw-finally-cleanup/` 下的 `cleanup.lwt` 与 `report.md`。
