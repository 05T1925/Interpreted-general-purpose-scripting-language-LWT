# freq.lwt 盲测报告

## 1. 任务与产物

- 题目：从 stdin 逐行读取（每行若干以单个空格分隔的单词），统计词频，按次数降序、同次数按单词升序输出前 3 行，格式 `word count`；无输入输出 `EMPTY`；用 `input()` 读到 EOF；不接收命令行参数。
- 产物：
  - `docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`（程序）
  - `docs/agent-eval/submissions/dict-word-frequency-topk/report.md`（本报告）

## 2. 依据的文档与小节

| 文档 | 小节 | 用途 |
|---|---|---|
| `docs/language-spec.md` | §2.1（UTF-8、字符串仅四种转义）、§3（`while`/`each`/`when`/`otherwise`/`break` 文法与上下文约束） | 语法合法性；`break` 仅在循环体内 |
| 同上 | §4.2（`<`/`>` 对字符串按码点比较；`and`/`or` 两侧必须是布尔、短路） | 排序比较与循环条件 |
| 同上 | §4.4（`dict{}`、键为整数或字符串、插入顺序、`d[k]` 缺键报错） | 词频计数容器 |
| 同上 | §5（顶层语句顺序执行、块作用域、`each` 浅快照、`while` 每轮新作用域） | 读循环与数组重排 |
| 同上 | §6（`input()` 剥 LF 及其前一 CR、EOF 为 `null`；`split` 保留空字段；`keys`/`get`/`put`/`len`/`str`；`emit` 一行一 LF） | 全部 I/O 与内建能力 |
| 同上 | §7（退出码 0/2/3/4 与诊断分流：stdout 只放 `emit`） | 核对自测证据 |
| `docs/developer-guide.md` | §1（`python -m lwt SOURCE`、`--check`、stdin 语义、退出码表）、§2–3（值/变量/循环/内建函数速查） | 运行方式与语义速查 |
| `.agents/skills/lwt-app/SKILL.md` | 工作流程 1–7、语言边界、S42 dict 要点 | 先读规范再写码、先 `--check` 后公开 CLI、只记录真实运行 |
| `docs/concurrency.md` | 全文（本次未使用） | 确认本题为纯串行 I/O 任务，不需要 `spawn`/通道；`input()` 在任务内非法，故单任务读取 stdin |

## 3. 实现要点

1. 计数：`counts = dict{}`；逐行 `input()` 到 `null` 结束；每行 `split(line, " ")`，跳过空字段（空行或多余空格产生的 `""`），`put(counts, w, get(counts, w, 0) + 1)`。
2. 排序：`keys(counts)` 取插入顺序键数组，对键做**插入排序**：`counts[prev] < counts[cur]` 时前移；次数相等时用 `prev > cur`（字符串按码点比较）保证同次数单词升序。
3. 输出：无键时 `emit "EMPTY";`；否则 `while (k < len(order) and k < 3)` 逐行 `emit order[k] + " " + str(counts[order[k]]);`。
4. 不使用 `args()`，不读写文件，单任务串行，无并发原语。

## 4. 自测命令与结果

所有命令在仓库根 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-dict-word-frequency-topk-s5` 运行，程序路径记为 `$F = docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`；stdout 用 `| cat -A` 观察行尾（`$` = LF），stderr 单独重定向后以 Python 读出 repr。

### 4.1 静态检查

```text
$ python -m lwt --check $F
Check passed: 1 source file(s).
exit=0
```

### 4.2 运行用例（stdin 用 `printf` 提供）

| # | 输入（stdin） | 命令 | stdout repr | stderr | 退出码 |
|---|---|---|---|---|---|
| 1 | `a b a c b a\nd e\n` | `printf 'a b a c b a\nd e\n' \| python -m lwt $F` | `'a 3\nb 2\nc 1\n'` | `''` | 0 |
| 2 | 空（EOF 立即到达） | `printf '' \| python -m lwt $F` | `'EMPTY\n'` | `''` | 0 |
| 3 | `b a b a c c\n` | 同上形式 | `'a 2\nb 2\nc 2\n'` | `''` | 0 |
| 4 | `x x y\n` | 同上形式 | `'x 2\ny 1\n'` | `''` | 0 |
| 5 | `one two two`（末行无 LF） | 同上形式 | `'two 2\none 1\n'` | `''` | 0 |
| 6 | `z z z z y y y x x w\n` | 同上形式 | `'z 4\ny 3\nx 2\n'` | `''` | 0 |
| 7 | `a b\r\nb\r\n`（CRLF） | 同上形式 | `'b 2\na 1\n'` | `''` | 0 |
| 8 | `a\n\nb\n`（含空行） | 同上形式 | `'a 1\nb 1\n'` | `''` | 0 |
| 9 | `\n\n`（仅空行） | 同上形式 | `'EMPTY\n'` | `''` | 0 |
| 10 | `ab a ab a abc\n`（前缀并列） | 同上形式 | `'a 2\nab 2\nabc 1\n'` | `''` | 0 |
| 11 | `d a\nd b\nd c\nd b\nc b`（逆序插入） | 同上形式 | `'d 4\nb 3\nc 2\n'` | `''` | 0 |
| 12 | `m\nm\nm\nm\na\na\na\nz\n`（后段大计数） | 同上形式 | `'m 4\na 3\nz 1\n'` | `''` | 0 |
| 13 | `中文 中文 词语\n`（UTF-8 词） | 同上形式 | `'中文 2\n词语 1\n'` | `''` | 0 |

逐条核对点：用例 1/6/11 覆盖“次数降序 + 截断 3 行”；用例 3/10 覆盖“同次数按单词升序”（含 `a`/`ab`/`abc` 前缀比较）；用例 4/5/2/9 覆盖不足 3 个键与空输入；用例 7 覆盖 `input()` 的 CRLF 剥离；用例 8 覆盖空行产生的空字段不被计为单词；用例 13 确认非 ASCII 单词原样输出。

### 4.3 stderr 实测

对用例 `p q p q r r s\n` 单独捕获 stderr 并读 repr：

```text
python -c "print(repr(open(<stderr文件>, encoding='utf-8', newline='').read()))"
''
```

即成功路径 stderr 为空、stdout 仅含 `emit` 的行（`'p 2\nq 2\nr 2\n'`，exit=0）。

## 5. 失败与修订次数

- 程序文件版本：**1 版**；`freq.lwt` 首次 `--check` 即通过，13 个运行用例一次性全部符合预期，**运行期失败 0 次、程序修订 0 次**。
- 唯一的执行障碍来自测试命令本身：最初用 `> /tmp/o1.txt` 重定向，Windows 原生 Python 解析不到 Git Bash 的 `/tmp`，读回时报 `FileNotFoundError`。改用管道 + `cat -A`/单独 stderr 文件后重跑，与被测程序无关，未修改 `freq.lwt`。

## 6. 隔离声明

- 仅阅读了 TASK.md 允许的四份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/concurrency.md`；未打开 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出，未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只用公开入口 `python -m lwt`（及 `--check`）运行；未用其他语言生成期望输出或改写程序（Python 仅用于打印 stderr 文件的 `repr`）。
- 写入范围仅 `docs/agent-eval/submissions/dict-word-frequency-topk/` 下的 `freq.lwt` 与 `report.md`；自测期间在该目录临时写过一个 stderr 文件并已删除，未在别处留文件。
