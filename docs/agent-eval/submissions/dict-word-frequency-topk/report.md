# freq.lwt 盲测实现报告

## 1. 交付物与结论

- 脚本相对路径（相对仓库根目录）：`docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt`
- 运行入口：`python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt`（stdin 提供输入，不使用 `--` 参数）
- 结果：静态检查通过；20 组真实 CLI 用例 stdout/stderr/退出码全部符合题目要求，0 次源码修订。

## 2. 依据的文档与具体小节

| 文档 | 使用的小节 | 用途 |
|---|---|---|
| `docs/language-spec.md` | §2.1（注释、标识符、字符串） | 源码写法与注释 |
| 同上 | §3（`fn`/`let`/`while`/`each`/`when`/`dict`/索引与字段赋值 EBNF） | 确认本题可用的语句与表达式形式 |
| 同上 | §4.1（求值次序、`let` 绑定）、§4.2（整数除法、字符串按 Unicode 码点比较、严格类型） | 排序比较与整数运算 |
| 同上 | §4.4（`dict{...}`、键只能是整数/字符串、插入顺序、`d[k]` 读写在缺键/新键时的行为） | 词频计数容器 |
| 同上 | §5（顶层函数先登记、函数无闭包、`while`/`each` 作用域、`break`/`continue` 约束） | 归并排序与逐行处理 |
| 同上 | §6（`input()` EOF 返回 `null`、`split` 保留空字段、`len`、`str`、`keys`、`has`、`emit`） | 输入、切分、输出 |
| 同上 | §7（成功 0 / 词法语法 2 / 运行时 3 / CLI 4） | 核对退出码 |
| `docs/developer-guide.md` | §1「CLI、参数和输入」「退出码和诊断」「运行前静态检查」 | `input()` 语义、`--check` 工作流 |
| 同上 | §2「值、变量、表达式和注释」「分支、循环和函数」 | 基本语法确认 |
| 同上 | §3「内置函数与输出」表 | `input`/`split`/`len`/`str`/`emit` 易错点 |
| 同上 | §4「调试和验证」 | 先 `--check` 再用公开 CLI 核对 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」1–7；「S42 新增能力的使用要点」dict 段 | 只写 `.lwt`、先检查后运行、`each` 不直接遍历 dict，改用 `keys(d)` |
| `docs/concurrency.md` | 「I/O 边界」「五个调度点」 | 确认并发不适用于本题：任务内 `input()` 是 `RuntimeError`，且 stdin 只有单一来源，故采用单任务顺序读取 |

## 3. 实现说明

1. `input()` 逐行读取，`null` 表示 EOF；每行 `split(line, " ")` 按单个空格切分。
2. 切分产生的空字段（空行、连续空格）被跳过，不计为单词。
3. 用 `dict{}` 计数：`has(counts, w)` 判定后 `counts[w] = counts[w] + 1` 或 `counts[w] = 1`；`dict` 键均为字符串。
4. `keys(counts)` 取得去重单词数组；自行实现稳定归并排序：先按次数降序，次数相同按单词 Unicode 码点升序（`a < b`）。
5. 输出 `min(3, 单词数)` 行，每行 `word + " " + str(count)`。
6. 单词数为 0（stdin 为空、或仅有空行/空白行）时输出 `EMPTY`。

边界决策：题目只规定「无输入时输出 `EMPTY`」。本实现把「没有任何单词」统一视为该情形，因此空 stdin、仅空行、仅空格行都输出 `EMPTY`；这样不会出现「有输入行但零单词时输出 0 行」的二义结果。该决策不影响任何含至少一个单词的输入。

## 4. 自测证据

### 4.1 命令模板

在仓库根目录执行（Git Bash；`${PIPESTATUS[0]}` 为 `python -m lwt` 阶段的退出码）：

```bash
cd C:/Users/28641/AppData/Local/Temp/lwt-s47-blind-dict-word-frequency-topk
P=docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt
printf '<STDIN>' | python -m lwt "$P" \
  2> >(python -c 'import sys;sys.stderr.write("ERR="+repr(sys.stdin.buffer.read())+"\n")' >&2) \
  | python -c 'import sys;sys.stdout.write("OUT="+repr(sys.stdin.buffer.read())+"\n")'
echo "EXIT=${PIPESTATUS[0]}"
```

说明：末尾两个 `python -c` 只是把**真实捕获到的字节**格式化为 repr 以便记录，不参与程序逻辑、不生成或改写输出。

### 4.2 静态检查

```bash
python -m lwt --check docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt
```

- stdout repr：`b'Check passed: 1 source file(s).\n'`
- stderr repr：`b''`
- 退出码：`0`

### 4.3 运行用例

所有用例 stderr 均为 `b''`、退出码均为 `0`。

