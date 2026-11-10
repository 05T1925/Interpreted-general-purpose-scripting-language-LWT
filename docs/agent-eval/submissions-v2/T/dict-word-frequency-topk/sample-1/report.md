# dict-word-frequency-topk — 实现与自测报告

## 1. 交付与脚本路径

- 程序：`docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt`
- 本报告：`docs/agent-eval/submissions/dict-word-frequency-topk/report.md`
- 所有命令的工作目录：仓库根 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-dict-word-frequency-topk-s1`
- 运行入口只用公开 CLI：`python -m lwt <file>`（另用 `--check` 做静态自检）。

## 2. 依据的文档与小节

| 文档 | 具体小节 | 用于什么 |
|---|---|---|
| `docs/language-spec.md` | §2.1 标识符/字符串/注释与分号 | 源码形态；`#` 注释、字符串仅四种转义 |
| 同上 | §3 语法（`while`、`each`、`when/otherwise`、`break`、`fn`、`let`、`emit`、`dict{...}`、EBNF） | 全部语法结构；`break` 只能作用于本函数最近的循环 |
| 同上 | §4.2 运算与比较（`==`/`!=`、整数比较、字符串按码点逐位比较） | 计数比较、`line != null`、`counts[...] + 1`、单词升序比较 |
| 同上 | §4.3 数组与 `push`、§4.4 映射（`dict{}`、插入顺序、`d[k]` 读、缺失键报错、键为整数或字符串） | 用 dict 累计词频，键为单词字符串 |
| 同上 | §5 作用域与函数（顶层 `fn` 先登记、函数外层为变量根作用域、`while`/`each`、`break`） | 把排序与比较写成两个 `fn`，其余为顶层语句 |
| 同上 | §6 预置能力表（`input()`、`split`、`len`、`str`、`keys`、`has`、`emit`） | 逐行读到 `null`、按单空格切分、取键数组、判断键是否存在、输出格式 |
| 同上 | §7 错误与退出码、诊断格式 | 自测时核对退出码 0 与 stderr 为空 |
| 同上 | §8.7 映射示例 | dict 写入/读取的惯用写法 |
| 同上 | §11 并发（`spawn`/通道） | 本题为纯 CPU 顺序统计，**未使用**并发；§11.1 明确并发不加速 CPU 计算 |
| `docs/developer-guide.md` | §1「CLI、参数和输入」（`input()` 语义：剥 LF 与前置一个 CR、EOF 返回 `null`）、「退出码和诊断」 | 读取循环的终止条件、验证方式 |
| 同上 | §3「内置函数与输出」表（`input`/`len`/`split`/`str`/`emit`） | 内置函数签名与严格类型规则 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」1/5/6（先查规范 → 先 `--check` 再公开 CLI → 核对 stdout/stderr/退出码）、「语言边界」与 S42 dict 要点 | 流程约束；dict 用 `keys(d)` 遍历、不用 `each` 直接遍历映射 |
| `docs/concurrency.md` | 全文（调度点、反模式、工具边界） | 阅读后确认本题无需并发；`input()` 在任务内是运行时错误（§11.3），因此更不能把读 stdin 放进任务 |

## 3. 设计与实现要点

1. **读入**：`let line = input();` 后 `while (line != null) { ... line = input(); }`，EOF 得到 `null` 即结束（规范 §6 `input()`）。
2. **分词**：`split(line, " ")`；题目约定单词以单个空格分隔，实现中仍跳过空串（`when (word != "")`），从而对空行、行首/行尾空格、连续空格保持稳健。
3. **计数**：`dict{}` + `has` / `d[w]` / `d[w] = d[w] + 1`；键是字符串，符合 §4.4 的键类型要求。
4. **排序**：LWT 没有内置排序（§6 表），故自写**插入排序** `sort_words(counts, words)`；比较函数 `precedes` 实现「次数降序、同次数单词升序」，字符串用 `<`（§4.2 按 Unicode 码点逐位比较，前缀较短更小）。
5. **输出**：取 `keys(counts)` 排序后输出前 3 条，格式 `word count`（单个空格，`str(counts[w])`）；不足 3 条时按实际条数输出。
6. **EMPTY**：判据为**没有任何单词**（`len(counts) == 0`）。这样既覆盖「stdin 为空」，也覆盖「只有空行」的退化输入；未采用「是否读过行」作为判据，避免只有空白行时输出 0 行。

## 4. 自测记录（命令 / stdout repr / stderr / 退出码）

所有 stdout 均以 `repr()` 形式给出，stderr 为 `''` 表示空。管道中退出码取 `python` 进程本身的码。

