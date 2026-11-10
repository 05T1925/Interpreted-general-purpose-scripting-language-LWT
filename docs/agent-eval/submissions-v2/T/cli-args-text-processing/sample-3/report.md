# wordcount.lwt 盲测报告

## 1. 产物

| 文件 | 说明 |
|---|---|
| `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt` | 提交程序 |
| `docs/agent-eval/submissions/cli-args-text-processing/fixtures/*.txt` | 自测输入夹具（basic / no_trailing_newline / empty / blank_lines / crlf / whitespace_only / utf8_cn） |
| `docs/agent-eval/submissions/cli-args-text-processing/report.md` | 本报告 |

## 2. 依据文档与小节

- `docs/language-spec.md`
  - §2.1 源文件与字符串字面量（UTF-8、`\n` 转义规则）；
  - §3 语法（`fn`、`each`、`when/otherwise`、`return`、`emit`、`split`/`trim` 等按 `IDENT "(" ... ")"` 调用）；
  - §4.2 运算（`+` 仅整数相加或字符串拼接，`str(value)` 显式转换为字符串；无隐式转换）；
  - §4.3 数组、索引与 `str` 显示规则；
  - §5 作用域与函数（顶层 `fn` 先登记、可前向调用；`each` 建立循环作用域；块内 `let` 遮蔽规则）；
  - §6 预置能力表：`args()`（仅 `--` 之后实参）、`read_text(path)`（UTF-8、剥除开头 BOM、CRLF/CR 规范化为 LF）、`split(text, separator)`（保留空字段）、`trim(text)`（只裁剪两端 ASCII 空白）、`str(value)`、`emit`；
  - §7 诊断与退出码（成功 0；运行时错误 3；不得出现 traceback）；
  - §8.3 规范示例（`args()[0]` + `read_text` + `split(..., "\n")` 的标准写法）。
- `docs/developer-guide.md`
  - §1 CLI 形式 `python -m lwt SOURCE [-- ARGS...]`，`--` 后参数才属于程序，`python -m lwt` 为唯一公开入口；
  - §1「退出码和诊断」表与「先 `--check`，再按程序需要提供 `--` 参数以公开执行 CLI 核对真实行为」的工作流；
  - §2「文本和参数」（`read_text` 相对进程工作目录、`args()` 用法）；
  - §3 语义速查（`split` 保留空字段、`trim` 仅 ASCII 空白、`str` 格式）。
- `.agents/skills/lwt-app/SKILL.md`
  - 「工作流程」第 1、3、5、6、7 条（先读指南/规范，只用已支持能力，先 `--check` 再公开 CLI，核对 stdout/stderr/退出码，只记录真实运行结果）。

## 3. 实现要点

```lwt
fn count_lines_and_words(lines) {
    let line_count = 0;
    let word_count = 0;
    each (line in lines) {
        let body = trim(line);
        when (body != "") {
            line_count = line_count + 1;
            each (part in split(body, " ")) {
                when (part != "") { word_count = word_count + 1; }
            }
        }
    }
    return [line_count, word_count];
}

let content = read_text(args()[0]);
let totals = count_lines_and_words(split(content, "\n"));
emit "lines " + str(totals[0]) + " words " + str(totals[1]);
```

- 行切分：`split(read_text(...), "\n")`。`read_text` 已把 CRLF/CR 规范为 LF，故 CRLF 文件与 LF 文件计数一致；文件末尾无换行时最后一段是真实内容而非空段，末尾有换行时多出的空尾段由「非空行」判定自然排除。
- 非空行判定：`trim(line) != ""`，即剔除只含 ASCII 空白（空格/TAB/CR/LF/VT/FF）的行；空文件 `split("", "\n")` 得到 `[""]` 也被排除，因此 `lines 0 words 0`。
- 单词计数：在非空行内 `split(body, " ")` 后只统计非空片段，从而对连续多空格稳健；按题目约定「单词以单个空格分隔」，不做其他分隔符推断。未使用 `input()`，程序完全不读 stdin。

## 4. 真实 CLI 记录

工作目录：仓库根目录（`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-cli-args-text-processing-s3`）。
简写 `P=docs/agent-eval/submissions/cli-args-text-processing`。

### 4.1 静态检查

命令：

```text
python -m lwt --check docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt
```

stdout repr：`'Check passed: 1 source file(s).\n'`；stderr：空；退出码：0。

### 4.2 自测用例

| # | 夹具内容（说明） | 命令 | stdout repr | stderr | 退出码 | 预期 |
|---|---|---|---|---|---|---:|---|
| 1 | `alpha beta gamma\ndelta epsilon\n` | `python -m lwt P/wordcount.lwt -- P/fixtures/basic.txt` | `'lines 2 words 5\n'` | 空 | 0 | lines 2 words 5 |
| 2 | `one two\nthree`（**末尾无换行**） | `python -m lwt P/wordcount.lwt -- P/fixtures/no_trailing_newline.txt` | `'lines 2 words 3\n'` | 空 | 0 | lines 2 words 3 |
| 3 | 空文件（0 字节） | `python -m lwt P/wordcount.lwt -- P/fixtures/empty.txt` | `'lines 0 words 0\n'` | 空 | 0 | lines 0 words 0 |
| 4 | `\n\nalpha\n\n beta gamma \n`（空行与两端空白） | `python -m lwt P/wordcount.lwt -- P/fixtures/blank_lines.txt` | `'lines 2 words 3\n'` | 空 | 0 | lines 2 words 3 |
| 5 | `a b\r\nc\r\nd\r\n`（CRLF） | `python -m lwt P/wordcount.lwt -- P/fixtures/crlf.txt` | `'lines 3 words 4\n'` | 空 | 0 | lines 3 words 4 |
| 6 | `   \n\t\n`（纯空白行） | `python -m lwt P/wordcount.lwt -- P/fixtures/whitespace_only.txt` | `'lines 0 words 0\n'` | 空 | 0 | lines 0 words 0 |
| 7 | `第一行 两个词\n第二行`（UTF-8 中文，末尾无换行） | `python -m lwt P/wordcount.lwt -- P/fixtures/utf8_cn.txt` | `'lines 2 words 3\n'` | 空 | 0 | lines 2 words 3 |
| 8 | 不读 stdin 验证：`printf 'ignored stdin line\nsecond\n' \| python -m lwt P/wordcount.lwt -- P/fixtures/basic.txt` | 同左 | `'lines 2 words 5\n'` | 空 | 0 | 与用例 1 完全一致 |

用例 8 的 stdin 内容未影响输出，说明程序只经 `args()[0]` + `read_text` 取输入。

### 4.3 失败与修订次数

- 程序版本：v1（一次写成），`--check` 与全部 8 次运行均第一次通过。
- 失败次数：0；修订次数：0。未出现词法/语法/运行时诊断，未出现 Python traceback。

## 5. 隔离声明

1. 仅阅读 TASK.md 允许的三份文档（`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`）及 TASK.md 本身；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
2. 未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
3. 运行只用 `python -m lwt <file> [-- args]` 与 `python -m lwt --check <file>` 公开入口；未用其他语言生成程序输出或改写程序（`printf`/`od` 仅用于构造夹具与查看字节）。
4. 写入范围仅限 `docs/agent-eval/submissions/cli-args-text-processing/` 下的 `wordcount.lwt`、`fixtures/*.txt` 与 `report.md`。
