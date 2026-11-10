# module-record-dict-mix 盲测报告

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-module-record-dict-mix-s1`

## 1. 依据的文档与具体小节

| 文档 | 具体小节 | 用于决定 |
|---|---|---|
| `docs/language-spec.md` | §3 语法（`program` / `module_file` / `import_decl` / `record_decl` / `fn_decl` / `atom` 中的 `dict "{" ... "}"` 与 `IDENT "{" field_init "}"`） | 入口文件结构、库文件只能有 `import` + `fn`、`import "lib.lwt" as lib;` 形式、`record Item {name, price};` 与 `Item{name: ..., price: ...}` 构造、末尾分号 |
| `docs/language-spec.md` | §4.3 数组、记录和显示 | record 构造字段集合须与声明完全一致、`r.f` 字段读取、`+` 只在两个整数/两个字符串间有效（故需 `str()`） |
| `docs/language-spec.md` | §4.4 映射（S42） | `dict{ key: value }` 只能以 `dict` 关键字构造、键须为字符串或整数、`d[k]` 读取缺键报错 |
| `docs/language-spec.md` | §4.2 运算与比较 | 整数 `/` 向负无穷取整，`200 * 8 / 100` 得整数 16（非浮点，无隐式转换） |
| `docs/language-spec.md` | §6 预置能力与 CLI | `str(value)` 显示规则、`python -m lwt <source-path>` 命令形式、stdout 只含 `emit` 输出且成功不打印状态 |
| `docs/language-spec.md` | §9.1–§9.3 静态函数库模块 | 库文件语法限制、导入路径相对声明文件解析、`lib.tax(...)` 限定调用、模块函数独立命名空间 |
| `docs/language-spec.md` | §7 错误与退出码 | 0/2/3/4 语义，用于核对自测退出码 |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」「运行前静态检查」 | 先 `--check` 再普通执行的工作流；`SOURCE` 相对进程 cwd；无 `--` 时不传参数 |
| `docs/developer-guide.md` | §2「多文件函数库」 | 导入写在入口开头、别名限定调用、库文件不得有顶层执行语句或 `record` |
| `.agents/skills/lwt-app/SKILL.md` | 「工作流程」第 4–7 条；「语言边界」S42 dict 要点 | 多文件用静态模块、只记录真实命令与结果、dict 键类型与插入序、不得使用未规范特性 |
| `examples/modules/main.lwt` | 全文（4 行） | `import "…" as alias;` + `record` 声明 + 构造并调用模块函数的实际写法范例 |

## 2. 交付脚本（相对工作目录的路径）

- `docs/agent-eval/submissions/module-record-dict-mix/main.lwt`（主入口，交付清单要求名）
- `docs/agent-eval/submissions/module-record-dict-mix/lib.lwt`（库：仅 `fn tax` 声明）
- `docs/agent-eval/submissions/module-record-dict-mix/mix.lwt`（与 `main.lwt` 内容逐字相同；因题目正文称主程序为 `mix.lwt`，交付清单称 `main.lwt`，两者并存以确保任一路径可用）

`lib.lwt`：

```lwt
# 静态函数库：只含顶部 import（此处无）与顶层 fn 声明（规范 §9.1）
fn tax(amount) { return amount * 8 / 100; }
```

`main.lwt`（`mix.lwt` 同）：

```lwt
import "lib.lwt" as lib;

record Item { name, price };
let item = Item{name: "book", price: 200};
let ledger = dict{"book": lib.tax(item.price)};
emit item.name + " " + str(ledger[item.name]);
```

要点：`lib.tax(item.price)` 求值为 `200 * 8 / 100 = 16`，作为 `dict{"book": …}` 的值存入（显示即 `dict{"book": 16}`）；最后一行同时用到 record 字段读取、dict 下标读取与字符串拼接，输出 `book 16`。程序不调用 `input()` / `args()`，不读 stdin、不接收参数。

## 3. 运行命令、stdout、stderr、退出码

所有命令均在上述工作目录下执行；stdout/stderr 以 Python `repr` 形式给出（已用 `od -c` 核对原始字节）。

| # | 命令 | stdout | stderr | 退出码 |
|---|---|---|---|---|
| 1 | `python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/main.lwt` | `'Check passed: 2 source file(s).\n'` | `''` | 0 |
| 2 | `python -m lwt docs/agent-eval/submissions/module-record-dict-mix/main.lwt` | `'book 16\n'` | `''` | 0 |
| 3 | `python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt` | `'book 16\n'` | `''` | 0 |
| 4 | `python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt`（stdin 为 `/dev/null`） | `'book 16\n'` | `''` | 0 |

命令 2 的原始字节：`b o o k   1 6 \n`（`od -c`：`0000000 b o o k 1 6 \n`）；stderr 为 0 字节。stdin 未提供任何内容，程序不读取，故不产生影响。

临时佐证（验证内部值确为 16 与 record 内容，文件已删除，不计入交付）：

```lwt
import "lib.lwt" as lib;

record Item { name, price };
let item = Item{name: "book", price: 200};
let ledger = dict{"book": lib.tax(item.price)};
emit ledger;
emit item;
emit lib.tax(item.price);
```

| # | 命令 | stdout | stderr | 退出码 |
|---|---|---|---|---|
| 5 | `python -m lwt docs/agent-eval/submissions/module-record-dict-mix/verify_tmp.lwt < /dev/null` | `'dict{"book": 16}\nItem{name: "book", price: 200}\n16\n'` | `''` | 0 |

之后执行 `rm docs/agent-eval/submissions/module-record-dict-mix/verify_tmp.lwt`，交付目录仅剩 `lib.lwt`、`main.lwt`、`mix.lwt`（及本报告）。

## 4. 失败尝试与修订次数

- LWT 程序失败次数：**0**；语法/语义修订：**0** 次。首版 `lib.lwt` + `main.lwt` 即通过 `--check` 与实运行，与预期 `book 16` 一致。
- 仅有一次非程序性环境操作返回非零：首次 `ls docs/agent-eval` 因目录尚不存在退出 2，随后 `mkdir -p` 创建提交目录，与 LWT 代码无关。
- 未使用 Python 或其他语言生成/改写输出，所有输出均来自 `python -m lwt` 执行 `.lwt` 源文件。

## 5. 隔离声明（如实）

- 实际阅读的文件仅限允许清单：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`examples/modules/main.lwt`。
- 另读取/写入的仅为本任务自己的提交目录 `docs/agent-eval/submissions/module-record-dict-mix/` 下的文件。
- 在仓库根目录执行过 `ls -la` 与 `ls docs`，只看到条目名称，未打开 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/` 中的任何文件，也未读取其他题目目录或任何期望输出文件。
- 未访问网络；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业` 下任何路径。
- 运行入口只使用 `python -m lwt <source>` 与 `python -m lwt --check <source>` 公开 CLI。
