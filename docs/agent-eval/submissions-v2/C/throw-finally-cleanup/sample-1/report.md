# 盲测报告：throw / finally / cleanup

## 1. 产物

- 程序：`docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt`
- 本报告：`docs/agent-eval/submissions/throw-finally-cleanup/report.md`

程序内容要点：顶层 `fn charge(n)`；`n < 0` 时 `throw error("Validation", "negative amount");`，否则 `return n * 2;`。主程序用带 `finally` 的 `attempt` 捕获，随后 `emit str(charge(4));`。未使用 `args()`、`input()`，不读 stdin。

## 2. 依据文档与小节

只阅读了 C 组允许的 `docs/language-spec.md`：

| 依据 | 用于决定 |
|---|---|
| §3 语法（`attempt_stmt`、`throw_stmt`、`fn_decl`） | `attempt { } recover (x) { } finally { }` 三段均不写分号；`throw expr;` 是语句；函数只可顶层声明 |
| §3「`throw` 只能作为语句使用，后接一个表达式和分号」 | `throw error(...);` 的写法 |
| §5 作用域与函数 | `charge` 在顶层登记，主程序可调用；形参与函数体同作用域 |
| §6 预置能力表（`error`、`str`） | `error(category, message)` 返回 Error 值，`source/line/column` 取调用点；`str(value)` 生成显示字符串 |
| §10.1 / §10.6「捕获边界扩展」 | attempt 捕获从 body 动态逸出、退出码 3 的错误，包含经普通函数传播的错误与 `throw` 产生的 `User`/自定义类别错误 |
| §10.3 Error 值 | `category`、`message` 为只读字段；Error 字段顺序与显示规则 |
| §10.6「throw」 | 值为 Error 时原样重抛，保留 `category/message`；故 `problem.category` 为 `Validation`，`problem.message` 为 `negative amount` |
| §10.6「finally 执行语义」 | body 抛错 → 执行 handler → handler 正常结束 → 执行 finally → 继续 attempt 之后的语句；finally 至多一次 |
| §10.2 / §10.6 | attempt 不是事务；finally 中 `problem` 不可见（本程序 finally 未引用它） |
| §4.3 / §6 `str` | `str(8)` 为 `"8"`，`emit` 追加一个 LF |
| §7 退出码 | 全部捕获且正常结束 → 0；stderr 为空 |

关键预期推导：`charge(-5)` 抛错使 `str(...)` 与 `emit` 都不执行（无该行输出）；handler 输出类别与消息；finally 输出 `cleanup`；最后 `charge(4)` 返回 8。

## 3. 运行命令

在工作目录 `C:/Users/28641/AppData/Local/Temp/lwt-s48-C-throw-finally-cleanup-s1` 下，仅使用公开入口：

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/cleanup.lwt
```

## 4. 实测结果

- **stdout repr**：`b'Validation\nnegative amount\ncleanup\n8\n'`
- **stderr repr**：`b''`
- **退出码**：`0`

即四行文本：`Validation`、`negative amount`、`cleanup`、`8`。

补充核验：以 `< /dev/null` 复跑一次，输出与退出码完全相同（`Validation / negative amount / cleanup / 8`，退出 0），确认不依赖 stdin，也不使用 `args()`。

## 5. 失败与修订次数

- 失败次数：0（首版程序即通过）。
- 修订次数：0（未改动 `cleanup.lwt`）。
- 试跑杂项：首轮为采集精确字节 repr 使用了 `/tmp` 重定向，该路径在 Git Bash 与 Python 之间不一致导致读取失败；随后改为直接运行并用 Python `subprocess` 采集 repr，程序本身未做任何修改。这与 LWT 程序语义无关。

## 6. 隔离声明

1. 仅阅读 `TASK.md`、仓库根 `AGENTS.md`（协作规则）与 `docs/language-spec.md`；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
2. 未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
3. 只写入 `docs/agent-eval/submissions/throw-finally-cleanup/` 下的 `cleanup.lwt` 与 `report.md`。
4. 只通过 `python -m lwt <file>` 公开入口执行程序；未用其他语言生成或改写程序输出。
