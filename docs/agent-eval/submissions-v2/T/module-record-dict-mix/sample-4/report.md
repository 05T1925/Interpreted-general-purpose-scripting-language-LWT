# 盲测报告：module-record-dict-mix

## 1. 题目与结论

编写两个 LWT 文件：`lib.lwt` 只含函数声明并导出 `tax(amount) = amount * 8 / 100`；`mix.lwt` 用 `import "lib.lwt" as lib;` 导入，声明 `record Item {name, price};`，构造 `Item{name: "book", price: 200}`，把 `lib.tax(item.price)` 存入形态为 `dict{"book": 16}` 的映射，最后输出 `book 16`。程序不接收 CLI 参数，也不读 stdin。

实测结果：stdout 为 `book 16\n`（字节 `b'book 16\n'`），stderr 为空，退出码 0。一次通过，程序代码 0 次修订。

## 2. 依据文档与小节

| 文档 | 用于本任务的要点 |
|---|---|
| `docs/language-spec.md` §3 语法 | `import_decl` 只能位于文件开头；`module_file = { import_decl } { fn_decl } EOF`；`record` 只能作为顶层项且声明后必须写分号；`dict{...}` 是映射字面量、`Name{...}` 是记录构造；分号必需 |
| `docs/language-spec.md` §4.3 | 记录按声明顺序存储与显示；`r.f` 字段读取；字段名集合必须与声明一致 |
| `docs/language-spec.md` §4.4 | 映射键必须是整数或字符串，键值按源码从左到右求值；映射按插入顺序保存；`d[k]` 缺键读取是运行时错误 |
| `docs/language-spec.md` §5 | 顶层 `fn`/`record` 在普通语句执行前一次性登记，可前向调用；函数局部作用域外层是所属文件的变量根作用域 |
| `docs/language-spec.md` §6 | `str(value)` 返回显示字符串；`emit` 输出该字符串加一个 LF；stdout 只承载 `emit` 输出 |
| `docs/language-spec.md` §9.1–§9.4 | 库文件只可含开头 import 与顶层 `fn`，不得有顶层语句或 `record`；导入路径相对书写该声明的文件解析；调用必须写成 `alias.member(...)`；模块诊断路径相对入口目录 |
| `docs/developer-guide.md` §1「先运行」「CLI、参数和输入」「退出码和诊断」「运行前静态检查」 | 公开入口为 `python -m lwt SOURCE [-- ARGS...]`；建议先 `--check` 再执行；退出码 0/2/3/4 含义 |
| `docs/developer-guide.md` §2「多文件函数库」「数组、record 和 each」 | 入口用 `import "text_utils.lwt" as text;` + `text.clean(...)` 的限定调用形式；record 构造与字段访问写法 |
| `.agents/skills/lwt-app/SKILL.md`「工作流程」第 4–6 条 | 多文件程序用静态函数模块、import 路径相对声明文件、库只含顶部 import 与函数；先 `--check` 再按公开 CLI 运行并核对 stdout/stderr/退出码 |
| `examples/modules/main.lwt` | 入口文件结构范式：先 import，再 `record` 声明，再构造记录并调用 `stats.summarize(batch)` |

## 3. 程序文件

`docs/agent-eval/submissions/module-record-dict-mix/lib.lwt`：

```lwt
# 税率库：仅含函数声明，供入口文件 import 使用。
fn tax(amount) { return amount * 8 / 100; }
```

`docs/agent-eval/submissions/module-record-dict-mix/mix.lwt`：

```lwt
# 入口程序：导入函数库，构造 record，把计算结果存入 dict，最后输出 book 16。
import "lib.lwt" as lib;

record Item { name, price };

let item = Item{name: "book", price: 200};
let totals = dict{item.name: lib.tax(item.price)};
emit item.name + " " + str(totals[item.name]);
```

实现要点：

- `lib.lwt` 只有一条 `fn` 声明，没有顶层语句或 `record`，符合 §9.1 的 `module_file` 文法；函数体内是整数运算 `200 * 8 / 100 = 16`（§4.2 整数除法向负无穷取整，本例整除无余数）。
- `dict{item.name: lib.tax(item.price)}` 的键取 `item.name`（字符串 `"book"`），值取 `lib.tax(200)`（整数 `16`），构造结果即题目要求的 `dict{"book": 16}`；键值按 §4.4 逐项先键后值求值。
- 输出行由 `item.name` 与 `totals[item.name]` 拼接，取自实际记录与映射数据，而非直接硬编码 `book 16`；顶层字符串 `emit` 不带引号（§4.3）。

## 4. 自测命令与结果

工作目录为仓库根 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-module-record-dict-mix-s4`，全部通过公开入口 `python -m lwt` 执行。

### 4.1 静态检查

```text
$ python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
stdout: "Check passed: 2 source file(s).\n"
stderr: ""
exit:   0
```

检查器同时扫描入口与 `lib.lwt` 两个源文件，未报告未定义名字、调用参数数量或 record 构造字段问题。

### 4.2 正式运行

```text
$ python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
stdout repr: b'book 16\n'
stderr repr: b''
exit:        0
```

stdout 仅一行 `book 16`，与题目要求逐字节一致；stderr 为空，无诊断、无 Python traceback；未传入 `--` 之后的程序参数，也未提供 stdin，程序本身不读取二者。

## 5. 失败与修订次数

- 程序文件修订：0 次（首版即通过静态检查与正式运行，无需改动）。
- 运行失败：1 次环境性失败，非程序缺陷。第一次为图省事在提交子目录内直接执行 `python -m lwt mix.lwt`，因该目录不是仓库根、`lwt` 包不可导入而得到 `No module named lwt`、退出码 1；随后按文档要求回到仓库根、以相对入口路径重新执行即成功。该尝试未修改任何程序文件，也未修改解释器。

## 6. 隔离声明

- 只阅读了 TASK.md 允许的四份材料：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`examples/modules/main.lwt`；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 运行只用 `python -m lwt <file>` 公开入口（含 `--check`），未用其他语言生成或改写程序输出；报告中的 stdout 为对真实进程字节的直接 `repr`。
- 仅写入 `docs/agent-eval/submissions/module-record-dict-mix/` 下的 `lib.lwt`、`mix.lwt`、`report.md`；捕获输出用的临时文件 `run_out.bin`、`run_err.bin` 用完已删除。
