# freq.lwt 盲测报告

## 1. 程序与运行方式

- 程序文件：`freq.lwt`（本目录）
- 运行入口：`python -m lwt <源文件>`；stdin 提供输入，EOF 结束；不使用命令行参数。
- 实现要点：用 `dict` 统计词频（§4.4），`input()` 读到 `null` 为止（§6），再用 `keys`/`get`/`delete` 做 3 轮选择：每轮取「次数最大、同次数单词码点序最小」者并 `emit word + " " + str(count)`（§4.2 字符串比较、§4.3 显示规则、§6 `str`）。无任何词时输出 `EMPTY`。空行与 `split` 产生的空字段按“非单词”跳过。

## 2. 依据文档与小节

仅依据 `docs/language-spec.md`（LWT 0.3.0 正式语言规范）：

- §2.1 词法与注释：`#` 注释、标识符、字符串与转义。
- §3 语法：`let`、赋值、`when/otherwise`、`while`、`each`、`dict{...}`、调用与后置索引、分号规则。
- §4.2 比较：整数比较、字符串按 Unicode 码点逐位比较（用于同次数单词升序）。
- §4.3 显示：`str(整数)` 为十进制；`emit` 追加一个 LF。
- §4.4 映射：`dict{}` 可变、字符串键合法、插入顺序、缺键读取报错（故用 `get` 带默认值）。
- §5 作用域与控制流：块作用域、`let` 不可同作用域重声明、循环体每轮新作用域、赋值修改最近可见绑定。
- §6 预置能力：`input()`（EOF 返回 `null`，移除行尾 LF/CRLF）、`split`（分隔符非空）、`len`（支持映射）、`keys`/`values`/`get`/`put`/`has`/`delete`、`str`；stdout 仅承载 `emit`。
- §7 退出码：成功为 0，诊断只写 stderr。
- §8.3、§8.7 的输入/映射示例作为用法佐证。

## 3. 关键命令与实测结果

工作目录为仓库根目录，`F=docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`。

| # | stdin | 命令 | stdout（Python repr） | stderr | 退出码 |
|---|---|---|---|---|---|
| T1 | `a b a\nc b a\n` | `printf 'a b a\nc b a\n' \| python -m lwt "$F"` | `'a 3\nb 2\nc 1\n'` | 空 | 0 |
| T2 | `b a c\nd d c\ne e e\n` | 同上 | `'e 3\nc 2\nd 2\n'` | 空 | 0 |
| T3 | 空（立即 EOF） | `printf '' \| python -m lwt "$F"` | `'EMPTY\n'` | 空 | 0 |
| T4 | `hello`（无行尾 LF） | `printf 'hello' \| python -m lwt "$F"` | `'hello 1\n'` | 空 | 0 |
| T5 | `β α β\n` | 同上 | `'β 2\nα 1\n'` | 空 | 0 |
| T6 | `\n\na a\n` | 同上 | `'a 2\n'` | 空 | 0 |
| T7 | `d c b a\n` | 同上 | `'a 1\nb 1\nc 1\n'` | 空 | 0 |
| T8 | `d c\n`（插入序与字典序相反） | 同上 | `'c 1\nd 1\n'` | 空 | 0 |
| T9 | `k k\nm\n`（不足 3 个不同词） | 同上 | `'k 2\nm 1\n'` | 空 | 0 |
| T10 | `a b\r\na\r\n`（CRLF） | 同上 | `'a 2\nb 1\n'` | 空 | 0 |
| T11 | `a Z\n`（码点序 `Z` < `a`） | 同上 | `'Z 1\na 1\n'` | 空 | 0 |

说明：T2 验证次数降序与同次数升序（`c` 在 `d` 前）；T7/T8 验证同次数时按单词升序而非插入序；T3 验证无输入输出 `EMPTY`；T10 验证 `input()` 的 CRLF 处理；T11 验证大小写按码点比较。

## 4. 失败与修订

- 编译/运行失败：0 次。
- 语义失败（与题目预期不符）：0 次。
- 代码修订：0 次（首版通过全部用例）。

## 5. 隔离声明

- 仅阅读了 `TASK.md` 与允许的 `docs/language-spec.md`；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网；未访问桌面上的 `大作业` 目录。
- 仅用 `python -m lwt <file>` 公开入口运行程序；未用其他语言生成/改写程序或其输出。
- 仅在本目录 `docs/agent-eval/submissions/dict-word-frequency-topk/` 下写入了 `freq.lwt` 与 `report.md`。
