# snapshot.lwt 盲测报告（each 浅快照 + record 别名）

## 1. 依据的文档与小节

| 依据 | 用到的条款 |
|---|---|
| `docs/language-spec.md` §5（作用域、函数与控制流） | “`each (item in expr)` 先求 `expr`，必须得到数组；进入循环时复制其**元素引用序列**作为浅快照……循环中追加或替换原数组元素不改变尚待遍历的快照”；`continue` 亦“不重建快照，也不纳入循环中新追加的数组元素” |
| `docs/language-spec.md` §4.1 / §4.3 | 数组与记录是**按引用传递的可变对象**，赋值与传参不复制对象；`push(array, value)` 原地追加、返回 `null`，别名可见修改 |
| `docs/language-spec.md` §4.2 | `==` 对数组/记录只按**对象身份**比较同一对象时为真（本题两变量指向同一实例故为 `true`） |
| `docs/language-spec.md` §4.3（显示） | `str(value)` 与 `emit` 同规则：`true` 显示为 `true`，整数为十进制 |
| `docs/language-spec.md` §2.1 / §3 | 分号必需；`record Name { f };` 为顶层声明，`Name{f: v}` 构造；变量名可与预置函数名 `values`（`§6` 列表）同名，语法位置决定查找（§5），故局部变量 `values` 合法 |
| `docs/developer-guide.md` §1、§2（数组、record 和 `each`） | 运行入口为 `python -m lwt SOURCE`；“`each` 开始时保存数组元素引用序列的浅快照；本轮向原数组追加或替换元素不会改变这份快照”；`push` 原地追加 |
| `.agents/skills/lwt-app/SKILL.md` 工作流 5–7 | 先 `--check` 再真实 CLI 运行；只记录真实运行的命令与结果 |

## 2. 程序要点

`docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt`

- `let values = [1, 2, 3];`，`iterations = 0`；循环体 `each (v in values)` 内先 `iterations = iterations + 1;` 再 `push(values, 99);`。若 `each` 不取快照而是实时长度遍历，会无限增长；实测只迭代 3 次，证明进入循环时取浅快照。
- `record Box { value };`，`let b = Box{value: 1};`，`let alias = b;`（引用别名，未复制），`alias.value = 9;` 后 `b.value` 为 9，`b == alias` 为 `true`（同一对象身份）。
- 不读取 `args()`、不调用 `input()`，不接收参数与 stdin；仅 3 行 `emit`。

## 3. 命令与实测结果

### 3.1 静态检查（同一公开 CLI 的非执行入口，仅辅助）

```text
python -m lwt --check docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```
stdout：`Check passed: 1 source file(s).\n`，stderr 空，退出码 0。该步不执行任何 LWT 语句，语义结论均以下方真实执行为准。

### 3.2 真实执行（唯一判定依据）

工作目录：仓库根目录 `lwt-s48-T-each-snapshot-alias-s5`

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```

- 退出码：`0`
- stdout repr（二进制逐字节）：`b'iterations 3\nb.value 9\nb == alias true\n'`
- 可读 stdout：

```text
iterations 3
b.value 9
b == alias true
```

- stderr repr：`b''`（空）
- 未提供 stdin、未提供 `--` 程序实参；程序不含任何输入调用。

题目要求的三项对齐：`iterations 3`（快照下恰 3 次迭代）；`b.value 9`（别名写入可见）；`b == alias true`（身份相等）。

## 4. 失败与修订次数

- 失败次数：0
- 修订次数：0（首版即通过静态检查与真实 CLI 执行，stdout/stderr/退出码一次命中预期）
- 未遇词法/语法/运行时错误，未使用 `attempt/recover` 掩盖错误。

## 5. 隔离声明

- 仅阅读 `TASK.md` 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录、任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅用 `python -m lwt` 公开入口运行，未用其他语言生成或改写输出；`str()`/`emit` 全部由解释器产生。
- 仅写入 `docs/agent-eval/submissions/each-snapshot-alias/` 下的 `snapshot.lwt` 与本 `report.md`（临时重定向文件 `out.txt`/`err.txt` 已删除，未留在仓库内）。
