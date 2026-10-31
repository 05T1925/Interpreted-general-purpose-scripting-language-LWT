# S30 执行报告：LWT 源码级交互调试器

**阶段结论：实施完成，等待主窗口审查。** S30 只增加开发调试工具和对应证据；没有修改正式语言规范、LWT 语义、黑盒矩阵或用例，也没有开始 S12。

## 1. 基线、分支和环境

- S30 基线：`744d0ca0aa6e2d96c7bf211ff842365b7827f891`。这是 S29 执行报告 SHA 自包含修正提交；S30 从该提交建立独立分支。
- 初始执行分支：`stage/s30-source-debugger`，起始工作区干净；未改写或覆盖 `main`。
- S29 分支此前从 `5eaacccd04cb8b2d00865114424099f6983fa13c` 继续，并先提交报告修正 `744d0ca0aa6e2d96c7bf211ff842365b7827f891`。记录此来源不代表本报告代替主窗口审查 S29。
- 环境：Windows，CPython 3.13.7，Tk/Tcl 8.6（本阶段无 Tk GUI 工作）。
- 运行 `git ls-remote --heads origin main` 做只读远端核查时，GitHub HTTPS 的 Schannel TLS 握手失败，未取得 `origin/main` tip。没有 fetch、pull、push 或以远端覆盖本地状态。
- S30 完成前最后一个非报告提交为 `25057dbff8a8619a906ca152e3d307e809c83b0b`；本报告是阶段最后一个文档提交。最终分支 tip 的完整 SHA 在执行窗口交接中给出。

## 2. 实现内容与关键决策

新增 `python -m lwt.debugger [--commands COMMAND_FILE] [--program-stdin INPUT_FILE] SOURCE [-- ARGS...]`。CLI 用 argv 列表和同进程 loader/runtime 加载并执行程序，不启动第二个解释器子进程。runtime 增加可选调试 hook；普通 CLI 和 profile 不传 hook 时不进入调试路径。调试器没有使用 Python `pdb`、`sys.settrace`、`eval` 或 `exec`。

调试器在 AST 可执行语句开始前暂停。断点以规范化文件路径和精确行号匹配；不可映射项明确显示为 unmapped，不移动到邻近行。同一行有多个语句时稳定选择起始列最小的节点，列相同按 AST 遍历顺序选择。循环重入同一节点时会再次命中；从当前断点 continue 会执行当前语句，不会在同一 hook 位置立即重复暂停。

支持 `help`、`continue/c`、`step/s`、`next/n`、`finish/out`、`break/b PATH:LINE`、`delete ID`、`breakpoints`、`where/stack`、`locals`、`globals`、`print/p IDENTIFIER`、`list [COUNT]` 和 `quit/q`。`next` 依据 LWT frame ID 越过被调函数；栈只显示 LWT 帧。locals 按当前词法环境向外查到所属模块的全局环境，并遵从遮蔽；globals 只显示当前模块根环境。`print` 只读一个标识符，不执行任意表达式。复合值使用 LWT 格式化器，循环引用安全显示，超过 240 字符截断；源码列表最多 40 行。

stdout 仅保留 LWT `emit`；断点、源代码、栈、变量与调试诊断写入 stderr。无 `--commands` 时控制台 stdin 专供调试命令，程序 stdin 默认为 EOF；`--commands` 和 `--program-stdin` 分别指定命令文件和程序输入文件。命令文件严格 UTF-8，允许去掉一个开头 BOM，并以 CRLF/LF/CR 拆行；源码继续由 LWT loader 严格 UTF-8 解码、去除一个文件开头 BOM 并规范化换行；程序 stdin 严格验证 UTF-8 后以原始字节交给 `input()`。

普通成功/词法或语法错误/运行时错误/CLI 或文件错误沿用退出码 0/2/3/4。用户 quit 或程序暂停时命令 EOF 返回 1 并报告 DebugError。单步、next 或 finish 只会在真实存在的下一条可执行语句暂停；程序随当前操作直接结束时不会额外制造“程序结束”停点。

## 3. 测试与示例证据

