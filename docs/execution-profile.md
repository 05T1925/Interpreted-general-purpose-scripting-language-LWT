# LWT 执行档案与覆盖率工具（S28）

执行档案是解释器开发和答辩展示工具。LWT 程序不能读取档案；profile 不属于 LWT 源语言语法或运行时 API。未启用 profile 的普通执行路径保持原有 CLI 输出和退出码。

## CLI

```powershell
python -m lwt --profile reports/run.json examples/modules/main.lwt
python tools/render_lwt_profile.py reports/run.json --output reports/run.html
python tools/merge_lwt_profiles.py run-a.json run-b.json --output merged.json
```

`--profile PROFILE SOURCE [-- PROGRAM_ARGS...]` 中 profile 选项必须在源文件之前；`--` 后的所有参数原样交给 LWT 程序。它不能与 `--check` 组合，输出路径不能是 `-`，也不能覆盖入口或静态导入模块。普通执行与 `--check` 不生成档案。词法、语法、CLI、源文件及模块加载在运行前失败时不生成 profile；运行时错误则保留已发生的副作用，写档案后返回原运行时退出码 3。正常程序保持 stdout、stderr 和退出码；profile 文件写入失败给出单行工具错误和退出码 4。若程序已产生副作用而最终档案写入仍失败，无法回滚副作用；可预检的目录/路径问题在执行前拦截。写入使用同目录临时文件、UTF-8 紧凑 JSON、LF 结尾和原子替换。

## Schema v1

JSON 顶层字段顺序固定为 `schema_version`、`tool`、`entry`、`status`、`exit_code`、`modules`、`events`、`coverage`；合并档案另含 `runs`。输出不包含墙钟时间、机器标识、Python 栈、对象地址或绝对路径。入口路径沿用用户给定路径（绝对路径在当前工作目录内时转为相对路径，否则只保留文件名）；库模块显示为相对入口目录的 `/` 分隔路径。每个已加载模块包含源显示路径、原始 UTF-8 字节 SHA-256、入口标记、函数/语句/decision 静态数。

单次运行的 `status` 为 `success`、`runtime_error` 或 `error`。事件从 `sequence=1` 连续编号，含事件名、来源、行列（不可用时为 null）和 LWT 函数调用深度。事件目录：

| 事件 | 附加信息 |
|---|---|
| `program_start` | 入口启动 |
| `statement` | 静态语句 ID 与 AST 类别 |
| `function_call` | 函数 ID、所属模块、函数名/限定名、声明位置、调用位置和新深度 |
| `function_return` | 函数 ID、限定名以及 `explicit` 或 `natural`；运行时错误逸出时不会伪造返回 |
| `decision` | decision ID、类别和实际 outcome |
| `recover` | 捕获错误类别及原始错误位置，不含恢复变量/值 |
| `runtime_error` | 类别、诊断消息及是否已脱敏 |
| `program_end` | 状态和退出码 |

profile 不序列化局部变量、表达式结果、函数实参、数组/record 内容、stdin 或文件内容。`fail(message)` 的事件消息统一替换为固定的脱敏提示；CLI 的原始 stderr 仍遵循既有诊断契约。工具对 profile 做严格字段、类型、路径、重复 JSON 键、节点 ID、连续序号、事件—静态节点计数和汇总一致性校验。未知 schema version、未知字段或矛盾计数均拒绝。

## 覆盖模型

- **语句分母：** 完整模块 AST 中的 `let`、表达式、`emit`、`return`、`break`、`continue`、`attempt`、`when`、`while`、`each`。普通块只提供结构，不单独计数；import、function 和 record 声明不作为可执行语句。
- **函数分母：** 入口与每个库模块的全部函数声明；函数调用至少一次算 covered，显式/自然 return 次数另计。
- **Decision outcome 分母：** `when` 的 then/otherwise，`while` 的 true/false，`each` 的 empty/nonempty，`and`/`or` 的 short_circuit/evaluate_right，`attempt` 的 normal/recovered。无 otherwise 的 when 仍有 otherwise outcome；break 不会记成 while 条件 false；each 按浅快照是否为空计一次 outcome。
- 每类分别输出 covered/total/percentage 与模块汇总。分母为零时 percentage 为 `null`。错误前已执行的节点保留计数，未走到节点为 0。

覆盖率只说明所选运行场景到达了哪些节点，**不是正确性证明、规范完整性证明或无缺陷证明**。profile 通过显式 observer hook 观察 LWT 控制流，不使用宿主 Python `sys.settrace()`，也不对用户值调用显示/序列化逻辑。profile 模式增加哈希读取、事件记录和 JSON 写入开销，不能用于 S11 性能比较；S10 并发原始证据也不会因本工具自动更新。`KeyboardInterrupt`、`SystemExit` 或宿主进程强杀不保证留下完整档案。

## 合并与 HTML

合并只接受至少两个单次运行档案，要求入口、模块集合、模块 SHA-256、静态节点 ID 和静态定义一致。合并后语句 hit、函数 call/return 和 decision outcome 计数相加；每次运行的状态、退出码、事件数和独立事件序列保存在 `runs`。顶层 `events` 为空，不把多次执行伪装为一条连续轨迹。

HTML renderer 只用标准库、无网络依赖，校验 schema 后转义全部动态文本并产生确定性单文件。若能从当前工作目录或 profile 所在目录解析源文件，就验证其 SHA-256；renderer 不显示源码文本，只呈现来源位置/命中、模块摘要、函数调用/恢复/错误和可折叠事件。离线与打印视图均可读。
