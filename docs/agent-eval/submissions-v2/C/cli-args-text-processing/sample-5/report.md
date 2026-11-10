# wordcount.lwt 实现报告（C 组：仅语言规范）

## 1. 任务与交付

按 TASK.md 编写 `wordcount.lwt`：通过 `args()[0]` 取路径，用 `read_text` 读入文本，统计非空行数与非空行中的单词总数（单词以单个空格分隔），输出一行 `lines <L> words <W>`。不读取 stdin，末尾无换行也必须正确。

交付文件：

- `wordcount.lwt`：LWT 源程序
- `fixtures/*.txt`：自测夹具（可在报告命令中复现）
- `report.md`：本报告

## 2. 依据文档与小节

仅依据 `docs/language-spec.md`：

| 用途 | 依据小节 |
|---|---|
| `args()` 只含 `--` 之后的程序实参 | §6 预置能力表、§8.3 |
| `read_text` 读取 UTF-8、剥除开头 BOM、CRLF/CR 规范化为 LF；失败为运行时错误（码 3） | §6、§7 |
| `split(text, sep)` 保留首尾及连续分隔产生的空字段；`split("", ",")` 为 `[""]` | §6 |
| `trim` 只删除两端 ASCII 空白 | §6 |
| `each` 遍历数组浅快照；`when` 要求严格布尔；`break` 之外的自然结束 | §5、§4.2 |
| 变量赋值、块作用域与最近可见绑定 | §4.1、§5 |
| `+` 仅整数求和或字符串拼接；`str` 返回可显示字符串；`emit` 追加 LF | §4.2、§4.3、§6 |
| `len` 对数组计数 | §6 |
| 退出码：成功 0、RuntimeError 3 | §7 |

## 3. 算法与关键取舍

1. `let lines = split(content, "\n");`——以 LF 切分。文件末尾有换行时 `split` 会产生末尾空字段，按“非空行”规则被跳过；无换行时不多产生字段，因此末尾换行有无结果一致。
2. 每行先 `trim` 再判空：纯空白行（如 `"   "`）视为空行，不计数。规范 §6 明确 `trim` 只删两端 ASCII 空白，故行内空格不受影响。
3. 单词计数：对去两端空白后的行 `split(line, " ")`，再逐个跳过空字段累加。这样连续空格不会被误计为单词；题目已说明单词以单个空格分隔，正常文本与“按空白分词”一致。
4. 结果用字符串拼接 `"lines " + str(L) + " words " + str(W)` 一次 `emit`，输出恰为一行并以 LF 结束。

程序全文（`wordcount.lwt`）：

```lwt
# wordcount.lwt: 统计非空行数与非空行中的单词总数
let path = args()[0];
let content = read_text(path);
let lines = split(content, "\n");
let line_count = 0;
let word_count = 0;
each (raw_line in lines) {
    let line = trim(raw_line);
    when (line != "") {
        line_count = line_count + 1;
        each (word in split(line, " ")) {
            when (word != "") {
                word_count = word_count + 1;
            }
        }
    }
}
emit "lines " + str(line_count) + " words " + str(word_count);
```

## 4. 命令与实测结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-cli-args-text-processing-s5`（下表中 `S=docs/agent-eval/submissions/cli-args-text-processing`）。所有运行均只用公开入口 `python -m lwt`。

命令模板：

```text
python -m lwt $S/wordcount.lwt -- $S/fixtures/<name>.txt
```

| # | 夹具 | 内容（`\n` 为真实换行） | stdout（repr） | stderr | 退出码 |
|---|---|---|---|---:|---:|
| 1 | basic.txt | `hello world\nsecond line\n\nthird\n` | `'lines 3 words 5\n'` | 空 | 0 |
| 2 | no_trailing_newline.txt | `alpha beta\ngamma` | `'lines 2 words 3\n'` | 空 | 0 |
| 3 | empty.txt | 空文件 | `'lines 0 words 0\n'` | 空 | 0 |
| 4 | blank_only.txt | `\n\n\n` | `'lines 0 words 0\n'` | 空 | 0 |
| 5 | extra_spaces.txt | `a  b\n   \nc d` | `'lines 2 words 4\n'` | 空 | 0 |
| 6 | crlf.txt | `x y\r\nz\r\n` | `'lines 2 words 3\n'` | 空 | 0 |
| 7 | unicode.txt | `中文 测试\n\n第二行 here\n` | `'lines 2 words 4\n'` | 空 | 0 |
| 8 | with space.txt | `one two\nthree`（路径含空格） | `'lines 2 words 3\n'` | 空 | 0 |
| 9 | one_trailing_nl.txt | `a\n` | `'lines 1 words 1\n'` | 空 | 0 |
| 10 | single_no_nl.txt | `a` | `'lines 1 words 1\n'` | 空 | 0 |
| 11 | one_line_multi_nl.txt | `a\n\n` | `'lines 1 words 1\n'` | 空 | 0 |

补充验证：

- stdout 字节级检查：`python -m lwt $S/wordcount.lwt -- $S/fixtures/basic.txt | od -c` 得到 `lines 3 words 5 \n`，仅一个 LF，无多余空白。
- stdin 隔离：`echo "ignored stdin" | python -m lwt $S/wordcount.lwt -- $S/fixtures/basic.txt` 仍输出 `'lines 3 words 5\n'`、退出码 0，说明程序不消费 stdin。
- 错误路径（非题目要求）：`python -m lwt $S/wordcount.lwt -- $S/fixtures/nope.txt` → stdout 空，stderr 为 `docs/agent-eval/submissions/cli-args-text-processing/wordcount.lwt:3:15: RuntimeError: could not read text file`，退出码 3，符合 §6/§7 的 `read_text` 失败语义。

## 5. 失败与修订

- 自测运行共 13 次（表 1–11 + od 1 次 + stdin 1 次；错误路径另 1 次），全部符合预期。
- 失败次数：0。修订次数：0（首版程序一次通过，未改代码）。
- 未使用 `--check`、`--profile` 等其他入口；未用其他语言生成或改写输出。

## 6. 隔离声明

- 仅阅读了 `TASK.md` 和 `docs/language-spec.md`；仅用 `ls` 查看了目录/文件名，未打开 `lwt/`、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/` 或其他题目目录、任何期望输出，未联网。
- 未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 所有写入均限于 `docs/agent-eval/submissions/cli-args-text-processing/`（程序、夹具、本报告）。
- 所有执行均通过 `python -m lwt <file>` 公开入口完成。
