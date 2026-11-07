# LWT 静态检查器

`python -m lwt --check SOURCE` 使用现有严格 UTF-8 读取、lexer、parser 和静态模块加载器，检查入口及所有静态导入模块的完整 AST。它不执行程序，不是静态类型系统，也不证明程序运行成功。普通 `python -m lwt SOURCE [-- ARGS...]` 继续使用原执行路径。可运行的三文件成功示例是 [`examples/modules/main.lwt`](../examples/modules/main.lwt)，检查器不会输出该程序的 `emit` 结果。

## 诊断目录（S27）

所有静态诊断的 `severity` 固定为 `error`，`category` 固定为 `StaticError`。码值稳定，消息使用对应运行时名称解析的既有语义，位置为触发标识符或构造位置。

| Code | 诊断 |
|---|---|
| `STC001` | 同一模块重复函数声明 |
| `STC002` | 同一模块重复 record 声明 |
| `STC003` | 函数名与内置函数冲突 |
| `STC010` | 未定义函数名 |
| `STC011` | 函数/内置函数实参数量不匹配 |
| `STC020` | 未定义 record 类型 |
| `STC021` | record 构造字段重复 |
| `STC022` | record 构造缺少字段 |
| `STC023` | record 构造包含声明外字段 |
| `STC030` | 模块别名未定义 |
| `STC031` | 模块没有指定函数 |
| `STC040` | 变量名在当前可见词法作用域及模块全局中均未定义 |
| `STC041` | 同一词法作用域内重复 `let` 绑定 |
| `STC042` | dict 字面量中静态字面量键重复 |
| `STC043` | dict 字面量的静态字面量键不是整数或字符串 |
| `E-SPAWN-001` | `spawn` 目标函数不存在（本地函数或模块成员） |
| `E-SPAWN-002` | `spawn` 目标实参数量与形参数量不符 |

词法、语法、CLI、源文件和模块加载诊断保留原有类别、消息、位置和退出码；机器码分别为 `LEX001`、`PAR001`、`CLI001`、`SRC001`、`MOD001`。静态错误、词法错误、语法错误退出码为 2；无错误为 0；CLI、源文件和模块加载错误为 4。JSON 中 `files_checked` 对完全加载并解析的模块图是模块数；任何 CLI 或加载失败时为 `null`，不报告部分加载计数。

S43 的 `E-SPAWN-001/002` 是针对第 11 节 `spawn` 表达式的**目标存在性与实参数量**诊断（文本与 `--format=json` 两种模式都输出，机器码沿用该稳定码）；它只检查可静态确定的名字与调用形状，**不检查并发正确性**（死锁、通道使用、轨迹合法性等属于运行期与专门工具）。`--check` 不执行任何 LWT 语句，也不创建任务。

## 作用域模型

- 每个模块使用自己的函数命名空间、变量根作用域和导入别名表；入口 record 类型仅在入口可见。函数名与 record 名属不同命名空间；变量、模块别名也独立处理。
- 一个模块的全部顶层 `let` 名进入该模块根作用域的静态可见集合，因此函数可以解析源码中后来声明的模块全局变量。此集合不等同于运行时 definite assignment。
- 函数局部作用域由形参和函数体最外层 `let` 共同组成；函数的父作用域固定为所属模块根作用域，不读取调用者局部绑定。
- 显式块创建子作用域。`each` 迭代变量位于 body 块外层的迭代作用域；`attempt`、body、`recover` handler 与可选的 `finally` 各自创建块作用域，错误变量只在 recover 块可见，finally 中不可见（引用按未定义变量诊断）。recover 变量位于 recover body 的父 handler 作用域中，因此 body 可按普通规则遮蔽它。
- 每个作用域的直接 `let` 声明构成该作用域的静态名字集合；同一作用域重复绑定诊断。解析 initializer 时当前 `let` 自身不作为已写入绑定，因此同名引用会查找外层作用域。

诊断按模块加载顺序，再按模块内源码行、列排序；同一位置保持 analyzer 遇到诊断的次序。完整且可加载的程序允许汇总多条静态诊断。任何 lexer、parser 或模块加载错误仍采用当前首错契约，不做错误恢复。

## 边界

检查器不推断表达式类型，不检查运行时值、索引范围、字段对象类型、`read_text` 文件内容、用户输入、分支可达性或除零是否实际发生。它不做控制流证明或路径敏感 definite-assignment 分析；可能未执行或未初始化的变量不会被当作确定静态错误。字段访问和任意表达式的类型仍由运行时判断。

因此检查通过只表示本目录所列问题未发现。它不改变正常执行的函数查找、实参求值顺序、运行时错误、recover 捕获或副作用。

声明存在但可能尚未执行或初始化的值、条件/循环的可达性、值类型、数组内容、record 实际对象和除零是否发生，都不构成此版本的确定诊断。特别是函数可引用源码中之后出现的模块全局名字；检查器不承诺该绑定在每条运行路径上都已经初始化。该选择避免将未做路径敏感证明的问题误报为静态错误。

## CLI 和 JSON

```text
python -m lwt --check SOURCE
python -m lwt --check --format=json SOURCE
```

JSON stdout 固定为 UTF-8、单个紧凑 JSON 对象及一个 LF：

```json
{"schema_version":1,"ok":true,"files_checked":1,"diagnostics":[]}
```

对象键顺序固定为 `schema_version`、`ok`、`files_checked`、`diagnostics`。每条诊断键顺序固定为 `code`、`severity`、`category`、`message`、`source`、`line`、`column`；不可用的位置为 JSON `null`。文本模式成功输出简短文件数摘要；诊断写 stderr。JSON 模式所有检查/参数错误只写 stdout 的 JSON，stderr 保持为空，不打印 banner 或 traceback。

完整多诊断对象示例：

```json
{"schema_version":1,"ok":false,"files_checked":1,"diagnostics":[{"code":"STC010","severity":"error","category":"StaticError","message":"undefined function 'missing'","source":"demo.lwt","line":1,"column":6}]}
```

检查 CLI 仅接受 `--check [--format=json] SOURCE`，格式选项必须位于源路径之前，且只接受 `json`。检查模式不接受程序 stdin 或 `--` 参数；多余参数为 `CliError`/4。静态诊断写文本 stderr 或 JSON stdout，但都不会被包装成 LWT 程序的运行时错误。

## 示例

从仓库根检查多层模块示例：

```powershell
python -m lwt --check examples/modules/main.lwt
python -m lwt --check --format=json examples/modules/main.lwt
```

该检查只读取并解析模块图；不调用模块函数，也不运行示例中的任何语句。错误夹具和诊断实测见 [S27 执行报告](s27-static-checker.md)。
