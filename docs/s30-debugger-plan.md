# S30 源码级交互调试器实施计划

状态：**实施中；此文档记录执行窗口的设计与验收边界，最终结果以 [S30 执行报告](s30-debugger.md) 和实际提交为准。**

## 目标与范围

新增 `python -m lwt.debugger`，通过 LWT AST/runtime 的专用回调在源语句开始前暂停，支持精确行断点、单步、跨函数 step-over/finish、LWT 栈和只读变量查看。调试器执行真实 LWT 程序；它不是静态检查器、Language Server、Python 调试器，也不改变正式语言语义或普通 CLI/profile 契约。

阶段只修改调试器入口/控制器、runtime 的可选调试钩子、独立定向测试、确定性示例和必要文档。不得依赖 `pdb`、`sys.settrace`、Python `eval`/`exec`，不得新增依赖，不进入 S12。

## 实施决策

| 问题 | 采用规则 | 理由/影响 |
|---|---|---|
| 断点行含多个节点 | 精确文件与物理行匹配；选择起始列最小的可执行语句，列相同按 AST 遍历顺序；不可映射时保留为 unmapped | 不做邻近行猜测，行为稳定且容易解释 |
| 循环与继续 | 每次运行到断点 AST 节点都可再次停；从当前暂停点 continue 直接完成该节点，不重入同一次 hook | 支持循环断点，同时避免继续后立即原地重复暂停 |
| step/next/finish | step 在下一个可执行语句停；next 以当前 LWT frame ID 为边界；finish 在目标函数返回后到达调用方后续语句时停，若程序随返回结束则直接结束 | 仅追踪 LWT 帧，不根据 Python 调用栈猜测 |
| 变量访问 | locals 从当前词法环境向外至模块全局，遮蔽由最近绑定优先；globals 只看当前模块根环境；print 只接受标识符 | 不执行表达式，也不产生程序副作用 |
| 调试命令与程序 stdin | 无 `--commands` 时控制台 stdin 专供调试命令，LWT stdin 默认为 EOF；`--commands` 和 `--program-stdin` 是独立文件输入 | 防止 `input()` 消费调试命令 |
| 输出与退出码 | emit 保持 stdout；调试信息写 stderr；原词法/语法/运行时/CLI 错误码保持 2/3/4；用户退出或暂停时命令 EOF 返回 1 | 可将调试会话输出与程序输出独立复核 |
| 控制器异常 | 专用调试控制信号可穿过 runtime；其它调试 hook 故障不伪装成 LWT RuntimeError，入口输出简洁 DebugError | 语言错误模型不受工具实现错误污染 |
| 复杂能力 | 不做条件断点、表达式求值、变量写入、远程调试、异常停点或时间回溯 | 限制范围在可验证的源码语句调试 |

## 验收对应

| 验收面 | 证据 |
|---|---|
| 命令解析、断点映射、单步/帧边界、变量可见性、显示安全 | `tests/test_debugger.py` 中隔离临时目录与公开子进程用例 |
| 真实解释器集成与退出码保持 | 调试/普通 CLI 的 stdout、退出码成对比较；stdin 与 argv 分离用例 |
| 模块与 Unicode 路径 | 含空格、中文路径和 Windows 冒号的静态模块断点用例 |
| 可复现演示 | `examples/debugger/` 中主程序、函数模块、stdin 和命令脚本 |
| 普通解释器/profile 不回退 | 完整 unittest、语言黑盒和 execution-profile 定向测试 |
| 文档与状态 | `docs/debugger.md`、阶段报告以及 README/project/路线图/规划/S12 状态同步 |

测试运行结果、固定文件保护对比和提交 SHA 只在最终报告生成后填写，不从旧阶段报告推定。
