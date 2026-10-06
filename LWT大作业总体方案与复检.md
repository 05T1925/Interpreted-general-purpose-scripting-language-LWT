# LWT 语言大作业：总体方案与复检

> 状态：规划版，2026-10-06。语言名 **LWT** 已确认；解释器、测试、应用和性能数据尚未实现。本文件是实施蓝图，不代替最终语法规范或测试报告。

## 1. 目标与取舍

以一个能现场演示、行为定义清楚的解释型语言为主线，交付解释器、语言规范、黑盒测试、性能对比、Agent 开发指南、Agent 编写的应用、开发记录、Git 历史和介绍 PPT。优先完成全部必需功能及可复现证据，再做语法糖和性能优化。目标不是在基准测试中击败 Python，而是给出正确、公平、可解释的结果。

**建议实现方式：Python 3 标准库 + 手写词法分析器 + 递归下降/优先级表达式解析器 + AST 解释执行。** 不把 LWT 源码替换成 Python 代码后交给 `eval`/`exec`；这样词法、语法、作用域和运行时语义都能在答辩时逐层解释。[《Crafting Interpreters》作者仓库](https://github.com/munificent/craftinginterpreters)展示了树遍历解释器、测试集和字节码虚拟机两条实现路径；本项目先采用范围更可控的树遍历路径。Python 用于宿主实现和测试驱动，LWT 才是被测试与应用开发的语言。

| 宿主语言选择 | 对本作业的影响 | 判断 |
|---|---|---|
| Python 标准库 | 解析器、测试驱动和脚本分发速度快；AST 遍历性能通常受宿主调用开销影响 | 首选，目标兼容 Python 3.10+；当前机器已检测到 Python 3.13.7 |
| Java | 类型与模块边界清楚，性能潜力较好；同样范围需要更多样板代码和构建配置 | 若课程要求 Java 再切换 |
| C++ | 可控制底层性能；内存、构建和跨平台演示成本最高 | 当前评分重点下不优先 |

### 需求与交付映射

| 评分项 | 必须能展示的证据 | 计划交付位置 |
|---|---|---|
| 解释器 20 分 | 从 `.lwt` 文件执行整数、字符串、数组、结构、输入输出、分支循环、函数；错误有定位 | `lwt/`、`examples/`、`README.md` |
| 自动测试 20 分 | LWT 编写的正反用例；一条命令运行；覆盖表与真实通过记录 | `tests/cases/*.lwt`、`tests/expected/`、`tools/run_tests.py`、`docs/test-matrix.md` |
| 性能测试 10 分 | LWT 与同功能 Python 脚本，结果一致、环境和原始时间可复现 | `bench/`、`reports/performance.md` |
| 语法与指南 20 分 | 完整 EBNF、语义、内置函数、错误说明、示例；人和 Agent 都可使用 | `docs/language-spec.md`、`docs/developer-guide.md`、`AGENTS.md`、`.agents/skills/lwt-app/SKILL.md` |
| Agent 应用 30 分 | 至少 200 行有效 LWT 源码，功能完整；提示与修改记录、独立测试和演示 | `app/log_report.lwt`、`app/fixtures/`、`docs/agent-dev-log.md` |
| 总交付 | 可追溯 Git 提交；现场讲解与演示 | `.git/`、`slides/LWT介绍.pptx`、`README.md` |

`大作业内容.md` 是要求原文，以它为最终范围基线。课件另外强调模块接口、自动测试、性能、Agent 规则与技能、代码审查和 Git 工作流；这些转成下文的验收动作，而不额外扩张语言核心功能。参阅[课程简介](../第1章：课程简介.pdf)、[编程智能体简介](../第%202%20章：编程智能体简介.pdf)、[工作流与代码审查](../第%203%20章：工作流与代码审查.pdf)。

## 2. LWT 0.1 语言设计草案

定位为面向文本处理和命令行小工具的动态类型脚本语言。特色是 `record` 命名字段结构、`when ... otherwise` 分支、`each` 数组遍历和 `emit` 输出语句的组合；同时保留熟悉的表达式、花括号与分号。**“有特色”须体现在语法与行为文档和演示代码中，不能只改语言名。** 最终语法文档须在实现前冻结下面的边界。

```lwt
record Student { name, score };

fn result(s) {
    when (s.score >= 60) { return "pass"; }
    otherwise { return "retry"; }
}

let students = [Student{name: "Li", score: 87}, Student{name: "Wu", score: 56}];
each (s in students) {
    emit s.name + ":" + result(s);
}
```

| 主题 | 拟定语义，需写入最终规范和对应测试 |
|---|---|
| 词法 | UTF-8 源码；标识符用 ASCII 字母、数字和 `_`（首字符不能是数字）；字符串内容可含 Unicode；`#` 到行尾是注释；语句以 `;` 结束；记录行列号。 |
| 值 | 任意精度整数、字符串、布尔 `true/false`、`null`、数组、命名 `record` 实例。`null` 用于无显式返回值和输入结束。 |
| 表达式 | `+ - * / %`、比较、`== !=`、`and/or/not`、括号、调用、数组索引、字段访问。`/` 为向负无穷取整的整数除法，`%` 与之配套；除零报错。`+` 只允许整数加法或字符串拼接，不做隐式转换。条件必须是布尔值；`and/or` 短路。 |
| 数组 | `[a, b]`、零起始索引、索引赋值、`len(a)`、`push(a, x)`。负索引或越界报错。`each` 在进入循环时复制元素序列，因此循环内追加元素不改变本轮次数。 |
| 结构 | 顶层 `record Name { field, ... };` 声明；`Name{field: value, ...}` 构造时每个字段恰好一次；支持读写 `obj.field`，未声明字段报错。 |
| 相等 | 整数、字符串、布尔、`null` 按值比较，且类型不同不相等；数组和结构实例按身份比较，避免循环引用造成无限递归。 |
| 变量与作用域 | `let name = expr;` 创建当前块变量，`name = expr;` 修改已存在变量；重复声明、未定义读写报错。块有词法作用域，函数调用有独立局部环境；全局变量可访问。 |
| 控制与函数 | `when (...) {...} otherwise {...}`、`while (...) {...}`、`each (x in array) {...}`；`fn name(params) {...}` 仅在顶层声明，可递归；实参与形参数量不符报错；`return` 仅在函数内。暂不支持闭包、类、异常捕获和多线程语法。 |
| I/O 与内置函数 | `emit expr;` 输出一行；`input()` 读一行，EOF 返回 `null`；`args()` 获取脚本参数；`read_text(path)` 以 UTF-8 读文件；`len`、`push`、`split`、`trim`、`to_int`、`str`。文件不存在和转换失败应是有定位的运行时错误。 |
| 命令行 | `python -m lwt file.lwt -- arg1 arg2`；成功退出码 0，词法/语法错误 2，运行时错误 3，入口或文件无法读取 4。错误写 stderr，正常输出写 stdout。 |

**需要在语法冻结时再核对的细节：** 一元负号与乘除优先级、赋值结合性、转义字符、字符串换行、函数声明前调用、`emit` 对复合值的显示形式、`split` 对空字段的处理、`to_int` 的空白与符号规则、`read_text` 读取到变化中的文件时的行为。每项必须有一个正例或反例；不能让 Python 的默认行为无意中变成 LWT 语义。

## 3. 解释器结构与接口

```text
UTF-8 源文件
  → lexer.py（Token：类型、文本、行、列）
  → parser.py（AST；语法错误）
  → runtime.py（环境、值、函数、内置函数、解释执行）
  → cli.py / __main__.py（参数、stdin/stdout/stderr、退出码）
```

`ast_nodes.py` 仅描述语法树；`errors.py` 统一错误类别和源位置。解释器不应在内部调用 CLI；测试只通过公开的 `python -m lwt` 入口执行，避免把白盒测试误称黑盒。数组和 record 使用 LWT 运行时包装对象，便于限定索引、字段、相等和输出行为。内置函数检查参数数量与类型，不直接把 Python 异常栈暴露给用户。

实现顺序：词法与定位 → 表达式/变量/输出 → 块与控制流 → 函数与调用栈 → 数组与结构 → 输入/文件内置函数 → 诊断与命令行。每一步必须同步更新规范、用例和示例。

## 4. 黑盒测试方案

一条命令：`python tools/run_tests.py`。每个测试的**被执行脚本均为 `.lwt`**；Python 驱动只负责启动进程、提供 stdin、收集 stdout/stderr/退出码并与固定期望比较，不在 Python 中重写 LWT 逻辑。[Python `subprocess.run` 文档](https://docs.python.org/3/library/subprocess.html)支持输入、输出捕获和超时。用例旁放 `.out`、可选 `.err`、`.in` 与元数据（预期退出码）；驱动限制单例运行时间，全部结束输出通过数、失败差异和总耗时。

| 测试组 | 重点场景 | 规划数量 |
|---|---|---:|
| 词法与语法 | 空文件、注释、Unicode 字符串、转义、优先级、缺分号、未闭合字符串、错误位置 | 12+ |
| 基本类型与运算 | 大整数、负数除法、除零、严格类型、字符串拼接、短路、条件类型错误 | 12+ |
| 数组 | 空/嵌套数组、读写、追加、别名、负索引、越界、遍历时追加 | 9+ |
| 结构 | 字段顺序、读写、别名、缺失/重复/未知字段、跨类型相等 | 8+ |
| 控制流 | `when/otherwise`、嵌套 `while/each`、零次循环、块作用域 | 8+ |
| 函数 | 零/多参数、递归、返回、隐式 `null`、重名、参数数量错误、非法 `return` | 9+ |
| I/O 与 CLI | stdin/EOF、Unicode、参数、文件读、缺文件、stderr/退出码 | 7+ |
| 综合回归 | 多功能组合、应用样例、基准脚本正确输出 | 5+ |

目标是 **70 个以上可独立执行用例**，但覆盖完整性以 `docs/test-matrix.md` 的“规范条款 → 正常/边界/错误用例”对应关系判定，不靠数量代替覆盖。错误信息中路径或平台行尾可能变化；驱动只规范化换行，其他输出应严格比较。测试结果记录 Python 版本、操作系统、Git 提交号和失败清单。解释器内部还可有少量单元测试，但不能替代交付的黑盒集。

## 5. 性能对比方案

至少两组同功能脚本：①整数循环与分支计算；②数组构建和遍历统计。每组有 `bench/<name>.lwt` 和同算法的 `bench/<name>.py`，输入规模通过参数传递，输出同一校验值。Python 对照脚本应使用相同循环算法，不能换成 `sum` 等 C 实现内置捷径。测前先比较输出，不一致则停止计时。

`tools/benchmark.py` 分别启动两个独立进程测**端到端时间**（含启动、读取与解析）；对每个输入先预热，再重复至少 10 次，交错运行两种实现，使用 `time.perf_counter_ns()` 计时，保存每次原始结果，报告中位数、最小值、波动范围和 `LWT/Python` 时间比。分别给出小/中/大输入，确认大输入不至于让答辩超时；记录 CPU、内存、OS、Python 版本、命令、输入、输出校验值、Git 提交。`timeit` 官方文档提醒重复测量和环境噪声会影响解释，因此不只报告单次最快数字；[计时器说明](https://docs.python.org/3/library/timeit.html)、[`perf_counter_ns` 说明](https://docs.python.org/3/library/time.html#time.perf_counter_ns)。

解释结果时把端到端差距、算法复杂度和解释器热点分开：若 LWT 更慢，应如实说明词法/AST 遍历、动态类型检查和 Python 宿主调用开销；只有测出瓶颈后才考虑缓存 token、减少重复查找等优化。优化前后保留同输入数据和原始记录，不调整算法来“制造”优势。

## 6. Agent 应用：只读日志分析器

应用名暂定 **LWT Log Report**，主体源码 `app/log_report.lwt` 至少 200 行**有效 LWT 代码**（不靠空行、复制注释或生成数据凑数）。命令行从一个 UTF-8 文本日志读取记录，输入每行 `时间|级别|模块|消息`，只允许消息中不含 `|`；接受级别过滤、关键词过滤和 Top-N 参数，输出总数、有效/无效记录数、各级别数量、模块排名和匹配示例。空输入、坏记录、Unicode、非法选项给出明确行为。提供小型样例和预期结果，用脚本一键演示。

代码自然使用数组、`record`、函数、分支、两种循环、文件读取、参数解析、字符串处理。统计按一次线性扫描组织；模块数量较少时可用数组保存模块统计，明确记录高基数情况下的查找成本。输入一次读入内存，所以报告说明文件大小与内存限制。该工具**只读输入、只写 stdout**：多个进程可并发读取同一份不变的日志，验证 1/2/4 个并发进程输出一致并记录耗时；运行期间日志若被其他进程修改，不承诺一致快照，演示使用固定样本。这是针对应用并发与读取性能的实际设计与验证，不依赖尚未实现的 LWT 多线程语法。

Agent 开发记录应记录任务提示、使用的 Agent/模型、时间、生成文件、Git 提交、运行命令与结果、人工审查发现和修正；不把未经运行的 Agent 文字当作成功证据。第一轮由人冻结 LWT 规范和最小 API，再让 Agent 按指南实现应用；测试或接口不足时先补文档/解释器，再继续应用开发。

## 7. 人与 Agent 的文档设计

- `docs/language-spec.md`：完整词法、EBNF、优先级表、类型和内置函数、作用域、错误码、边界语义，示例都能执行。
- `docs/developer-guide.md`：安装与运行、一页速查、常见模式、调试、测试、文件处理、已知限制和示例索引。
- `AGENTS.md`：本仓库固定约束，例如从规范出发、使用公开 CLI 验证、修改语言行为同步更新规范和用例、不得调用 Python `eval/exec` 实现 LWT 语义。
- `.agents/skills/lwt-app/SKILL.md`：面向“用 LWT 写应用”的可复用步骤、触发描述、示例与验收命令；引用规范而不大段复制。官方 OpenAI Docs 说明 `AGENTS.md` 用于项目级指导，而 `SKILL.md` 带 `name`、`description` 和操作步骤，仓库技能可放在 `.agents/skills`：[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、[Build skills](https://learn.chatgpt.com/docs/build-skills)。

Agent 实测任务：让一个新会话**只读上述文档与样例**，独立写出数组去重、结构统计、文本筛选三个短脚本，并运行通过。若经常误用语法，优先修改指南与示例，再重测；这样能验证“Agent 能顺利编写代码”，而不只验证文档存在。

## 8. Git、阶段计划与验收门槛

工作目录本次检查时尚无 Git 仓库；从规划文件开始初始化并保持真实的阶段提交。Git 官方教材说明提交记录的是暂存区快照，建议每到可复查状态保存一次：[Recording Changes](https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository)。课程课件要求先审查和测试再提交，并保留可追溯的修改原因。

| 阶段 | 具体结果 | 进入下一阶段的门槛 | 建议提交主题 |
|---|---|---|---|
| 0 方案冻结 | 本方案、目录约定、Git、需求映射 | 讲得清语言边界和交付物 | `docs: establish LWT plan` |
| 1 最小解释器 | 词法、解析、基础表达式、变量、输出 | hello/运算/错误定位黑盒通过 | `feat: add lexer and parser` 等 |
| 2 全功能 | 控制流、函数、数组、结构、I/O | 必需功能矩阵全部有运行证据 | 按功能拆分提交 |
| 3 规范与测试 | 完整规范、70+ 黑盒、一次执行入口 | 全套通过；失败信息可复现 | `test:`、`docs:` |
| 4 性能 | 两组配对脚本、原始数据、报告 | 输出相同；方法、环境、结论一致 | `bench:` |
| 5 Agent 应用 | 200+ 行 LWT 应用、指南、开发记录 | 功能、异常输入、并发读取演示通过 | `feat: add log report app` |
| 6 交付与答辩 | README、PPT、演示脚本、最终复检 | 全新目录按说明可运行；PPT 与代码一致 | `docs: prepare presentation`，打提交标签 |

每个阶段采用“看需求 → 小块修改 → 运行相关测试 → 检查 `git diff` → 提交”的闭环。最后从 Git 历史证明迭代过程，不能到结束才一次性提交。PPT 建议 10 页左右：任务与目标、语言特色、语法示例、架构、核心实现、测试覆盖、性能方法与结果、Agent 指南与记录、应用演示、限制与总结；现场顺序为解释器运行 → 全部测试 → 应用 → 性能报告与 Git 历史。

## 9. 方案复检：已识别风险与处理

| 风险或易漏点 | 复检结论与处理 |
|---|---|
| 语法自由导致测试与文档不一致 | 先冻结词法/优先级/错误/作用域；任何改动同提交更新规范、用例、示例。 |
| 把测试驱动代码当作“LWT 测试脚本” | 测试输入全部使用 `.lwt`，驱动仅比较外部行为；保留覆盖映射。 |
| 脚本可运行但不算独立解释器 | 明确 Token → AST → 运行时；禁止直接把用户源码交给 Python `eval/exec`。 |
| Python 比较不公平或没有复现实验 | 同算法、同输入、先核对输出；保留原始时间和完整环境，端到端口径一致。 |
| Agent 文档存在但 Agent 用不起来 | 新会话盲测三道小任务，按失败修订指南；开发记录保留人工纠错。 |
| 应用够 200 行但功能空洞 | 统计有效代码行，要求过滤、聚合、排行、坏输入处理和可重复样例同时成立。 |
| 并发需求被忽略 | 应用采用只读设计，并行进程一致性与读取耗时作为证据；语言级线程属于后续扩展。 |
| Git、PPT 和演示临近提交才补 | 从阶段 0 开始提交；每阶段保留截图/命令/结果，阶段 6 只整合真实证据。 |

**当前尚未验证的事项：** 目标机器上的 Python 版本和执行耗时、完整语法实现复杂度、实际 benchmark 数据、70+ 用例通过率、Agent 的 LWT 编码成功率、应用行数与并发读取结果、PPT 与最终代码一致性。这些只会在对应阶段有运行结果后标为“通过”。

## 10. 最终提交前逐项检查

1. `python -m lwt examples/hello.lwt` 与故意出错的脚本展示 stdout、stderr、退出码。
2. `python tools/run_tests.py` 一次跑完全部 `.lwt` 用例，覆盖表无空项。
3. `python tools/benchmark.py` 生成可复核原始数据，报告中的数字与其一致。
4. LWT 应用有效源码行数不少于 200；正常、空、坏记录、Unicode、并发读取场景都能复现。
5. 新 Agent 会话能依据指南完成三个小脚本；开发记录含失败、修正和验证。
6. `git log --oneline --decorate` 展示阶段过程；工作区状态明确；README 给出从零运行命令。
7. PPT、现场演示命令、最终语法、测试数和报告数字逐一对照当前提交。

## 11. 资料与判断边界

- **作业原文**：[`大作业内容.md`](大作业内容.md)，本方案所有“必须”项以此为准。
- **课程课件**：上文列出的三份 PDF，提供课程重视的 Agent、接口、工作流、审查、测试和性能背景。
- **解释器实现参考**：[Robert Nystrom 的《Crafting Interpreters》仓库](https://github.com/munificent/craftinginterpreters)。借鉴分层思路，不复制 Lox 语法或代码作为 LWT 交付。
- **工具依据**：[Python `subprocess`](https://docs.python.org/3/library/subprocess.html)、[`timeit`](https://docs.python.org/3/library/timeit.html)、[`time.perf_counter_ns`](https://docs.python.org/3/library/time.html#time.perf_counter_ns)、[Git 官方教材](https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository)。
- **Agent 文档依据**：官方 OpenAI Docs 的 [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) 与 [Build skills](https://learn.chatgpt.com/docs/build-skills)。

外部资料用于方法核对，语言特色、应用边界与阶段门槛是本项目的设计判断。实施时按当前规范和实测结果修订，不把规划中的数量或性能写成已完成事实。
