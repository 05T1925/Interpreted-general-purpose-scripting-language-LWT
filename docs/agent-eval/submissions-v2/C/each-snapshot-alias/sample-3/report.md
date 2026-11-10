# 盲测报告：snapshot.lwt

## 1. 题目要求
- 构造数组 `[1, 2, 3]`，在 `each (v in values)` 循环体内 `push(values, 99)`。
- 验证循环遍历的是进入循环时的**浅快照**，仍只迭代 3 次，输出 `iterations 3`。
- 构造 `record Box { value };` 的实例 `b`，令 `alias = b`，`alias.value = 9`，输出 `b.value 9` 与 `b == alias true`。
- 不接收命令行参数，不读 stdin。

## 2. 依据文档与小节（仅 docs/language-spec.md）
| 语义点 | 规范依据 |
|---|---|
| `each (x in e)` 先求 `e` 得到数组，进入循环时复制**元素引用序列**作为浅快照；循环中追加元素不改变尚待遍历的快照 | §5（第 145 行）；§4.3（第 119 行 `push` 原地追加、别名可观察） |
| 迭代变量在每轮新建的循环作用域中绑定，`each` 空数组零次、正常结束继续后续语句 | §5（第 145、147 行） |
| `record` 只能作为顶层项，声明后必须写分号；构造 `Name{f: v}` 字段集合须与声明完全一致 | §3（第 50、95、99、121 行）；§4.3（第 121 行） |
| 数组与记录为按引用传递的可变对象，赋值不复制；`r.f = v` 修改字段 | §4.1（第 105 行）；§4.3（第 121 行） |
| `==` 对记录为**身份相等**（同一对象才相等），不做递归结构比较 | §4.2（第 113 行） |
| `emit` 输出显示字符串并追加一个 LF；顶层字符串不加引号；`str(true)` 为 `true` | §4.3（第 123 行）；§6（第 155 行） |
| `+` 仅接受两整数或两字符串，无隐式转换，故用 `str(...)` 拼接 | §4.2（第 111 行）；§6（第 166 行） |
| 顶层语句按源码顺序执行；`record` 在普通语句前统一登记 | §5（第 139、141 行） |

## 3. 程序
`docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt`：

```lwt
record Box { value };

let values = [1, 2, 3];
let iterations = 0;
each (v in values) {
    push(values, 99);
    iterations = iterations + 1;
}
emit "iterations " + str(iterations);

let b = Box{value: 1};
let alias = b;
alias.value = 9;
emit "b.value " + str(b.value);
emit "b == alias " + str(b == alias);
```

设计要点：
- 循环体每轮都 `push(values, 99)`。若解释器遍历实时数组，迭代将不终止；实测恰好 3 轮，直接证明浅快照语义。
- `alias = b` 只复制引用（§4.1），`alias.value = 9` 通过同一对象修改字段，故 `b.value` 为 9，且 `b == alias` 因身份相同为 `true`。
- 全程不调用 `input()`/`args()`，不依赖 stdin 与程序实参。
- `alias` 不是保留字（`as` 仅在导入声明中作上下文词，§2.1/§9.1），可安全作变量名。

## 4. 运行与实测（只用公开入口 `python -m lwt`）
工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-C-each-snapshot-alias-s3`

命令：
```
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt < /dev/null
```

- stdout（字节 repr）：`b'iterations 3\nb.value 9\nb == alias true\n'`
- stderr（字节 repr）：`b''`
- 退出码：`0`
- stdin 以空设备提供（程序从不读取），未传任何程序实参。

## 5. 失败与修订
- 失败次数：0。首版程序一次通过，无语法/运行时错误。
- 修订次数：0（未改动任何语句）。
- 复核运行：同一命令重复执行 2 次，输出与退出码完全一致。

## 6. 隔离声明
- 仅阅读了 `TASK.md` 与允许文档 `docs/language-spec.md`。
- 未读取 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、示例目录、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅通过 `python -m lwt <file>` 公开 CLI 执行与自测，未使用其他语言生成输出或改写程序。
- 仅在本目录 `docs/agent-eval/submissions/each-snapshot-alias/` 下写入了 `snapshot.lwt` 与 `report.md`。
