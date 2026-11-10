# 盲测报告：module-record-dict-mix

## 依据文档与小节

- 仅阅读 `docs/language-spec.md`。
- 语法与顶层结构：§3（`import_decl`、`record_decl`、`fn_decl`、`dict` 字面量、`emit`）。
- 值与显示：§4.3（record 构造与字段读取）、§4.4（dict 构造、字符串键、插入顺序、`d[k]` 读取）。
- 函数与作用域：§5（顶层 `fn` 在普通语句前登记，函数调用与 `return`）。
- 预置能力：§6（`str` 的显示规则）。
- 模块：§9.1–§9.3（库文件只允许开头 import 与 `fn` 声明；导入路径相对声明文件目录；`lib.tax(...)` 限定调用）。
- 错误与退出码：§7（成功为 0，诊断只写 stderr）。

## 程序

- `lib.lwt`：仅一个函数声明，提供 `tax(amount) = amount * 8 / 100`。
- `mix.lwt`：`import "lib.lwt" as lib;`；声明 `record Item { name, price };`；构造 `Item{name: "book", price: 200}`；构造 `dict{item.name: lib.tax(item.price)}`；用 `emit item.name + " " + str(prices[item.name]);` 输出。

## 运行命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-module-record-dict-mix-s5`

命令：

```text
python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- 未传入程序实参，未提供 stdin。
- stdout repr：`'book 16\n'`（实测 8 字节：`book 16` 加一个 LF）
- stderr：空（0 字节）
- 退出码：0

## 失败与修订

- 首次运行即通过，失败次数 0，修订次数 0。
- 未使用其他语言生成或改写输出；所有验证均通过 `python -m lwt` 公开入口完成。

## 隔离声明

- 仅读取了 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅在本目录 `docs/agent-eval/submissions/module-record-dict-mix/` 下写入 `lib.lwt`、`mix.lwt` 与本报告。
