# wordcount 盲测提交报告（cli-args-text-processing）

## 1. 交付物

| 项目 | 值 |
|---|---|
| LWT 源码（相对仓库根） | `docs/agent-eval/submissions/cli-args-text-processing/program.lwt` |
| 自测夹具目录 | `docs/agent-eval/submissions/cli-args-text-processing/fixtures/` |
| 运行方式 | `python -m lwt <program.lwt> -- <path>`，工作目录为仓库根 |
| 失败尝试 / 修订次数 | 失败 0 次，修订 0 次（首版即通过全部用例） |

## 2. 依据的文档与具体小节

| 文档 | 使用的小节 | 用到的结论 |
|---|---|---|
| `docs/language-spec.md` | §2.1 编码、位置和空白 | `#` 起注释；分号必需；字符串只支持 `\\ \" \n \t` 四种转义，故源码中写 `"\n"` 表示换行 |
| 同上 | §3 语法（EBNF） | 顶层 `fn`、`let`、`when/otherwise`、`each`、`emit`、`return`、`fail(...)` 作为 `expr_stmt` 的语句形式；`when` 条件必须带括号且为布尔 |
| 同上 | §4.2 运算与比较 | `+` 只接受两整数或两字符串，**无隐式类型转换**，因此整数必须经 `str()` 才能拼接；`!=` 对字符串按值比较 |
| 同上 | §4.3 数组、记录和显示 | `emit` 追加一个 LF；顶层字符串不带引号显示 |
| 同上 | §5 作用域、函数与控制流 | 顶层 `fn` 在执行前一次性登记（可前向调用）；函数调用新作用域、`let` 不可重声明；块每次进入新建作用域（`each` 体内 `let text` 每轮合法）；`each` 遍历进入时的元素浅快照 |
| 同上 | §6 预置能力与 CLI 表 | `args()` 只含 `--` 之后实参、不含源路径、每次返回新数组；`read_text(path)` 返回全文、**剥除开头一个 BOM 并把 CRLF/CR 规范化为 LF**、相对路径按进程 cwd 解析；`split(text, sep)` 保留首尾与连续分隔产生的空字段、`split("", ",")` 为 `[""]`；`trim` 只裁两端 ASCII 空白；`to_int` 严格；`len` 按码点；`fail(message)` 产生运行时错误 |
| 同上 | §6 命令形式段 | 命令为 `python -m lwt <source> [-- <args>...]`；`--` 之后原样属于 `args()`；stdout 只承载 `emit`，诊断走 stderr |
| 同上 | §7 错误、退出码 | 成功 0；`RuntimeError`（含 `read_text` 失败、`fail`）为 3；源码诊断格式 `<path>:<line>:<col>: <类别>: <消息>` |
| `docs/developer-guide.md` | §1「先运行」→「CLI、参数和输入」 | `python -m lwt SOURCE -- ARGS`；`args()` 不含源文件名与 `--`；`read_text` 相对路径按**进程 cwd**、去 BOM、CRLF→LF |
| 同上 | §1「退出码和诊断」 | 退出码 0/2/3/4 含义；stderr 不含 Python traceback |
| 同上 | §3「内置函数与输出」表 | `args`/`read_text`/`len`/`split`/`trim`/`str`/`fail` 的边界；`emit` 是语句；参数类型错误属运行时错误 3 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」1、3、5、6 条 | 先读指南与规范、只用已支持能力、先静态检查再公开 CLI、核对 stdout/stderr/退出码；「语言边界」确认不得使用浮点/类/闭包等未列入规范的能力 |

## 3. 程序要点（实现决策与依据）

