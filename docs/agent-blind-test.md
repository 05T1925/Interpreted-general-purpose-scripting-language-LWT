# LWT S9 独立盲测记录

日期：2026-10-07。本文记录开发指南与仓库级 Skill 的三道独立 Agent 盲测、主执行窗口复跑、Skill 触发边界评估，以及可观察的限制。该记录在三道题全部完成后才写入仓库，盲测 Agent 均不能读取本文或其他题目的解答。

## 1. 目的、依据与协议

### 盲测目的和通过标准

验证一个没有本轮规划对话隐含解法的新 Agent，能否先阅读[开发指南](developer-guide.md)、[仓库 Skill](../.agents/skills/lwt-app/SKILL.md)和[正式语言规范](language-spec.md)，再仅使用有文档依据的 LWT 语法独立完成一项小任务，并通过公开 CLI 得到精确结果。通过标准为：使用 LWT 完成指定计算/筛选；只改自己的题目目录；CLI 退出码为 0、stderr 为空且 stdout 与题目逐字一致。

### 独立性和基线

- 三个新 Agent 上下文按 A、B、C 顺序分别调度；创建时使用 `fork_turns="none"`，不继承本执行对话。每个 Agent 只收到自己的那一道任务文字和同一份简短隔离规则，没有收到其他题目或答案。
- 三者均从包含当时开发指南与 Skill 的提交 `74bd743` 创建独立 detached Git 工作树；各自只写入自己的 `examples/agent-blind/<题目>/` 目录。前一 Agent 完成后才启动下一 Agent。
- 隔离规则要求先读开发指南、Skill 和规范；不得查看 `lwt/` 源码、`tests/cases/` 期望文件或其他盲测题/答案；只能通过 `python -m lwt` 执行程序；只报告可观察步骤和结果，不提供隐藏思维链。
- 上下文标识为协作工具提供的任务路径 `/root/blind_a`、`/root/blind_b`、`/root/blind_c`。调度界面没有向本执行窗口显示各 Agent 的模型标签，故模型标识记为“未能观测”。三个新上下文和三个独立工作树均已实际创建，不是当前聊天自测。
- 日期均为 2026-10-07。指南和 Skill 的盲测版本为提交 `74bd743`；没有在盲测中途修改指南或 Skill。

### 课程依据

核对了课程作业原文及上级目录课程材料：

- 《第 2 章：编程智能体简介》§2.2–2.3，尤其“技能文档”“规则文档”页：Agent 使用技能流程和项目规则，Coding Agent 应根据命令执行、观察结果并迭代。
- 《第 3 章：工作流与代码审查》§3.3–3.4：CI 不替代人工设计审查；AI 生成代码要对照差异和命令结果，避免虚构 API 或把未运行的检查说成通过。
- 《第 1 章：课程简介》后续章节目标和考核方式：课程要求开发指南与 AI 使用文档，并包含代码审查、文档检查、功能演示和答辩。

## 2. 实际发送的题目提示

每个 Agent 还收到了第 1 节的隔离规则。下列是分别交给 A、B、C 的任务文字；没有 Agent 收到三题合集。

### A：数组去重

> 阅读本仓库的 LWT 开发指南和语言规范，用 LWT 写一个独立脚本，处理数组 `[3, 1, 3, 2, 1]`。请构造一个新的结果数组，保留每个整数第一次出现的顺序，并用公开 CLI 执行脚本。脚本运行时应输出且只输出 `[3, 1, 2]` 这一行，退出码为 0。不要用 Python 代替 LWT，也不要把预期输出硬编码为多次 `emit`；请实际构造并输出结果数组。报告所依据的文档、脚本路径、命令、stdout、stderr 和退出码。

### B：record 统计

> 阅读本仓库的 LWT 开发指南和语言规范，用 LWT 定义 `record Task {name, done};`，构造以下四个任务：`design/true`、`implement/false`、`test/true`、`docs/false`。遍历这些 record，统计任务总数、已完成数和未完成数；按此顺序各输出一行。预期 stdout 精确为 `4\n2\n2\n`，退出码为 0。不要用 Python 代替 LWT。报告所依据的文档、脚本路径、命令、stdout、stderr 和退出码。

### C：文本筛选

> 阅读本仓库的 LWT 开发指南和语言规范，用 LWT 写一个脚本：从第一个 CLI 参数读取 UTF-8 文本文件；按 LF 分行，再按 `|` 分列；忽略空行；只保留首列经 `trim()` 后恰好等于 `WARN` 的行，并输出对应第二列经 `trim()` 后的文本，保持原顺序。输入 fixture 内容为以下文字（含一行空行）：
>
> ```text
> INFO|service ready
>
>  WARN | disk low \x20
> WARN|retry scheduled
> INFO|shutdown
> ```
>
> 这里 `\x20` 是为了在审计文档中无损保留提示行末一个 ASCII 空格的转写，实际发送给 Agent 的 fixture 行在 `low` 后、换行前含一个 U+0020。使用 CLI 的 `--` 参数传入 fixture 路径。预期 stdout 精确为 `disk low\nretry scheduled\n`，退出码为 0。不要用 Python 代替 LWT。报告所依据的文档、脚本和 fixture 路径、命令、stdout、stderr 和退出码。

