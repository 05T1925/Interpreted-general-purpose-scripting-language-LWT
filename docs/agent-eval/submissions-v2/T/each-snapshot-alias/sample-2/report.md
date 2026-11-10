# snapshot.lwt 交付报告（each 浅快照 + record 别名）

## 1. 题目要求与实现对应

| 要求 | 实现 | 依据 |
|---|---|---|
| 构造 `[1, 2, 3]` | `let values = [1, 2, 3];` | 规范 §3 `atom` 数组字面量、§4.3 数组从零索引 |
| `each (v in values)` 体内 `push(values, 99)` | 循环体首句 `push(values, 99);` | 规范 §3 `each_stmt`、§6 `push(array, value)` 原地追加返回 `null` |
| 验证浅快照仍只迭代 3 次 | 循环体内 `iterations = iterations + 1;`，循环后输出 | 规范 §5：「`each` 先求 `expr`…进入循环时复制其**元素引用序列**作为浅快照…循环中追加或替换原数组元素不改变尚待遍历的快照」；§4.3 同义 |
| 统计并输出 `iterations 3` | `emit "iterations " + str(iterations);` | 规范 §6 `str(value)` 与 `emit`；§4.2 `+` 仅整数或字符串拼接 |
| `record Box {value};` 的 `b` | `record Box { value };` + `let b = Box{value: 1};` | 规范 §3 `record_decl`、§4.3 构造字段集合须与声明完全一致 |
| `alias = b`，`alias.value = 9` | `let alias = b;` `alias.value = 9;` | 规范 §4.1「数组和记录是按引用传递的可变对象；把它们赋给另一变量…不会复制对象」；§4.3 `r.f = v` |
| 输出 `b.value 9` | `emit "b.value " + str(b.value);` | 同上 + §4.3 字段读取 |
| 输出 `b == alias true` | `emit "b == alias " + str(b == alias);` | 规范 §4.2「两个数组或两个记录实例只在指向同一个对象时相等」 |
| 不接收参数与 stdin | 程序不调用 `args()` / `input()` | 规范 §6 两者分别为显式调用才生效 |

补充约束核对：`record` 为顶层项，按 §5 在普通语句执行前一次性登记，因此写在语句之后仍合法；语句结束分号均显式写出（§2.1）；输出仅三行，成功时 CLI 不额外打印状态（§6）。

## 2. 依据文档与小节

- `docs/language-spec.md`
  - §2.1 编码/空白：分号不可省略，`#` 行注释。
  - §3 语法：`record_decl`、`each_stmt`、`assignment`/`postfix`（`alias.value = 9` 为合法左值）。
  - §4.1 值与求值次序：数组/记录按引用传递，赋值不复制对象。
  - §4.2 运算与比较：`+` 仅整数或字符串；`==` 对数组/记录为身份相等。
  - §4.3 数组、记录和显示：`push` 原地追加；`str`/`emit` 的显示格式（`true` 显示为 `true`）。
  - §5 作用域与循环：`each` 的浅快照语义、`break`/`continue` 不在本程序使用。
  - §6 预置能力与 CLI：`push`、`str`、`emit`、`--check`；命令形式 `python -m lwt SOURCE`。
  - §7 错误与退出码：成功 0，运行时错误 3，词法/语法 2。
- `docs/developer-guide.md`
  - §1「先运行」：公开入口 `python -m lwt SOURCE`，不要用 Python 执行 `.lwt`；§1「运行前静态检查」建议先 `--check`。
  - §2「数组、record 和 `each`」：浅快照与 `push` 原地追加说明。
  - §3「内置函数与输出」：`push`、`str`、`emit` 的行为摘要。
- `.agents/skills/lwt-app/SKILL.md`
  - 「工作流程」第 5–7 步：先 `--check`，再用公开 CLI 运行，只记录真实运行的命令与结果。

## 3. 交付文件

- `docs/agent-eval/submissions/each-snapshot-alias/program.lwt`（518 字节，UTF-8 无 BOM，LF）
- `docs/agent-eval/submissions/each-snapshot-alias/report.md`（本文件）

程序全文：

```lwt
# snapshot.lwt
# 1) each 的浅快照：循环体内 push(values, 99) 不改变本次遍历的快照。
# 2) record 是引用类型：alias = b 后 alias.value 赋值对 b 可见，且 b == alias 为 true。

let values = [1, 2, 3];
let iterations = 0;
each (v in values) {
    push(values, 99);
    iterations = iterations + 1;
}
emit "iterations " + str(iterations);

record Box { value };

let b = Box{value: 1};
let alias = b;
alias.value = 9;
emit "b.value " + str(b.value);
emit "b == alias " + str(b == alias);
```

## 4. 真实运行的命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-each-snapshot-alias-s2`；Python 3.13.14。

### 4.1 静态检查

```text
python -m lwt --check docs/agent-eval/submissions/each-snapshot-alias/program.lwt
```

- stdout: `Check passed: 1 source file(s).\n`
- stderr: 空
- 退出码: 0

### 4.2 正式运行（stdin 关闭，无 `--` 参数）

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/program.lwt
```

- stdout repr: `'iterations 3\nb.value 9\nb == alias true\n'`（39 字节）
- stdout 逐行：`iterations 3` / `b.value 9` / `b == alias true`
- stderr repr: `''`（0 字节）
- 退出码: 0

### 4.3 附加自测（临时脚本，运行后已删除）

为把「循环执行了几次」与「快照遍历了几次」分开核验，临时写了一个只输出 `iterations` 和 `values` 的脚本 `.scratch.lwt`，运行后立即删除：

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/.scratch.lwt
```

- stdout repr: `'3\n[1, 2, 3, 99, 99, 99]\n'`
- stderr: 空
- 退出码: 0

结论：`push` 在原数组上确实执行了 3 次（`values` 由 3 个元素变为 6 个），而 `each` 仍只遍历进入时的 3 个元素，符合规范 §5 的浅快照规则。record 别名的两项断言由正式程序的 `b.value 9` 与 `b == alias true` 直接覆盖。

## 5. 失败与修订

- 运行失败次数：0（`--check` 与正式运行首次即通过）。
- 程序修订次数：0（`program.lwt` 自首次写入后未改动）。
- 未遇到词法/语法/运行时诊断，stderr 始终为空。

## 6. 隔离声明

- 只阅读了允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目内容或任何期望输出；未联网。
- 未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 解释执行只经 `python -m lwt` 公开入口；未使用其他语言生成程序输出，也未用其他语言改写程序。
- 全部写入均限于 `docs/agent-eval/submissions/each-snapshot-alias/`；过程中的临时 stdout/stderr 捕获文件与 `.scratch.lwt` 已删除，目录内仅保留 `program.lwt` 与 `report.md`。