| # | stdin（printf 字面量） | stdout repr |
|---:|---|---|
| 1 | `''`（EOF） | `b'EMPTY\n'` |
| 2 | `'a b a\nc a b\n'` | `b'a 3\nb 2\nc 1\n'` |
| 3 | `'B a b A\n'` | `b'A 1\nB 1\na 1\n'` |
| 4 | `'b b a c c c d d\n'` | `b'c 3\nb 2\nd 2\n'` |
| 5 | `'x y z w\n'` | `b'w 1\nx 1\ny 1\n'` |
| 6 | `'apple apple\npear\n'` | `b'apple 2\npear 1\n'` |
| 7 | `'a  b\n\n a\n'` | `b'a 2\nb 1\n'` |
| 8 | `'alpha beta\nalpha'`（末行无 LF） | `b'alpha 2\nbeta 1\n'` |
| 9 | `'a b\r\na\r\n'` | `b'a 2\nb 1\n'` |
| 10 | `'苹果 香蕉 苹果\n香蕉 苹果\n'` | `b'\xe8\x8b\xb9\xe6\x9e\x9c 3\n\xe9\xa6\x99\xe8\x95\x89 2\n'`（即 `苹果 3\n香蕉 2\n`） |
| 11 | `'\n\n\n'` | `b'EMPTY\n'` |
| 12 | `'d c b a\nd c b\nd c\nd\n'` | `b'd 4\nc 3\nb 2\n'` |
| 13 | `'a a b b c c d d e\n'` | `b'a 2\nb 2\nc 2\n'` |
| 14 | `'a1 A1 1 2\n'` | `b'1 1\n2 1\nA1 1\n'` |
| 15 | `'solo\n'` | `b'solo 1\n'` |
| 16 | `'c c b b a a\n'` | `b'a 2\nb 2\nc 2\n'` |
| 17 | `'   \na a\n'` | `b'a 2\n'` |
| 18 | `'the quick brown fox jumps over the lazy dog\nthe fox\n'` | `b'the 3\nfox 2\nbrown 1\n'` |

每条命令均为 4.1 模板，例如用例 2 实际执行：

```bash
printf 'a b a\nc a b\n' | python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt \
  2> >(python -c 'import sys;sys.stderr.write("ERR="+repr(sys.stdin.buffer.read())+"\n")' >&2) \
  | python -c 'import sys;sys.stdout.write("OUT="+repr(sys.stdin.buffer.read())+"\n")'
echo "EXIT=${PIPESTATUS[0]}"
```

其实际回报为 `OUT=b'a 3\nb 2\nc 1\n'`、`ERR=b''`、`EXIT=0`。

### 4.4 规模用例

```bash
awk 'BEGIN{for(i=1;i<=2000;i++) printf "w%04d ", i; print ""; print "zzz zzz zzz zzz zzz"}' \
  | { time python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt \
      2> >(python -c 'import sys;sys.stderr.write("ERR="+repr(sys.stdin.buffer.read())+"\n")' >&2); } \
  | python -c 'import sys;sys.stdout.write("OUT="+repr(sys.stdin.buffer.read())+"\n")'
echo "EXIT=${PIPESTATUS[0]}"
```

- stdout repr：`b'zzz 5\nw0001 1\nw0002 1\n'`
- stderr repr：`b''`
- 退出码：`0`
- `time` 实测：`real 0m1.121s`

另有 10000 个不同单词的同类用例：

```bash
awk 'BEGIN{for(i=1;i<=10000;i++) printf "w%05d ", i; print ""}' \
  | { time python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt \
      2> >(python -c 'import sys;sys.stderr.write("ERR="+repr(sys.stdin.buffer.read())+"\n")' >&2); } \
  | python -c 'import sys;sys.stdout.write("OUT="+repr(sys.stdin.buffer.read())+"\n")'
echo "EXIT=${PIPESTATUS[0]}"
```

- stdout repr：`b'w00001 1\nw00002 1\nw00003 1\n'`
- stderr repr：`b''`
- 退出码：`0`
- `time` 实测：`real 0m3.986s`

两个用例验证了归并排序在大量不同键下仍能正确取前 3 行，且无栈溢出或超时。

## 5. 失败尝试与修订

- 失败运行：0 次；源码修订：0 次；`--check` 首次即通过。
- 唯一一次非最终形态的证据采集：最初一次空 stdin 测试用 `> /tmp/freq_out1.txt 2> /tmp/freq_err1.txt` 暂存捕获结果（文件仅含本次自测输出），随后立即 `rm -f` 删除。程序本身未失败；此后全部测试改为 4.1 的纯管道方式，未再在提交目录外写文件。
- 设计取舍：初始版本即采用「零单词 → `EMPTY`」与「跳过空 token」，未因测试结果返工。

## 6. 隔离与工具边界声明

- 已读内容仅限题目允许的四份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/concurrency.md`。
- 除这四份文档外，只执行过根目录与 `docs/` 的 `ls` 元数据列举（仅文件名/大小/时间），未打开其中任何文件；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下的任何路径。
- 程序只通过公开入口 `python -m lwt <file>` 运行；未用 Python 或其他语言实现题目逻辑、生成期望输出或改写 `.lwt` 程序。`python -c` 仅用于把真实捕获的 stdout/stderr 字节格式化为 repr。
- 交付文件均位于 `docs/agent-eval/submissions/dict-word-frequency-topk/`（`program.lwt` 与本报告）；除第 5 节披露并已删除的两个临时捕获文件外，未在该目录外写入文件。
