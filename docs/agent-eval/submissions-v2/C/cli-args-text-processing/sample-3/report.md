# wordcount.lwt 盲测报告（C 组：仅语言规范）

## 1. 任务与交付

- 程序：`wordcount.lwt`（本目录）。
- 行为：读取 `args()[0]` 指定文本文件（`read_text`），统计非空行数 L 与非空行中的单词总数 W，输出一行 `lines <L> words <W>`；程序不读 stdin。
- 调用形式：`python -m lwt wordcount.lwt -- <path>`。

## 2. 依据文档与小节

仅阅读 `docs/language-spec.md`，用到的规范点：

| 规范位置 | 用于 |
|---|---|
| §2.1 编码与空白 | 源文件 UTF-8；`#` 注释；字符串仅支持 `\\ \" \n \t` 转义 |
| §3 语法 | 顶层 `let`、`each`、`when` 语句；块后不加分号；`args()`/`split`/`trim` 均为普通命名调用 |
| §4.1 求值与作用域 | `let` 初始化后才可见；数组按引用传递 |
| §4.2 运算 | `+` 仅整数或双字符串；`>` 仅整数/字符串；`==` 全类型有定义 |
| §5 作用域与控制流 | 块每次进入新作用域，块内赋值修改最近可见外层绑定；`each` 对数组做元素浅快照；`when` 要求布尔 |
| §6 预置能力 | `args()` 只含 `--` 之后实参且每次返回新数组；`read_text` 剥 BOM、CRLF/CR 统一为 LF；`split(text, sep)` 保留空字段；`trim` 只删两端 ASCII 空白；`len` 按码点；`str` 显示整数 |
| §7 错误与退出码 | 成功 0；运行时错误 3；诊断写 stderr，stdout 只承载 `emit` |

## 3. 程序实现要点

```lwt
let path = args()[0];
let text = read_text(path);
let all_lines = split(text, "\n");
let line_count = 0;
let word_count = 0;
each (raw in all_lines) {
    let line = trim(raw);
    when (len(line) > 0) {
        line_count = line_count + 1;
        each (word in split(line, " ")) {
            when (len(word) > 0) { word_count = word_count + 1; }
        }
    }
}
emit "lines " + str(line_count) + " words " + str(word_count);
```

语义决策：

1. 以 `split(text, "\n")` 切行。`read_text` 已把 CRLF/CR 规范化为 LF，故 CRLF 文件同样正确。
2. “非空行”定义为 `trim` 后长度大于 0 的行：纯空行与仅含空格/TAB 的行均不计行、不计词。
3. 单词按规范约定的单个空格切分；对切分出的空字段不再计数（保证多空格输入不产生伪词），合法输入（单空格分隔）下与直接 `len(split(...))` 等价。
4. 文件末尾无换行时，`split` 末元素即最后一行文本，仍被统计；有末尾换行时产生的末尾空元素被 `trim` 判空跳过，不会多算行。
5. 不调用 `input()`，不读取 stdin。

## 4. 运行命令与观察结果

全部命令在仓库根目录执行，源文件与测试数据均位于 `docs/agent-eval/submissions/cli-args-text-processing/`。
测试数据文件：`t_trailing.txt`（末尾换行，含空行与缩进行）、`t_nonl.txt`（末尾无换行）、`t_empty.txt`（0 字节）、`t_blank.txt`（仅空白行）、`t_spaces.txt`（多空格/尾部空格）、`t_single.txt`（单行无换行）、`t_crlf.txt`（CRLF）、`t_bom.txt`（UTF-8 BOM）、`t_big.txt`（1000 行，500 行非空）。

命令模板：

```text
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt -- docs/agent-eval/submissions/cli-args-text-processing/<file>
```

| 用例 | stdout（Python repr） | stderr | 退出码 |
|---|---|---|---|
| t_trailing.txt | `'lines 2 words 5\n'` | 空 | 0 |
| t_nonl.txt | `'lines 2 words 5\n'` | 空 | 0 |
| t_empty.txt | `'lines 0 words 0\n'` | 空 | 0 |
| t_blank.txt | `'lines 0 words 0\n'` | 空 | 0 |
| t_spaces.txt | `'lines 2 words 4\n'` | 空 | 0 |
| t_single.txt | `'lines 1 words 1\n'` | 空 | 0 |
| t_crlf.txt | `'lines 2 words 3\n'` | 空 | 0 |
| t_bom.txt | `'lines 2 words 3\n'` | 空 | 0 |
| t_big.txt | `'lines 500 words 1000\n'` | 空 | 0 |

字节级核对（`od -An -c`，t_nonl.txt）：`l i n e s   2   w o r d s   5 \n`，即输出恰为一行、以单个 LF 结束、无 CR、无额外提示。

错误路径（非题目要求，仅确认诊断契约）：

| 场景 | 命令尾部 | stdout | stderr | 退出码 |
|---|---|---|---|---|
| 缺少程序实参 | `--` | `''` | `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt:3:18: RuntimeError: array index is out of range\n` | 3 |
| 文件不存在 | `-- no_such_file_xyz.txt` | `''` | `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt:4:12: RuntimeError: could not read text file\n` | 3 |

stdout 在两种错误下均为空，符合“stdout 只承载 emit 输出”的约定。

## 5. 失败与修订

- 修订次数：1 次。
- 首版用 `word_count + len(split(line, " "))`。在 `t_spaces.txt`（`"  a  b"`）上得到 `'lines 2 words 5\n'`，把连续空格切出的空字段计成了单词，判定为不符合“单词”语义。
- 修订：改为遍历切分结果、只累计非空字段。复测 `t_spaces.txt` 得 `'lines 2 words 4\n'`，其余 8 个用例输出不变。
- 修订后最终 9 个功能用例全部通过（退出码 0、stderr 为空、输出格式与预期一致），未再出现失败。

## 6. 隔离声明

- 只阅读了 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只通过公开入口 `python -m lwt <source> -- <args>` 运行；未用其他语言生成或改写程序输出。
- 写入范围仅限 `docs/agent-eval/submissions/cli-args-text-processing/`（程序、报告与测试数据文件）。
