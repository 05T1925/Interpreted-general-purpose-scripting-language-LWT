# wordcount.lwt 盲测提交报告

## 1. 产物

| 路径（相对本目录） | 说明 |
|---|---|
| `wordcount.lwt` | 题目要求的程序（唯一源码文件） |
| `fixtures/*.txt` | 自测输入文本，均为手写小文件，仅用于复现本报告命令 |
| `report.md` | 本报告 |

运行方式：`python -m lwt wordcount.lwt -- <path>`（进程工作目录为仓库根
`/tmp/lwt-s48-C-cli-args-text-processing-s1`，路径按规范 §6 相对进程 cwd 解析）。

## 2. 依据的文档与小节

C 组仅允许阅读 `docs/language-spec.md`，本程序全部语义依据均来自该规范：

| 用到的事实 | 出处 |
|---|---|
| `args()` 无参数，返回**仅含 `--` 之后实参**的新字符串数组，不含源文件名与分隔符 | §6 预置能力表 `args()` 行；§6 命令形式段 |
| `read_text(path)` 读全文，UTF-8，剥除开头一个 BOM，CRLF/CR 规范化为 LF；读取失败是运行时错误（码 3），位置为调用处 | §6 `read_text` 行 |
| `split(text, separator)` 从左到右按最早非重叠匹配切分，**保留首尾及连续分隔符产生的空字段**；`split("", ",")` 为 `[""]` | §6 `split` 行 |
| `trim(text)` 只删两端 ASCII 空白（空格 TAB LF CR VT FF） | §6 `trim` 行 |
| `len` 按 Unicode 码点计字符串长度（本程序未使用，仅作排除项记录） | §6 `len` 行 |
| `each (x in expr)` 先求 expr 且必须是数组，按元素顺序迭代 | §5 循环段；§3 EBNF `each_stmt` |
| 块每次进入新建作用域，`let` 不可在同一作用域重声明；块内赋值修改最近可见绑定 | §5 |
| 顶层语句按源码顺序执行；`fn`/`record` 先登记 | §5 |
| `str(value)` 返回可显示字符串；`emit value;` 输出该字符串并追加一个 LF；stdout 只承载 `emit` | §4.3；§6 首段 |
| 整数 `+` 只接受两个整数、字符串 `+` 只做拼接，无隐式转换 | §4.2 |
| 运行时错误退出码 3，诊断格式 `<source-path>:<line>:<column>: <类别>: <消息>` 写 stderr | §7 |
| 调用结果仍可索引（`args()[0]` 合法）；索引须为整数且在范围内，否则运行时错误 | §3 表达式段；§4.3 |

题目要求本身（输出 `lines <L> words <W>`、只统计非空行、单词以单个空格分隔、
文件末尾无换行也必须正确、不读 stdin）来自 `TASK.md`。

## 3. 实现要点

```lwt
let path = args()[0];
let text = read_text(path);
let all_lines = split(text, "\n");
...
each (line in all_lines) {
    let content = trim(line);
    when (content != "") { ... }
}
```

1. **末尾无换行**：`split(text, "\n")` 在有尾随 LF 时会多出一个空字段，该字段正好
   对应「末尾换行之后并不存在的行」，被非空判定丢弃；无尾随 LF 时最后一行仍有内容字段。
   两种情况都只按实际有内容的行计数，无需额外分支。
2. **空文件**：`split("", "\n")` 依 §6 为 `[""]`，唯一字段为空 → `lines 0 words 0`。
3. **非空行判定**：用 `trim(line) != ""`，即仅含空白（空格/TAB/CR 残留）的行算空行。
4. **单词计数**：在非空行上 `split(content, " ")`，再丢弃空字段，因此
   连续空格不会虚增词数；TAB 不作为分隔符（题目为「单个空格分隔」，与 §6 `split`
   的严格语义一致）。
5. **不读 stdin**：程序不调用 `input()`。
6. 未使用 `attempt/recover`、模块、并发等无关能力，也不依赖任何未在规范中出现的语义。

## 4. 自测命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-cli-args-text-processing-s1`
`SUB=docs/agent-eval/submissions/cli-args-text-processing`

统一命令形式：

```
python -m lwt "$SUB/wordcount.lwt" -- "$SUB/fixtures/<name>.txt"
```

