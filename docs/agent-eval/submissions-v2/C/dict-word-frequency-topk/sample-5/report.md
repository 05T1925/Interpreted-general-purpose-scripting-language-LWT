# 盲测报告：dict-word-frequency-topk（freq.lwt）

## 1. 依据文档

仅阅读 `docs/language-spec.md`（另按任务要求阅读 `TASK.md`）。实现依据：

- §2.1 词法（字符串、注释、标识符）；§3 语法（`while`、`each`、`when/otherwise`、`let`、`emit`、赋值表达式）。
- §4.1 求值与作用域；§4.2 整数/字符串比较与 `==`；§4.4 `dict` 字面量、插入顺序、`d[k]` 读取与赋值、身份相等。
- §5 块作用域、`each` 的浅快照、`while` 条件；§6 预置函数表：`input()`（EOF 返回 `null`，剥离行尾 LF/CRLF）、`split`、`len`、`keys`、`has`、`put`、`str`，以及 `emit` 输出规则。
- §7 诊断与退出码（成功 0，stderr 不混入 stdout）。

## 2. 程序

`docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`

- 用 `dict{}` 计数；`input()` 循环到 `null`；空行与空字段跳过。
- 无任何键时 `emit "EMPTY";`。
- 无内置排序，采用「三轮扫描选最大」：每轮在未被选中的键中按 `count` 降序、同数按单词 Unicode 码点升序选第一，最多输出 3 行；复杂度 O(3n)，不做全量排序。
- 输出 `word + " " + str(count)`，每行一次 `emit`。

## 3. 自测命令与结果

所有命令均在仓库根目录执行，程序路径为 `docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`，仅通过公开入口 `python -m lwt <file>` 运行。下表 stdin 由 `printf` 管道提供。

| # | stdin（shell 形式） | stdout repr | stderr | 退出码 |
|---|---|---|---|---:|---:|
| 1 | `printf ''` | `'EMPTY\n'` | `''`（0 字节） | 0 |
| 2 | `printf 'a b a c b a\nd c c\n'` | `'a 3\nc 3\nb 2\n'` | `''` | 0 |
| 3 | `printf 'z y x w v u\nz y x w\nz y x\nz y\nz'` | `'z 5\ny 4\nx 3\n'` | `''` | 0 |
| 4 | `printf 'e e e e\nd d c c b b a a\n'` | `'e 4\na 2\nb 2\n'` | `''` | 0 |
| 5 | `printf 'x'`（无行尾 LF） | `'x 1\n'` | `''` | 0 |
| 6 | `printf '中 a B b A 中\n'` | `'中 2\nA 1\nB 1\n'` | `''` | 0 |
| 7 | `printf '\n\na  a\n'`（空行、双空格） | `'a 2\n'` | `''` | 0 |
| 8 | `printf '\n\n'`（仅空行） | `'EMPTY\n'` | `''` | 0 |
| 9 | `printf 'b a\r\na b\r\nb c\r\n'`（CRLF） | `'b 3\na 2\nc 1\n'` | `''` | 0 |
| 10 | `printf 'k k k\n'` | `'k 3\n'` | `''` | 0 |
| 11 | `awk` 生成 5000 行 / 15000 词 / 5000 个不同词 | `'w1004 5\nw1009 5\nw1014 5\n'` | `''` | 0 |

补充实测：

- 用例 2 的输出经 `od -An -c` 核验为 `a   3 \n c   3 \n b   2 \n`，仅 LF，无 CR；退出码 0，stderr 0 字节。
- 用例 11 运行耗时约 1 秒（含解释器启动），验证 5000 键时线性选三不退化。

## 4. 边界核对

- 计数相同按单词升序：用例 2 的 `a/c`（均 3 次）与用例 4 的 `a/b`（均 2 次）均按码点升序；用例 6 验证 `A`(65) < `B`(66) < `a`(97) < `b`(98) < `中`(U+4E2D)，且次数优先。
- 只输出 3 行：用例 3、4、11 均截断，`d`/`c`/`v` 等未输出。
- EOF：`input()` 返回 `null` 结束循环；末行无 LF 也完整计数（用例 5）。
- 空输入与无有效单词均输出 `EMPTY`（用例 1、8）。
- 输出格式恒为单词 + 单个空格 + 十进制次数 + LF；`str` 对整数无额外符号。

## 5. 失败与修订

- 测试失败次数：0。最终版本 11 个用例全部通过，stderr 均为空、退出码均为 0。
- 修订次数：1。v1 对全部键做选择排序（O(n²)）并通过用例 1–9；为避免大词表退化，提交前重写为「三轮选最大 + 已选集合」的 O(3n) 版本（v2），重跑全部用例通过。未出现语法/运行时错误修复。

## 6. 隔离声明

- 只阅读 `TASK.md` 与允许的 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。
- 只写入本目录 `docs/agent-eval/submissions/dict-word-frequency-topk/` 下的 `freq.lwt` 与本报告；未修改仓库其他文件。
- 只用 `python -m lwt <file>` 运行程序；未用其他语言实现或改写程序逻辑，`awk`/`od`/`wc` 仅用于生成测试输入与检查输出字节。
