# freq.lwt 盲测报告

## 1. 交付物

- `docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`（程序；不接收命令行参数，`input()` 逐行读到 EOF）

## 2. 依据文档与小节

| 文档 | 使用的小节 | 用于决定 |
|---|---|---|
| `docs/language-spec.md` | §2.1 词法与空白、§3 语法（`let`/`while`/`when`/`otherwise`/`each`/`emit`、字典字面量）、§4.2 运算与比较（整数、字符串比较规则）、§4.4 映射、§5 作用域与循环、§6 预置能力（`input`/`split`/`len`/`keys`/`get`/`put`/`str`）、§7 退出码 | 全部语义：行读取、切分、计数、排序比较、输出格式 |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」、§3 语义速查（`input`/`split`/`str`/`emit` 行为） | `python -m lwt` 公开入口、stdin 供给方式、stdout/stderr 契约 |
| `.agents/skills/lwt-app/SKILL.md` | 工作流程 3/5/6/7；S42 dict 使用要点 | 只用已实现能力；先 `--check` 再跑真实 CLI；只记录真实结果 |
| `docs/concurrency.md` | 全文（并发契约卡） | 确认本题为纯串行统计，不需要 `spawn`/通道；未引入并发 |

## 3. 实现要点

1. 用 `dict{}` 计数：`put(counts, w, get(counts, w, 0) + 1)`，新键追加、旧键原位更新（规范 §4.4）。
2. `split(line, " ")` 切分，`len(w) > 0` 过滤空字段（空行、连续/首尾空格产生的空串不计为单词）。
3. 取 `keys(counts)` 保持插入序，`each` 收集计数到并行数组。
4. 只需求前 3：做 3 轮线性选择（每轮扫描剩余项，比较规则为「计数大者优先，同计数词小者优先」），选出后把该位置计数置 `-1` 作已选标记（真实计数恒 ≥ 1）。复杂度 O(n)，避免 O(n²) 排序在解释器下过慢。
5. 无任何单词时输出 `EMPTY`；否则按 `word + " " + str(count)` 逐行 `emit`，最多 3 行。

## 4. 命令与实测结果

所有运行均在仓库根目录 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-dict-word-frequency-topk-s3`，程序路径记为 `$P = docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`，仅用公开入口 `python -m lwt`。

### 4.1 静态检查

```
$ python -m lwt --check $P
stdout: 'Check passed: 1 source file(s).\n'
stderr: ''
exit: 0
```

### 4.2 黑盒用例

| # | stdin（`printf` 字面量） | stdout repr | stderr | exit |
|---|---|---|---|---|
| T0 | `''`（空输入） | `'EMPTY\n'` | `''` | 0 |
| T1 | `'a b a\nb c\n'` | `'a 2\nb 2\nc 1\n'` | `''` | 0 |
| T2 | `'x x x y y z\n'` | `'x 3\ny 2\nz 1\n'` | `''` | 0 |
| T3 | `'b a\nc b\na c\nd\n'` | `'a 2\nb 2\nc 2\n'` | `''` | 0 |
| T4 | `'e a d b c f\ne a d b c\ne a b c\ne a\n'` | `'a 4\ne 4\nb 3\n'` | `''` | 0 |
| T5 | `'\n  \na b\n\n'`（空行/纯空格行） | `'a 1\nb 1\n'` | `''` | 0 |
| T6 | `'z A a\n'`（大小写） | `'A 1\na 1\nz 1\n'` | `''` | 0 |
| T7 | `'p q p'`（末行无 LF） | `'p 2\nq 1\n'` | `''` | 0 |
| T8 | `'m n m\r\nn\r\n'`（CRLF） | `'m 2\nn 2\n'` | `''` | 0 |
| T9 | `'z y x w v\n'` | `'v 1\nw 1\nx 1\n'` | `''` | 0 |
| T10 | `'a b b c c c\n'` | `'c 3\nb 2\na 1\n'` | `''` | 0 |
| T11 | `'m m n n o o p\n'` | `'m 2\nn 2\no 2\n'` | `''` | 0 |
| T12 | `'solo\n'` | `'solo 1\n'` | `''` | 0 |
| T13 | `'z é Z\n'`（码点序） | `'Z 1\nz 1\né 1\n'` | `''` | 0 |
| T14 | 1000 个不同词 `k0000..k0999`，第 i 词重复 `(i%7)+1` 次，乱序输入 | `'k0006 7\nk0013 7\nk0020 7\n'` | `''` | 0 |
| T15 | 200 个词 `w0000..w0199`，重复 `(i%3)+1` 次，逆序输入 | `'w0002 3\nw0005 3\nw0008 3\n'` | `''` | 0 |
| T16 | 10000 个不同词，各 1 次，逆序输入 | `'z00000 1\nz00001 1\nz00002 1\n'` | `''` | 0 |
| T17 | `'1 2 1 2 x\n'`（数字形词） | `'1 2\n2 2\nx 1\n'` | `''` | 0 |
| T18 | `'a,b a,b c!\n'` | `'a,b 2\nc! 1\n'` | `''` | 0 |
| T19 | `'\na a\n\nb\n\n'` | `'a 2\nb 1\n'` | `''` | 0 |

字节级核对（T1）：

```
$ printf 'a b a\nb c\n' | python -m lwt $P | od -c
0000000   a       2  \n   b       2  \n   c       1  \n
```

即每行 `word` + 单个空格 + 十进制计数 + LF，无额外输出，无 CR。

T14/T15 期望值手工推演：T14 中计数 7 的词为 `i%7==6` 的 `k0006,k0013,k0020,...`，按词升序前三个即测得结果；T15 中计数 3 的词为 `i%3==2` 的 `w0002,w0005,w0008`，结果一致。

### 4.3 性能（非功能，仅说明未超时）

```
$ time (python -m lwt $P < /tmp/lwt_in_1000.txt)   # 1000 个不同词
real 0m1.314s   exit 0
$ time (python -m lwt $P < /tmp/lwt_in_10k.txt)    # 10000 个不同词、10000 行
real 0m1.716s   exit 0
```

## 5. 失败与修订次数

- 功能失败：0 次。首版即通过 T0–T13 全部功能用例。
- 修订：1 次（性能修订，非语义缺陷）。首版用插入排序按「计数降序、词升序」全排序，1000 个不同词实测 `real 0m4.774s`，判断在更大输入下不可接受；改写为「3 轮线性选择 + `-1` 已选标记」，同一用例降至 `real 0m1.314s`，语义不变（T0–T13、T14 复跑结果与修订前完全一致）。
- 词法/语法/运行时错误：0 次（`--check` 与所有运行 stderr 均为空，退出码均为 0）。

## 6. 隔离声明

- 只阅读了 TASK.md 允许的四份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/concurrency.md`；未打开 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出，未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只用 `python -m lwt <file>`（含其 `--check` 子命令）运行程序，未用其他语言生成或改写程序输出。
- 写入范围仅为 `docs/agent-eval/submissions/dict-word-frequency-topk/`（`freq.lwt`、`report.md`）。测试输入通过 `printf` / 临时文件 `/tmp/lwt_in_*.txt` 经管道提供，测试脚本仅生成输入数据，不参与结果计算。
