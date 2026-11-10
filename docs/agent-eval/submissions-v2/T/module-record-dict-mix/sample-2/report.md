# module-record-dict-mix 提交报告

## 1. 交付物

| 文件 | 作用 |
|---|---|
| `lib.lwt` | 库模块，仅含一个顶层 `fn tax(amount)` 声明（无 import、无顶层语句） |
| `mix.lwt` | 主程序：导入库、声明并构造 `record Item`、把 `lib.tax(item.price)` 存入 `dict{"book": ...}`、输出 `book 16` |
| `main.lwt` | 与 `mix.lwt` 逐字节相同的副本（题面称主程序为 `mix.lwt`，交付清单写 `main.lwt`，故两者同时提供，行为完全一致） |
| `report.md` | 本报告 |

程序源码：

```lwt
# lib.lwt
fn tax(amount) {
    return amount * 8 / 100;
}
```

```lwt
# mix.lwt
import "lib.lwt" as lib;

record Item { name, price };

let item = Item{name: "book", price: 200};
let totals = dict{"book": lib.tax(item.price)};
emit item.name + " " + str(totals[item.name]);
```

`tax(200) = 200 * 8 / 100 = 16`，映射项为 `"book": 16`；输出把 record 的 `name` 与映射中同名键的值拼接，得到 `book 16`。全部整数运算为整数除法，16 为精确值，不涉及截断。

## 2. 依据文档与小节

| 用法 | 依据 |
|---|---|
| `import "lib.lwt" as lib;` 必须位于所有顶层项之前，路径相对声明文件解析 | language-spec.md §3 `import_decl`、§9.1、§9.2 |
| 库文件语法 `module_file = { import_decl } { fn_decl } EOF`，只允许顶部导入与顶层函数 | language-spec.md §3、§9.1（developer-guide.md §2「多文件函数库」、SKILL.md 工作流第 4 条同述） |
| `record Item { name, price };` 顶层声明、字段名不可重复、声明后必须写分号 | language-spec.md §3、§4.3、§5 |
| `Item{name: "book", price: 200}` 构造字段集合须与声明完全一致，按声明顺序存储 | language-spec.md §4.3 |
| `dict{"book": ...}` 字面量、键为字符串、保持插入序 | language-spec.md §3 `dict_entry`、§4.4 |
| `lib.tax(item.price)` 为限定模块调用，实参在调用方上下文求值 | language-spec.md §5、§9.3 |
| `emit` 语句输出显示字符串加一个 LF；`str(value)` 与 `emit` 同一显示规则，顶层字符串不带引号 | language-spec.md §4.3、§6 |
| 诊断/退出码契约（成功为 0，stdout 只含 `emit` 输出） | language-spec.md §6、§7；developer-guide.md §1「退出码和诊断」 |
| 工作流（先 `--check` 再公开 CLI 运行，核对 stdout/stderr/退出码） | .agents/skills/lwt-app/SKILL.md 第 5–7 条；developer-guide.md §1「运行前静态检查」 |
| 多文件示例形态（入口 import + record + 调用模块函数） | examples/modules/main.lwt |

## 3. 实际执行命令与结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-module-record-dict-mix-s2`

### 3.1 静态检查（mix.lwt）

```text
$ python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
Check passed: 2 source file(s).
```

- stdout：`Check passed: 2 source file(s).\n`
- stderr：空
- 退出码：0

### 3.2 运行（mix.lwt）

```text
$ python -m lwt docs/agent-eval/submissions/module-record-dict-mix/mix.lwt
```

- stdout（repr）：`'book 16\n'`（`od -c`：`b o o k   1 6 \n`，共 8 字节，LF 结尾单行无多余空行）
- stderr（repr）：`''`（0 字节）
- 退出码：0

### 3.3 运行（main.lwt，同内容副本）

```text
$ python -m lwt --check docs/agent-eval/submissions/module-record-dict-mix/main.lwt
Check passed: 2 source file(s).
$ python -m lwt docs/agent-eval/submissions/module-record-dict-mix/main.lwt
```

- stdout（repr）：`'book 16\n'`
- stderr（repr）：`''`
- 退出码：0（两项命令均为 0）

### 3.4 结论

两次运行与两次静态检查均符合题目要求：无参数、不读 stdin、stdout 恰为 `book 16` 一行、stderr 为空、退出码 0。

## 4. 失败与修订次数

- 首次 `--check`：通过，失败 0 次。
- 首次运行：stdout/stderr/退出码均符合预期，失败 0 次。
- 修订次数：0（源码在首次运行前已定稿，未因错误或不符合题意而改动）。
- 唯一一次命令层面的问题：首次字节级核对时把重定向目标写成 Git Bash 的 `/tmp/`，与 Windows 版 Python 的目录视图不一致，导致读取文件失败（该失败发生在核对输出的辅助命令上，未涉及 LWT 程序本身，也不是 LWT 退出码）；随后改用工作目录内的相对路径重做，LWT 程序本身始终为退出码 0。

## 5. 隔离声明

- 只阅读了允许的四份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`examples/modules/main.lwt`。
- 未阅读 `lwt/` 解释器源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、任何其他题目或任何期望输出文件；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`；未联网。
- 只使用公开入口 `python -m lwt`（`--check` 与普通执行）；未用其他语言生成或计算程序输出，未修改解释器或任何既有文件。
- 所有交付文件只写在本目录 `docs/agent-eval/submissions/module-record-dict-mix/` 内。字节级核对时曾在工作目录根下短暂创建 `.scratch/` 用于重定向 stdout/stderr，随后删除；最终核对改为在本提交目录内写临时文件（`.tmp_out`/`.tmp_err`），读取后立即删除，目录现仅含 `lib.lwt`、`main.lwt`、`mix.lwt`、`report.md`。
