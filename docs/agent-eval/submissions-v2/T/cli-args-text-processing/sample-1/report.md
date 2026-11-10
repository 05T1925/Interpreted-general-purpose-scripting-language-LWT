# wordcount.lwt 盲测提交报告

## 1. 交付物与脚本相对路径

- 程序：`docs/agent-eval/submissions/cli-args-text-processing/program.lwt`
- 报告：`docs/agent-eval/submissions/cli-args-text-processing/report.md`

题目文字称程序为 `wordcount.lwt`，交付清单要求文件名 `program.lwt`，故以 `program.lwt` 交付；程序内容与文件名无关，可用任意名调用。

程序逻辑（源文本）：

```lwt
# wordcount.lwt: count non-empty lines and words in the file named by args()[0].
let path = args()[0];
let text = read_text(path);
let all_lines = split(text, "\n");
let line_count = 0;
let word_count = 0;
each (line in all_lines) {
    let body = trim(line);
    when (body != "") {
        line_count = line_count + 1;
        let fields = split(body, " ");
        each (field in fields) {
            when (field != "") {
                word_count = word_count + 1;
            }
        }
    }
}
emit "lines " + str(line_count) + " words " + str(word_count);
```

## 2. 依据的文档与具体小节

| 依据 | 用到的结论 |
|---|---|
| `docs/language-spec.md` §3 语法（`atom`、`postfix`、`each_stmt`、`when_stmt`、`emit_stmt`） | `args()[0]` 合法（"调用结果仍可索引"）；`each (x in expr) { }`、`when (...) { }`、`emit expr;` 均为标准语句；块后不写分号，简单语句必须写分号 |
| §5 作用域与函数 | 顶层 `let` 绑定可被块内赋值修改（"块内赋值修改最近可见绑定"）；每次进入块创建新作用域，故循环体内 `let` 不冲突 |
| §4.1 值与求值次序 / §4.2 运算 | `+` 只接受"两个整数"或"两个字符串"，因此计数用 `str(int)` 显式转字符串后拼接，不做隐式转换；`!=` 对字符串按值比较，与 `""` 比较合法 |
| §6 预置能力表（`args`、`read_text`、`split`、`trim`、`str`） | `args()` 只含 `--` 之后的实参且不含源文件名；`read_text(path)` 相对路径以**进程当前工作目录**为基准，UTF-8、剥除开头一个 BOM、CRLF/CR 规范化为 LF，失败为运行时错误（码 3）；`split(text, sep)` 保留首尾及连续分隔产生的空字段，`split("", ",")` 为 `[""]`；`trim` 只删两端 ASCII 空白 |
| §6 CLI 命令形式 + §7 退出码 | `python -m lwt <source> [-- <args>...]`；源路径不入 `args()`；成功 0，运行时错误 3，CLI/源文件错误 4；stdout 只承载 `emit` 输出，诊断走 stderr |
| §8.3 示例 | 确认 `read_text(args()[0])` + `split(..., "\n")` 是规范给出的文本处理写法（示例中 `"a\nb"` 切出 2 段） |
| `docs/developer-guide.md` §1「CLI、参数和输入」、§2「文本和参数」、§3 内置函数表 | `args()` / `read_text` 路径以 cwd 为基准、BOM 与 CRLF 处理；`split` 保留空字段；函数实参先求值再检查 → 与 §2 依据一致 |
| `.agents/skills/lwt-app/SKILL.md`「工作流程」第 5–6 条 | 先 `python -m lwt --check`，再用公开 CLI 传 `--` 实参跑真实用例并核对 stdout/stderr/退出码 |

### 关键设计决定（文档未直接规定处）

1. **空行判定**：题目要求"非空行"。实现用 `trim(line) != ""` 判定，即只含空白的行不计入非空行（也不贡献单词）。理由：`trim` 只裁剪 ASCII 空白，与"空白行不是有效文本行"的常识一致；纯空串判定会把只含空格的残行算作有词行数为 0 的"非空行"，两种口径只在含空白行时不同，此处选择语义更自洽的一种。
2. **单词切分**：`split(line, " ")` 后跳过空字段（`field != ""`），等价于把"单个或连续多个空格"都视作分隔、忽略行首行尾空格；符合题面"单词以单个空格分隔"，且不会把连续空格误计成单词。
3. **末尾无换行**：`read_text` 不做行切分，`split(text, "\n")` 对 `"a b\nc"` 返回 `["a b", "c"]`，因此末行无 LF 也按一行计；对 `"...\n"` 则多出一个空字段，被空行规则滤掉，不会多计一行。
4. **不读 stdin**：程序只调用 `args()` 与 `read_text`，未使用 `input()`；已用管道喂入 stdin 做过对照（见 §4 第 8 条）。

## 3. 运行环境

