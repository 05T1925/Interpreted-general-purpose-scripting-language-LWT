# 盲测报告：wordcount.lwt（CLI 参数与文本处理）

## 1. 依据文档与小节

唯一阅读的规范文档：`docs/language-spec.md`（LWT 0.3.0）。

| 用到的语义 | 依据章节 |
|---|---|
| `args()` 只返回 `--` 之后的程序实参，不含源路径；每次返回新数组 | §6（预置能力表 `args`）、§6 命令形式段 |
| `read_text(path)` 读全文、UTF-8、剥除开头一个 BOM、CRLF/CR 规范化为 LF；相对路径以进程 cwd 为基准；失败为运行时错误（码 3） | §6、§7 |
| `split(text, sep)` 保留首尾与连续分隔产生的空字段；`split("", ",")` 为 `[""]` | §6 |
| `trim` 只删两端 ASCII 空白（空格、TAB、LF、CR、VT、FF），内部字符不变 | §6 |
| `len` 对字符串按 Unicode 码点计数 | §6 |
| `str` + `+` 字符串拼接、`emit` 输出一个值并以 LF 结尾、stdout 只承载 `emit`、诊断走 stderr | §4.2、§4.3、§6 |
| `each` 遍历数组（进入时浅快照）、`when/otherwise`、`let` 作用域与重新赋值 | §5、§4.1 |
| `#` 注释到行尾；源文件 UTF-8 | §2.1 |
| 运行时错误格式 `<path>:<line>:<col>: RuntimeError: <msg>`、退出码 0/2/3/4 | §7 |
| 官方示例 `read_text(args()[0])` + `split(..., "\n")` 的调用形式 | §8.3 |

## 2. 程序与关键决策

程序：`wordcount.lwt`（与本报告同目录），单文件、仅顶层语句，调用形式
`python -m lwt wordcount.lwt -- <path>`（cwd = 仓库根目录，源路径按 §6 相对 cwd 解析）。

```
let argv = args();
let text = read_text(argv[0]);
let parts = split(text, "\n");
...
each (line in parts) {
    let content = trim(line);
    when (content != "") {
        line_count = line_count + 1;
        word_count = word_count + len(split(content, " "));
    }
}
emit "lines " + str(line_count) + " words " + str(word_count);
```

边界决策（均由规范推导，非猜测）：

1. **末尾换行**：`read_text` 已把 CRLF/CR 归一为 LF（§6），故统一按 `"\n"` 切分。文件以 LF 结尾时 `split` 会多出一个末尾空字段（§6 明确保留空字段），该字段 `trim` 后为 `""`，按“非空行”规则自然被跳过；文件末尾**无换行**时最后一行是真实内容，照常计数。因此 `"a\nb\n"` 与 `"a\nb"` 都得 2 行，满足题目“文件末尾无换行也必须正确计数”，无需额外的去尾特判。
2. **空行判定**：`trim(line) == ""` 即视为空行（包含仅由 ASCII 空白组成的行），不计行也不计词。这与“非空行”的自然语义一致，且不改变正常文本的计数。
3. **词数**：对非空行内容按**单个空格**切分，`len(split(content, " "))` 即词数；题目已约定“单词以单个空格分隔”，故不再过滤空字段（连续空格属题面约定之外的输入，会按单空格字面切分产生空字段）。用 `trim` 后的内容切分，使行首/行尾多余空白不会虚增词数。
4. **不读 stdin**：程序只使用 `args()` 与 `read_text`；实测 stdin 为空（`< /dev/null`）与 stdin 有数据时输出完全一致。
5. **不做隐式转换**：整数与字符串拼接需显式 `str(...)`（§4.2 `+` 只接受两整数或两字符串）。

## 3. 实测（真实 CLI）

运行环境：Windows 11，Python 3.13.14；cwd 固定为仓库根目录；命令均为
`python -m lwt docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt -- <fixture>`。
`stdout repr` 由捕获后按字节核对（`od -c`）得到，stderr 为空时记为 `""`。

