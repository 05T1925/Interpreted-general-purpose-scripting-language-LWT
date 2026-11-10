# throw / finally 清理路径 — 独立盲测提交报告

## 1. 交付物

| 文件 | 说明 |
|---|---|
| `docs/agent-eval/submissions/throw-finally-cleanup/program.lwt` | 唯一源程序，17 行有效代码 + 空行 |
| `docs/agent-eval/submissions/throw-finally-cleanup/report.md` | 本报告 |

程序概要（行号对应 `program.lwt`）：

- 1–6 行：`fn charge(n)`，`n < 0` 时 `throw error("Validation", "negative amount");`，否则 `return n * 2;`（3 行、5 行）。
- 8–15 行：`attempt { emit str(charge(-5)); } recover (problem) { emit problem.category; emit problem.message; } finally { emit "cleanup"; }`。
- 17 行：`emit str(charge(4));`。

## 2. 依据文档与小节

只引用 T 组允许的三份文档（`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`）。

| 需求点 | 依据 |
|---|---|
| `fn` 顶层声明、形参、`return`、`when/otherwise` 分支 | 规范 §3 语法（`fn_decl`、`when_stmt`、`return_stmt`，第 51、54–68 行）；§5（函数在普通语句前登记、`return` 语义，第 139–147 行） |
| `throw expr;` 语法与上下文 | 规范 §3（`throw_stmt = "throw" expression ";"`，第 63 行）；§2.1 保留字表含 `throw`、`finally`（第 31 行） |
| `throw` 语义：`error(category, message)` 构造自定义类别 Error 并在 throw 处重抛 | 规范 §10.6「throw」段（第 450 行）；§6 内置 `error(category, message)` 返回 Error，`source/line/column` 取调用点（第 176 行）；§4.1 Error 仅由 recover handler 创建/按身份传递（第 105 行） |
| attempt 捕获 `User`/自定义类别（退出码 3 类）错误，`problem` 绑定该 Error | 规范 §10.6「捕获边界扩展」（第 452 行）；§5（第 149–151 行）；§10.1（第 396–400 行） |
| `finally` 至多执行一次，handler 正常结束后执行 finally，再继续之后语句 | 规范 §10.6「finally 执行语义」第 2 条（第 457 行）、第 454–460 行整体规则 |
| `problem` 只在 handler 动态执行期间可见 | 规范 §10.6（第 454 行）；§10.2（第 404 行） |
| `str(value)` 与 `emit` 的显示规则（整数十进制、字符串顶层不带引号） | 规范 §4.3（第 123 行）；§6 `str` 行（第 166 行） |
| 成功执行退出码 0、stdout 只含 `emit` 输出、诊断走 stderr | 规范 §7 表（第 198–205 行）；§6（第 155 行） |
| 该组合的可运行性先例（`User` 类别 + finally 顺序） | 规范 §8.8（第 330–345 行）示例模式；本题用 `error("Validation", ...)` 只改变类别与消息，捕获/finally 顺序不变 |
| 操作流程：先 `--check`，再用公开 CLI 运行并核对 stdout/stderr/退出码 | 开发指南 §1「运行前静态检查」「退出码和诊断」（第 77–86、54–75 行）；SKILL「工作流程」第 5–6 条（第 16–20 行） |

不接收参数与 stdin 的依据：程序未调用 `args()`/`input()`，规范 §6（第 160、159 行）说明二者只在显式调用时读取；`python -m lwt SOURCE` 不带 `--` 时无可传程序实参（规范第 186 行；开发指南第 28–35 行）。

## 3. 命令与实测记录

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-throw-finally-cleanup-s2`

### 3.1 静态检查

```text
python -m lwt --check docs/agent-eval/submissions/throw-finally-cleanup/program.lwt
```

- stdout：`Check passed: 1 source file(s).\n`
- stderr：空
- 退出码：0

### 3.2 正常运行（无参数、不喂 stdin）

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/program.lwt
```

- stdout（Python `repr`）：`'Validation\nnegative amount\ncleanup\n8\n'`
- stdout 原始字节：`[86, 97, 108, 105, 100, 97, 116, 105, 111, 110, 10, 110, 101, 103, 97, 116, 105, 118, 101, 32, 97, 109, 111, 117, 110, 116, 10, 99, 108, 101, 97, 110, 117, 112, 10, 56, 10]`（即四行、每行以 LF `0x0A` 结尾，无 CR）
- stderr（Python `repr`）：`''`
- 退出码：0

逐行对应：`Validation`（`problem.category`，来自 `error("Validation", ...)`）→ `negative amount`（`problem.message`）→ `cleanup`（finally，在 handler 正常结束后执行）→ `8`（`charge(4)` = 4 × 2，经 `str` 输出）。`emit str(charge(-5));` 未产生任何输出，说明 `throw` 在 `emit` 求值期间立即转移控制。

### 3.3 关闭 stdin 复跑（验证不依赖 stdin）

```text
python -m lwt docs/agent-eval/submissions/throw-finally-cleanup/program.lwt < /dev/null
```

- stdout（`repr`）：`'Validation\nnegative amount\ncleanup\n8\n'`
- stderr（`repr`）：`''`
- 退出码：0

两次运行输出逐字节一致（同一 36 字节序列），程序不读取 stdin、未挂起等待输入。

### 3.4 采集方式说明

为给出精确 `repr`，把 stdout/stderr 重定向到提交目录内的临时文件 `.stdout.bin`、`.stderr.bin`、`.stdout2.bin`、`.stderr2.bin`，运行结束后以 `python -c` 只做「读字节并 `repr` 解码」的展示，**没有**用其它语言生成或修改任何 LWT 输出；四个临时文件已在记录完成后删除。

## 4. 失败与修订次数

| 项 | 次数 | 说明 |
|---|---:|---|
| 程序失败（非 0 退出、stderr 非空、输出不符） | 0 | `--check` 0 次失败；正常运行 0 次失败 |
| `program.lwt` 修订 | 0 | 首版即通过静态检查与两次实跑，未改动内容 |
| 采集环节的偶发错误 | 1 | 首次捕获把临时文件写到 Git Bash 的 `/tmp`，而 Windows 原生 `python -c` 看不到该路径，报 `FileNotFoundError`；改为在提交目录内捕获后成功。此项属证据采集工具路径问题，不涉及 LWT 程序，也未触发任何程序修改 |

## 5. 隔离声明

- 全程 `cd` 到 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-throw-finally-cleanup-s2`，读写仅限该目录；写入仅发生在 `docs/agent-eval/submissions/throw-finally-cleanup/`（含上述临时捕获文件，用后删除）。
- 仅阅读 T 组允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目或任何期望输出；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 未联网。
- 执行只用公开入口 `python -m lwt`（含 `--check`）；未用其他语言生成输出，未修改程序以外的解释器文件。
- 报告中的命令、stdout `repr`、stderr、退出码均来自本会话真实执行，未复制或猜测期望值。
