# freq.lwt 盲测报告（C 组：仅语言规范）

## 1. 任务与提交物

- 题目：从 stdin 逐行读取（每行若干以单个空格分隔的单词），统计词频，按次数降序、同次数按单词升序输出前 3 行，每行 `word count`；无输入输出 `EMPTY`；stdin 用 `input()` 读取，EOF 结束；不接收命令行参数。
- 提交文件：`docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`（本目录）。
- 运行方式：`python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`（stdin 提供数据）。

## 2. 依据文档与小节

只使用 `docs/language-spec.md`：

- §2.1 词法：`#` 注释、字符串字面量、标识符与保留字规则（`dict` 为保留字，`put/get/keys/len/split/str` 为预置名）。
- §3 语法：`while`、`each (x in arr)`、`when/otherwise`、`let`、`emit`、赋值与 `dict{...}` 字面量、`f(...)` 调用形式。
- §4.1 求值次序：赋值先验证目标再求右侧；`let` 初始化成功后才创建绑定。
- §4.2 比较：`<` 对两个字符串按 Unicode 码点逐位比较、前缀短者小；`==`/`!=` 对所有值有定义（字符串与 `null` 类型不同即不等）；`and` 要求布尔且短路。
- §4.4 映射：`dict{}` 构造、插入顺序、`d[k]` 读（缺键报错）、`d[k] = v` 写、键须为整数或字符串、`put/get/has/keys` 能力。
- §5 作用域与控制流：`when`/`while` 条件必须为布尔；块每次进入新建作用域，块内赋值修改最近可见绑定；`each` 遍历进入时的浅快照；`let` 不可重复声明同名绑定。
- §6 预置能力：`input()`（返回一行或 EOF 时 `null`）、`split(text, sep)`、`len`、`get(d, k, default)`、`put(d, k, v)`、`keys(d)`、`str`；CLI 形如 `python -m lwt <source-path>`。
- §7 诊断与退出码：成功为 0，诊断写 stderr、不混入 stdout。

## 3. 算法说明

1. `let counts = dict{};`，`while (line != null)` 循环 `input()` 读行。
2. 跳过空行；`split(line, " ")` 逐词处理（并跳过空字段，作为对多余空格的额外健壮性处理，规范输入不会产生该情况）。
3. 计数用 `put(counts, w, get(counts, w, 0) + 1)`：`get` 的缺省值 0 省去存在性分支，`put` 对已有键原位更新、不改插入序。
4. `names = keys(counts)`，`n = len(names)`；`n == 0` 时 `emit "EMPTY";`。
5. 否则做**部分选择排序**：只进行 `limit = min(3, n)` 轮；每轮在剩余区间扫描，`cj > cb` 取更大次数，`cj == cb` 且 `names[j] < names[best]` 取更小单词（§4.2 码点比较），交换到第 `i` 位。复杂度 O(3n) 次比较与 O(1) 额外空间（键数组原地改）。
6. `emit names[k] + " " + str(counts[names[k]]);` 输出至多 3 行；`emit` 自带 LF，故格式恰为 `word count` 且单空格。

## 4. 自测记录（真实 CLI）

命令统一为：

```text
python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt
```

stdin 由 shell `printf`/`seq` 构造；预期值全部人工推导（未用其他语言生成答案）。每次运行 stderr 均为空串 `''`，退出码均为 0。

| # | stdin（转义表示） | 手算预期 | 实际 stdout repr | 退出码 |
|---|---|---|---|---|
| T1 | `''`（立即 EOF） | `EMPTY` | `'EMPTY\n'` | 0 |
| T2 | `'apple banana apple cherry banana apple\ncherry date date\n'` | apple 3，banana/cherry/date 各 2，取 banana、cherry | `'apple 3\nbanana 2\ncherry 2\n'` | 0 |
| T3 | `'a a a b b\nc d d e e e\n'` | a 3、e 3、b 2、d 2、c 1 | `'a 3\ne 3\nb 2\n'` | 0 |
| T4 | `'x y x'`（末行无 LF） | x 2、y 1 | `'x 2\ny 1\n'` | 0 |
| T5 | `'solo\nsolo\n'` | 仅 1 种词，输出 1 行 | `'solo 2\n'` | 0 |
| T6 | `'P p a B\n'` | 4 词各 1；码点序 `B(66) < P(80) < a(97) < p(112)` | `'B 1\nP 1\na 1\n'` | 0 |
| T7 | `'\n\n'`（仅空行） | 无词 → EMPTY | `'EMPTY\n'` | 0 |
| T8 | 200 个不同词 `w001`…`w200`，各 1 次 | 升序前三 | `'w001 1\nw002 1\nw003 1\n'` | 0 |
| T9 | 500 个不同词 `k001`…`k500`，各 2 次 | 升序前三 | `'k001 2\nk002 2\nk003 2\n'` | 0 |
| T10 | `'z z z z z y x\n'` | z 5、x 1、y 1（并列按升序） | `'z 5\nx 1\ny 1\n'` | 0 |
| T11 | `'你好 世界 你好\n'` | 你好 2、世界 1 | `'你好 2\n世界 1\n'` | 0 |
| T12 | `'1 2 1\n'` | `1` 2 次、`2` 1 次（词字符串排序） | `'1 2\n2 1\n'` | 0 |
| T13 | 2000 个不同词 `m0001`…`m2000`，各 3 次 | 升序前三 | `'m0001 3\nm0002 3\nm0003 3\n'` | 0 |

耗时（`time` 内建，仅作规模参考）：T8 约 0.86 s，T9 约 1.13 s，T13 约 1.04 s（含解释器启动）。

## 5. 失败与修订

- 失败次数：0。上述 13 组用例首轮（修订前版本）与回归（修订后版本）均通过，无错误输出、无非零退出码。
- 修订次数：1。首版对全部键做完整选择排序（O(n²)）；为在大词表下减少比较，改为只选前 `min(3, n)` 名的部分选择排序（O(3n)），输出结果不变。修改后 T1–T13 全部重跑通过。
- 其他设计取舍：空行不计数；空字段（多余空格）跳过；`input()` 的 EOF 以 `null` 判定（§6）。

## 6. 隔离声明

- 仅阅读 `TASK.md` 与允许文档 `docs/language-spec.md`；另外只做了 `docs/`、`docs/agent-eval/submissions/` 的目录列举以确认写路径，未打开任何其他文档内容。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、任何其他题目目录或任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只用公开入口 `python -m lwt <file>` 运行；未使用其他语言生成或改写程序输出（测试输入由 shell `printf`/`seq` 构造，预期值手工推导）。
- 仅在本目录 `docs/agent-eval/submissions/dict-word-frequency-topk/` 下创建 `freq.lwt` 与本报告。
