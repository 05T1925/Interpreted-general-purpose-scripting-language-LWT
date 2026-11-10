# report.md — freq.lwt（C 组：仅语言规范）

## 1. 题目与产物

- 题目：从 stdin 逐行读取单词（单空格分隔），统计词频，按次数降序、同次数按单词升序输出前 3 行，格式 `word count`；无输入输出 `EMPTY`；用 `input()` 读 stdin，EOF 结束。
- 程序文件：`docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`
- 本报告：`docs/agent-eval/submissions/dict-word-frequency-topk/report.md`

## 2. 依据文档与小节

唯一阅读的规范文档为 `docs/language-spec.md`（C 组仅允许语言规范）。实现依据：

| 规范小节 | 用到的内容 |
|---|---|
| §2.1 词法 | 标识符规则、保留字表（未使用保留字作标识符）、`#` 注释 |
| §3 语法 | `fn` 只能顶层；`while`/`each`/`when-otherwise`/`break`/`continue` 的语法与块后不写分号；`emit` 语句；`dict{...}` 字面量；循环外不能用 `break`/`continue` |
| §4.4 映射 | `dict{}` 构造、字符串键、`get`/`put`/`has`/`keys` 的语义、插入顺序、缺键读取报错故必须用 `get` 带默认值 |
| §4.2、§4.3 | 字符串按 Unicode 码点逐位比较（用于同次数升序）；`+` 仅同为字符串或同为整数；`str(int)` 显示为十进制 |
| §5 作用域与控制流 | 顶层 `fn` 先登记可前向调用；块创建新作用域、内层赋值修改最近可见绑定；`each` 先对数组求值并按元素顺序迭代；`continue` 进入下一轮 |
| §6 预置能力 | `input()` 返回行字符串、EOF 返回 `null`、剥离行尾 LF 及其前 CR；`split(text, " ")` 保留空字段；`len`；`get(d,k,default)`；`put`；`has`；`keys`；`str`；`emit` 输出后接 LF |
| §7 错误与退出码 | 正常执行退出码 0；错误信息写 stderr；stdout 只承载 `emit` |
| §8.7 | 映射插入顺序与 `each (k in keys(d))` 的推荐遍历方式（本程序用 `each` 遍历键数组） |

## 3. 实现要点

1. 用 `dict{}` 累计词频；`put(counts, w, get(counts, w, 0) + 1)` 完成“首次插入 / 原位自增”。
2. 读取循环 `while (true) { let line = input(); when (line == null) { break; } ... }`，靠 EOF 的 `null` 结束（§6）。
3. `split(line, " ")` 后跳过空字段：题目承诺单词以单个空格分隔，跳过空字段使空行、行首尾空白、连续空格都不会产生伪单词。
4. 排序不做全量排序：`pick_best` 线性扫描未被选中的键，按（次数降序，单词码点升序）选出当前最优；最多选 3 次，复杂度 O(3·n)，避免大输入下 O(n²) 插入排序。
5. 无任何单词（含 stdin 立即 EOF、仅空行）时输出 `EMPTY`；否则输出前 `min(3, 不同单词数)` 行。
6. 不读取 `args()`，无命令行参数依赖；未使用 `spawn`/`attempt` 等无关特性。

## 4. 自测（真实 CLI）

工作目录固定为题目根目录 `C:/Users/28641/AppData/Local/Temp/lwt-s48-C-dict-word-frequency-topk-s1`，全部通过 `python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt` 运行，输入由 shell 管道提供（仅用作 stdin 测试数据）。

### T1 空输入（stdin 立即 EOF）
命令：`printf '' | python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`
- stdout repr：`'EMPTY\n'`
- stderr：空
- 退出码：0

### T2 基本计数与同次数并列
stdin：`the quick brown fox\nthe lazy dog\nthe fox jumps\ndog sleeps\n`
- stdout repr：`'the 3\ndog 2\nfox 2\n'`（the 3；dog/fox 同为 2，按单词升序 d<f）
- stderr：空；退出码：0

### T3 不同单词数少于 3
stdin：`b a\na\n`
- stdout repr：`'a 2\nb 1\n'`
- stderr：空；退出码：0

### T4 全部同次数（纯字典序取前三）
stdin：`z y x w v\n`
- stdout repr：`'v 1\nw 1\nx 1\n'`
- stderr：空；退出码：0

### T5 Unicode 单词（码点序）
stdin：`猫 狗 猫\n狗 鸟\n`
- stdout repr：`'狗 2\n猫 2\n鸟 1\n'`（U+72D7 < U+732B < U+9E1F）
- stderr：空；退出码：0

### T6 CRLF 输入（`input()` 剥除行尾 CR）
stdin：`a b\r\na c\r\n`
- stdout repr：`'a 2\nb 1\nc 1\n'`
- stderr：空；退出码：0

### T7 仅空行
stdin：`\n\n\n`
- stdout repr：`'EMPTY\n'`
- stderr：空；退出码：0

### T8 空行夹在中间 + 末行无换行
stdin：`a b\n\nb`（末行无 LF，按 §6 原样返回）
- stdout repr：`'b 2\na 1\n'`
- stderr：空；退出码：0

### T9 输出字节校验（格式为单个空格 + LF）
stdin：`a b\nb c\na b\n`
命令：`... | python -m lwt .../freq.lwt | od -c`
- od 输出：`0000000   b       3  \n   a       2  \n   c       1  \n`
- stderr：空；退出码：0

### T10 规模与性能（4000 行、4000 个不同单词，次数全为 2）
命令：`seq 1 4000 | awk '{printf "w%s w%s\n", $1, $1}' | python -m lwt docs/agent-eval/submissions/dict-word-frequency-topk/freq.lwt`
- stdout repr：`'w1 2\nw10 2\nw100 2\n'`（字符串升序，非数值序）
- stderr：空；退出码：0；无卡顿（线性扫描三次的复杂度）

## 5. 失败与修订

- 自测运行的 10 组用例全部一次通过：失败 0 次，修订 0 次，`freq.lwt` 首版即终版。
- 唯一的设计前调整（写码前，非失败修订）：原本考虑用插入排序全量排序，评估大输入 O(n²) 风险后改为“最多三轮线性选优”，语义不变、复杂度降为 O(3n)。

## 6. 隔离声明

- 只阅读了 `TASK.md` 与 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 程序全部用 `python -m lwt <file>` 公开入口运行，未用其他语言生成或改写程序输出；shell（printf/seq/awk/od）仅用于构造 stdin 测试数据与查看字节。
- 写入范围：仅 `docs/agent-eval/submissions/dict-word-frequency-topk/` 下的 `freq.lwt`、`report.md`。
- 需说明的轻微越界：压测时曾在系统临时目录生成 `/tmp/lwt_freq_big.txt` 作为 stdin 数据（未参与任何输出对照），随即删除，之后改为纯管道；除此之外未在提交目录外留下任何文件。