`tests/test_debugger.py` 新增 28 项 unittest，通过真实 `python -m lwt.debugger` 子进程、临时 UTF-8 源文件、命令脚本和输入文件测试公开入口。覆盖断点验证/unmapped、精确行与同一行映射、循环重入、继续不重复命中、step/next/finish 和程序结束边界、递归与跨模块栈、局部/全局/遮蔽、只读标识符、循环/错误/复合值显示、UTF-8/BOM/CR 命令脚本、stdin 分流、`--` argv、错误恢复和退出码。测试用 `shell=False`、argv 数组及有上限超时。

固定示例位于 `examples/debugger/`：入口程序调用含空格文件名的函数模块，读入独立程序 stdin，命令脚本设置模块断点并查看栈与 locals。实际执行命令：

```powershell
python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt
```

退出码为 0；程序 stdout 精确为：

```text
demo:5
```

stderr 包含入口停点、`math helpers.lwt:2` 的已验证断点、函数 `math.sum` 的 LWT 栈和 `items = [2, 3]`。`test_checked_in_example_matches_the_normal_lwt_cli` 将同一示例通过普通 CLI 运行，并把程序输入 fixture 字节传入子进程；两种模式的退出码与 stdout 均相同，结果为 `0` 和 `demo:5\n`。调试器信息没有混入 stdout。

## 4. 实际验证记录

所有退出码均来自本轮实际命令；黑盒、完整性、profile 和 LSP 结果没有改写 S10/S11/S28/S29 固定数据。

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `python -m unittest discover -s tests -p "test_debugger.py" -v` | 0 | 28 项通过；含真实调试器 CLI 子进程、默认 stdin 与 checked-in 示例成对比较。 |
| `python -m unittest discover -s tests -q` | 0 | 421 项通过，耗时 77.401 秒。 |
| `python tools/run_tests.py` | 0 | 黑盒 287/287 通过，0 失败；数组/record/each 32，内置函数 43，CLI 错误 13，控制流/函数 43，错误恢复 40，集成 3，lexer/parser 52，modules 30，值/运算符 31。 |
| `python tools/check_project_integrity.py` | 0 | 287 cases、384 matrix links、287 referenced cases，完整性通过。 |
| `python -m unittest discover -s tests -p "test_execution_profile.py" -v` | 0 | S28 profile 19 项通过。 |
| `python -m unittest discover -s tests -p "test_lsp*.py" -v` | 0 | S29 Language Server codec/server 20 项通过。 |
| `python -m compileall -q lwt tests tools bench app` | 0 | 编译检查通过。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0 | `Effective LWT lines: 246`。 |
| `python -m lwt.debugger --help` | 0 | 显示 S30 命令和调用形式，无 traceback。 |
| 上述脚本化真实示例命令 | 0 | stdout `demo:5\n`；stderr 显示断点、停点、LWT 栈及局部变量。 |
| 示例普通 CLI 与调试 CLI 成对比较（unittest 子进程） | 0 | 两次退出码均为 0；stdout 逐字节一致。 |
| `git diff --check 744d0ca0aa6e2d96c7bf211ff842365b7827f891...HEAD` | 0 | 阶段提交差异无空白错误；最终报告提交后的复核结果由执行交接再次记录。 |

初次全量 unittest 在执行窗口达到 30 秒返回边界后没有及时保留会话句柄，因此没有使用其不可见输出作为证据；之后使用可追踪会话重新运行完整命令，取得上表 421 项结果。一次 PowerShell 直接使用 `<` 的普通 CLI 对照写法被 shell 拒绝（不是 LWT 错误）；随后改为 unittest 中 `subprocess.run(input=fixture_bytes, shell=False)` 成对运行并通过。

## 5. 保护范围与偏差

以 S30 基线 `744d0ca0aa6e2d96c7bf211ff842365b7827f891` 对比，以下文件/区域的 Git 差异为空：`app/log_report.lwt`、`tests/test_app.py`、S10 并发原始记录与报告、S11 `bench/results.json` 与性能报告、S28 固定 profile JSON/HTML、S29 `lwt/lsp*` 实现/测试/`reports/lsp-smoke.json`、正式语言规范、黑盒矩阵和 `tests/cases/`。更广的 `git diff --name-only <S30基线> -- lwt` 仅列出新建 `lwt/debugger.py`、`lwt/debugger_core.py` 和按本阶段范围修改的 `lwt/runtime.py`。

