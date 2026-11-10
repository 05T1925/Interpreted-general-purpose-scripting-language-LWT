# 盲测报告：snapshot.lwt（each 浅快照 + 记录别名）

## 1. 交付物

- `snapshot.lwt`：本目录下的 LWT 程序。

## 2. 依据文档与小节

只阅读了 `docs/language-spec.md`（C 组：仅语言规范），未读实现源码、测试、其他题目或期望输出。

| 语义点 | 规范依据 |
|---|---|
| `each (item in expr)` 进入循环时复制**元素引用序列**作为浅快照；循环中追加元素不改变尚待遍历的快照 | §3（`each_stmt` 文法）、§5 第 145 段 |
| `push(array, value)` 原地追加、返回 `null`，别名可观察修改 | §4.3、§6 预置能力表 |
| 整数 `+` 求和、`str(value)` 返回可显示字符串（`true` 显示为 `true`） | §4.2、§4.3、§6 |
| `record Name { f };` 声明与 `Name{f: v}` 构造；字段访问/赋值；记录按引用传递，`==` 为身份相等 | §4.1、§4.3、§4.2 |
| `emit` 输出显示字符串并接一个 LF；成功不额外输出，诊断才写 stderr | §4.3、§6 |

程序未调用 `args()` 或 `input()`，不接收参数与 stdin（题目要求）。

## 3. 程序要点

- `let values = [1, 2, 3];` 后 `each (v in values) { push(values, 99); iterations = iterations + 1; }`：若遍历的是活动数组，循环将不会终止；实际只迭代 3 次，证明遍历的是进入循环时的浅快照。
- `Box{value: 1}` → `alias = b` → `alias.value = 9`：记录按引用传递，`b.value` 与 `b == alias` 均反映同一对象。

## 4. 运行命令与结果

命令（工作目录为本题目录）：

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```

- stdout repr：`'iterations 3\nb.value 9\nb == alias true\n'`
- stderr repr：`''`（空）
- 退出码：`0`

可读形式：

```text
iterations 3
b.value 9
b == alias true
```

## 5. 与题目要求的对照

| 要求 | 实际输出 | 结论 |
|---|---|---|
| 数组 `[1, 2, 3]`，循环体内 `push(values, 99)` | 循环仅迭代 3 次 | 符合 |
| 统计迭代次数并输出 `iterations 3` | `iterations 3` | 符合 |
| `record Box {value};` 实例 `b`，`alias = b`，`alias.value = 9` | `b.value 9` | 符合 |
| 输出 `b == alias true` | `b == alias true` | 符合 |
| 不接收参数与 stdin | 未使用 `args()`/`input()`；以 `/dev/null` 作 stdin 运行 | 符合 |

## 6. 失败与修订次数

- 首次运行即得到预期输出，失败 0 次、修订 0 次。程序未做任何修改后重跑，结果一致。

## 7. 隔离声明

- 仅阅读 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅使用公开入口 `python -m lwt <file>` 运行；未使用其他语言生成输出或改写程序。
- 仅写入本目录 `docs/agent-eval/submissions/each-snapshot-alias/` 下的 `snapshot.lwt` 与本 `report.md`。