1. **读文件**：`read_text(args()[0])`，不调用 `input()`，故完全不消费 stdin（规范 §6 表；指南 §1）。
2. **切行**：`split(content, "\n")`。`read_text` 已把 CRLF/CR 规范化成 LF（规范 §6 表），因此行尾不会残留 `\r`。文件以换行结尾时 `split` 多出的末尾空字段被「空行」判定过滤，不会多算一行；**文件末尾无换行时不会产生多余元素**，同样正确（规范 §6 `split` 语义 + 实测用例 2、11）。
3. **非空行判定**：`trim(line) != ""`。`trim` 只裁两端 ASCII 空白（空格、TAB、LF、CR、VT、FF），因此纯空格/纯 TAB 行按空行处理，行内字符不受影响（规范 §6 `trim` 行）。
4. **单词计数**：先 `trim`，再 `split(text, " ")`，逐字段统计 `part != ""` 的个数。题目约定「单词以单个空格分隔」，正常输入下与直接取 `len(split(...))` 等价；跳过空字段只为让连续空格不产生伪单词（不改变规范行为）。
5. **输出**：`emit "lines " + str(line_total) + " words " + str(word_total);`。`+` 不接受混合类型（规范 §4.2），故两处整数显式 `str()`；`emit` 自带行尾 LF（§4.3）。
6. **缺参**：`args()` 为空时用 `fail("wordcount: missing file path argument")` 报运行时错误（退出码 3），而不是去读 stdin（规范 §6 `fail`、§7）。这是唯一的显式输入校验。

## 4. 真实运行记录

所有命令的工作目录均为仓库根 `C:/Users/28641/AppData/Local/Temp/lwt-s47-blind-cli-args-text-processing`。为排版简洁，下表中 `$SUB` 表示 `docs/agent-eval/submissions/cli-args-text-processing`（**实际命令中输入的是完整字面路径，未使用 shell 变量**）。stdout 一律用 Python `repr` 形式给出。

### 4.1 成功用例

| # | 命令（源与实参） | 夹具内容（字节要点） | stdout（repr） | stderr | 退出码 |
|---|---|---|---|---|---|
| 1 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/basic.txt` | `alpha beta gamma\ndelta epsilon\n\nzeta\n` | `'lines 3 words 6\n'` | `''` | 0 |
| 2 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/no_final_newline.txt` | `hello world\nfoo`（**末尾无换行**） | `'lines 2 words 3\n'` | `''` | 0 |
| 3 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/empty.txt` | 0 字节 | `'lines 0 words 0\n'` | `''` | 0 |
| 4 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/only_newlines.txt` | `\n\n\n` | `'lines 0 words 0\n'` | `''` | 0 |
| 5 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/crlf.txt` | `one two\r\nthree\r\n` | `'lines 2 words 3\n'` | `''` | 0 |
| 6 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/extra_spaces.txt` | `a  b\n   \n c \n\n` | `'lines 2 words 3\n'` | `''` | 0 |
| 7 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/unicode.txt` | `中文 词\nhello 世界\n` | `'lines 2 words 4\n'` | `''` | 0 |
| 8 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/bom.txt` | `EF BB BF` + `one two\nthree\n` | `'lines 2 words 3\n'` | `''` | 0 |
| 9 | `python -m lwt $SUB/program.lwt -- "$SUB/fixtures/with space.txt"` | `solo line`（无换行，文件名含空格） | `'lines 1 words 2\n'` | `''` | 0 |
| 10 | `python -m lwt $SUB/program.lwt -- "C:/Users/28641/AppData/Local/Temp/lwt-s47-blind-cli-args-text-processing/$SUB/fixtures/basic.txt"` | 同 #1，传**绝对路径** | `'lines 3 words 6\n'` | `''` | 0 |
| 11 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/two_trailing_lf.txt` | `a b\n\n`（两个末尾 LF） | `'lines 1 words 2\n'` | `''` | 0 |
| 12 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/tab_line.txt` | `a\n\t\nb\n`（中间为纯 TAB 行） | `'lines 2 words 2\n'` | `''` | 0 |

### 4.2 不读 stdin 的验证

| # | 命令 | stdout（repr） | stderr | 退出码 |
|---|---|---|---|---|
| 13 | `printf 'zzz zzz zzz\n' \| python -m lwt $SUB/program.lwt -- $SUB/fixtures/no_final_newline.txt` | `'lines 2 words 3\n'` | `''` | 0 |

注入的 stdin 为 `zzz zzz zzz\n`，输出与 #2 完全一致，证明计数只来自 `read_text(args()[0])`，程序不读标准输入。

### 4.3 stdout/stderr 字节级核对

| # | 命令 | 实测字节（`od -c`） |
|---|---|---|
| 14 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/basic.txt 2>/dev/null \| od -c` | `0000000   l i n e s   3   w o r d s   6  \n` / `0000020` |
| 15 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/basic.txt 2>&1 >/dev/null \| od -c` | 无输出（stderr 长度 0） |

