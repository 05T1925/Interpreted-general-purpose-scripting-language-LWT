# 盲测报告：module-record-dict-mix

## 1. 题目与交付

在 `docs/agent-eval/submissions/module-record-dict-mix/` 下交付：

- `lib.lwt`：模块文件，仅含函数声明 `fn tax(amount) { return amount * 8 / 100; }`（含一行 `#` 注释，规范 §2.1 允许）。
- `mix.lwt`：入口程序，`import "lib.lwt" as lib;`、`record Item { name, price };`、`Item{name: "book", price: 200}`、`dict{"book": lib.tax(item.price)}`，输出 `book 16`。
- `report.md`：本文件。

程序不读取 `args()` 与 `input()`，因此不依赖命令行参数与标准输入。

## 2. 依据文档与小节

仅阅读 `docs/language-spec.md`（C 组消融：仅语言规范）：

- §2.1 词法与注释：`#` 注释不产生 token。
- §3 语法：`import_decl` 位于程序/模块开头连续区；`record IDENT { name_list } ;`；`fn IDENT(...) block`；`dict "{" entries "}"` 为独立 atom；`IDENT{...}` 结构构造；`emit` 语句与显式分号。
- §4.2 运算：整数 `*`、`/`，`/` 向负无穷取整；200*8/100 = 1600/100 = 16（整数精确）。
- §4.4 映射：`dict{key: value}` 键须为整数或字符串，允许字符串键 `"book"`，下标读取 `d["book"]`；`emit` 显示规则见 §4.3。
- §5 作用域与函数：顶层 `fn`/`record` 先登记后执行；记录字段 `item.name`、`item.price` 按声明顺序；表达式从左到右求值。
- §6 预置能力：`emit` 输出显示字符串 + LF；`str(value)` 生成显示字符串，整数显示为十进制。
- §9.1–§9.3 模块：库文件文法为 `{ import_decl } { fn_decl } EOF`，不含顶层语句/record；`import "lib.lwt" as lib;` 路径相对书写文件目录解析；限定调用 `lib.tax(...)` 进入模块函数上下文。

## 3. 实现要点

`mix.lwt`：

```lwt
import "lib.lwt" as lib;

record Item { name, price };

let item = Item{name: "book", price: 200};
let fees = dict{"book": lib.tax(item.price)};
emit item.name + " " + str(fees["book"]);
```

- `lib.tax(item.price)` 返回 16 并作为 `dict{"book": ...}` 的值；随后从映射按键读回，用 `+` 拼接字符串（§4.2 仅允许双字符串拼接）与 `str` 转换的整数，单次 `emit` 输出一行 `book 16`。

## 4. 运行与观测

运行目录：项目根 `C:/Users/28641/AppData/Local/Temp/lwt-s48-C-module-record-dict-mix-s4`（唯一公开入口）。

命令：

```text
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout（repr）：`'book 16\n'`
- stderr：空（0 字节）
- 退出码：0

字节级核对（`od -An -c`）：`b o o k   1 6 \n`，即内容恰为 `book 16` 加一个 LF，无额外输出。

## 5. 失败与修订次数

- 失败运行：0 次；修订（修改程序）次数：0 次。
- 首次运行即通过，未出现 LexError/SyntaxError/RuntimeError，也未产生任何 stderr。

## 6. 隔离声明

- 仅阅读 `docs/language-spec.md`、`TASK.md` 与本目录提交文件；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅使用 `python -m lwt <file>` 公开入口运行；未用其他语言生成输出或改写程序。
- 仅在 `docs/agent-eval/submissions/module-record-dict-mix/` 下创建文件；临时捕获文件用后已删除。
