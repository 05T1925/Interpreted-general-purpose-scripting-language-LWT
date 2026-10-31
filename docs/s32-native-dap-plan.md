# S32 规划与验收契约：LWT 的 VS Code 原生 Debug Adapter Protocol

> 后续复核：S32 已通过主窗口审查、远端精确 SHA 四格 CI 成功，并快进进入本地 `main`。详见 [S32 主窗口复核](s32-main-review.md)。本文件其余“待审”文字为原实施契约的历史记录。

状态：**已在 `feature/editor-integration` 实现，等待主窗口审查。** 已审查 S31 的三个原始提交通过正常合并保留并集成，合并提交为 `ddf1759fa4239eabc15488730917daec990da390`；S32 实施证据见 [S32 阶段报告](s32-native-dap.md)。S12 仍为最后交付阶段。

## 目标与价值

S31 把 LWT Run、Check 和 CLI Debug 接入 VS Code；S32 在此基础上实现原生 DAP，使 VS Code 标准调试界面可以设置源码断点、单步、查看 LWT 调用栈和只读变量。它复用 S30 真实 LWT runtime hook，不解析或模拟 LWT 语义。本文件保留设计边界与验收契约，实际实现结论以阶段报告为准。

这是开发工具创新，不新增课程语言语法，不替代 30 分的 LWT 课程应用，也不能作为解释器评分的新增语言能力。答辩时应展示“源程序—断点—栈帧—变量”的可复现实证，同时清楚说明局限。

## 资料依据

