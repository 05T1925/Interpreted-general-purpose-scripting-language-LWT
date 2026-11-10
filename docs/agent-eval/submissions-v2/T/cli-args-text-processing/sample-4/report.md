# wordcount.lwt 盲测报告

## 1. 题目与实现结果

- 题目：编写 `wordcount.lwt`，读取 `args()[0]` 指定文本文件（`read_text`），统计**非空行数**与**非空行中的单词总数**（单词以单个空格分隔），输出 `lines <L> words <W>`；通过 `python -m lwt wordcount.lwt -- <path>` 调用；文件末尾无换行也必须正确计数；不读 stdin。
- 产物：
  - `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt`（唯一程序文件，`--check` 通过）
  - `docs/agent-eval/submissions/cli-args-text-processing/fixtures/`（11 个自测输入，可复现报告中的数字）

程序正文（全文 19 行）：

```lwt
let path = args()[0];
let text = read_text(path);
let lines = 0;
let words = 0;
each (raw in split(text, "\n")) {
    let line = trim(raw);
    when (line != "") {
        lines = lines + 1;
        each (token in split(line, " ")) {
            when (token != "") {
                words = words + 1;
            }
        }
    }
}
emit "lines " + str(lines) + " words " + str(words);
```

## 2. 依据的文档与小节

| 依据 | 用到的结论 |
|---|---|
| `docs/language-spec.md` §6 `args` | 返回仅含 CLI `--` 之后实参的新字符串数组，不含源文件名；不读 stdin |
| §6 `read_text` | 一个字符串路径，相对路径以进程 cwd 为基准；UTF-8、剥除开头一个 BOM、CRLF/CR 规范化为 LF；失败为运行时错误（码 3） |
| §6 `split` / `trim` / `str` / §4.3 | `split` 保留首尾与连续分隔产生的空字段；`trim` 只删两端 ASCII 空白；`str` 与 `emit` 同格式 |
| §3 语法 | `IDENT "("` 为命名调用；`postfix` 允许对调用结果索引（`args()[0]`）；`each (x in e) { }`、`when (...) { }` 无 `otherwise` 合法；分号必需 |
| §4.1 / §5 | 块有词法作用域，块内赋值修改最近可见外层绑定；`let` 初始化成功后才可见 |
| §5 `each` | 先求数组、取元素引用浅快照，逐元素迭代；空数组零次 |
| §6 `emit` + §7 | stdout 只承载 `emit` 输出，每个 `emit` 追加一个 LF；成功不额外输出状态；诊断走 stderr |
| `docs/developer-guide.md`「CLI、参数和输入」「内置函数与输出」「退出码和诊断」 | 命令形式 `python -m lwt SOURCE [-- ARGS...]`；`args()`/`read_text` 边界；成功 0、运行时错误 3 |
| `.agents/skills/lwt-app/SKILL.md` 工作流程 1/5/6 | 先 `--check` 再跑公开 CLI，核对 stdout/stderr/退出码；只记录真实命令 |

## 3. 设计决策

1. **行切分**：`split(read_text(path), "\n")`。`read_text` 已把 CRLF/CR 归一为 LF 并剥离 BOM，因此 Windows 换行与 BOM 文件无需额外处理；文件末尾有 `\n` 时多出的末尾空字段被判为空行，末行无换行时该字段仍是完整最后一行，故两种情况计数一致（对应题目「末尾无换行也必须正确」）。
2. **非空行判定**：对该行 `trim` 后与 `""` 比较。`trim` 只删 ASCII 空白（空格、TAB、LF、CR、VT、FF），所以纯空白行、`\t` 行不计入行数；同时行首尾多余空格不影响词数。
3. **词数**：对 trim 后的行按单个空格 `split`，只累计非空 token。对题目约定的「单词以单个空格分隔」输入，这与 `len(split(line, " "))` 完全相同；对偶发连续空格不会把空字段误计为单词。
4. **不使用 stdin**：全程只调用 `args()` 与 `read_text`，没有任何 `input()` 调用。

## 4. 自测记录（全部为真实 `python -m lwt` 运行，cwd 为仓库根目录）

命令模板：

```text
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt -- docs/agent-eval/submissions/cli-args-text-processing/fixtures/<file>
```

先做静态检查：

```text
$ python -m lwt --check docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt
stdout: 'Check passed: 1 source file(s).\n'
stderr: ''
exit: 0
```

