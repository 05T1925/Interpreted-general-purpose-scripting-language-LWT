# each 浅快照与记录别名身份 — 实现报告

## 1. 交付物与脚本路径

- 程序：`docs/agent-eval/submissions/each-snapshot-alias/program.lwt`（相对仓库/工作目录根，下称“脚本相对路径”）
- 报告：`docs/agent-eval/submissions/each-snapshot-alias/report.md`
- 注：题目正文称 `snapshot.lwt`，交付清单指定文件名为 `program.lwt`，本提交按交付清单命名。

## 2. 依据的文档与具体小节

仅阅读了允许的三份文档：

| 文档 | 小节 | 用于支撑的实现决策 |
|---|---|---|
| `docs/language-spec.md` | §3 语法（`record`/`each`/`push`/赋值/`emit`） | 顶层 `record Box { value };`、`each (v in values) { ... }`、`Box{value: 0}` 构造、`alias.value = 9` 字段赋值、语句分号 |
| `docs/language-spec.md` | §4.1 值与求值次序 | 数组和记录按引用传递，赋值不复制对象；`let` 初始化成功后才建绑定 |
| `docs/language-spec.md` | §4.2 运算与比较 | `==` 对两个记录实例仅在指向同一对象时为 `true`（身份相等，不做递归比较） |
| `docs/language-spec.md` | §4.3 数组、记录和显示 | `push(array, value)` 原地追加、返回 `null`、别名可见；`r.f = v` 修改字段；顶层字符串/整数/布尔显示格式 |
| `docs/language-spec.md` | §5 作用域、函数与控制流（`each` 段） | “进入循环时复制其**元素引用序列**作为浅快照；循环中追加或替换原数组元素不改变尚待遍历的快照” → 循环只迭代 3 次 |
| `docs/language-spec.md` | §6 预置能力与 CLI（`push`、`str` 行） | `push` 参数与返回；`str(value)` 生成与 `emit` 相同的显示字符串；stdout 只含 `emit` 输出 |
| `docs/developer-guide.md` | §2「数组、record 和 `each`」 | 操作性确认：`each` 浅快照、`push` 原地追加、记录引用语义 |
| `docs/developer-guide.md` | §3「值、运算和作用域」 | 操作性确认：数组/record 的 `==` 比较对象身份 |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」 | 公开入口 `python -m lwt SOURCE`；成功退出码 0；stdout/stderr 分离 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」第 5–6 条 | 先 `python -m lwt --check`，再运行公开 CLI，并核对 stdout/stderr/退出码 |
| `.agents/skills/lwt-app/SKILL.md` | 「语言边界」 | 只使用已支持能力（record、数组、`each`、`push`）；不使用浮点、闭包等未支持特性 |

## 3. 程序要点

1. 浅快照：`values = [1, 2, 3]`，`each (v in values)` 内每次都 `push(values, 99)`；若遍历实时数组将不终止，实测循环体执行 3 次，`iterations` 为 3。
2. 引用别名：`b = Box{value: 0}`，`alias = b`（引用赋值，不复制），`alias.value = 9` 后 `b.value` 为 9；`b == alias` 为同一对象，输出 `true`。
3. 输出拼接：`emit "iterations " + str(iterations);` 等，`str` 对整数/布尔给出 `3`/`true`（§4.3、§6）。
4. 程序不调用 `args()` 与 `input()`，不接收参数与 stdin。

## 4. 运行记录（真实 CLI）

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s47-blind-each-snapshot-alias`（所有命令先 `cd` 到该目录）。

### 4.1 静态检查

命令：

```text
python -m lwt --check docs/agent-eval/submissions/each-snapshot-alias/program.lwt
```

- stdout（repr）：`'Check passed: 1 source file(s).\n'`
- stderr（repr）：`''`
- 退出码：`0`

### 4.2 正式运行

命令：

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/program.lwt
```

- stdout（repr）：`'iterations 3\nb.value 9\nb == alias true\n'`
- stderr（repr）：`''`
- 退出码：`0`

字节级复核（`python -m lwt ... | od -An -c`）显示 stdout 为：

```text
i t e r a t i o n s   3 \n b . v a l u e   9 \n b   = =   a l i a s   t r u e \n
```

（`od` 输出按原样展开；等价 repr 见上。）另以 `stderr=$(python -m lwt ... 2>&1 >/dev/null)` 复核，得到 `STDERR_REPR=''`、退出码 0。

三行输出与题目要求逐字一致：`iterations 3`、`b.value 9`、`b == alias true`。

## 5. 失败尝试与修订次数

- 失败运行：0 次。`--check` 首次通过；正式运行首次即得到目标输出。
- 程序修订：0 次（初版即最终版）。
- 证据采集：正式运行重复 3 次用于捕获原始字节、区分 stdout/stderr、确认退出码，结果完全一致（程序确定性，无 stdout 之外的输出）。

## 6. 隔离与合规声明

- 已读文档：仅 `docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md` 三份允许文档。
- **未读取** `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径。
- 开工时执行过一次只读目录列举（`find . -maxdepth 3 -type f` 与 `ls`），用于确认文档与提交目录位置；其输出仅涉及 `docs/` 文件名与目录项，未打开任何禁止文件。
- 解释器只通过 `python -m lwt` 公开入口运行；未用 Python 或其他语言生成/改写输出或程序。
- **需要如实说明的一处越界**：首次运行曾用 shell 重定向把该程序自身的 stdout/stderr 临时写入工作目录之外的 `/tmp/lwt_out.txt`、`/tmp/lwt_err.txt`（内容仅为本次运行输出，未涉及仓库任何文件，也未用于生成答案）。发现后立即改用不落盘的变量/管道方式采集证据（见 §4），后续所有运行均未再写工作目录之外的文件。交付物仅位于 `docs/agent-eval/submissions/each-snapshot-alias/` 下。