没有改写日志分析器、正式语言规则或 S28/S29 能力。本阶段在 runtime 的执行上下文增加默认值为空的可选 hook；普通 CLI/profile 路径不传 hook，profile 19 项及全量/黑盒测试通过。S29 代码未改，LSP 定向 20 项通过。没有运行并发/性能/profile 生成器，也没有新增依赖。

与阶段边界一致：没有写新的源语言语法，没有改 `docs/language-spec.md`、黑盒测试或矩阵；没有做 GUI、真实编辑器适配、时间回溯、条件断点、变量写入或任意表达式求值。

## 6. 变更文件清单

| 文件 | 内容 |
|---|---|
| `lwt/runtime.py` | 加入默认关闭的调试 hook 接口，并在程序开始、语句执行前、函数进入/退出时通知调试控制器。 |
| `lwt/debugger_core.py` | AST 源位置索引、断点、步进计划、LWT 调用帧、变量查看、显示格式和命令循环。 |
| `lwt/debugger.py` | CLI 参数、严格 UTF-8 命令/输入文件读取、同进程 loader/runtime 执行和退出码映射。 |
| `tests/test_debugger.py` | 28 项隔离子进程回归，覆盖命令、断点、栈/变量、错误、I/O 和普通 CLI 对照。 |
| `examples/debugger/main.lwt` | 可复现调试入口程序。 |
| `examples/debugger/math helpers.lwt` | 含空格路径的静态函数模块。 |
| `examples/debugger/program-input.txt` | 稳定的 `input()` 示例数据。 |
| `examples/debugger/session.txt` | 设置断点、next、step、栈与 locals 的命令脚本。 |
| `docs/debugger.md` | 调试器使用、命令语义、路径、输出/退出码和限制。 |
| `docs/s30-debugger-plan.md` | S30 设计取舍和验收对应表。 |
| `docs/s30-debugger.md` | 本执行报告。 |
| `docs/developer-guide.md` | 增加源码级调试工作流入口。 |
| `README.md` | 增加 S30 状态、阅读入口和 CLI 说明。 |
| `project.md` | 更新阶段状态及 S12 前置依赖，明确 S30 仍待审查。 |
| `docs/s12-final-delivery-plan.md` | 将 S30 纳入最终阶段前置审查与新克隆调试示例核验。 |
| `详细实施规划.md` | 更新阶段总览、最终交付依赖及 S30 状态。 |
| `LWT大作业总体方案与复检.md` | 将源码调试工具加入既定阶段路径，不改变语言目标。 |
| `阶段执行与审查路线图.md` | 增加 S30 阶段项、S12 依赖和执行结果。 |

## 7. 提交顺序、未验证项与交接

阶段分支提交按依赖顺序排列：

| SHA | 提交 |
|---|---|
| `562a89ecdfbd0f227712e48f720a942bd3843399` | `feat: add LWT runtime debugger hooks` |
| `9c877a2acb31c318fd2f7d7fbe9932621a603780` | `feat: add LWT debugger command-line entry` |
| `b0231b16210a5e5583f4e321e226a2c3db2ef1cf` | `test: cover LWT debugger sessions and example` |
| `2b18ec062fcca631cf78bc4524a00493ab413742` | `docs: specify LWT debugger usage and design` |
| `9d0f34dd32e8b05782b2bc98ee864ca80f258921` | `test: clarify debugger completion stepping` |
| `c44a5f5665de99c48fc7106e053936a2a4091040` | `docs: record S30 debugger review status` |
| `25057dbff8a8619a906ca152e3d307e809c83b0b` | `docs: mark S30 debugger implementation complete` |
| 最终报告提交 | 本文件为阶段最后一个提交；完整 SHA 在最终执行交接中列明。 |

尚未由本阶段验证：Python 3.10、Linux、远端 Actions、远端 `origin/main` tip（TLS 查询失败）、真实人工终端长期交互体验和真实编辑器集成。调试器不带 GUI；上述 S21 人工 GUI 遗留仍按 S12 规划处理。S23–S29 状态仍以各主窗口审查为准，S30 不表示先前阶段已经审查通过。执行窗口未合并、推送或开始 S12，最终工作区与分支状态见交接回复。