正常用例（stdout 以 Python repr 给出，含末尾 LF；`bytes` 为 stdout 字节数）：

| 夹具（内容说明） | 期望 | stdout repr | stderr | 退出码 | bytes |
|---|---|---|---|---|---|
| `basic.txt`：`alpha beta` / `gamma` / 空行 / `   ` / `delta epsilon zeta` + 末尾 LF | 3 行 6 词 | `'lines 3 words 6\n'` | `''` | 0 | 16 |
| `no-final-newline.txt`：`one two\nthree`（**末尾无换行**） | 2 行 3 词 | `'lines 2 words 3\n'` | `''` | 0 | 16 |
| `two-lines.txt`：`hello\nworld\n` | 2 行 2 词 | `'lines 2 words 2\n'` | `''` | 0 | 16 |
| `empty.txt`：0 字节 | 0 行 0 词 | `'lines 0 words 0\n'` | `''` | 0 | 16 |
| `blank-only.txt`：`\n\n  \n\t\n` | 0 行 0 词 | `'lines 0 words 0\n'` | `''` | 0 | 16 |
| `crlf.txt`：`a b\r\nc\r\n\r\nd\r\n` | 3 行 4 词 | `'lines 3 words 4\n'` | `''` | 0 | 16 |
| `cr-only.txt`：`a b\rc d\r`（旧式 CR 换行） | 2 行 4 词 | `'lines 2 words 4\n'` | `''` | 0 | 16 |
| `bom.txt`：UTF-8 BOM + `a b\nc` | 2 行 3 词 | `'lines 2 words 3\n'` | `''` | 0 | 16 |
| `unicode.txt`：`你好 世界\n\n  x  y  \n` | 2 行 4 词 | `'lines 2 words 4\n'` | `''` | 0 | 16 |
| `two-digit.txt`：12 行（10 行 `w w` + 2 行 `a b c d e f g`） | 12 行 34 词 | `'lines 12 words 34\n'` | `''` | 0 | 18 |
| `space name.txt`：文件名含空格，内容 `x y\n` | 1 行 2 词 | `'lines 1 words 2\n'` | `''` | 0 | 16 |

补充验证：

| 场景 | 命令 | 结果 |
|---|---|---|
| stdin 不影响结果 | `printf 'junk line one two three\njunk\n' \| python -m lwt ...wordcount.lwt -- .../basic.txt` | stdout `'lines 3 words 6\n'`，stderr `''`，退出码 0（与无 stdin 时一致，证明不读 stdin） |
| 未提供程序实参 | `python -m lwt ...wordcount.lwt` | stdout `''`，stderr `wordcount.lwt:4:18: RuntimeError: array index is out of range\n`，退出码 3 |
| 文件不存在 | `... -- .../fixtures/does-not-exist.txt` | stdout `''`，stderr `wordcount.lwt:5:12: RuntimeError: could not read text file\n`，退出码 3 |

（上两行的诊断前缀实际为完整 CLI 路径 `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt`，此处为排版简写；两类错误都是题面未规定的输入用法，程序按 §6 的运行时错误契约以退出码 3 结束，未产生 Python traceback。）

## 5. 失败与修订次数

- 程序逻辑失败次数：**0**；`wordcount.lwt` 自首次写出后未做任何修改（修订次数 0）。
- 全部 11 个正常用例、`--check`、stdin 独立性用例均在第一次运行即得到期望输出。
- 唯一的过程性调整不属于代码修订：首轮测试用 shell 变量直接比较输出、并把 stderr 捕获到系统临时文件；为使证据落在提交目录内并便于复现，改为在提交目录下暂存 `runs/` 逐用例 stdout/stderr 后再汇总到本报告，交付前已删除该临时目录。

## 6. 隔离声明

- 只阅读了 TASK.md 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`（以及题目文件 `TASK.md`）。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录、任何期望输出，也未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。
- 所有运行只用公开入口 `python -m lwt`（含 `--check`），未用其他语言生成或改写程序输出。
- 全部写入都在 `docs/agent-eval/submissions/cli-args-text-processing/` 之下（程序、`fixtures/` 输入、本报告）；中途一次 stderr 捕获曾重定向到系统临时文件 `/tmp/err.txt`，仅用于观察诊断文本，随后即改用提交目录内的临时捕获并在交付前清理。
