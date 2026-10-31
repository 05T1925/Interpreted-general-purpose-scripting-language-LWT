# LWT 源码级调试器（S30/S32）

调试器是 Python 实现的显式运行工具。它通过 LWT AST/runtime 的独立 hook，在 LWT 语句开始前暂停；它不会使用 Python pdb、sys.settrace 或宿主调用栈推测 LWT 状态。调试器会执行被调试程序。

这与仓库其它开发工具的职责不同：

| 命令 | 是否执行被分析的 LWT 程序 | 用途 |
|---|---:|---|
| python -m lwt SOURCE | 是 | 普通运行 |
| python -m lwt --check SOURCE | 否 | 一次性静态检查 |
| python -m lwt --profile PROFILE SOURCE | 是 | 记录确定性运行档案，不交互 |
| python -m lwt.lsp_server | 否 | stdio 静态编辑器辅助 |
| python -m lwt.debugger SOURCE | 是 | 语句级交互调试 |
| VS Code `type: lwt` DAP | 是 | 原生断点、单步、LWT 栈和只读变量 |

调试器不增加 LWT 语法，不改变普通 CLI 输出/退出码，不修改 profile schema。调试信息写到 stderr；LWT emit 输出只写到 stdout。

## 启动

交互命令从控制台 stdin 读取，被调试程序默认收到 EOF：

    python -m lwt.debugger examples/debugger/main.lwt

如果程序需要 input()，应通过单独文件传入：

    python -m lwt.debugger --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt

调试脚本可重复运行，不需要人工输入：

    python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt

参数顺序为可选项在前、源文件在后、LWT 参数在 -- 后：

    python -m lwt.debugger [--commands COMMAND_FILE] [--program-stdin INPUT_FILE] SOURCE [-- ARGS...]

选项和值、源文件和输入文件中的相对路径都以启动命令的当前工作目录为基准。--help 展示当前实际支持的命令。

入口和导入模块沿用 LWT loader：源码严格按 UTF-8 解码，允许剥除文件开头一个 UTF-8 BOM，并将 CRLF/CR 统一为 LF。断点行号和显示列表都对应此规范化后的源码行。调试器命令文件按其自身规则解码和拆行；`--program-stdin` 在严格 UTF-8 校验后把原始字节交给 `input()`，不会剥除输入文件的 BOM。

## 命令

命令只读取当前调试状态，不允许给变量赋值或计算任意表达式。

| 命令 | 作用 |
|---|---|
| help | 展示命令 |
| continue / c | 继续至断点或程序结束 |
| step / s | 执行当前语句，停在下一条语句；进入 LWT 用户函数 |
| next / n | 跳过被调用户函数体，在当前帧下一条语句停住；若当前帧返回，则停在调用方恢复后的下一条语句 |
| finish / out | 运行至当前用户函数返回，并在调用方下一条语句停住 |
| break / b PATH:LINE | 在加载的入口或静态导入模块中添加精确行断点 |
| delete ID | 删除一个断点 |
| breakpoints | 列出已验证和未映射断点 |
| where / stack | 从当前帧到入口帧显示 LWT 调用栈 |
| locals | 显示当前函数帧的可见局部绑定 |
| globals | 显示当前模块自己的全局环境 |
| print / p IDENTIFIER | 读取一个当前可见标识符 |
| list [COUNT] | 显示当前语句附近的源码，默认 5 行，最多 40 行 |
| quit / q | 取消调试会话 |

断点路径含空格时用双引号包住整个 PATH:LINE，例如：

    break "examples/debugger/math helpers.lwt:2"

路径最后一个冒号用于分隔行号，因此 Windows 驱动器号中的冒号可正常保留。相对断点路径相对进程当前工作目录解析。断点只精确匹配该物理源码行，不移动到邻近行；没有可执行语句或文件不在已加载模块图中的断点显示为 unmapped。若一行包含多个可执行节点，稳定选择该行起始列最小的节点；列相同时按源码遍历顺序选第一个。

断点在 AST 语句开始前暂停；循环再次进入同一语句仍会命中。用户从当前断点输入 continue 时，当前 hook 调用直接恢复执行，不会在同一个节点立即重复暂停。

Blocks 是作用域容器，不是独立暂停节点。when、while、each、attempt 和 recover 本身以及其内部可执行语句都按真实解释顺序触发单步/断点。循环每次执行其 body 时都会再次遇到 body 语句节点。

