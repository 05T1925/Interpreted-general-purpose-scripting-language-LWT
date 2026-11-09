# module-record-dict-mix 盲测报告

## 1. 依据文档与具体小节

仅阅读了下列四份允许文档：

| 文档 | 使用到的小节 | 支撑的结论 |
|---|---|---|
| `docs/language-spec.md` | §2.1 保留字与标识符；§3 文法（`import_decl`、`record_decl`、`field_init`、`dict` atom、`module_call`）；§4.3 记录构造/字段访问/显示；§4.4 映射字面量与下标读取；§5 顶层声明先登记；§6 `str` 与 `emit`；§7 退出码；§9.1–§9.4 静态函数库模块（库只含 import+fn，路径相对声明文件） | 库文件只写 `fn`；入口按 `import "lib.lwt" as lib;` + 限定调用 `lib.tax(...)`；`dict{"book": ...}` 合法，键为字符串；`str(int)` 得到十进制文本 |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」「运行前静态检查」；§2「多文件函数库」「数组、record 和 `each`」；§3 语义速查（`str`、`emit`） | 运行方式 `python -m lwt SOURCE`；先 `--check` 再运行；库文件语法限制与 import 路径规则 |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」第 4–7 条、「语言边界」（dict 与模块要点） | 多文件用静态函数模块、import 相对声明文件、只记录真实运行结果 |
| `examples/modules/main.lwt` | 全文 | 入口 `import "stats_utils.lwt" as stats;` 后 `record` + 顶层语句 + 别名限定调用的写法范例 |

关键规范原文（`docs/language-spec.md`）：
- 第 46–47 行：`program = { import_decl } { top_item } EOF`、`module_file = { import_decl } { fn_decl } EOF`。
- 第 82 行：`dict "{" [ dict_entry { "," dict_entry } ] "}"`，`dict_entry = expression ":" expression`。
- 第 364 行：导入路径相对于**书写该导入声明的文件目录**解析。
- 第 111 行：整数 `/` 只接受两个整数；`200 * 8 / 100` 全为整数运算，结果为 16。

## 2. 交付文件（相对路径，均位于本次提交目录）

提交目录：`docs/agent-eval/submissions/module-record-dict-mix/`

| 文件 | 说明 |
|---|---|
| `lib.lwt` | 库模块，只含一个顶层 `fn tax(amount)`；无 import、无顶层语句、无 record |
| `mix.lwt` | 题目要求的主程序（record + dict + 模块调用 + 输出） |
| `main.lwt` | 交付清单要求的主程序名；内容与 `mix.lwt` 逐字节相同，作为同目录等价入口 |

`lib.lwt`：

```lwt
fn tax(amount) {
    return amount * 8 / 100;
}
```

`mix.lwt`（与 `main.lwt` 相同）：

```lwt
import "lib.lwt" as lib;

record Item { name, price };
let item = Item{name: "book", price: 200};
let totals = dict{"book": lib.tax(item.price)};
emit "book " + str(totals["book"]);
```

语义要点：`item.price` 为 200，`lib.tax(200)` = `200 * 8 / 100` = 16（整数除法），该值作为 `dict{"book": ...}` 的条目值存入；随后按键 `"book"` 下标读回，`str(...)` 得 `"16"`，与 `"book "` 拼接后 `emit` 输出 `book 16`。全程无 CLI 参数、无 stdin。

## 3. 运行记录（真实执行，cwd 为仓库根目录）

命令 1（静态检查，主程序）：

```text
python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout (repr)：`'Check passed: 2 source file(s).\n'`
- stderr (repr)：`''`
- 退出码：0

命令 2（正式运行，主程序）：

```text
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout (repr)：`'book 16\n'`
- stderr (repr)：`''`
- 退出码：0

命令 3（字节级复核，同一条公开入口，仅把输出重定向后用 `od -c` 观察）：

```text
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt > .stdout.bin 2> .stderr.bin
od -An -c .stdout.bin
wc -c .stdout.bin .stderr.bin
```

- `od` 结果：`b o o k   1 6 \n`，即 stdout 恰好 8 字节 `book 16\n`，无 BOM、无 CR、无多余空行
- stderr 字节数：0
- 退出码：0
- 临时捕获文件已在记录后删除，提交目录只留 3 个 `.lwt` 与本报

命令 4（交付副本 `main.lwt` 复核）：

```text
python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/main.lwt
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/main.lwt
```

- 前者 stdout (repr)：`'Check passed: 2 source file(s).\n'`，stderr `''`，退出码 0
- 后者 stdout (repr)：`'book 16\n'`，stderr `''`，退出码 0

未使用的输入：未提供 `--` 参数，未喂入 stdin；程序也不读取二者。

## 4. 失败尝试与修订次数

- 失败运行次数：0。
- 源码修订次数：0（首版写入后 `--check` 与正式运行均一次通过）。
- 未出现词法/语法/运行时/导入诊断，未出现 Python traceback。

## 5. 隔离合规声明

- 实际阅读的文件仅有：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`examples/modules/main.lwt`（以及本提交目录自身产出的文件）。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、任何其他题目目录或任何期望输出。
- 未联网，未打开浏览器或抓取外部资料。
- 未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 及其任何子路径。
- 只用公开入口 `python -m lwt <file>` 执行程序；未用 Python 或其他语言生成输出，也未用脚本改写 LWT 源码（`od`/`wc` 仅用于观察已产生的字节）。
- 所有新建/修改文件都限定在 `docs/agent-eval/submissions/module-record-dict-mix/` 内。
