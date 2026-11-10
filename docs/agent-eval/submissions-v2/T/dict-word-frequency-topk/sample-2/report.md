# freq.lwt 交付报告（dict-word-frequency-topk）

## 1. 交付物

| 文件 | 说明 |
|---|---|
| `program.lwt` | 题目要求的 `freq.lwt` 程序本体（交付名按目录约定为 `program.lwt`） |
| `report.md` | 本报告 |

程序行为：从 stdin 逐行读取，按单个空格切分单词，统计词频；按次数降序、同次数按单词升序排序，输出前 3 行，每行 `word count`；无输入（无任何单词）输出 `EMPTY`；用 `input()` 读到 EOF；不读取、不使用任何命令行参数。

## 2. 依据文档与小节

仅使用 T 组允许文档，对应关系如下：

- `docs/language-spec.md`
  - §2.1 词法：`#` 注释、标识符、字符串转义（本程序注释与字符串只用到规范内字符）。
  - §3 语法：`record` 声明、`fn`、`while`、`each`、`when/otherwise`、`break`、`emit`、索引/字段访问与赋值；`record` 只能顶层。
  - §4.2 比较：`<`/`>` 对两个字符串按 Unicode 码点逐位比较（同次数时单词升序的比较依据）；`==`/`!=` 对全部值有效。
  - §4.4 映射：`dict{}` 构造、`d[k]` 读写、字符串键合法、插入顺序与身份相等。
  - §5 作用域与控制流：块级作用域、`while` 每轮新作用域、`each` 的浅快照、`break` 作用于最近循环、函数局部作用域外层为全局。
  - §6 预置能力表：`input()`（EOF 返回 `null`，剥除行尾 LF 及一个 CR）、`split`（保留空字段）、`keys`、`get`（缺键返回默认值）、`put`、`len`、`push`、`str`。
  - §7 退出码：成功 0、运行时错误 3、诊断只走 stderr。
  - §8.7 映射示例（`keys`/`get`/`put`/`d[k]` 用法佐证）。
- `docs/developer-guide.md`
  - §1「CLI、参数和输入」：`input()` 逐行、EOF 为 `null`；`python -m lwt SOURCE [-- ARGS...]` 为公开入口。
  - §2「分支、循环和函数」「数组、record 和 `each`」「`while`/`each` 循环控制」：顶层函数登记、前向调用、`each` 浅快照、`break;` 带分号。
  - §3「语义速查」：严格类型、无隐式转换、内置函数表、`str`/`emit` 显示规则。
- `.agents/skills/lwt-app/SKILL.md`
  - 工作流程第 3–7 条：只用规范已支持能力、不写 Python 语法、先 `--check` 再公开 CLI 实跑、核对 stdout/stderr/退出码、只记录真实命令。
- `docs/concurrency.md`
  - 仅用于确认边界：本任务为纯 stdin 文本统计，不使用 `spawn`/通道；任务内 `input()` 不可用，因此程序不引入并发。

## 3. 实现要点

1. `record Entry { word, count };` 保存「单词—次数」对。
2. `fn before(a, b)`：`count` 大者在前；`count` 相等时 `a.word < b.word` 者在前（字符串按码点比较）。
3. `fn sort_entries(items)`：对 `Entry` 数组做原地插入排序（`while` + 内层 `while` + `break`），避免依赖任何不存在的排序内置。
4. 主流程：`let line = input(); while (line != null) { ... line = input(); }`；空行跳过；`split(line, " ")` 后跳过空 token（`split` 按规范会保留连续分隔符产生的空字段）；计数用 `put(counts, w, get(counts, w, 0) + 1);`，`dict` 的字符串键与缺键默认值语义来自 §4.4/§6。
5. 输出：`len(keys(counts)) == 0` 时输出 `EMPTY`；否则构造 `Entry` 数组、排序、截断到 3 条，逐行 `emit items[k].word + " " + str(items[k].count);`。

设计选择（题目未规定处的简单一致处理）：不同单词不足 3 个时输出全部；空行与纯空白行不产生单词；仅含空白行的输入与空 stdin 一样输出 `EMPTY`；不调用 `args()`，附加参数被忽略。

## 4. 环境与静态检查

```text
Python 3.13.14
lwt 0.3.0
```

```bash
cd "C:/Users/28641/AppData/Local/Temp/lwt-s48-T-dict-word-frequency-topk-s2"
python -m lwt --check docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt
```

- stdout：`Check passed: 1 source file(s).`
- stderr：（空）
- 退出码：`0`