| 用例 | 文件字节内容（od/printf 实际写入） | 期望 | stdout（repr） | stderr | 退出码 |
|---|---|---|---|---:|---:|
| basic | `alpha beta\ngamma\n\ndelta epsilon zeta\n` | 3 行 6 词 | `'lines 3 words 6\n'` | `''` | 0 |
| nonl | `one two\nthree`（**末尾无换行**） | 2 行 3 词 | `'lines 2 words 3\n'` | `''` | 0 |
| empty | 0 字节 | 0 行 0 词 | `'lines 0 words 0\n'` | `''` | 0 |
| blanks | `"   \n\n\t\n"` | 0 行 0 词 | `'lines 0 words 0\n'` | `''` | 0 |
| crlf | `a b\r\nc\r\n` | 2 行 3 词（CRLF 归一） | `'lines 2 words 3\n'` | `''` | 0 |
| multispace | `a  b\n c \n` | 2 行 3 词（连续空格不虚增，见下注） | `'lines 2 words 3\n'` | `''` | 0 |
| bom | `EF BB BF` + `hi there\n` | 1 行 2 词（BOM 剥除） | `'lines 1 words 2\n'` | `''` | 0 |
| single | `hello`（无换行） | 1 行 1 词 | `'lines 1 words 1\n'` | `''` | 0 |
| onlynl | `\n` | 0 行 0 词 | `'lines 0 words 0\n'` | `''` | 0 |
| trailing | `a\n\n\n` | 1 行 1 词 | `'lines 1 words 1\n'` | `''` | 0 |
| mixed | `the quick brown fox\n\njumps over\tthe lazy dog\n   \nlast line` | 3 行 10 词 | `'lines 3 words 10\n'` | `''` | 0 |
| unicode | `中文 测试 行\n第二 行\n` | 2 行 5 词 | `'lines 2 words 5\n'` | `''` | 0 |

注（multispace）：`a  b` 为 `a`、空、`b` 三段，丢弃空段后计入 2 词；` c ` 先被
`trim` 成 `c` 计入 1 词，合计 3 词。若按「按空格切分后含空段全部计数」将是 5 词，
本实现选择丢弃空段，与「单词以单个空格分隔」的意图一致，并已在此显式记录。

负路径（错误契约）自测：

| 命令 | stdout | stderr | 退出码 |
|---|---|---|---:|
| `python -m lwt "$SUB/wordcount.lwt" --`（无程序实参） | `''` | `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt:12:18: RuntimeError: array index is out of range\n` | 3 |
| `python -m lwt "$SUB/wordcount.lwt" -- "$SUB/fixtures/no_such_file.txt"` | `''` | `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt:13:12: RuntimeError: could not read text file\n` | 3 |

两条诊断都符合 §7 的 `<source-path>:<line>:<column>: <类别>: <消息>` 形式，
无 Python traceback，位置分别落在 `args()[0]` 的索引符与 `read_text(...)` 调用名上。

stdin 隔离自测：以 `input="SHOULD NOT BE READ\n"` 运行 basic.txt，
stdout 仍为 `'lines 3 words 6\n'`、stderr `''`、退出码 0，证明程序不读取 stdin。

静态检查（同为 `python -m lwt` 公开入口的开发者子命令，仅用于自查，非语言语义）：
`python -m lwt --check "$SUB/wordcount.lwt"` → stdout `'Check passed: 1 source file(s).\n'`，
stderr `''`，退出码 0。

## 5. 失败与修订次数

- 编写前按 §6 预置函数边界先推演了尾随换行、空文件、BOM、CRLF 四个边界，首版即通过。
- **失败次数：0**（12 个功能用例 + 2 个错误路径 + 1 个 stdin 隔离 + 1 个 `--check` 全部一次通过）。
- **修订次数：0**（`wordcount.lwt` 自写盘后未被修改；无迭代式改错记录）。
- 唯一一次「表述调整」是把测试夹具目录 `_tmp/` 重命名为 `fixtures/`，不涉及程序改动，
  重命名后 12 个用例全部复跑并记录于上表。

## 6. 隔离声明

1. 全程只读取了 `TASK.md` 与 `docs/language-spec.md`；未读 `lwt/` 源码、`tests/`、`app/`、
   `reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；
   未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
2. 程序只用 `python -m lwt <file> -- <args>` 公开入口运行；未用其他语言生成程序输出，
   未用其他语言改写或「代跑」程序。报告中的表格仅是对上述 CLI 调用 stdout/stderr 的
   转写（`repr`）与退出码记录；Python 子进程脚本只负责发起调用并捕获管道，不参与计算。
3. 只写入了 `docs/agent-eval/submissions/cli-args-text-processing/` 下的
   `wordcount.lwt`、`report.md` 与 `fixtures/*.txt`，未改动仓库其他任何文件。
   补充说明：开工时该子目录在磁盘上是空的（`ls -la` 仅见 `.` 与 `..`）；事后 `git status`
   显示索引里另有更早的文件记录（如 `program.lwt`、其他夹具名），这些条目在我动手前就已不在
   工作区，我既未读取其内容，也未删除或恢复它们。本提交的全部内容即上列三个路径。