## 3. Agent 过程与首次结果

平台没有给主执行窗口展示每个 Agent 的逐工具调用时间线；下表的首次尝试、文件和运行结果来自每个新 Agent 完成时提交的可观察报告，并由主执行窗口随后独立检查、复跑。三个 Agent 均报告没有失败尝试、提问或主执行窗口协助；没有收到需修正文档的问题。

| 题目 / 上下文 | 隔离工作树及基线 | Agent 产物 | Agent 首次报告的命令和结果 |
|---|---|---|---|
| A / `/root/blind_a` | `C:\Users\28641\AppData\Local\Temp\lwt-s9-blind-a-74bd743`，`74bd743` | `examples/agent-blind/array-dedup/main.lwt` | `python -m lwt examples/agent-blind/array-dedup/main.lwt`；stdout `[3, 1, 2]\n`，stderr 空，退出码 0。Agent 说明使用输入数组、结果数组、嵌套循环、`push` 和一次 `emit`。 |
| B / `/root/blind_b` | `C:\Users\28641\AppData\Local\Temp\lwt-s9-blind-b-74bd743`，`74bd743` | `examples/agent-blind/record-stats/record-stats.lwt` | `python -m lwt examples/agent-blind/record-stats/record-stats.lwt`；stdout `4\n2\n2\n`，stderr 空，退出码 0。 |
| C / `/root/blind_c` | `C:\Users\28641\AppData\Local\Temp\lwt-s9-blind-c-74bd743`，`74bd743` | `examples/agent-blind/text-filter/main.lwt`、`examples/agent-blind/text-filter/fixture.txt` | `python -m lwt examples/agent-blind/text-filter/main.lwt -- examples/agent-blind/text-filter/fixture.txt`；stdout `disk low\nretry scheduled\n`，stderr 空，退出码 0。 |

三份 Agent 产物从隔离工作树收集后，主执行窗口检查了源文件，确认算法均在 LWT 中实现；没有把计算委托给 Python。C 的 fixture 保留题目要求的空行和 `WARN` 行两侧空格。

## 4. 主执行窗口独立复跑

主执行窗口在阶段分支仓库根目录通过捕获进程字节的临时 subprocess harness 逐项调用下列公开 CLI 命令，并逐字检查 stdout、空 stderr 和退出码。Harness 只负责启动 CLI 和比较输出；没有作为项目文件提交。

| 命令 | 实际 stdout | stderr | 退出码 / 核对 |
|---|---|---|---|
| `python -m lwt examples/agent-blind/array-dedup/main.lwt` | `[3, 1, 2]\n` | 空 | 0；与预期完全一致 |
| `python -m lwt examples/agent-blind/record-stats/record-stats.lwt` | `4\n2\n2\n` | 空 | 0；与预期完全一致 |
| `python -m lwt examples/agent-blind/text-filter/main.lwt -- examples/agent-blind/text-filter/fixture.txt` | `disk low\nretry scheduled\n` | 空 | 0；与预期完全一致 |

表中 `\n` 表示一个实际 LF。C 题使用仓库根目录相对路径，验证了 CLI `--` 参数进入 `args()`，以及 `read_text()` 相对进程当前工作目录解析。

## 5. 指南示例的实际命令和结果

下表逐一运行了指南所展示/引用的完整程序。输入示例的 harness 向 stdin 写入 UTF-8 字节 `guide input\n`。命令均从仓库根目录经公开入口运行。

| 命令 | 实际 stdout | stderr | 退出码 |
|---|---|---|---:|
| `python -m lwt examples/guide/hello.lwt` | `hello, LWT\n42\n` | 空 | 0 |
| `python -m lwt examples/basic_io.lwt`（stdin=`guide input\n`） | `Enter one line:\nguide input\n` | 空 | 0 |
| `python -m lwt examples/control_flow.lwt` | `0\n-1\n2\n-3\n` | 空 | 0 |
| `python -m lwt examples/functions.lwt` | `120\n` | 空 | 0 |
| `python -m lwt examples/collections.lwt` | `draft\nreview\n["draft", "review"]\n[Task{name: "draft", done: true}, Task{name: "replacement", done: false}, Task{name: "late", done: false}]\n` | 空 | 0 |
| `python -m lwt examples/text_tools.lwt -- examples/fixtures/text_tools.txt preview` | `2\n[12, "apple", 5]\n[7, "pear", 4]\n` | 空 | 0 |

指南中的诊断格式也用既有非法字符用例实跑：

```text
命令：python -m lwt tests/cases/cli-errors/lex-location-invalid-character.lwt
stdout：空
stderr：tests/cases/cli-errors/lex-location-invalid-character.lwt:1:6: LexError: unexpected character U+0040\n
退出码：2
```

