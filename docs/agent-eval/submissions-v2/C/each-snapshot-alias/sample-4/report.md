# snapshot.lwt 盲测报告

## 1. 依据文档与小节

仅阅读 `docs/language-spec.md`（C 组消融：仅语言规范）。程序用到的规则与出处：

| 规则 | 规范位置 |
|---|---|
| `record IDENT { name_list };` 只能作顶层项，构造 `Box{value: 0}`、字段读取与字段赋值 `alias.value = 9` | §3（record_decl / field_init）、§4.3 |
| 数组字面量、`push(array, value)` 原地追加并返回 `null`；数组按引用传递，别名可见修改 | §4.3、§6 预置能力表 |
| `each (item in expr)` 进入循环时复制**元素引用序列**作为浅快照；循环中 `push` 不改变尚待遍历的元素，`continue`/循环正常结束均按快照推进 | §5、§8.2（`push(students, s)` 后仍只遍历 2 个元素） |
| 块内赋值修改最近可见绑定（`count = count + 1` 作用于外层 `count`） | §5 |
| 记录实例的 `==` 为身份相等：别名指向同一实例即为 `true` | §4.2 |
| `str(integer)` 返回十进制显示；`emit` 输出显示字符串并追加 LF | §4.3、§6 |
| 变量名可与预置函数同名，按语法位置区分（本题数组变量取名 `values`，未作函数调用） | §5 |

## 2. 程序要点

文件：`docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt`

- 构造 `let values = [1, 2, 3];`，在 `each (v in values)` 体内执行 `push(values, 99)` 并 `count = count + 1`。
- 若未采用浅快照，追加会无限延长遍历；实际退出且计数为 3，说明迭代的是进入循环时的 3 元素快照。
- `record Box {value};`，`let b = Box{value: 0};`、`let alias = b;`、`alias.value = 9;`，随后 `emit b.value;` 与 `emit b == alias;`。
- 不读取 `args()`、`input()`，不接收参数与 stdin。

源程序：

```lwt
record Box {value};

let values = [1, 2, 3];
let count = 0;
each (v in values) {
    push(values, 99);
    count = count + 1;
}
emit "iterations " + str(count);

let b = Box{value: 0};
let alias = b;
alias.value = 9;
emit b.value;
emit b == alias;
```

## 3. 运行命令与结果

命令（工作目录为本题目录）：

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```

- stdout（`repr`）：`'iterations 3\n9\ntrue\n'`
- 字节核对（`... | od -c`）：`i t e r a t i o n s   3 \n 9 \n t r u e \n`
- stderr：空（`''`）
- 退出码：`0`

## 4. 失败与修订次数

- 首次编写后一次运行即符合预期，失败运行 0 次，修订 0 次。
- 未使用 `--check`、`--profile` 等附加入口，也未用其他语言生成或改写输出。

## 5. 隔离声明

- 只阅读了 `docs/language-spec.md`；未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出文件。
- 未联网，未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 全部执行只用公开入口 `python -m lwt <file>`。
- 只在本目录 `docs/agent-eval/submissions/each-snapshot-alias/` 下写入 `snapshot.lwt` 与本报告。
