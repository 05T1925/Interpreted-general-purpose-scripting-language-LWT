# 盲测报告：snapshot.lwt（each 浅快照 + record 别名）

## 1. 产物

- 程序：`docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt`
- 报告：`docs/agent-eval/submissions/each-snapshot-alias/report.md`

程序全文：

```lwt
# snapshot.lwt — each 浅快照与 record 别名身份验证
let values = [1, 2, 3];
let iterations = 0;
each (v in values) {
    iterations = iterations + 1;
    push(values, 99);
}
emit "iterations " + str(iterations);

record Box { value };
let b = Box{value: 1};
let alias = b;
alias.value = 9;
emit "b.value " + str(b.value);
emit "b == alias " + str(b == alias);
```

## 2. 依据文档与小节

| 设计点 | 依据 |
|---|---|
| `each (item in expr)` 进入循环时复制数组元素引用序列作为浅快照；循环中 `push` 追加不改变尚待遍历的快照 | `docs/language-spec.md` §5（第 145–147 行），§3（第 68 行 EBNF `each_stmt`） |
| 规范示例 8.2 明确「循环只遍历进入时的两个元素」，与本题浅快照预期一致 | `docs/language-spec.md` §8.2 |
| `record Box { value };` 声明、`Box{value: ...}` 构造、`r.f` 读写 | `docs/language-spec.md` §3（第 50、99 行）、§4.3（第 121 行） |
| 数组/记录按引用传递，赋值不复制；`alias.value = 9` 与 `b.value` 观察同一对象 | `docs/language-spec.md` §4.1（第 105、107 行）、§4.3 |
| `==` 对两个记录实例比较对象身份，同一对象为 `true` | `docs/language-spec.md` §4.2（第 113 行） |
| `push(array, value)` 原地追加并返回 `null` | `docs/language-spec.md` §4.3、§6 预置能力表 |
| `str(value)` 生成显示字符串，顶层布尔显示为 `true` | `docs/language-spec.md` §4.3、§6 |
| `emit` 输出显示形式 + 一个 LF；stdout 只承载 `emit` | `docs/language-spec.md` §6（第 155 行） |
| 成功退出码 0；诊断写 stderr | `docs/language-spec.md` §7 |
| `each` 浅快照、数组/记录引用语义、`push` 的可操作摘要 | `docs/developer-guide.md` §2「数组、record 和 `each`」（第 208–220 行）、§3「内置函数与输出」 |
| 工作流：先 `--check`，再用公开 CLI 运行并核对 stdout/stderr/退出码 | `.agents/skills/lwt-app/SKILL.md`「工作流程」第 5–7 步 |

程序未使用 `args()`、`input()`、`read_text()`，不读取参数与 stdin；`iterations`、`alias` 均非保留字（§2.1 保留字表），可作标识符；`record` 在顶层声明，符合 §3 的顶层限制。

## 3. 命令与实测结果

工作目录：`C:/Users/28641/AppData/Local/Temp/lwt-s48-T-each-snapshot-alias-s3`

### 3.1 静态检查

```text
python -m lwt --check docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```

- stdout：`Check passed: 1 source file(s).\n`
- stderr：空
- 退出码：0

### 3.2 执行

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt
```

- stdout repr：`'iterations 3\nb.value 9\nb == alias true\n'`
- 可见文本：

```text
iterations 3
b.value 9
b == alias true
```

- stderr：空
- 退出码：0

### 3.3 无 stdin 复核

```text
python -m lwt docs/agent-eval/submissions/each-snapshot-alias/snapshot.lwt < /dev/null | od -c
```

- 字节级输出：

```text
0000000   i   t   e   r   a   t   i   o   n   s       3  \n   b   .   v
0000020   a   l   u   e       9  \n   b       =   =       a   l   i   a
0000040   s       t   r   u   e  \n
0000047
```

- 说明：全部换行为 LF（`\n`），无 CR；stdin 关闭时结果不变，程序不依赖输入。

## 4. 行为核对

| 题目要求 | 实测 | 结论 |
|---|---|---|
| 构造 `[1, 2, 3]`，循环体内 `push(values, 99)` | 程序原样执行，无运行时错误 | 符合 |
| 循环只迭代 3 次（浅快照） | `iterations 3`；若按活数组遍历将无限追加，实际 3 次后结束 | 符合 |
| 统计迭代次数并输出 `iterations 3` | stdout 第一行 `iterations 3` | 符合 |
| `record Box {value};` 实例 `b`，`alias = b`，`alias.value = 9` | 无错误；`emit` 得到 `b.value 9` | 符合 |
| 输出 `b == alias true` | stdout 第三行 `b == alias true`（身份相等） | 符合 |
| 不接收参数与 stdin | 未调用 `args()`/`input()`；`< /dev/null` 运行结果相同 | 符合 |

## 5. 失败与修订次数

- 失败次数：0
- 修订（编辑程序文件）次数：0
- 过程：一次写成 → `--check` 通过 → 首次运行即得到预期三行输出，退出码 0、stderr 为空；随后补充字节级与无 stdin 复核，程序未再改动。

## 6. 隔离声明

- 只阅读了 TASK.md 允许的三份文档：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`；另读了任务文件 `TASK.md` 本身。
- 未阅读 `lwt/` 源码、`tests/`、`app/`、`reports/`、`tools/`、`editors/`、`slides/`、其他题目目录或任何期望输出；未联网；未访问 `C:/Users/28641/Desktop/大三上/程序设计实践/大作业`。
- 仅通过 `python -m lwt` 公开入口（`--check` 与普通执行）运行程序；未用其他语言生成或改写输出。
- 只在 `docs/agent-eval/submissions/each-snapshot-alias/` 下写入 `snapshot.lwt` 与本报告，未改动仓库其他文件。