`stderr` 最后一处 `\n` 表示实际结尾 LF；没有 Python traceback。

## 6. Skill 元数据与路由评估

### Skill 格式核对

`.agents/skills/lwt-app/SKILL.md` 包含 YAML front matter，`name` 为 `lwt-app`，描述列出 `.lwt` 程序/小型应用的创建、修改、调试、验证触发场景，并明确排除概念/语言设计问题、解释器开发和普通 Python 程序。正文给出按文档、澄清需求、用已实现语义设计、编辑 `.lwt`、运行 CLI、核对输出、报告限制的流程；三条相对链接从 Skill 所在目录解析均存在。

官方资料核对日期：2026-10-07。

| 官方资料 | 支持的结论 |
|---|---|
| [Skills – Plugins](https://developers.openai.com/plugins/concepts/skills) | `SKILL.md` 提供名称、用于判断何时考虑 Skill 的描述、工作流指令和可选资源；元数据用于匹配请求，详细步骤适合放在正文。 |
| [Build skills – Plugins](https://developers.openai.com/plugins/build/skills) | 手写 Skill 应有 `name`/`description`；描述应表达触发场景；正文说明输入、步骤、输出、不能推断的事实以及参考文件；保持单一聚焦，可把详细资料放在引用文件；评估应覆盖直接、间接、不完整、不应触发和边界请求。 |
| [Testing Agent Skills Systematically with Evals](https://developers.openai.com/blog/eval-skills) | 使用少量代表性正向和 `should_trigger=false` 负向提示检查触发边界，并根据误触发/漏触发持续补充评估样例。 |
| [Build skills（Codex 本地技能）](https://learn.chatgpt.com/docs/build-skills) | 当前 Codex 文档说明仓库级技能从 `.agents/skills` 等位置发现；这支持本项目用该目录放置 Skill。它不是关于所有 Agent 平台自动发现规则的证据。 |

前三项是任务指定的官方 Developers 页面；最后一项用于核对 Codex 项目级目录。项目保留通用 Agent Skills 文件格式，不声称其他产品或所有 Agent 都会扫描本仓库目录。

### 代表性请求评估

当前调用界面没有给本执行窗口提供“Skill 自动路由/是否加载”的事件或调试结果。下表的“实际观察”因此只记录对已写描述的人工复核；没有把期望触发结果冒充为自动路由实测。

| 请求 | 期望 | 实际可观察结果 |
|---|---|---|
| “请用 LWT 写一个数组处理脚本。” | 触发 | 无法直接观测自动选择；人工检查描述确认匹配创建 LWT 程序的明确场景。 |
| “帮我修改这个 `.lwt` 程序，让它正确读取参数并输出统计。” | 触发 | 无法直接观测自动选择；人工检查描述确认修改、调试 `.lwt` 程序属于适用范围。 |
| “请用 Python 写一个文件统计脚本。” | 不触发 | 无法直接观测自动选择；描述明确排除普通 Python 程序。 |
| “请帮我修复 `lwt/parser.py` 的语法解析 bug。” | 不触发 | 无法直接观测自动选择；描述明确排除解释器实现修改。 |
| “我想了解 `each` 的浅快照语义。” | 通常不触发；若要求实际写/改程序则触发 | 无法直接观测自动选择；描述排除单纯语言设计讨论，适用条件限定为创建、修改、调试或验证 LWT 程序。 |

盲测 Agent 被明确要求阅读 Skill，因此三次成功不是“Skill 自动路由成功”的证据。未来如运行环境提供可观察的 Skill 选择记录，应对上表提示做真实路由回归。

## 7. 文档修订与未验证项

- 三道题均一次运行成功；Agent 没有报告失败、疑问或需要协助的事项。未发现指南或 Skill 遗漏、含糊或错误导致的失败，因此没有盲测驱动的内容修订，也没有把同一个已看过解法的上下文称作复测。
- 入门完整程序和所引用的输入输出、控制流、函数、集合、文本示例都由主执行窗口运行通过。指南完整 hello 程序与 `examples/guide/hello.lwt` 内容相同；其他示例代码块已标注为片段并链接到完整文件。
- 三个 Agent 的模型标签、平台内部会话 ID 和逐工具事件时间线未暴露；报告使用可观测的任务路径标识。独立上下文通过 `fork_turns="none"` 和三个分别创建的工作树得到验证。
- Skill 的自动激活结果无法在当前平台直接观察，故只完成 front matter/描述人工审查和正反向场景评估，不宣称自动路由评测通过。
- 盲测和示例均在当前 Windows 环境通过本地 CLI；没有以此替代 S8 CI 中尚未验证的 Linux/Python 3.10 结果。
- 三份 Agent 盲测脚本和 fixture 是 S9 示例，不加入 S8 `tests/cases/`，也不改变其 194 项计数或覆盖矩阵。