- [VS Code Debugger Extension Guide](https://code.visualstudio.com/api/extension-guides/debugger-extension)：调试器扩展通过 debugger contribution、launch 配置和 Debug Adapter 接入通用 UI；Executable 型 adapter 经标准输入/输出与 VS Code 通信。
- [Debug Adapter Protocol 官网](https://microsoft.github.io/debug-adapter-protocol/)与[协议概览](https://github.com/microsoft/debug-adapter-protocol/blob/main/overview.md)：DAP 是 JSON 消息协议，定义 initialize/launch/配置断点/停止事件/线程/栈帧/scopes/variables 和结束流程。外部 adapter 的 stdio framing 使用 Content-Length。
- [VS Code API](https://code.visualstudio.com/api/references/vscode-api)：扩展可通过 DebugAdapterExecutable 或 DebugAdapterDescriptorFactory 提供 adapter。
- [OpenAI AGENTS.md 建议](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)：仓库级指令应保持当前、适用且按任务条件指向文档；避免所有任务强制读取无关材料。
- [Agent Skills 规范](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx)：Skill frontmatter 必须包含 name/description，描述要明确任务触发条件；按需展开资源，避免把仓库所有上下文复制到 Skill。

## 建议架构

1. VS Code extension 增加 debugger contribution 与 launch 配置 schema；默认 Debug 当前保存的 .lwt 文件，允许程序参数、工作目录和程序 stdin 文件配置。
2. Python 标准库侧增加 stdio DAP server，例如 python -m lwt.dap_server。VS Code 使用配置的 Python executable，以 workspace 根作为 cwd 启动。DAP protocol stdout 必须只写 Content-Length 帧；日志和内部诊断写 stderr。
3. 复用 S30 的模块图、精确源码位置、runtime hook、step/next/finish、frame 环境和 LWT 值显示。新增可复用的事件驱动控制接口；不要通过解析 CLI debugger 的人类可读输出或合成文本命令来实现 DAP。
4. 继续保留 S30 CLI debugger，作为终端后退路径。重构后必须验证现有 CLI debugger 输出、退出码、脚本会话和示例无回归。
5. 单线程调试会话使用稳定的单个 DAP thread ID。每次暂停提供栈帧、局部/全局 scopes、可展开的数组/record/Error 子变量。执行恢复后使旧 variablesReference 失效。
6. 在 capabilities 中只声明真正实现的能力。默认不支持任意 expression evaluate、setVariable、function/conditional/log breakpoints、attach、multi-thread 或 exception pause。
7. 程序 stdin 用独立 UTF-8 文件配置；未配置时与 S30 一致按 EOF 处理。DAP stdio 永远保留给协议。本阶段不宣称 Debug Console 可交互地充当 LWT input()。

## 有界 MVP 功能

- DAP 生命周期：initialize、launch、configurationDone、disconnect/terminate，以及准确的 initialized、stopped、output、exited、terminated 事件。
- 断点：单文件/导入模块的源行断点；按 S30 精确行规则校验，未映射断点返回 verified=false，不静默挪到邻近语句。
- 执行：continue、stepIn、next、stepOut；暂停请求若无法安全实现则不声明，不用虚假响应。
- 检查状态：threads、stackTrace、scopes、variables；变量值遵守 LWT str/显示语义，引用只在当前暂停状态有效。
- 输出与退出：LWT stdout/stderr 转成 DAP output events，不污染协议 stdout；语法/模块预检/运行时错误有清晰输出和正确 exited code。
- 结束和取消：disconnect/terminate 能可靠结束正常程序和无界循环；runtime hook 在语句边界检查取消状态，不能用不受控宿主线程强杀留下残余进程。
- VS Code：使用 F5/Run and Debug 启动，支持 launch.json 与默认当前文件配置；旧的终端 CLI Debug 命令保留并改名以消除歧义。

## 必须解决的设计风险

- DAP 请求与运行线程协调：协议读取不能被正在运行的 LWT 程序阻塞；停止状态下的 DAP inspection 请求必须及时响应。实现需定义单一状态机、线程/队列边界、请求错误和关闭行为。
- Breakpoint 生命周期：VS Code 的 setBreakpoints 是针对一个 source 的整批替换；重复设置要替换而非追加。加载源码后返回真实 verified 状态和源位置。
- DAP 对象引用：stack frame IDs 与 variablesReference 在每次恢复后按规范失效或重建；防止过期引用访问新帧。
- 模块源路径：断点和 stack frame Source 使用规范化本地路径；含空格/Unicode 路径和相对 import 必须覆盖。
- 输入输出隔离：DAP framing 以 UTF-8 字节长度计算；处理分片读取、多帧、LF/CRLF 源内容与非 ASCII 输出；malformed frame 不得把 tracebacks 写入 stdout。
- 生命周期事件顺序：遵循 initialize → launch → initialized/configuration requests → configurationDone → stopped/continued → exited/terminated；对未知请求返回协议错误，而不是悬挂。
- 值格式化与循环引用：调用现有循环安全显示，不展开宿主对象，不允许求值产生副作用。

## 验收矩阵

| 层级 | 必须证据 |
|---|---|
| DAP codec | Content-Length 字节计数、UTF-8、分片/粘连帧、空/超长/坏 header、非法 JSON、响应序号与错误响应；protocol stdout 无杂字。 |
| DAP engine | 断点替换/验证、step/next/stepOut、递归与模块栈帧、shadowing 作用域、数组/record/Error 展开、引用失效、错误与 disconnect。 |
| 子进程端到端 | 使用真实 python -m lwt.dap_server，以标准 DAP 帧驱动真实 LWT 程序；断点停止、取栈与变量、继续退出；验证 argv/cwd/stdin、Unicode 路径、stdout/stderr 分离和正确退出码。 |
| S30 回归 | 现有 debugger 单测、28 项协议/CLI 回归和固定脚本示例全部通过；原命令不变。 |
| VS Code Extension Host | 在隔离 Host 中从 manifest 启动真实 DAP adapter；实测 F5 launch、gutter source breakpoint、停点行、Call Stack/Variables 请求、Continue 和结束事件；任何 skip 都必须显示为未验收。 |
| 回归与仓库 | Python 黑盒、完整 unittest、完整性工具、compileall、Node 单测、Extension Host、VSIX 构建、Markdown 链接、diff check 均记录准确。确认 S10/S11/S28/S29 保护证据未改变。 |

## 非目标

不新增 LWT 语法或运行时功能；不实现 Python 调试器；不重写整个 S30 控制器；不支持 attach、远程调试、多线程、任意表达式 evaluate、修改变量、条件/函数断点、logpoints、Watch、图形 REPL、动态模块、交互式 LWT stdin 或 Marketplace 发布。后续若确需拓展，应独立提出，而非偷偷扩展 MVP。

## Git 与交付边界

- 开始前核对工作树、stage/s31、main、origin/main、feature/editor-integration 的实际 SHA 和远端 Actions，不因旧报告照抄基线。
- 已在 `feature/editor-integration` 通过正常非快进合并集成 S31，保留了 S31 三个原始实现/测试/报告提交与 main 侧历史；完整关系见阶段报告。
- S32 完成后保留在功能分支，等待主窗口复审；不得把未复审的 S32 合入 main。
- 不强推、不 squash、不覆盖用户改动。保持 S31 与 S32 报告可单独追踪。
- S32 完成后更新 README、project.md、AGENTS.md 中仅需长期保留的协作规则、VS Code/调试器说明、路线图、S12 规划、开发记录和验收矩阵。
- S32 先经主窗口审查并按用户既有授权集成；S12 仍是最后的新克隆、CI、现场验收、PPT 与交付阶段。
