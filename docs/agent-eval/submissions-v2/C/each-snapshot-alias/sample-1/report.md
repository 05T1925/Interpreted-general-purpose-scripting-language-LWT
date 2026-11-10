# report.md —— each 浅快照与记录别名

## 1. 任务与依据

题面：构造数组 `[1, 2, 3]`，在 `each (v in values)` 循环体内 `push(values, 99)`，验证循环遍历进入循环时的浅快照（仍只迭代 3 次）并输出 `iterations 3`；再构造 `record Box {value};` 实例 `b`，`alias = b`，`alias.value = 9`，输出 `b.value 9` 与 `b == alias true`。不接收参数与 stdin。

依据文档与章节（C 组仅允许 `docs/language-spec.md`）：

| 需求点 | 规范依据 |
|---|---|
| `each` 进入循环时复制元素引用序列作为浅快照、循环内 `push` 不影响待遍历序列 | §5（`each` 语义）、§4.3（`push` 原地追加、别名可观察）、§8.2（结构、数组和浅快照的规范性示例） |
| `record Box { value };` 声明、`Box{value: 0}` 构造、字段读取与赋值 | §3（`record_decl`、`field_init`）、§4.3 |
| 数组/记录是按引用传递、赋值不复制对象，故 `b == alias` 为 `true` | §4.1、§4.2（记录只在同一对象时相等，不做递归结构比较） |
| `+` 字符串拼接、`str(value)` 显示（布尔显示为 `true`） | §4.2、§4.3、§6 预置函数表 |
| 程序入口 `python -m lwt <source-path>`、成功退出码 0、stdout 只承载 `emit` | §6、§7 |
| 语句以显式分号结束、`record` 声明后必须写分号 | §2.1、§3 |

## 2. 程序

文件：`docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt`

```lwt
record Box { value };

let values = [1, 2, 3];
let iterations = 0;
each (v in values) {
    push(values, 99);
    iterations = iterations + 1;
}
emit "iterations " + str(iterations);

let b = Box{value: 0};
let alias = b;
alias.value = 9;
emit "b.value " + str(b.value);
emit "b == alias " + str(b == alias);
```

自测辅助：迭代次数由循环体内自增计数器独立统计（不读 `len(values)`），这样若快照语义被破坏（例如遍历边追加边扩展）计数会偏离 3，可真实暴露问题；`b == alias` 使用记录的身份相等而非字段值比较，符合 §4.2。

## 3. 自测命令与结果

在仓库根目录（`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-each-snapshot-alias-s1`）执行：

### 3.1 主测试

```
$ python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
iterations 3
b.value 9
b == alias true
$ echo $?
0
```

- stdout repr：`'iterations 3\nb.value 9\nb == alias true\n'`
- stderr：空（`''`）
- 退出码：`0`

字节级核对（`od -c`）：`i t e r a t i o n s   3 \n b . v a l u e   9 \n b   = =   a l i a s   t r u e \n`，共 39 字节，全部为 LF 换行，无 CR、无 BOM、无多余空行。

### 3.2 重复运行（确定性）

再次执行同一命令，第二次输出与首次逐字节相同（`cmp` 无差异），退出码同为 0。程序不使用 `args()`、`input()`、`read_text`，无并发与 I/O，行为确定。

### 3.3 参数与 stdin 无关性

程序不调用 `args()`/`input()`，故命令行不带 `--` 与 stdin 内容；未传任何程序实参，符合「不接收参数与 stdin」。

## 4. 失败与修订次数

- 失败次数：0
- 修订次数：0（首版即通过，未改动任何语句）
- 未出现 `LexError`/`SyntaxError`（2）、`RuntimeError`（3）或 CLI/文件错误（4），stderr 全程为空

## 5. 隔离声明

- 只读取了允许文档 `docs/language-spec.md`（C 组仅语言规范）；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 未联网。
- 仅通过公开入口 `python -m lwt <file>` 运行程序；未使用其他语言实现或改写程序逻辑，未用任何语言直接生成期望输出（`od`/`cmp` 只用于查看与比对已由 CLI 产生的 stdout/stderr 字节）。
- 只在本目录 `docs/agent-eval/submissions/each-snapshot-alias/` 下写入 `snapshot.lwt` 与 `report.md`。
