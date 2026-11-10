# wordcount.lwt 盲测提交报告

## 1. 任务与结论

任务：编写 `wordcount.lwt`，读取 `args()[0]` 指定文本文件（`read_text`），统计非空行数与这些行中的单词总数（单词以单个空格分隔），输出 `lines <L> words <W>`；文件末尾无换行也必须正确；不读 stdin。

结论：程序一次写成，静态检查与全部自测均通过（0 次失败、0 次修订）。

## 2. 依据文档与小节

只读了允许的 T 组文档：

| 文档 | 使用的小节 / 内容 |
|---|---|
| `docs/language-spec.md` | §3 语法（`fn`、`let`、`when`、`each`、`emit`、数组与下标）；§4.1 求值次序；§4.2 字符串 `+` 与 `!=`；§4.3 数组从 0 索引、`str` 显示规则；§5 函数只在顶层声明、函数作用域外层是全局、`each` 浅快照；§6 `args()`/`read_text`/`split`/`trim`/`str` 契约（`read_text` 剥 BOM、CRLF/CR→LF，路径相对进程 cwd；`split` 保留空字段）；§7 退出码；§8.3 参数与文件示例；§8.5 循环控制示例 |
| `docs/developer-guide.md` | §1 CLI 形式 `python -m lwt SOURCE [-- ARGS...]`、`--` 语义、退出码表、`--check` 先行的建议工作流；§2 文本与参数、内置函数表；§4 调试与验证 |
| `.agents/skills/lwt-app/SKILL.md` | 工作流程 1–7：先读指南/规范、提取输入输出与 CLI 契约、只用已支持能力、先 `--check` 再公开 CLI、核对 stdout/stderr/退出码 |

未查阅 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目或任何期望输出。

## 3. 实现要点

- `args()[0]` 取路径，`read_text` 读全文（CRLF/CR 已被规范为 LF，开头 BOM 已剥除）。
- `split(text, "\n")` 切行；文件末尾有换行时产生末尾空字段，末尾无换行时最后一行原样保留，两种情况都由“空行跳过”自然处理。
- 非空判定：`trim(line) != ""`，即空行与仅含 ASCII 空白的行都算空行。
- 单词计数：对非空行 `split(line, " ")`，只累加非空字段，从而容忍行首/行尾空格与连续空格。
- 输出：`"lines " + str(L) + " words " + str(W)`，由 `emit` 追加一个 LF。
- 只使用整数、字符串、布尔、数组、顶层 `fn`、`when`、`each`；未用 stdin、浮点、闭包或未写入规范的能力。

程序文件：`docs/agent-eval/submissions/cli-args-text-processing/program.lwt`
自测夹具：同目录 `_selftest/`（`multi/nonl/trailing/empty/blank/crlf`，非交付要求，仅用于复现）。

## 4. 命令与实测结果

均从仓库根目录执行（`read_text` 相对路径以进程 cwd 为基准）。

### 4.1 静态检查

```text
python -m lwt --check docs/agent-eval/submissions/cli-args-text-processing/program.lwt
```

- stdout：`'Check passed: 1 source file(s).\n'`
- stderr：空
- 退出码：0

### 4.2 运行自测

命令模板：

```text
python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- <fixture>
```

| 夹具 | 文件内容（`\n` 为实际换行） | stdout repr | stderr | 退出码 |
|---|---|---|---:|---:|
| `multi.txt` | `alpha beta\n\ngamma delta epsilon`（末尾无换行） | `'lines 2 words 5\n'` | 空 | 0 |
| `nonl.txt` | `one two\nthree`（末尾无换行） | `'lines 2 words 3\n'` | 空 | 0 |
| `trailing.txt` | `a b\nc d\n`（末尾有换行） | `'lines 2 words 4\n'` | 空 | 0 |
| `empty.txt` | 0 字节 | `'lines 0 words 0\n'` | 空 | 0 |
| `blank.txt` | `   \n\t\n solo  \n`（空白行 + 带首尾空格的行） | `'lines 1 words 1\n'` | 空 | 0 |
| `crlf.txt` | `x y\r\n\r\nz\r\n`（CRLF） | `'lines 2 words 3\n'` | 空 | 0 |

stdout 均以单个 LF 结束（`od -c` 核实，例：`l i n e s 2 w o r d s 5 \n`），未被任何状态文字污染。

### 4.3 stdin 隔离验证

```text
printf 'should_not_be_read\n' | python -m lwt docs/agent-eval/submissions/cli-args-text-processing/program.lwt -- docs/agent-eval/submissions/cli-args-text-processing/_selftest/nonl.txt
```

- stdout：`'lines 2 words 3\n'`（与无 stdin 时一致）
- stderr：空
- 退出码：0

### 4.4 汇总

- 运行次数：1 次 `--check` + 6 次夹具运行 + 1 次 stdin 注入运行。
- 失败次数：0；修订次数：0（首次 `--check` 与首次运行即符合预期，未修改过程序）。

## 5. 关键边界与取舍

1. 末尾无换行：`split` 的最后字段即末行，正常计数（`nonl.txt`、`multi.txt` 已验证）。
2. 末尾有换行：多出的空字段被“空行跳过”吸收，不虚增行数（`trailing.txt` 已验证）。
3. 空白行：`trim` 后为空即视为空行，不计入行数与单词数（`blank.txt` 已验证）。这是对“非空行”的简单一致解释。
4. 多空格：按单个空格切分后只计非空字段；题目约定单词以单个空格分隔，此处理对规范输入结果相同，对多余空格更稳健。
5. 编码/换行：依赖 `read_text` 的 BOM 剥除与 CRLF/CR 规范化（规范 §6），CRLF 夹具结果与 LF 相同。
6. 错误路径：题目只要求正常读取；路径缺失或不可读时由 `read_text` 产生运行时错误（退出码 3），未添加额外包装。

## 6. 隔离声明

- 只阅读了 `docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`。
- 未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 只使用公开入口 `python -m lwt`（`--check` 与普通执行）；未用其他语言生成输出或修改程序。
- 仓库内所有写入均限于 `docs/agent-eval/submissions/cli-args-text-processing/`（`program.lwt`、`report.md`、`_selftest/` 自测夹具）。
- 核对字节时曾用 shell 重定向把 stdout/stderr 暂存到系统临时目录（`/tmp`）的独立文件，已删除；未触碰仓库其他目录，也未读取其中内容。
