# throw / finally / cleanup 盲测提交报告

## 1. 程序与脚本路径

- LWT 源码：`docs/agent-eval/submissions/throw-finally-cleanup/program.lwt`（相对仓库根目录，下文所有命令均在仓库根目录 `C:/Users/28641/AppData/Local/Temp/lwt-s47-blind-throw-finally-cleanup` 下执行）
- 程序内容要点：`fn charge(n)` 在 `n < 0` 时 `throw error("Validation", "negative amount")`，否则 `return n * 2`；主程序 `attempt { emit str(charge(-5)); } recover (problem) { emit problem.category; emit problem.message; } finally { emit "cleanup"; }`，随后 `emit str(charge(4));`；不读参数、不读 stdin。

## 2. 依据的文档与具体小节

| 文档 | 小节 | 用于确定的行为 |
|---|---|---|
| `docs/language-spec.md` | §3 语法（`fn_decl`、`throw_stmt`、`attempt_stmt = "attempt" block "recover" "(" IDENT ")" block [ "finally" block ]`） | 顶层 `fn` 声明形式；`throw expr;` 的语句形式；`finally` 紧跟 recover 块、三者后都不写分号 |
| `docs/language-spec.md` | §10.6「throw 与 finally」 | `throw` 先求值表达式；`error(category, message)` 构造的 Error 值被 `throw` 时保留类别与身份；attempt 捕获退出码 3 的 LWT 错误；handler 正常结束后执行 finally，再继续后续语句 |
| `docs/language-spec.md` | §10.3「Error 值」 | `problem.category`、`problem.message` 为只读字符串字段，`error()` 的 `source/line/column` 取调用点 |
| `docs/language-spec.md` | §6 预置能力表 `error(category, message)` 行 | 该内置返回 Error 值，用于自定义 category |
| `docs/language-spec.md` | §5「作用域、函数与控制流」 | 顶层 `fn` 在执行普通语句前一次性登记，允许顶层语句调用；函数体 `return` 语义 |
| `docs/language-spec.md` | §4.3「数组、记录和显示」与 §6 `str(value)` 行 | `str` 与 `emit` 使用同一显示字符串并追加 LF；顶层字符串不带引号，整数显示为十进制 |
| `docs/language-spec.md` | §7「错误、退出码与实现约束」 | 成功退出码 0；未捕获运行时错误为 3（本程序全部被捕获，故为 0） |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」 | 公开入口 `python -m lwt <source-path>`；源路径相对进程工作目录；stdout 只放 `emit` 结果 |
| `docs/developer-guide.md` | §1「恢复运行时错误」小节 | `attempt/recover` 只捕获执行期 `RuntimeError`（退出码 3），错误前的输出不回滚 |
| `docs/developer-guide.md` | §3「内置函数与输出」表（`str`、`emit`、`error` 相关行） | `str(value)` 与 `emit` 同规则；`emit` 是语句，输出一个值加 LF |
| `docs/developer-guide.md` | §4「调试和验证」 | 每次修改后用公开 CLI 核对 stdout/stderr/退出码 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」1–8 步 | 先读指南/规范，再 `--check`，再公开 CLI 运行并核对 stdout、stderr、退出码，只记录真实运行结果 |
| `.agents/skills/lwt-app/SKILL.md` | 「S42 新增能力的使用要点」throw/finally 条目 | `throw error("Category", "message")` 抛出自定义类别；finally 在正常/错误路径都会执行一次；`problem` 只在 recover 可见 |

## 3. 运行命令与结果

### 3.1 静态检查

命令：

```
python -m lwt --check docs/agent-eval/submissions/throw-finally-cleanup/program.lwt
```

- stdout（repr）：`'Check passed: 1 source file(s).\n'`
- stderr（repr）：`''`
- 退出码：`0`

### 3.2 正式运行（主要证据）

命令：

```
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/program.lwt
```

同时把 stdout/stderr 重定向到本提交目录内的临时文件，再用 `od -c` 核对原始字节（核对后已删除临时文件）：

- stdout 字节：`V a l i d a t i o n \n n e g a t i v e   a m o u n t \n c l e a n u p \n 8 \n`
- stdout（repr）：`'Validation\nnegative amount\ncleanup\n8\n'`
- stderr（repr）：`''`
- 退出码：`0`

与题目要求一致：`attempt` 体内 `charge(-5)` 抛出自定义类别 `Validation`，handler 依次输出 `Validation`、`negative amount`，finally 输出 `cleanup`，随后 `charge(4)` 正常返回 `8`。

### 3.3 无 stdin 依赖的补充验证

命令：

```
printf 'ignored line\n' | python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/program.lwt
```

- stdout（repr）：`'Validation\nnegative amount\ncleanup\n8\n'`
- stderr（repr）：`''`
- 退出码：`0`

说明程序不消费 stdin，输入被忽略、输出不变；`args()` 也从未调用，符合"不接收参数与 stdin"。

## 4. 失败尝试与修订次数

- **程序修订次数：0 次。** `program.lwt` 一次写成；`--check` 首次通过，首次正式运行即得到预期输出，未做任何语义或语法修改。
- **采集环节的一次失误（不影响程序，也不涉及改程序）**：最初把 stdout/stderr 重定向到 `/tmp/out.txt`、`/tmp/err.txt` 再用 Python 读取，因该路径是 MSYS 虚拟路径、Windows 上的 Python 解析不到，读取报 `FileNotFoundError`（退出码 1）。改用提交目录内的临时文件重定向并用 `od -c` 读原始字节后取得证据，临时文件已删除。此失误只发生在取证据的命令上，`program.lwt` 未改动，LWT 程序的运行结果不受影响。
- 未出现 LWT 词法/语法/运行时错误，未出现非 0 退出码。

## 5. 隔离声明

- 实际读取内容的文件仅三份白名单文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- **未读取** `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下的任何路径。
- 需如实说明的边界：为定位工作目录与提交目录，执行过 `ls`（仓库根目录与 `docs/agent-eval/submissions/throw-finally-cleanup`）。`ls docs` 的输出中出现了 `docs/` 下其他文件名（含非白名单文档名），但只是目录条目名称，未打开或读取其中任何文件内容。
- 所有写入仅限 `docs/agent-eval/submissions/throw-finally-cleanup/` 下：最终保留 `program.lwt` 与 `report.md`；过程性临时字节文件已删除。
- 运行只使用公开入口 `python -m lwt`（含 `--check`），未用 Python 或其他语言生成/改写程序输出。
