# 盲测提交报告：module-record-dict-mix

## 1. 交付文件

| 文件 | 内容 |
|---|---|
| `lib.lwt` | 仅含顶层函数声明 `fn tax(amount) { return amount * 8 / 100; }`（无顶层语句、无 record） |
| `mix.lwt` | `import "lib.lwt" as lib;` → `record Item { name, price };` → 构造 `Item{name: "book", price: 200}` → `dict{"book": lib.tax(item.price)}` → 输出 `book 16` |

`mix.lwt` 全文：

```lwt
import "lib.lwt" as lib;

record Item { name, price };

let item = Item{name: "book", price: 200};
let prices = dict{"book": lib.tax(item.price)};
emit "book " + str(prices["book"]);
```

## 2. 依据的规范小节

| 小节 | 用于 |
|---|---|
| §2.1 词法 | 标识符、双引号字符串、`#` 注释、分号不可省略；`import`/`as`/`record`/`dict` 的词法身份 |
| §3 语法 | `program = { import_decl } { top_item } EOF`、`module_file = { import_decl } { fn_decl } EOF`；`record_decl` 后必须有分号；`dict{...}` 为 DICT atom，与 record 构造区分；`field_init` 为 `IDENT ":" expression`；导入必须位于所有其他顶层项之前 |
| §4.3 记录 | `Name{f1: v, f2: v}` 每次构造新实例，字段集合须与声明完全一致；`r.f` 读取字段，字段无类型限制；显示规则 |
| §4.4 映射 | `dict{ key: value }` 逐项先键后值求值；键须为整数或字符串；插入顺序；`d[k]` 读取、缺键为运行时错误；映射为引用类型 |
| §5 作用域与调用 | 所有顶层 `fn`/`record` 在普通语句前一次性登记（允许前向引用）；函数调用创建独立作用域；传参数目/类型严格 |
| §6 预置能力与 CLI | `emit` 输出显示字符串并接一个 LF；`str(value)` 返回可显示字符串；stdout 只承载 emit 输出，诊断走 stderr；命令形式 `python -m lwt <source-path>` |
| §7 错误与退出码 | 成功退出码 0；诊断格式与「运行时首个错误终止、先前输出保留」 |
| §9.1 模块声明限制 | 库文件只可在开头 import，随后仅 `fn_decl`；不得有顶层变量、record 或普通语句 |
| §9.2 路径解析 | 导入路径相对于书写该声明的文件目录解析，因此 `lib.lwt` 与 `mix.lwt` 同目录 |
| §9.3 独立命名空间与限定调用 | `lib.tax(...)` 为模块限定调用；模块函数不闭包、不能借用入口 record 类型名，但可按字段规则读取传入记录 |

整数语义依据 §4.2：`200 * 8 = 1600`，`1600 / 100 = 16`（整数除法向负无穷取整，此处整除），故 `lib.tax(item.price)` 恰为 16，`dict{"book": 16}` 的键值均与题目一致。

`emit "book " + str(prices["book"]);` 只做字符串拼接（`+` 仅接受两个整数或两个字符串，§4.2），故必须经 `str` 转换；输出 `book` 与 `16` 之间为单空格。

## 3. 运行命令与结果

执行目录：工作目录根 `C:/Users/28641/AppData/Local/Temp/lwt-s48-C-module-record-dict-mix-s2`。

命令 1（正式验收命令）：

```
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout repr：`'book 16\n'`
- stderr：空
- 退出码：0

字节核对（同一命令管道至 `od -An -c`）：`b o o k   1 6 \n`，确认仅一个空格分隔且末尾恰一个 LF，无 BOM、无多余空行。

命令 2（重复性 / 不依赖 stdin）：

```
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt < /dev/null
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- 两次均 stdout `book 16`，stderr 空，退出码 0；程序不调用 `input()`、`args()`，也不接收 `--` 之后的参数。

## 4. 失败与修订次数

- 源文件修订次数：**0**（`lib.lwt`、`mix.lwt` 首版一次写成即通过）。
- 运行尝试：3 次成功（含一次字节核对、一次空 stdin、一次重复运行），0 次语义失败。
- 另有 1 次**非程序性**命令失败：在提交目录内直接执行 `python -m lwt mix.lwt` 报
  `No module named lwt`（退出码 1）。原因是该目录不是项目根，`lwt` 包不在 `sys.path` 上，属入口调用位置错误，与题目程序无关；随后统一改回从项目根执行，未修改任何源文件。

## 5. 隔离声明

- 只阅读了 `TASK.md` 与允许的 `docs/language-spec.md`；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件，未查阅 `README.md`、`project.md`、`SUBMISSION.md` 等非允许文档。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 全程只用 `python -m lwt <file>` 公开入口执行与自测（另用 `python -m lwt --version` 确认入口可用、`od` 仅做字节核对），未用其他语言生成或改写程序输出。
- 只写入 `docs/agent-eval/submissions/module-record-dict-mix/` 下的 `lib.lwt`、`mix.lwt`、`report.md`。
