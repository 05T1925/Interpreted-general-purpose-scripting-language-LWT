# 盲测报告：module-record-dict-mix

## 1. 产物

| 文件 | 作用 |
|---|---|
| `lib.lwt` | 静态函数库：只含函数声明 `fn tax(amount) { return amount * 8 / 100; }`（无顶层 import，故仅有函数声明） |
| `mix.lwt` | 主程序：`import "lib.lwt" as lib;` + `record Item { name, price };` + record 构造 + `dict{...}` + `emit` |

两个文件同放于 `docs/agent-eval/submissions/module-record-dict-mix/`，因此 `import "lib.lwt"` 的相对路径（相对声明该 import 的文件目录，规范 §9.2）无需任何 `../`。

`mix.lwt` 全文：

```lwt
import "lib.lwt" as lib;

record Item { name, price };
let item = Item{name: "book", price: 200};
let prices = dict{"book": lib.tax(item.price)};
emit item.name + " " + str(prices["book"]);
```

## 2. 设计依据（允许文档内的小节）

| 需求 | 依据 |
|---|---|
| 库文件「只含顶部 import 与函数声明」 | 规范 §9.1 `module_file = { import_decl } { fn_decl } EOF`；开发指南「多文件函数库」：库文件只能有开头导入和顶层 `fn`，不能有顶层执行语句或 `record` |
| `import "lib.lwt" as lib;` 必须位于所有其他顶层项之前 | 规范 §3 `program = { import_decl } { top_item } EOF`、§9.1 |
| 路径相对「书写该 import 的文件目录」 | 规范 §9.2；故 lib.lwt 与 mix.lwt 同目录 |
| `record Item { name, price };` 与 `Item{name: "book", price: 200}` | 规范 §3 语法、§4.3：字段集合须与声明完全一致，构造按声明顺序存储 |
| `tax(200) == 16` | 规范 §4.2：`/` 为整数除法、向负无穷取整；200*8/100 = 1600/100 = 16 |
| `dict{"book": ...}` 与 `d["book"]` 读取 | 规范 §4.4：键必须是整数或字符串，`d[k]` 缺键报错 |
| `emit item.name + " " + str(prices["book"]);` 输出 `book 16` | 规范 §4.2 `+` 支持两字符串拼接（不隐式转换，故整数需 `str`）；§6 `str(value)`；§4.3 `emit` 追加一个 LF |

未使用任何规范外能力：无浮点、无闭包、无 `input()`/`args()`（题目要求不接收参数与 stdin）。

## 3. 自测命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-module-record-dict-mix-s3`（仓库根）。

### 3.1 静态检查

```text
$ python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
Check passed: 2 source file(s).
EXIT=0
```

（`--check` 仍走 `python -m lwt` 公开入口，只解析不执行；覆盖入口与 lib.lwt 两个文件。）

### 3.2 正式运行

```text
$ python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
stdout: 'book 16\n'
stderr: ''
exit:   0
```

- stdout repr：`'book 16\n'`（逐字节核对为 `b o o k SP 1 6 \n`，共 8 字节）
- stderr：空（0 字节，无诊断、无 Python traceback）
- 退出码：0

### 3.3 确定性复跑

同一命令连续运行两次，均输出 `book 16`，退出码 0；无 `args()`/`input()`，不依赖 stdin 与命令行参数。

## 4. 失败与修订次数

- 运行失败次数：0（首次执行即符合预期）
- 代码修订次数：0（未改动已写文件）
- 未出现 `LexError`/`SyntaxError`/`RuntimeError`，无需按诊断位置排错

## 5. 隔离声明

- 只阅读了 TASK.md 允许的四份材料：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`examples/modules/main.lwt`（另加 TASK.md 本身）。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、任何其他题目目录、任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仓库内唯一写入位置：`docs/agent-eval/submissions/module-record-dict-mix/`（`lib.lwt`、`mix.lwt`、本 `report.md`）。未修改解释器、未改动其他任何仓库文件。
- 运行方式：仅 `python -m lwt`（普通执行与 `--check` 两种公开模式），未用其他语言生成输出或改写程序。
- 需如实说明的一处操作细节：为做 stdout/stderr 的逐字节核对，曾把 stderr 重定向到仓库外的系统临时文件 `/tmp/lwt_mix_err.txt`（仅 0 字节），核对后已 `rm -f` 删除；此外全程只用 shell 管道（`od -c`）观察输出，未在仓库内产生额外文件。