- 平台：Windows 11，Python 3.13.14
- 所有命令的工作目录为本仓库根目录 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-cli-args-text-processing-s1`
- 测试夹具均位于 `docs/agent-eval/submissions/cli-args-text-processing/tmp/`（仅用于自测，交付前已删除）

夹具内容（repr）：

| 夹具 | 内容 repr | 期望 |
|---|---|---|
| `basic.txt` | `'hello world\n\nfoo bar baz\n'` | lines 2 words 5 |
| `nonl.txt` | `'a b\nc'`（末尾无换行） | lines 2 words 3 |
| `empty.txt` | `''` | lines 0 words 0 |
| `blank.txt` | `'\n\n   \n'` | lines 0 words 0 |
| `crlf.txt` | `'alpha\r\nbeta gamma\r\n'` | lines 2 words 3 |
| `multispace.txt` | `'a  b\nc d'` | lines 2 words 4 |
| `ignored.txt` | `'x y z\n'` | lines 1 words 3 |

## 4. 每条运行命令与结果

以下 stdout/stderr 均为捕获 UTF-8 文本后的 `repr`，退出码为实际进程退出码。

**1) 静态检查**

```
python -m lwt --check docs/agent-eval/submissions/cli-args-text-processing/program.lwt
```
- stdout: `'Check passed: 1 source file(s).\n'`
- stderr: `''`
- 退出码: `0`

**2) 常规文件（含空行、末尾换行）**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/basic.txt
```
- stdout: `'lines 2 words 5\n'`
- stderr: `''`
- 退出码: `0`

**3) 文件末尾无换行（题面硬性要求）**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/nonl.txt
```
- stdout: `'lines 2 words 3\n'`
- stderr: `''`
- 退出码: `0`

**4) 空文件**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/empty.txt
```
- stdout: `'lines 0 words 0\n'`
- stderr: `''`
- 退出码: `0`

**5) 仅空白行（含只含空格的行）**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/blank.txt
```
- stdout: `'lines 0 words 0\n'`
- stderr: `''`
- 退出码: `0`

**6) CRLF 文件（验证 `read_text` 规范化）**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/crlf.txt
```
- stdout: `'lines 2 words 3\n'`
- stderr: `''`
- 退出码: `0`

**7) 连续多空格 + 末尾无换行**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/multispace.txt
```
- stdout: `'lines 2 words 4\n'`
- stderr: `''`
- 退出码: `0`

**8) 不读 stdin 的对照（stdin 喂入 `SHOULD NOT BE READ`）**

```
printf 'SHOULD NOT BE READ\n' | python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/ignored.txt
```
- stdout: `'lines 1 words 3\n'`（只由文件决定，未受 stdin 影响）
- stderr: `''`
- 退出码: `0`

**9) 路径含空格**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- "docs/agent-eval/submissions/cli-args-text-processing/tmp/sp ace.txt"
```
夹具内容 `'one two\nthree'`。
- stdout: `'lines 2 words 3\n'`
- stderr: `''`
- 退出码: `0`

**10) 绝对路径（正斜杠）**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- "C:/Users/28641/AppData/Local/Temp/lwt-s48-T-cli-args-text-processing-s1/docs/agent-eval/submissions/cli-args-text-processing/tmp/nonl.txt"
```
- stdout: `'lines 2 words 3\n'`
- stderr: `''`
- 退出码: `0`

**11) 绝对路径（Windows 反斜杠）**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- 'C:\Users\28641\AppData\Local\Temp\lwt-s48-T-cli-args-text-processing-s1\docs\agent-eval\submissions\cli-args-text-processing\tmp\nonl.txt'
```
- stdout: `'lines 2 words 3\n'`
- stderr: `''`
- 退出码: `0`

**12) 文件不存在（错误路径行为，非题目要求）**

```
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/tmp/nope.txt
```
- stdout: `''`
- stderr: `'docs/agent-eval/submissions/cli-args-text-processing/program.lwt:3:12: RuntimeError: could not read text file\n'`
- 退出码: `3`

符合规范 §6（`read_text` 失败为运行时错误，码 3）与 §7（诊断格式 `<source>:<line>:<column>: <类别>: <消息>`，位置指向调用处）。

**13) 交付前复检（删除夹具后）**

```
python -m lwt --check docs/agent-eval/submissions/cli-args-text-processing/program.lwt
```
- stdout: `'Check passed: 1 source file(s).\n'`
- stderr: `''`
- 退出码: `0`

## 5. 失败尝试与修订次数

- 失败尝试：0 次。首次写出的 `program.lwt` 即通过 `--check` 与全部 12 条运行用例。
- 代码修订次数：0 次。仅新增测试夹具与报告，未改动程序。
- 唯一需要判断的点是"非空行"与"连续空格"的口径（见 §2 设计决定 1、2），实现时按上述口径一次写成，未再回改。

## 6. 隔离声明

如实声明本会话的读取范围：

- **已读**（仅这三份）：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- **未读**：`lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、`examples/`、其他题目目录，以及任何期望输出文件；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下的任何路径；未读取 `docs/` 下三份允许文档之外的任何文件。
- 需披露的两条边界情况（均未读取被禁文件内容）：
  1. 第一次 `ls -la` 列出仓库根目录条目，输出中出现 `lwt`、`editors`、`slides` 等目录**名称**（未进入、未读取其中任何文件）。
  2. 一次 `ls -la docs/` 列出 `docs/` 下全部文件名（仅文件名，未读取 `docs/` 内除上述三份允许文档以外的任何文件内容）。
- 运行方式：只使用公开入口 `python -m lwt`（含 `--check` 与 `SOURCE -- ARGS` 形式），未用 Python 或其他语言生成、改写或预计算程序输出。捕获输出时只用 `python -c` 读取已重定向的 stdout/stderr 文件并打印其 `repr`，该脚本不参与产生被比较的程序输出。
- 写入范围：仅 `docs/agent-eval/submissions/cli-args-text-processing/` 下（`program.lwt`、`report.md`，以及自测用的 `tmp/` 夹具与捕获文件；`tmp/` 已在交付前删除）。