```bash
python -m lwt --check --format=json docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt
```

- stdout：`{"schema_version":1,"ok":true,"files_checked":1,"diagnostics":[]}`
- stderr：（空）
- 退出码：`0`

## 5. 真实运行记录

统一命令形式（仅使用公开入口，stdin 由管道提供）：

```bash
python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt
```

为精确记录字节，最后一轮用下列宿主脚本把同一 CLI 的 stdin 送入并打印 repr（脚本只做转发与格式化，程序输出全部来自 `python -m lwt`，未用其他语言生成或改写输出）：

```bash
python -c "
import subprocess,sys
cases=[(b'a b a c a b\n','basic'),(b'b a\n','tie'),(b'','empty'),(b'e d c b a e d c b e\n','top3'),(b'Zebra apple Apple apple zebra\n','case'),(b'one two two three three three','no-trailing-lf'),(b'\n\na b\n\n','blank-lines'),(b'a b\r\n','crlf'),(b'x\n','single')]
for data,name in cases:
    r=subprocess.run([sys.executable,'-m','lwt','docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt'],input=data,capture_output=True)
    print(name,'| rc=',r.returncode,'| out=',repr(r.stdout),'| err=',repr(r.stderr))
"
```

结果：

```text
basic | rc= 0 | out= b'a 3\nb 2\nc 1\n' | err= b''
tie | rc= 0 | out= b'a 1\nb 1\n' | err= b''
empty | rc= 0 | out= b'EMPTY\n' | err= b''
top3 | rc= 0 | out= b'e 3\nb 2\nc 2\n' | err= b''
case | rc= 0 | out= b'apple 2\nApple 1\nZebra 1\n' | err= b''
no-trailing-lf | rc= 0 | out= b'three 3\ntwo 2\none 1\n' | err= b''
blank-lines | rc= 0 | out= b'a 1\nb 1\n' | err= b''
crlf | rc= 0 | out= b'a 1\nb 1\n' | err= b''
single | rc= 0 | out= b'x 1\n' | err= b''
```

补充用例（`printf ... | python -m lwt <program>`，逐一核对 stdout/stderr/退出码）：

| 用例 | stdin | stdout repr | stderr | 退出码 |
|---|---|---|---|---|
| 四词全并列，验证取字典序前 3 | `d c b a\n` | `b'a 1\nb 1\nc 1\n'` | `b''` | 0 |
| 纯空白行，验证不产生空单词 | ` \n` | `b'EMPTY\n'` | `b''` | 0 |
| 跨行累计 | `hot hot\nwarm hot warm\ncold warm hot cold\ncool\n` | `b'hot 4\nwarm 3\ncold 2\n'` | `b''` | 0 |
| 非 ASCII 单词（码点序：测 U+6D4B < 词 U+8BCD） | `多行 词频\n多行 测试 多行\n` | `b'多行 3\n测试 1\n词频 1\n'` | `b''` | 0 |
| 附加 CLI 参数被忽略 | `a b\na\n`，命令加 `-- foo bar` | `b'a 2\nb 1\n'` | `b''` | 0 |
| 40 行相同输入（并列按字典序） | 40 × `aa bb cc dd ee\n` | `b'aa 40\nbb 40\ncc 40\n'` | `b''` | 0 |

以上 15 个用例 stdout 均符合题目要求（次数降序、同次数单词升序、最多 3 行、无输入 `EMPTY`），stderr 全为空，退出码全为 0。

## 6. 失败与修订次数

- 静态检查失败：0 次（首版 `--check` 即通过，文本与 JSON 两种模式均 `ok`）。
- 运行失败（stdout/stderr/退出码不符）：0 次。
- 程序修订：0 次（`program.lwt` 写出后未再改动）。
- 已知未覆盖：题目未规定超长行、单词内含制表符等情形；本程序按「单个空格分隔」实现，制表符会被视作单词内字符，这与题面一致。

## 7. 隔离声明

- 只阅读了允许的 4 份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/concurrency.md`；为定位文件执行过 `ls` 查看目录项名称，未打开 T 组之外任何文件的内容。
- 未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目文件或任何期望输出。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只通过公开入口 `python -m lwt`（含 `--check`）执行/检查程序；未用其他语言实现或改写程序逻辑，未用其他语言生成期望输出。
- 写入仅限 `docs/agent-eval/submissions/dict-word-frequency-topk/`（本报告与 `program.lwt`）；测试输入均由 shell 管道构造，未在工作目录内新增测试文件。
