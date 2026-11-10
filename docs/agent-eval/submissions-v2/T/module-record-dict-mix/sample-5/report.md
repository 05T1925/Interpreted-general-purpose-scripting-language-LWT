# 盲测报告：module-record-dict-mix

## 1. 题目与产物

| 项 | 内容 |
|---|---|
| 入口程序 | `docs/agent-eval/submissions/module-record-dict-mix/mix.lwt` |
| 库模块 | `docs/agent-eval/submissions/module-record-dict-mix/lib.lwt` |
| 要求 | `lib.lwt` 只含顶部 import 与函数声明，提供 `fn tax(amount) { return amount * 8 / 100; }`；`mix.lwt` 以 `import "lib.lwt" as lib;` 导入，声明 `record Item {name, price};`，构造 `Item{name: "book", price: 200}`，把 `lib.tax(item.price)` 存入 `dict{"book": 16}`，最后输出 `book 16`；不接收参数与 stdin |

实际源码：

`lib.lwt`

```lwt
fn tax(amount) {
    return amount * 8 / 100;
}
```

`mix.lwt`

```lwt
import "lib.lwt" as lib;

record Item { name, price };
let item = Item{name: "book", price: 200};
let prices = dict{"book": lib.tax(item.price)};
let key = keys(prices)[0];
emit key + " " + str(prices[key]);
```

输出路径：`emit key + " " + str(prices[key])`，`key` 取 `keys(prices)[0]`，即字典插入序首个键 `"book"`；值由 `lib.tax(200) = 200 * 8 / 100 = 16` 得到，故打印 `book 16`。

## 2. 依据的文档与小节

| 依据 | 用到的小节 | 具体用途 |
|---|---|---|
| `docs/language-spec.md` | §2.1 词法、§3 语法 EBNF | 分号必需、`record`/`dict` 字面量文法、`IDENT "("` 优先按调用解析、后接 `[expr]` 后缀索引合法 |
| 同上 | §4.2 运算 | 整数 `*`、`/` 只接受整数，除法向负无穷取整；本例被除数整除，结果 16 |
| 同上 | §4.3 记录 | `record Item {name, price};` 字段集合须与构造完全一致，构造按声明顺序存储 |
| 同上 | §4.4 映射 | `dict{"book": ...}` 字面量、键为字符串、保持插入顺序、`d[k]` 读取、`keys(d)` 按插入序返回键数组 |
| 同上 | §5 作用域与函数 | 顶层 `fn`/`record` 在执行前登记，允许前向/跨文件调用 |
| 同上 | §6 预置能力 | `keys`、`str`、`emit` 的语义与显示规则；`emit` 追加一个 LF 到 stdout |
| 同上 | §9.1–§9.4 模块 | 库文件语法 `{ import_decl } { fn_decl } EOF`（只允许 import 与 fn）、导入路径相对声明文件解析、`alias.member(...)` 限定调用 |
| `docs/developer-guide.md` | §1「先运行」「CLI、参数和输入」「退出码和诊断」「运行前静态检查」 | 使用 `python -m lwt SOURCE` 公开入口、先 `--check` 再运行、错误码含义 |
| 同上 | §2「多文件函数库」 | 库文件只能有顶部 import 与顶层 `fn`，导入须别名限定调用 |
| `.agents/skills/lwt-app/SKILL.md` | 工作流程 4–6 步、S42 dict 使用要点 | 先静态检查再跑公开 CLI；dict 键为整数/字符串、`keys` 遍历/取键；只记录真实运行结果 |
| `examples/modules/main.lwt` | 全文 | 参照 `import "x.lwt" as alias;` + record + 模块限定调用的写法 |

## 3. 实测命令、stdout/stderr 与退出码

均在工作目录 `C:/Users/28641/AppData/Local/Temp/lwt-s48-T-module-record-dict-mix-s5` 下执行，只用公开入口 `python -m lwt`。

### 3.1 静态检查

命令：

```text
python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout：`Check passed: 2 source file(s).\n`
- stderr：（空）
- 退出码：0

### 3.2 正式运行（判定用例）

命令：

```text
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout repr：`b'book 16\n'`
- stderr repr：`b''`
- 退出码：0

未提供 stdin，未使用 `--` 程序实参，程序也未调用 `input()`/`args()`，符合「不接收参数与 stdin」的要求。

## 4. 失败与修订次数

| 项 | 次数 |
|---|---|
| 首次落盘后运行失败 | 0 |
| 代码修订轮次 | 0 |
| 重跑次数 | 1 次（`--check` 与正式运行各 1 次，均一次通过） |

说明：`lib.lwt` 严格保持「仅函数声明」，`mix.lwt` 的 record 声明、dict 字面量、模块限定调用、`keys`/`str` 均按规范写就，故首轮即通过，没有出现需要排错的失败路径。

## 5. 隔离声明

1. 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件（如用例 `.json` oracle）。
2. 未访问网络，未读取 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
3. 只读取 TASK.md 允许的四份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`examples/modules/main.lwt`；另按提示读取了 `TASK.md` 本身。
4. 全部执行只经 `python -m lwt` 公开入口；未用其他语言生成或改写输出，未用 Python `eval`/`exec` 运行 LWT 源码。
5. 写入范围仅限 `docs/agent-eval/submissions/module-record-dict-mix/`（`lib.lwt`、`mix.lwt`、本报告）；自测时在仓库根生成的临时 stdout/stderr 捕获文件已删除，未改动解释器与仓库其他文件。
