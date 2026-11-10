# wordcount.lwt 盲测报告

## 1. 题目与依据

题目：读取 `args()[0]` 指定的文本文件（`read_text`），统计非空行数与非空行中的单词总数（单词以单个空格分隔），输出 `lines <L> words <W>`；`python -m lwt wordcount.lwt -- <path>` 调用；文件末尾无换行也必须正确；不读 stdin。

只依据 `docs/language-spec.md`（C 组消融：仅语言规范），对应小节：

| 规范位置 | 本文用到的约束 |
|---|---|
| §6 命令形式段 | 第一个 `--` 之后全部实参原样属于程序实参；源文件路径不入 `args()`；stdout 只承载 `emit`，诊断走 stderr |
| §6 `args()` 行 | 无参数，返回新的字符串数组，只含 `--` 后的程序实参 |
| §6 `read_text(path)` 行 | 返回全文；UTF-8，剥除开头一个 BOM，CRLF/CR 规范化为 LF；失败为运行时错误（码 3），位置在调用处 |
| §6 `split(text, separator)` 行 | 保留首尾及连续分隔产生的空字段，`split("", ",")` 为 `[""]`；这决定了末尾换行会多出一个空字段，必须过滤 |
| §6 `trim(text)` 行 | 只删两端 ASCII 空白（空格、TAB、LF、CR、VT、FF） |
| §6 `len(x)` 行 | 字符串按 Unicode 码点计数 |
| §6 `str(value)` 行 | 整数显示为十进制，字符串原样 |
| §4.3 | `emit value;` 把显示字符串后接一个 LF 写到 stdout；顶层字符串不加引号 |
| §4.2 | `+` 对两个字符串拼接，无隐式转换 |
| §5 `each` 段 | `each` 遍历数组元素，空数组零次；块内可嵌套块/分支/循环 |
| §3 | 语句必须以分号结尾；`let`、`each`、`when`、`emit` 的语法；调用结果可索引（`args()[0]`） |
| §7 | 成功退出码 0，未捕获运行时错误退出码 3，诊断格式 `<source>:<line>:<column>: <类别>: <消息>` |

## 2. 实现要点

```lwt
let text = read_text(args()[0]);
let line_count = 0;
let word_count = 0;

each (raw_line in split(text, "\n")) {
    let line = trim(raw_line);
    when (len(line) > 0) {
        line_count = line_count + 1;
        each (token in split(line, " ")) {
            when (len(token) > 0) {
                word_count = word_count + 1;
            }
        }
    }
}

emit "lines " + str(line_count) + " words " + str(word_count);
```

- 末尾换行：`split(text, "\n")` 在末尾换行后会产生一个空字段，被 `trim` 后长度 0，不计行、不计词；末尾无换行则不产生该字段，两种写法得到同一计数（§6 `split` 行）。
- 空文件：`read_text` 返回 `""`，`split("", "\n")` 为 `[""]`，结果为 `lines 0 words 0`。
- 非空行判定：先 `trim`，`len > 0` 才计行；纯空白行（如只含 TAB/空格）视为空行。单词侧同样跳过空 token，使得行首/行尾空格不会额外计词。对题目约定的"单词以单个空格分隔"的输入，这与直接取 `len(split(line, " "))` 等价；差异只出现在违背该约定的空白上，属实现选择，记录于此。
- CRLF 已被 `read_text` 规范化为 LF（§6），无需额外处理 `\r`。
- 不调用 `input()`，不触碰 stdin；只由 `args()` 取路径，故程序实参之外的 stdin 内容不参与。

## 3. 真实 CLI 测试（全部使用 `python -m lwt` 公开入口）

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-cli-args-text-processing-s4`
令 `S=docs/agent-eval/submissions/cli-args-text-processing`，统一命令：

```text
python -m lwt $S/wordcount.lwt -- $S/<fixture>.txt
```

stdout 用 `od -An -c` 与 `wc -c` 核对字节，stderr 单独重定向统计。`<内容>` 中的 `\n`/`\r\n` 为真实换行。

| # | 输入文件内容 | 期望 | stdout repr | stderr | 退出码 |
|---|---|---|---|---|---|
| 1 | `hello world\nsecond line here\n` | 2 行 5 词 | `"lines 2 words 5\n"` | `""` | 0 |
| 2 | `a b c\n\nlast line`（末尾无换行） | 2 行 5 词 | `"lines 2 words 5\n"` | `""` | 0 |
| 3 | 空文件（0 字节） | 0 行 0 词 | `"lines 0 words 0\n"` | `""` | 0 |
| 4 | `alpha\r\nbeta gamma\r\n`（CRLF） | 2 行 3 词 | `"lines 2 words 3\n"` | `""` | 0 |
| 5 | `  spaced   out  \n\t\n\nword` | 2 行 3 词 | `"lines 2 words 3\n"` | `""` | 0 |
| 6 | `single`（单行无换行） | 1 行 1 词 | `"lines 1 words 1\n"` | `""` | 0 |
| 7 | `\n\n\n`（仅空行） | 0 行 0 词 | `"lines 0 words 0\n"` | `""` | 0 |
| 8 | `one two three\nfour five\n\n\nsix` | 3 行 6 词 | `"lines 3 words 6\n"` | `""` | 0 |
| 9 | 路径含空格：`alpha beta\n` | 1 行 2 词 | `"lines 1 words 2\n"` | `""` | 0 |
| 10 | 用例 1 且 stdin 管道注入 `ignored input line\n` | 与用例 1 相同 | `"lines 2 words 5\n"` | `""` | 0 |

用例 1 的字节级核对：`od -An -c` 输出 `l i n e s 2 w o r d s 5 \n`，`wc -c` 为 16，stdout 只有一行且以单个 LF 结束，无额外空白。

最终冒烟（内容 `alpha beta\ngamma\n\ndelta epsilon zeta`，无末尾换行）：stdout `"lines 3 words 6\n"`（16 字节），stderr 0 字节，退出码 0。

## 4. 负向自测（非题目要求，用于确认契约）

| 场景 | stdout repr | stderr | 退出码 |
|---|---|---|---|
| 不给程序实参（`python -m lwt $S/wordcount.lwt`） | `""` | `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt:5:28: RuntimeError: array index is out of range\n` | 3 |
| 路径不存在（`-- $S/_nope.txt`） | `""` | `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt:5:12: RuntimeError: could not read text file\n` | 3 |

两条诊断均符合 §7 的 `source:line:column: 类别: 消息` 格式，无 Python traceback，stdout 不混入诊断。

## 5. 失败与修订次数

- 失败运行：0 次。上表 10 个正向用例与 2 个负向用例均在首次执行时得到预期 stdout/stderr/退出码。
- 程序修订：0 次。`wordcount.lwt` 自首次写入后内容未改动。
- 未使用 Python、Shell 或其他语言生成、改写或"代办"程序输出；仅用 `od`/`wc`/重定向观察真实 CLI 的字节结果。

## 6. 隔离声明

- 只阅读了 `docs/language-spec.md` 的正文；未打开 `docs/` 下其他文档、`lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、任何其他题目目录或任何期望输出。目录列举仅用于定位规范文件与确认提交目录。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只用公开入口 `python -m lwt <file> [-- args...]` 运行程序，未调用解释器内部 API、未用其他语言执行或生成输出。
- 只在本目录 `docs/agent-eval/submissions/cli-args-text-processing/` 下写入文件；测试用 fixture 与临时 stdout/stderr 均创建在该目录内并已删除，最终仅保留 `wordcount.lwt` 与本报告。