| # | 命令 | stdout (repr) | stderr | 退出码 |
|---|---|---|---|---|
| 0 | `python -m lwt --check docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'Check passed: 1 source file(s).\n'` | `''` | 0 |
| 1 | `printf 'a b a c b a\nd c\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'a 3\nb 2\nc 2\n'` | `''` | 0 |
| 2 | `printf '' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'EMPTY\n'` | `''` | 0 |
| 3 | `printf 'pear apple fig apple fig kiwi banana fig\nbanana apple\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'apple 3\nfig 3\nbanana 2\n'` | `''` | 0 |
| 4 | `printf 'x\ny\n\nx' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'x 2\ny 1\n'` | `''` | 0 |
| 5 | `printf '\n\n\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'EMPTY\n'` | `''` | 0 |
| 6 | `printf 'app apple app apple zebra zebra yak\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'app 2\napple 2\nzebra 2\n'` | `''` | 0 |
| 7 | `printf 'gamma beta alpha delta gamma beta alpha delta\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'alpha 2\nbeta 2\ndelta 2\n'` | `''` | 0 |
| 8 | `printf 'one two one\r\ntwo three\r\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'one 2\ntwo 2\nthree 1\n'` | `''` | 0 |
| 9 | `printf 'k1 k1 k1 k2 k2 k3 k4 k4 k4 k5 k6 k7 k8 k9 k10 k11 k12\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'k1 3\nk4 3\nk2 2\n'` | `''` | 0 |
| 10 | `awk 'BEGIN{for(i=1;i<=20;i++){s="";for(j=1;j<=i;j++){s=s "w" i " "} print s}}' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'w20 20\nw19 19\nw18 18\n'` | `''` | 0 |
| 11 | `printf '苹果 香蕉 苹果 樱桃 香蕉 苹果\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'苹果 3\n香蕉 2\n樱桃 1\n'` | `''` | 0 |
| 12 | `printf 'a a a a a\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'a 5\n'` | `''` | 0 |
| 13 | `printf 'a  b \na b\n' \| python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/program.lwt` | `'a 2\nb 2\n'` | `''` | 0 |

用例覆盖：基本计数与前三截断（#1）、空输入（#2）、同次数按单词升序且并列跨越截断边界（#3）、不足 3 条 + 空行 + 末行无 LF（#4）、仅空行（#5）、前缀词比较（#6 `app < apple`）、四路并列取字母序前 3（#7）、CRLF 行尾（#8）、多词与并列（#9）、20 个键的排序（#10）、非 ASCII 单词（#11）、单词（#12）、多余空格容错（#13）。

字节级核对：用例 #1 曾用 `od -c` 确认输出为 `a   3 \n b   2 \n c   2 \n`，即 `word` + 单个空格 + 十进制次数 + LF，无多余空格或空行。

## 5. 失败尝试与修订次数

- 程序版本：**1 版**（`program.lwt` 首次写入后未再修改）；**修订 0 次**。
- 运行失败：**0 次**。`--check` 与 13 组 CLI 用例全部一次通过，退出码均为 0，stderr 均为空。
- 唯一一次操作调整：首个证据用例（#1）为了同时查看 stdout 原始字节，曾把 stdout/stderr 重定向到 `/tmp/o1.txt`、`/tmp/e1.txt` 再用 `od -c` 查看；此后所有用例改为纯管道（`| sed -n l` / `| od -c` 直接串联）不再落盘。这一重定向写到了工作目录之外的系统临时目录，见第 6 节声明。

## 6. 隔离规则遵守情况声明

- **未读过** `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录，也**未**访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径；未联网。
- 只读过允许的四份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/concurrency.md`。
- 目录列举：执行过一次 `ls -R . | head -50`（查看工作目录结构）与 `ls docs/agent-eval`；仅列出文件名，未打开任何禁止文件的**内容**。此点如实记录，供判定参考。
- 写入范围：`docs/agent-eval/submissions/dict-word-frequency-topk/` 下的 `program.lwt`、`report.md`；另在该目录执行过一次 `mkdir -p`。
- **例外（如实声明）**：用例 #1 的首次运行把 stdout/stderr 重定向到系统临时目录的 `/tmp/o1.txt`、`/tmp/e1.txt`（Git Bash 映射的 Windows 临时目录），这两个文件仅为命令输出捕获，未参与程序逻辑；未删除。除此之外没有在工作目录之外创建或修改文件。
- 运行方式：全部通过 `python -m lwt` 公开入口；没有用 Python 或其他语言生成/改写 LWT 输出或程序文本（`awk` 只用于生成测试输入）。