即 stdout 恰为 `b'lines 3 words 6\n'`（14 字节，单个 LF 结尾，无 CR、无多余空白），stderr 为空。

### 4.4 错误路径（不影响主判定，用于确认无 traceback 泄漏）

| # | 命令 | stdout（repr） | stderr（原文） | 退出码 |
|---|---|---|---|---|
| 16 | `python -m lwt $SUB/program.lwt -- $SUB/fixtures/nope.txt` | `''` | `docs/agent-eval/submissions/cli-args-text-processing/program.lwt:22:15: RuntimeError: could not read text file` | 3 |
| 17 | `python -m lwt $SUB/program.lwt --` | `''` | `docs/agent-eval/submissions/cli-args-text-processing/program.lwt:18:5: RuntimeError: wordcount: missing file path argument` | 3 |
| 18 | `python -m lwt $SUB/program.lwt`（无 `--`，零实参） | `''` | `docs/agent-eval/submissions/cli-args-text-processing/program.lwt:18:5: RuntimeError: wordcount: missing file path argument` | 3 |

诊断格式符合规范 §7（`<源路径>:<行>:<列>: <类别>: <消息>`，LF 结尾，无 Python traceback）；`read_text` 失败按规范 §6 表为运行时错误 3，而非文件层 4——与规范「`read_text` 读取的文件出错仍是运行时错误（码 3）」一致。

### 4.5 期望值来源（人工核算，未借任何期望输出文件）

- #1：非空行 3 条（`alpha beta gamma`、`delta epsilon`、`zeta`），单词 3+2+1=6。
- #2：非空行 2 条，单词 2+1=3；文件末无 LF 未导致漏行或多行。
- #4：三行全空，按空行过滤，故 0 行 0 词（`split("\n\n\n","\n")` 得 4 个空字段，全被跳过）。
- #5：CRLF 已被 `read_text` 规范化为 LF，若未规范化则 `three\r` 仍算 1 词但行尾会带 `\r`；结果 2 行 3 词与规范化一致。
- #6：`a  b` → 2 词，`   ` → 空行跳过，` c ` → 1 词，空行跳过 ⇒ 2 行 3 词。
- #7：`中文 词` 2 词、`hello 世界` 2 词 ⇒ 2 行 4 词（`len` 按码点，`split` 按分隔符，与字节数无关）。
- #8：BOM 被 `read_text` 剥除，故首行首词为 `one` 而非含 BOM 的伪词。
- #11：`split("a b\n\n","\n")` → `["a b","",""]`，只有 1 条非空行。
- #12：纯 TAB 行被 `trim` 裁成空串而跳过。

## 5. 合规声明

- **只读过**以下三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- **未读**任何禁止路径或文件：未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径。目录列举只用 `ls` 查看了 `docs/`、`.agents/skills/lwt-app/` 与本次提交目录（`docs/` 的 `ls` 仅暴露文件名，未打开非白名单文档）。
- **运行入口**：只使用 `python -m lwt <file> -- <args>` 公开入口执行 LWT 程序；未用 `--check`/`--profile`/调试器等其他子入口。
- **未用其他语言生成输出或改写程序**：`program.lwt` 全部为手写 LWT 源码；夹具用 `printf` 写入固定字节；比对只用 `od -c` 观察真实 stdout 字节，未用 Python/其他语言计算或伪造任何期望输出。
- **写盘范围**：所有持久文件均在 `docs/agent-eval/submissions/cli-args-text-processing/` 下（`program.lwt`、`report.md`、`fixtures/*.txt`）。需说明一处过程瑕疵：最初一次字节核对曾把 stdout/stderr 重定向到系统临时目录的 `/tmp/wc_out.txt`、`/tmp/wc_err.txt`，随即删除并改为管道（见 #14、#15），仓库其他位置无任何写入。

## 6. 失败尝试与修订

| 轮次 | 现象 | 处理 |
|---|---|---|
| 第 1 版（唯一版本） | 全部 12 个成功用例、stdin 独立性、3 个错误路径均一次通过 | 无需修订；修订次数 0，失败运行 0 次 |

未出现词法/语法/运行时错误（除刻意构造的 #16–#18 错误路径），故无「失败—修订」循环可记录。