| # | 夹具（字节内容） | 人工预期 | stdout repr | stderr | exit |
|---|---|---|---|---|---|
| 1 | `basic.txt`：`apple banana\n\ncherry pie\n` | 2 行 / 4 词 | `'lines 2 words 4\n'` | `""` | 0 |
| 2 | `nonl.txt`：`one two\nthree four five`（**末尾无换行**） | 2 / 5 | `'lines 2 words 5\n'` | `""` | 0 |
| 3 | `single.txt`：`only`（单行无换行） | 1 / 1 | `'lines 1 words 1\n'` | `""` | 0 |
| 4 | `empty.txt`：0 字节 | 0 / 0 | `'lines 0 words 0\n'` | `""` | 0 |
| 5 | `blanks.txt`：`\n\n\n` | 0 / 0 | `'lines 0 words 0\n'` | `""` | 0 |
| 6 | `onelf.txt`：`\n` | 0 / 0 | `'lines 0 words 0\n'` | `""` | 0 |
| 7 | `spaced.txt`：`alpha\n   \nbeta gamma\n`（中间行仅空格） | 2 / 3 | `'lines 2 words 3\n'` | `""` | 0 |
| 8 | `unicode.txt`：`你好 世界\nsecond line\n` | 2 / 4 | `'lines 2 words 4\n'` | `""` | 0 |
| 9 | `trailing.txt`：`a\n\n` | 1 / 1 | `'lines 1 words 1\n'` | `""` | 0 |
| 10 | `crlf.txt`：`alpha beta\r\ngamma\r\n` | 2 / 3 | `'lines 2 words 3\n'` | `""` | 0 |
| 11 | `tail spaces.txt`：`a b\n   `（末行仅空格、无换行） | 1 / 2 | `'lines 1 words 2\n'` | `""` | 0 |
| 12 | `带 空格.txt`：`x\ny z\n`（路径含空格与中文） | 2 / 3 | `'lines 2 words 3\n'` | `""` | 0 |
| 13 | `many.txt`：500 行（250 行 `a b c` 与 250 空行交替） | 250 / 750 | `'lines 250 words 750\n'` | `""` | 0 |
| 14 | 不存在的路径 `fixtures/nope.txt` | 运行时错误 3 | `''` | `wordcount.lwt:7:12: RuntimeError: could not read text file\n` | 3 |
| 15 | 无程序实参（不写 `-- <path>`） | 运行时错误 3 | `''` | `wordcount.lwt:7:26: RuntimeError: array index is out of range\n` | 3 |
| 16 | 同 #1 但 `< /dev/null`（stdin 为空） | 与 #1 相同 | `'lines 2 words 4\n'` | `""` | 0 |
| 17 | 同 #1 但 stdin 为 `x y z\n` | 与 #1 相同 | `'lines 2 words 4\n'` | `""` | 0 |

补充说明：

- #14 的错误位置 `7:12` 指向 `read_text` 调用名，#15 的 `7:26` 指向 `argv[0]` 索引，与 §7“指向调用名/访问符”的规定一致；`read_text` 失败属运行时错误（码 3），与 CLI/源文件错误（码 4）区分正确（§6、§7）。
- #16/#17 证明程序不依赖 stdin：stdin 有无数据不影响结果。
- 夹具均在提交目录 `fixtures/` 下，可用同样命令复现；文件字节已用 `od -c` 核对（末尾换行/CRLF/空格行均按上表所列写入）。

## 4. 失败与修订次数

- 程序 `wordcount.lwt`：**一次写成，0 次修订**。
- 功能失败：**0 次**（上表 17 项全部符合预期；无一次输出不符）。
- 测试数据调整：1 次。最初 `unicode.txt` 误写成 `second  line`（两个空格），该输入超出题目“单词以单个空格分隔”的约定，输出为 5 词；为让证据表只覆盖题面约定内的输入，将其改为单空格后重测（#8 得 4 词）。此调整不涉及程序改动。
- 调用方式纠正：1 次。最初从提交目录内运行 `python -m lwt`，因该目录不含 `lwt` 包而得到 `No module named lwt`（退出码 1）；改为从仓库根目录运行后全部测试正常。这是运行目录问题，不是程序问题。

## 5. 隔离声明

1. 只阅读了 `TASK.md` 与允许的 `docs/language-spec.md`；未打开或读取 `lwt/` 任何源码文件、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。唯一涉及 `lwt/` 的操作是 `ls lwt | head -5` 列出顶层文件名以确认包存在，未读取文件内容。
2. 所有运行均通过公开入口 `python -m lwt <file> -- <args>`；未用其他语言生成或改写程序输出（`od -c` / `wc -l` / `awk` 仅用于核对输出字节与生成测试输入，未参与计算答案）；未使用 `--check`、`--profile` 等入口。
3. 所有写入均限于 `docs/agent-eval/submissions/cli-args-text-processing/`（程序、本报告、`fixtures/` 测试夹具）；临时 `.out`/`.err` 捕获文件已在核对后删除。
