# module-record-dict-mix 盲测报告

## 1. 任务与产物

- 题目：`lib.lwt` 提供 `tax(amount) = amount * 8 / 100`；`mix.lwt` 以 `import "lib.lwt" as lib;` 导入，声明 `record Item {name, price};`，构造 `Item{name: "book", price: 200}`，把 `lib.tax(item.price)` 存入 `dict{"book": 16}`，输出 `book 16`。不接收参数与 stdin。
- 产物（均位于 `docs/agent-eval/submissions/module-record-dict-mix/`）：
  - `lib.lwt`：仅一条顶层 `fn` 声明，无顶层可执行语句。
  - `mix.lwt`：导入 + `record` 声明 + 两条 `let` + 一条 `emit`。
  - `report.md`：本文件。

源程序：

```lwt
# lib.lwt
fn tax(amount) { return amount * 8 / 100; }
```

```lwt
# mix.lwt
import "lib.lwt" as lib;

record Item {name, price};

let item = Item{name: "book", price: 200};
let prices = dict{"book": lib.tax(item.price)};
emit item.name + " " + str(prices["book"]);
```

## 2. 文档依据

| 设计点 | 依据（`docs/language-spec.md`） |
|---|---|
| 库文件只含顶部 import 与 `fn` 声明（`module_file = { import_decl } { fn_decl } EOF`） | §3 文法、§9.1 |
| 入口导入区必须连续位于所有其他顶层项之前，`import "相对路径" as alias;` | §3 `import_decl`、§9.1 |
| 导入路径相对**书写该导入声明的文件目录**解析，入口路径相对进程工作目录 | §9.2 |
| 模块函数必须限定调用 `lib.tax(...)`，实参在调用方上下文求值 | §9.3 |
| `record Item {name, price};` 顶层声明，`Item{name: ..., price: ...}` 按名构造，字段集合必须完全一致 | §3、§4.3 |
| `dict{key: value}` 字面量，键为字符串/整数，插入序保持；`d[k]` 读缺键报错、有键返回值 | §4.4 |
| `emit` 输出显示字符串加一个 LF；`str(value)` 与 `emit` 同格式 | §4.3、§6 |
| 整数 `/` 向负无穷取整；`200 * 8 / 100` 先乘后除得 16 | §4.2 |
| 顶层 `fn`/`record` 在执行普通语句前一次性登记，函数可前向/递归 | §5 |
| 诊断格式与退出码 0/3 | §7 |

计算链：`item.price = 200` → `lib.tax(200) = 200 * 8 / 100 = 1600 / 100 = 16`（整数除法，无余数）→ 写入 `prices["book"] = 16` → 输出 `item.name + " " + str(16)` = `book 16`。

题目要求 `dict{"book": 16}` 中的 16 由 `lib.tax(item.price)` 产生，故映射值直接写该调用，再用 `prices["book"]` 回读输出，避免在 LWT 之外预先算结果。

## 3. 运行与自测

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-module-record-dict-mix-s1`

命令：

```text
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

实测结果：

- stdout repr：`b'book 16\n'`
- stderr repr：`b''`
- 退出码：`0`

补充静态自检（同一公开入口的 `--check` 子命令）：

```text
python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout repr：`b'Check passed: 2 source file(s).\n'`
- stderr repr：`b''`
- 退出码：`0`

程序不读取 stdin、不调用 `args()`，上述两次运行均未提供标准输入或 `--` 参数。

## 4. 失败与修订

- 首版即通过：正式运行 1 次，`--check` 1 次，均为退出码 0、stderr 为空。
- 失败次数：0；修订次数：0（未改动过 `lib.lwt` / `mix.lwt` 内容）。
- 唯一一次操作性问题：首次尝试把 stdout/stderr 重定向到 Git Bash 的 `/tmp`（Windows Python 不识别该路径）导致读取临时文件失败；该次并未执行 `python -m lwt`，改用一次性 Python 包装 `subprocess.run(..., capture_output=True)` 收集真实 CLI 的字节输出，未改变被测程序与命令。

## 5. 隔离声明

- 仅阅读了允许文档 `docs/language-spec.md`（C 组：仅语言规范）；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出，未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅通过 `python -m lwt <file>` 与同入口的 `--check` 公开命令运行程序；未用其他语言生成或改写输出。
- 仅写入 `docs/agent-eval/submissions/module-record-dict-mix/` 下的 `lib.lwt`、`mix.lwt`、`report.md`；未在目录外创建或修改任何文件。