step 在当前语句完成后停在下一条可执行语句，包括被调函数的第一条语句。next 以当前 LWT 帧 ID 为边界，跳过更深用户函数中的节点；函数返回后停在调用方下一条语句。finish 仅适用于用户函数帧，在入口帧输入会显示 DebugError 并保持暂停。step/next/finish 都只会在真实存在的下一条可执行语句处暂停；若程序因当前操作执行完成而直接结束，不会合成额外的“程序结束”暂停。断点优先于单步计划。调试器不会回滚副作用、重放程序或保存时间旅行快照。

## 栈和变量

where 只显示 LWT 帧，不显示 Python 实现帧。函数帧记录函数名、模块路径和调用位置；递归调用会显示多个独立 LWT 帧。

locals 会从当前词法环境向外遍历至当前帧的模块全局环境；内层遮蔽优先，因而能看到当前 block、each 变量、recover 绑定和函数参数。函数的外层 body 与参数共用激活环境。它不会显示调用者的局部变量。

globals 只显示当前帧所属 ModuleUnit 的全局 Environment。入口文件顶层 let 属于入口全局；库模块有独立 Environment，且现有模块语法只允许 imports/functions，所以库模块全局通常为空。函数不会捕获调用者的局部变量，也不会把入口变量当成模块全局。

print 只接受一个 ASCII LWT 标识符并通过 Environment.resolve 读取已有绑定。它不会执行函数、索引、字段访问或其它表达式。值使用 LWT 的安全格式化规则；字符串按字符串值格式引用，数组、record、Error 和循环引用保持 LWT 显示语义。显示超过 240 字符会加上截断标记；过深值不会输出 Python traceback。

## stdin、stdout、stderr 和退出码

- 未指定 --commands 时，调试命令从控制台 stdin 读取。指定 --commands 后，命令来自 UTF-8 文件，命令提示符不写入脚本 transcript。
- 命令脚本按严格 UTF-8 解码，允许并移除一个开头 UTF-8 BOM；CRLF、LF、CR 都作为命令分隔。U+2028 等 Unicode 字符不是命令换行符。空白行报告 empty command 并等待下一条命令。
- 未指定 --program-stdin 时，被调试程序拿到空字节流，input() 返回 LWT null/EOF 结果，不会消费调试命令。指定文件时，文件严格按 UTF-8 验证后作为原始字节交给 LWT input()；一个 UTF-8 BOM 若存在会作为程序输入字符保留。LWT 的 input() 按语言规范处理 LF/CRLF 和文件末尾无 LF 的行。
- --commands 和 --program-stdin 文件、入口或模块读取失败返回 4；词法/语法错误返回 2；未捕获 LWT RuntimeError 返回 3；正常运行返回 0。
- quit 或命令脚本在程序暂停时 EOF 返回 1，诊断类别为 DebugError，不会静默继续。未知命令、命令参数错误和不可用的入口 finish 会给出一行可读 DebugError，并留在当前暂停位置。
- stdout 只承载 LWT emit。断点、提示符、栈、变量、源码列表和调试器诊断全部写到 stderr。程序自身 RuntimeError 诊断仍使用原 CLI 规则。

## 可复现示例

示例源码、模块、程序输入和命令脚本位于 examples/debugger/。在仓库根目录执行：

    python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt

预期程序 stdout 为：

    demo:5

调试 stderr 会显示入口语句、math helpers.lwt:2 的验证断点、next/step 暂停、LWT 栈及 items 局部值。普通 CLI 的程序输出通过本阶段 CLI 回归测试与调试模式逐字节比较。

人工交互时可以不传 --commands，输入与同一脚本相同的命令。脚本模式更适合 CI、答辩复现和故障报告。

## 限制与故障排查

当前 CLI 调试器不支持条件断点、命中计数条件、变量写入、表达式 watch、远程/线程调试、time-travel 或异常停点。VS Code 原生 DAP 范围与 launch 配置见 [DAP 使用说明](dap.md)；它复用同一调试控制层，不提供任意 Evaluate/Watch 或 SetVariable。调试能力是 LWT 源码语句级，不是 Python 源码调试。

断点显示 unmapped 时先核对路径是否是当前工作目录下的加载模块，以及指定行是否确有可执行语句。调试脚本 EOF 表示脚本没有提供继续/单步命令，程序会按设计取消并返回 1。若程序需要 input()，总是用 --program-stdin 指定独立文件；调试命令脚本不会传给 LWT 程序。
