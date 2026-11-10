# 盲测报告：each 浅快照与 record 别名

## 程序

- 文件：`docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt`
- 构造数组 `[1, 2, 3]`，在 `each (v in values)` 内每次迭代执行 `push(values, 99)` 并计数，循环后输出 `iterations 3`。
- 声明 `record Box {value};`，构造 `b`，令 `alias = b` 后执行 `alias.value = 9`，输出 `b.value 9` 与 `b == alias true`。
- 不读取 `args()` 或 `input()`，不接收参数与 stdin。

## 依据文档与小节

仅阅读 `docs/language-spec.md`：

- §3 语法：`each_stmt = "each" "(" IDENT "in" expression ")" block`；`record_decl = "record" IDENT "{" [ name_list ] "}" ";"`；`let`、字段赋值 `r.f = v` 与结构构造 `Name{f: v}` 的合法形式。
- §4.1：数组和记录按引用传递，赋给另一变量不复制对象。
- §4.3：`push(array, value)` 原地追加，别名可观察到修改；记录字段可赋值；同名对象的记录实例按身份相等。
- §4.2：`==` 对两个记录实例仅在同一对象时为真。
- §5：`each` 进入循环时复制元素引用序列作为浅快照，循环内追加元素不改变尚待遍历的快照；`continue` 也不重建快照。
- §6：`emit` 输出规则，`str(value)` 返回可显示字符串，顶层字符串不带引号。
- §7：成功退出码 0，stdout 仅承载 `emit` 输出，诊断写 stderr。

## 运行命令

在项目根目录 `C:/Users/28641/AppData/Local/Temp/lwt-s48-C-each-snapshot-alias-s5` 执行：

```
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```

## 实测结果

- 退出码：`0`
- stdout（Python bytes repr）：`b'iterations 3\nb.value 9\nb == alias true\n'`（39 字节，LF 换行）
- stderr（Python bytes repr）：`b''`（0 字节）
- 可读形式：

```
iterations 3
b.value 9
b == alias true
```

`iterations 3` 表明循环只遍历进入时的 3 个元素：若遍历活动数组，`push` 会使迭代不终止，不可能得到 3。`b.value 9` 与 `b == alias true` 表明 `alias = b` 后字段赋值作用于同一记录对象，且记录相等为身份相等。

## 失败与修订次数

- 首次编写即通过，失败 0 次，修订 0 次。

## 隔离声明

- 仅阅读 `TASK.md` 与允许的 `docs/language-spec.md`；未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出。
- 未联网，未访问禁止目录 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅通过公开入口 `python -m lwt <file>` 运行程序，未使用其他语言生成或改写程序输出。
- 仅写入 `docs/agent-eval/submissions/each-snapshot-alias/` 下的 `snapshot.lwt` 与本报告。
