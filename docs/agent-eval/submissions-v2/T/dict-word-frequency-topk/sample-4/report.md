# 盲测报告：freq.lwt（词频 Top-3）

## 1. 产物

| 文件 | 说明 |
|---|---|
| `freq.lwt` | 程序文件（题目指定名），仅用 `python -m lwt` 运行 |
| `report.md` | 本报告 |

程序结构：`input()` 逐行读到 EOF → `split` 切词 → `dict` 计数 → `keys` 取词序 → 手写冒泡排序（次数降序、同次数单词升序）→ 最多 `emit` 3 行；无任何单词时输出 `EMPTY`。不调用 `args()`，不接收命令行参数。

## 2. 依据文档与对照小节

| 依据 | 用到的地方 |
|---|---|
| `docs/language-spec.md` §3 | 语法：`fn` 顶层声明、`while`/`each`/`when-otherwise`、`dict{}` 字面量、索引读写、`let` 与分号 |
| 同上 §4.2 | `<`、`!=`、`>` 严格类型比较；字符串按 Unicode 码点比较，用作同次数排序 |
| 同上 §4.4 | `dict` 键只能是整数或字符串、插入顺序、`d[k]` 缺键报错、`d[k] = v` 新键追加；`each` 不直接遍历映射，用 `keys(d)` |
| 同上 §5 | 块作用域、函数形参与局部绑定、`while` 每轮新作用域、`each` 浅快照 |
| 同上 §6 | `input()`（EOF 返回 `null`，剥行尾 LF/CRLF）、`split`（保留空字段）、`len`、`str`、`push`、`keys`、`has` |
| 同上 §7 | 成功退出码 0；stdout 只含 `emit` 输出，诊断走 stderr |
| `docs/developer-guide.md` §1 | CLI 形式 `python -m lwt SOURCE`，stdin/stdout 约定，退出码表 |
| 同上 §2、§3 | `let`/赋值、`when/otherwise`、数组索引、dict 与 `keys` 用法速查 |
| `.agents/skills/lwt-app/SKILL.md` | 工作流：先 `--check` 再公开 CLI 实测，核对 stdout/stderr/退出码 |
| `docs/concurrency.md` | 已阅读；本题为单任务流式统计，无需 `spawn`/通道，未使用 |

## 3. 自测命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-dict-word-frequency-topk-s4`（仓库根）。

### 3.1 静态检查

```
python -m lwt --check docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt
```

- stdout：`Check passed: 1 source file(s).\n`
- stderr：`''`
- 退出码：0

### 3.2 公开 CLI 运行（Python 子进程捕获原始输出，打印 `repr`）

命令模板：`python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`，stdin 为下表数据（均以 UTF-8 字节喂入）。

| 用例 | stdin | stdout（repr） | stderr | 退出码 |
|---|---|---|---:|---:|
| 空输入 | `` | `'EMPTY\n'` | `''` | 0 |
| 单词 | `apple\n` | `'apple 1\n'` | `''` | 0 |
| 三次并列 | `b a\nc a\nb c\n` | `'a 2\nb 2\nc 2\n'` | `''` | 0 |
| 多行混合 | `the cat sat\nthe cat\nsat the\nthe\n` | `'the 4\ncat 2\nsat 2\n'` | `''` | 0 |
| 五个单词取前三 | `a b c d e\na a a\nb b\n` | `'a 4\nb 3\nc 1\n'` | `''` | 0 |
| 全并列取前三 | `z y x w\n` | `'w 1\nx 1\ny 1\n'` | `''` | 0 |
| 大小写码点序 | `b A a B\n` | `'A 1\nB 1\na 1\n'` | `''` | 0 |
| 空行 | `\n\n` | `'EMPTY\n'` | `''` | 0 |
| 末行无 LF | `x y x`（无换行） | `'x 2\ny 1\n'` | `''` | 0 |
| CRLF | `a b\r\na\r\n` | `'a 2\nb 1\n'` | `''` | 0 |
| 50 词 | `w0 w1 ... w6` 循环 50 项 | `'w0 8\nw1 7\nw2 7\n'` | `''` | 0 |

shell 管道复现两条代表性用例（同一 CLI，无包装脚本）：

```
printf 'the cat sat\nthe cat\nsat the\nthe\n' | python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt
```

stdout：
```
the 4
cat 2
sat 2
```
退出码 0，stderr 为空。

```
printf '' | python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt
```

stdout：`EMPTY`，退出码 0，stderr 为空。

正确性要点核对：
- 次数降序、同次数按单词 Unicode 码点升序（`A` < `B` < `a`），与 §4.2 字符串比较一致；
- 前三行截断在循环条件 `i < 3` 处完成，不受并列影响；
- 空 stdin 与仅空行均无单词 → `EMPTY`；
- `input()` 已按 §6 剥除 CRLF，故 CRLF 输入不产生带回车的单词。

## 4. 失败与修订次数

- 程序修订次数：**0**。首次写入 `freq.lwt` 即通过 `--check` 与全部 11 条 CLI 用例，无语法/运行时错误，stderr 全程为空。
- 自测失败次数：**1**，且失败在**测试预期写错**而非程序：50 词用例中我手写的期望 `w1 8` 有误；`50 = 7*7 + 1`，余数 0 出现 8 次、其余余数各 7 次，实际输出 `'w0 8\nw1 7\nw2 7\n'` 才是正确结果，程序无需改动。
- 未使用 `attempt/recover` 兜底，也未针对测试数据特判；排序与计数均为通用逻辑。

## 5. 隔离声明

1. 仅阅读 TASK.md 允许的四份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/concurrency.md`；另读 `TASK.md` 本身。
2. 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。
3. 只用 `python -m lwt <file>`（含 `--check`）公开入口执行；未用其他语言生成程序输出或改写程序；Python 仅用于驱动 CLI 并格式化 `repr` 证据。
4. 只在本目录 `docs/agent-eval/submissions/dict-word-frequency-topk/` 下写入 `freq.lwt` 与 `report.md`。
