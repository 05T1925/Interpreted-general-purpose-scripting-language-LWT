# module-record-dict-mix 提交报告

## 1. 依据文档与小节

唯一阅读的规范文档：`docs/language-spec.md`（LWT 0.3.0 正式语言规范）。

| 设计点 | 依据小节 | 采用的规则 |
|---|---|---|
| 库文件形态 | §9.1 | `module_file = { import_decl } { fn_decl } EOF`；库文件只含函数声明，不执行初始化语句，故 `lib.lwt` 仅放 `fn tax` |
| 跨文件调用 | §9.3 | 入口用 `import "lib.lwt" as lib;` 后必须以 `lib.tax(...)` 限定调用；模块函数可读取传入记录的字段 |
| 导入位置 | §3、§9.1 | `import` 只能位于所有其他顶层项之前的连续导入区，故写在第一行 |
| 记录类型 | §3、§4.3 | `record Item {name, price};` 顶层声明；`Item{name: "book", price: 200}` 字段集合须与声明完全一致，显示/存储按声明顺序 |
| 映射字面量 | §3、§4.4 | `dict{"book": <expr>}` 由 DICT token 优先匹配；键为字符串，插入顺序保持；`d[k]` 缺键是运行时错误 |
| 整数运算 | §4.2 | `*`、`/` 只接受整数，`/` 向负无穷取整；`200 * 8 / 100` = `16` |
| 字符串拼接 | §4.2 | `+` 两字符串拼接，无隐式转换，故整数需 `str(...)` |
| 取值与遍历 | §4.4、§6 | `keys(d)` 按插入顺序返回键数组，`each` 遍历键后在循环体用 `taxes[name]` 取值 |
| 输出 | §4.3、§6 | `emit` 输出显示字符串加一个 LF，stdout 只承载 `emit` 输出 |
| 退出码 | §7 | 完整执行成功为 0 |

## 2. 程序文件

提交目录 `docs/agent-eval/submissions/module-record-dict-mix/` 下两个文件。

`lib.lwt`：

```lwt
fn tax(amount) { return amount * 8 / 100; }
```

`mix.lwt`：

```lwt
import "lib.lwt" as lib;

record Item {name, price};

let item = Item{name: "book", price: 200};
let taxes = dict{"book": lib.tax(item.price)};

each (name in keys(taxes)) {
    emit name + " " + str(taxes[name]);
}
```

`lib.tax(item.price)` 先取记录字段 `price`（200），在模块内计算 `200 * 8 / 100 = 16`；结果作为 `dict` 的 `"book"` 键值存入，再按插入顺序取回并输出 `book 16`。程序不调用 `input()`/`args()`，无参数、无 stdin 依赖。

## 3. 命令、stdout、stderr、退出码

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-module-record-dict-mix-s3`

```
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

实测结果（用 `subprocess` 捕获后打印 `repr`，仅为测量）：

- stdout repr：`'book 16\n'`
- stderr repr：`''`
- 退出码：`0`

即实际输出恰为一行 `book 16`，符合题目要求。

## 4. 失败与修订次数

- 编写版本：1 版（`lib.lwt`、`mix.lwt` 各一次写入）。
- 运行失败次数：0；首次运行即通过。
- 修订次数：0（未改动任何源码或命令）。
- 自测次数：2 次（直接运行 + 捕获 repr 复核），结果一致，无随机性来源。

## 5. 隔离声明

- 仅阅读 `TASK.md` 与本组允许的 `docs/language-spec.md`；未打开 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出，未联网，未访问 `Desktop/大三上/程序设计实践/大作业`。
- 为确认提交目录是否为空，仅对 `docs/agent-eval/submissions/` 与目标目录做了文件名列举，未读取除 `language-spec.md` 外的任何文档内容。
- 只用 `python -m lwt <file>` 公开入口执行；未用其他语言生成或改写输出，未使用 `--check`、`--profile` 等辅助入口替代运行。
- 只在本目录 `docs/agent-eval/submissions/module-record-dict-mix/` 下写入 `lib.lwt`、`mix.lwt`、`report.md`。
