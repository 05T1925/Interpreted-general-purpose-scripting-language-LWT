# 报告：each 浅快照与 record 别名身份相等

## 1. 依据文档与具体小节

| 文档 | 小节 | 用于支撑的要点 |
|---|---|---|
| `docs/language-spec.md` | §3 语法 | `record IDENT { name_list } ;`、`each ( IDENT in expression ) block`、`emit expression;`、赋值左值可为字段访问 `r.f`；`let` 必须带分号；不支持尾随逗号 |
| `docs/language-spec.md` | §4.1 值与求值次序 | 数组与记录按引用传递，赋给另一变量不复制对象；赋值先验证目标再求右值 |
| `docs/language-spec.md` | §4.2 运算与比较 | `==` 对两个记录实例仅在指向同一对象时为真，不做递归结构比较；`+` 只接受两个整数或两个字符串；无隐式类型转换 |
| `docs/language-spec.md` | §4.3 数组、记录和显示 | `push(array, value)` 原地追加、返回 `null`，别名可观察到修改；`record Name { f1 };` 构造 `Name{f1: v}`；`emit` 输出显示串加一个 LF，整数显示为十进制、布尔显示为 `true` |
| `docs/language-spec.md` | §5 作用域、函数与控制流 | `each (item in expr)` 先求 `expr` 得到数组，进入循环时复制其**元素引用序列**作为浅快照，循环中追加元素不改变尚待遍历的快照；变量名可与函数名同名，语法位置决定查找 |
| `docs/language-spec.md` | §6 预置能力与 CLI | `str(value)` 返回与 `emit` 相同规则的显示字符串；`push` 返回 `null`；命令形式 `python -m lwt <source-path>`，成功不额外输出状态信息 |
| `docs/language-spec.md` | §8.2 结构、数组和浅快照 | 规范示例同为「循环体内 `push` 原数组，仍只遍历进入时的元素」，预期 `len` 为 4 而循环只两次 |
| `docs/language-spec.md` | §7 错误、退出码 | 成功退出码 0；stdout 只承载 `emit`，诊断写 stderr |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」 | 使用公开入口 `python -m lwt`；`SOURCE` 后无 `--` 时不接收额外参数；stdout/stderr/退出码契约 |
| `docs/developer-guide.md` | §2「数组、record 和 `each`」 | `each` 开始时保存元素引用序列的浅快照，本轮追加或替换元素不改变该快照；`push` 原地追加 |
| `docs/developer-guide.md` | §3「值、运算和作用域」「内置函数与输出」 | 数组和 record 的 `==` 比较对象身份；`str` 与 `emit` 同规则；`emit` 输出值加 LF |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」第 5–7 条 | 先 `--check`，再用公开 CLI 运行，核对 stdout/stderr/退出码，只记录真实运行的命令与结果 |

## 2. 脚本相对路径

`docs/agent-eval/submissions/each-snapshot-alias/program.lwt`

## 3. 程序要点

- 数组快照：`let values = [1, 2, 3];` 后进入 `each (v in values)`，循环体内每轮 `push(values, 99);`，并用 `iterations` 计数。依据规范 §5，进入循环时的浅快照只含 3 个元素引用，追加的 `99` 不进入待遍历序列，因此 `iterations` 为 3。
- 记录别名：`record Box { value };`；`let b = Box{value: 0};`、`let alias = b;` 使两变量指向同一实例（§4.1 引用语义）。`alias.value = 9;` 修改该实例（§3 字段赋值左值、§4.3 字段修改），故 `b.value` 为 9；`b == alias` 按身份比较为 `true`（§4.2、§4.3）。
- 输出拼接使用 `"前缀 " + str(x)`，因 `+` 只接受两个整数或两个字符串，必须显式 `str`（§4.2、§6）。

## 4. 运行命令与结果

所有命令均在仓库根目录（`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-each-snapshot-alias-s1`）执行。

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

stdout 字节核对（`od -An -c`）确认三行均以单个 `\n` 结尾、无 CR、无 BOM、无多余状态文字：

```text
   i   t   e   r   a   t   i   o   n   s       3  \n   b   .   v
   a   l   u   e       9  \n   b       =   =       a   l   i   a
   s       t   r   u   e  \n
```

该次运行未传入任何程序实参，也未提供 stdin；程序本身不调用 `args()` 或 `input()`。

## 5. 失败尝试与修订次数

- 失败尝试：0 次。
- 修订次数：0 次（首版即通过 `--check` 与正式运行）。

## 6. 隔离声明

如实声明：本次会话只阅读了题目允许的三份文档 `docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`；只执行了 `python -m lwt --check` 与 `python -m lwt` 两个公开入口命令，以及目录创建、输出捕获与 `od`/`wc` 等只读检查命令。

未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、`examples/`、任何其他题目目录或任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下的任何路径。除工作目录根下的 `docs/`、`.agents/skills/lwt-app/SKILL.md` 与提交目录外，未读取仓库其他内容（根目录仅执行过一次 `ls` 以确认工作目录结构，未打开其中任何文件）。

写入范围仅限 `docs/agent-eval/submissions/each-snapshot-alias/`（`program.lwt`、`report.md`）；未使用 Python 或其他语言生成程序输出或改写程序。
