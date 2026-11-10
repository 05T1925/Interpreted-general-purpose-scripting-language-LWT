# freq.lwt 盲测报告

## 1. 任务与依据

题目：从 stdin 逐行读入（每行若干以单个空格分隔的单词）统计词频，按次数降序、同次数按单词升序输出前 3 行，格式 `word count`；无输入输出 `EMPTY`；`input()` 读到 EOF 结束；不接收命令行参数。

依据文档只有 `docs/language-spec.md`（C 组消融）。用到的条目：

- §2.1 词法：`#` 注释、字符串仅四种转义、标识符规则。
- §3 语法：`let`/`while`/`when`-`otherwise`/`each`/`emit` 形式，`f(...)` 调用，分号必需。
- §4.2 比较：`< <= > >=` 对两个字符串按 Unicode 码点逐位比较；`and`/`or` 左操作数必须为布尔且短路。
- §4.3 显示：`emit` 输出字符串不带引号，`str(int)` 为十进制。
- §4.4 映射：`dict{k: v}`、`d[k]` 读取/赋值（缺键读取报错、赋值追加）、`keys(d)` 按插入顺序、键必须为整数或字符串、`has(d, k)` 判存。
- §5 作用域：块每轮新建作用域（`while` 体每轮新作用域），因此循环体内 `let` 合法；`each` 先求数组并做元素引用浅快照。
- §6 预置：`input()` 返回行或 EOF 的 `null`（剥除行尾 LF 及其前 CR）、`split(text, sep)` 保留空字段、`len`、`str`、`has`、`keys`；stdout 只承载 `emit`，诊断走 stderr。
- §7 退出码：成功 0；本程序不触发运行期错误。

## 2. 程序

`docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`（首版即通过，未修订）。

结构：

1. `counts = dict{}`，逐行 `input()`，`null` 结束；空行跳过；`split(line, " ")` 后跳过空字段（空行或连续空格不产生“空单词”），用 `has` 判断后 `counts[w] = counts[w] + 1` 或置 1。
2. `keys(counts)` 取数组，插入排序：主键次数降序，次键单词升序（`counts[a] < counts[b] or (相等 and a > b)` 时后移）。
3. `n == 0` 时 `emit "EMPTY"`；否则输出 `min(n, 3)` 行 `words[k] + " " + str(counts[words[k]])`。

设计取舍：题目只保证“单个空格分隔的单词”，故把空行与连续空格产生的空字段视为非单词（不计入 `""` 键），这使空输入与全空行输入都得到 `EMPTY`，且不产生形如 ` 1` 的行。

## 3. 运行命令与结果

统一形式（工作目录为题目根目录，`F=docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`）：

```
printf '<stdin>' | python -m lwt $F
```

全部用例 stderr 为空、退出码 0。stdout repr 如下：

| # | stdin（printf 字面量） | stdout repr | stderr | 退出码 |
|---|---|---|---|---:|
| 1 | `''`（空输入） | `'EMPTY\n'` | 空 | 0 |
| 2 | `'a b a\nb c a\n'` | `'a 3\nb 2\nc 1\n'` | 空 | 0 |
| 3 | `'b a c a b d\n'`（同次数升序） | `'a 2\nb 2\nc 1\n'` | 空 | 0 |
| 4 | `'中文 中文 ab Ab\n'`（Unicode/大小写） | `'中文 2\nAb 1\nab 1\n'` | 空 | 0 |
| 5 | `'x\n'`（单词） | `'x 1\n'` | 空 | 0 |
| 6 | `'e e e d d c\n'`（降序截断） | `'e 3\nd 2\nc 1\n'` | 空 | 0 |
| 7 | `'a a b'`（末行无 LF） | `'a 2\nb 1\n'` | 空 | 0 |
| 8 | `'\n\na b\n'`（空行） | `'a 1\nb 1\n'` | 空 | 0 |
| 9 | `'a b\r\na\r\n'`（CRLF） | `'a 2\nb 1\n'` | 空 | 0 |
| 10 | `'a b \n'`（行尾空格） | `'a 1\nb 1\n'` | 空 | 0 |
| 11 | `'x1 x1 !ok !ok !ok\n'`（含标点/数字） | `'!ok 3\nx1 2\n'` | 空 | 0 |
| 12 | `'d c b a\n'`（第 3 名并列截断） | `'a 1\nb 1\nc 1\n'` | 空 | 0 |
| 13 | `'abc ab abd\n'`（前缀词升序） | `'ab 1\nabc 1\nabd 1\n'` | 空 | 0 |
| 14 | `'f e d c b a\n'`（全逆序） | `'a 1\nb 1\nc 1\n'` | 空 | 0 |
| 15 | `'a d b c f e a d b c a d b a d a\n'`（多档计数） | `'a 5\nd 4\nb 3\n'` | 空 | 0 |
| 16 | `'   \na\n'`（纯空格行） | `'a 1\n'` | 空 | 0 |
| 17 | 60 行循环生成的 `apple/banana/cherry/date/elder/fig` 流 | `'banana 40\ncherry 40\napple 30\n'` | 空 | 0 |

用例 17 的生成命令（仅生成输入，不参与计算）：

```
{ for i in $(seq 1 30); do echo 'apple banana cherry'; done
  for i in $(seq 1 10); do echo 'banana cherry date'; done
  for i in $(seq 1 8); do echo 'date elder'; done
  for i in $(seq 1 5); do echo 'elder fig'; done; } | python -m lwt $F
```

期望值核对：apple 30、banana 40、cherry 40、date 18、elder 13、fig 5；前 3 名为 banana/cherry 并列 40（按单词升序），第 3 名 apple 30，与输出一致。

repr 仅用于报告呈现：`printf ... | python -m lwt $F | python -c "import sys;print(repr(sys.stdin.buffer.read().decode('utf-8')))"`，该管道末段只做读取与格式化，不参与产生程序输出。

## 4. 失败与修订

- 运行用例：17 个，全部通过（stdout、stderr、退出码三项均符合预期）。
- 失败次数：0。
- 修订次数：0（首版 `freq.lwt` 一次写成，未改代码；仅新增本报告）。
- 未触发的分支：`attempt`/`throw`、模块、并发、`args()` 均未使用；程序不读命令行参数。

## 5. 隔离声明

- 只阅读了 `TASK.md` 与允许的 `docs/language-spec.md`（含其中指向的章节内容）；未读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`，未联网。
- 只通过公开入口 `python -m lwt <file>` 运行；未用其他语言生成或改写程序输出（Python 仅在自测管道中读取 stdout 并打印 repr）。
- 只写入 `docs/agent-eval/submissions/dict-word-frequency-topk/` 下的 `freq.lwt` 与 `report.md`；未创建临时文件。
