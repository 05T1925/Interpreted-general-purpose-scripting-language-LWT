# 盲测报告：wordcount.lwt（cli-args-text-processing）

## 1. 交付物

| 文件 | 说明 |
|---|---|
| `wordcount.lwt` | 题目要求的 LWT 程序 |
| `fixtures/*.txt` | 自测输入（均为本题自造，不含期望输出文件） |
| `report.md` | 本报告 |

运行方式：`python -m lwt docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt -- <path>`。

## 2. 依据的文档与小节

- `docs/language-spec.md`
  - §6：`args()` 仅含 `--` 之后实参且每次返回新数组；`read_text(path)` 读全文、相对路径以进程 cwd 为基准、剥除开头一个 BOM、CRLF/CR 规范化为 LF、读取失败为运行时错误；`split(text, separator)` 保留首尾与连续分隔产生的空字段；`trim` 只裁两端 ASCII 空白；`str(value)` 生成显示字符串；CLI 形式 `python -m lwt SOURCE [-- ARGS...]`。
  - §5：`when/otherwise` 条件必须为布尔；`each` 遍历数组、每轮新建循环作用域，块内赋值修改最近可见绑定。
  - §4.2：`!=` 对所有值有定义，字符串按值比较；`+` 只接受两个整数或两个字符串（故计数需 `str()`）。
  - §7：成功退出码 0、运行时错误 3、CLI/源文件错误 4；stdout 只承载 `emit`。
- `docs/developer-guide.md`
  - §1「CLI、参数和输入」「退出码和诊断」：`--` 分隔符、`read_text` 以 cwd 解析、退出码表；§3「内置函数与输出」：`split`/`trim`/`str` 的边界；§1「运行前静态检查」：建议先 `--check` 再跑公开 CLI。
- `.agents/skills/lwt-app/SKILL.md`
  - 工作流程第 1–3、5–7 条：先读指南与规范、提取输入输出与 CLI 参数、只用已支持能力、先 `--check` 再运行公开 CLI、只记录真实运行的命令与结果。

## 3. 程序要点

```lwt
let path = args()[0];
let text = read_text(path);
let lines = split(text, "\n");
let line_count = 0;
let word_count = 0;
each (line in lines) {
    let content = trim(line);
    when (content != "") {
        line_count = line_count + 1;
        each (word in split(content, " ")) {
            when (word != "") {
                word_count = word_count + 1;
            }
        }
    }
}
emit "lines " + str(line_count) + " words " + str(word_count);
```

边界处理及依据：

1. **末尾无换行**：`split(text, "\n")` 在无末尾 LF 时最后一段就是末行内容，在有末尾 LF 时多出一个 `""` 字段；`content != ""` 使这个空段不计行，因此两种结尾计数一致（规范 §6 `split` 保留空字段）。
2. **空行/仅空白行**：以 `trim(line)` 判空（规范 §6 `trim` 只裁 ASCII 空白），故 `""`、`"   "`、`"\t"` 行均不计入非空行；其内部也不产生单词。
3. **单词以单个空格分隔**：对行内容 `split(content, " ")`；因保留连续分隔产生的空字段，计词时跳过 `""`，避免连续空格被误计为单词。
4. **CRLF**：`read_text` 已把 CRLF/CR 规范化为 LF（规范 §6），故 `split(..., "\n")` 不会残留 `\r`；`trim` 也会裁掉行尾 CR 作为兜底。
5. **输出格式**：`"lines " + str(L) + " words " + str(W)`，`emit` 追加一个 LF（规范 §4.3、§6）。
6. **不读 stdin**：程序只调用 `args()`/`read_text()`，无 `input()`。

## 4. 真实命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-cli-args-text-processing-s5`
下文 `$D = docs/agent-eval/submissions/cli-args-text-processing`。

### 4.1 静态检查

命令：

```text
python -m lwt --check docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt
```

- stdout repr：`b'Check passed: 1 source file(s).\n'`（终端显示 `Check passed: 1 source file(s).`）
- stderr repr：`b''`
- 退出码：0

### 4.2 公开 CLI 运行（逐样例）

命令模板：

```text
python -m lwt $D/wordcount.lwt -- $D/fixtures/<name>.txt
```

| 样例 | 输入内容（POSIX 转义） | stdout repr | stderr repr | 退出码 | 预期 |
|---|---|---|---|---|---|
| basic | `alpha beta\n\ngamma delta epsilon\n` | `b'lines 2 words 5\n'` | `b''` | 0 | 2 非空行、5 词 |
| no_trailing_newline | `one two\nthree`（无末尾换行） | `b'lines 2 words 3\n'` | `b''` | 0 | 2 行、3 词，末行被计数 |
| empty | 空文件（0 字节） | `b'lines 0 words 0\n'` | `b''` | 0 | 0 行、0 词 |
| blank_only | `\n\n   \n\t\n` | `b'lines 0 words 0\n'` | `b''` | 0 | 全是空/空白行，不计 |
| single_word | `hello`（无末尾换行） | `b'lines 1 words 1\n'` | `b''` | 0 | 1 行、1 词 |
| crlf | `x y\r\nz\r\n` | `b'lines 2 words 3\n'` | `b''` | 0 | CRLF 规范化后 2 行、3 词 |

精确字节捕获示例（basic）：

```text
python -m lwt $D/wordcount.lwt -- $D/fixtures/basic.txt > $D/.out 2> $D/.err
exit=0
stdout b'lines 2 words 5\n'
stderr b''
```

### 4.3 不读取 stdin 的验证

命令：

```text
printf 'SHOULD-NOT-BE-READ\n' | python -m lwt $D/wordcount.lwt -- $D/fixtures/basic.txt
```

- stdout repr：`b'lines 2 words 5\n'`
- stderr repr：`b''`
- 退出码：0
- 结论：管道中的 stdin 未影响输出，符合“不读取 stdin”。

## 5. 失败与修订次数

- 失败次数：0（`--check` 与上表 6 个样例、stdin 验证均一次通过）。
- 修订次数：0（`wordcount.lwt` 首版即为最终版本，未改动）。
- 已知边界选择：题目未定义“非空行”是否含仅空白行，本实现按“空白行视为空行”处理（见 §3 第 2 条）；若判题要求把仅空白行算作非空行，需改动判空条件。此项为语义选择，非运行失败。

## 6. 隔离声明

1. 只阅读了 TASK.md 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`，另加 `TASK.md` 本身；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`，未联网。
2. 只通过公开入口 `python -m lwt <file>` / `python -m lwt --check <file>` 执行；未使用其他语言生成或改写程序输出（仅用 Python 读取捕获文件的字节以打印 repr 证据）。
3. 只在本目录 `docs/agent-eval/submissions/cli-args-text-processing/` 下写入文件（程序、fixtures、本报告；测试期间的临时 `.out`/`.err` 也仅在该目录内，用完即删）。
