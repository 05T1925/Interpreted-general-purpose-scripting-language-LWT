# snapshot.lwt 盲测报告

## 1. 题目与产物

- 题目目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-each-snapshot-alias-s4`
- 产物：`docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt`（本报告同目录）
- 要求：不用参数与 stdin；`each` 循环内 `push(values, 99)` 后仍只迭代 3 次；`alias = b` 后 `alias.value = 9` 应让 `b.value` 为 9 且 `b == alias` 为 `true`。

## 2. 依据的文档与小节

- `docs/language-spec.md`
  - §3 语法：`record Name { ... };`、`each (IDENT in expression) block`、字段赋值属于合法表达式语句，`record`/`let` 可作为顶层项。
  - §4.1 值与求值次序：数组和记录是按引用传递的可变对象，赋给另一变量不复制对象。
  - §4.2 运算与比较：`==` 对数组/记录按对象身份比较，同一对象为真；`+` 只接受两个整数或两个字符串。
  - §4.3 数组、记录和显示：`push` 原地追加且别名可见；`r.f = v` 修改字段；`Record{f: v}` 构造实例。
  - §5 作用域、函数与控制流：`each` 进入循环时复制元素引用序列作为浅快照，循环中追加元素不进入快照，快照元素逐个迭代一次。
  - §6 预置能力与 CLI：`push`、`str` 的签名；`emit` 输出显示字符串加一个 LF，stdout 只承载 `emit`。
  - §7 错误与退出码：成功为 0，stderr 为空。
- `docs/developer-guide.md`
  - §2「数组、record 和 `each`」：浅快照与引用语义说明；§3 语义速查中 `push`、`emit`、`str` 与身份相等的说明。
- `.agents/skills/lwt-app/SKILL.md`
  - 工作流程：先 `--check` 再公开 CLI，核对 stdout/stderr/退出码，只记录真实运行结果；语言边界不含本题外的特性。

## 3. 程序要点

- 用 `let values = [1, 2, 3];` 并以 `iterations` 计数；`each (v in values)` 每次迭代执行 `push(values, 99);` 与 `iterations = iterations + 1;`。按 §5，追加只改变原数组，不改变进入循环时建立的 3 元素快照，因此计数为 3。
- `record Box { value };` 声明后构造 `b`，`let alias = b;` 仅复制引用；`alias.value = 9;` 修改同一实例，故 `b.value` 为 9，且 `b == alias` 因身份相同为 `true`。
- 输出使用字符串拼接 `"iterations " + str(iterations)` 与 `str(...)` 转换，避免任何隐式类型转换。

## 4. 自测命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-each-snapshot-alias-s4`

### 4.1 静态检查

```text
$ python -m lwt --check docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
Check passed: 1 source file(s).
```

退出码 0，stderr 为空。

### 4.2 公开 CLI 运行（无参数、空 stdin）

```text
$ python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```

在子进程中以空 stdin 捕获原始字节：

```text
exit 0
stdout b'iterations 3\nb.value 9\nb == alias true\n'
stderr b''
```

- stdout（repr）：`'iterations 3\nb.value 9\nb == alias true\n'`，三行均符合题目要求。
- stderr（repr）：`''`
- 退出码：0

### 4.3 稳定性与 stdin 隔离复核

以 `b'ignored input\n'` 作为 stdin 连续运行两次（程序未调用 `input()`，应完全忽略）：

```text
0 0 b'iterations 3\nb.value 9\nb == alias true\n' b''
1 0 b'iterations 3\nb.value 9\nb == alias true\n' b''
```

两次退出码均为 0，stdout 完全一致且不含 stdin 内容，stderr 为空；程序未使用 `args()`，未接收 `--` 参数。

## 5. 失败与修订次数

- 程序设计：1 稿定稿；程序自身运行失败 0 次，语义修订 0 次。
- 首次 `--check` 与首次运行即通过，输出与题目要求逐行一致。
- 自测过程说明：最初用 Bash 重定向把 stdout 写入 `/tmp` 再读取，因 Git Bash 与 Windows Python 对 `/tmp` 的路径解释不一致而读取临时文件失败（`FileNotFoundError`）；该问题只影响取证脚本，不涉及 LWT 程序或解释器，随后改用 `subprocess` 直接捕获内存中的字节输出，程序未作任何修改。此后的所有证据均来自真实 `python -m lwt` 进程。

## 6. 隔离声明

- 仅阅读了 TASK.md 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 未运行测试套件或仓库工具；所有执行只通过公开入口 `python -m lwt <file>`（含 `--check`），未用其他语言生成或改写程序输出。
- 仅写入 `docs/agent-eval/submissions/each-snapshot-alias/` 下的 `snapshot.lwt` 与 `report.md`。
