# S39 完整派发提示：Agent 可编写 LWT 策略的编程工作坊

> 这是 S12 前**最后一个功能阶段**。目标不是再增加一套固定 AI 或只给 GUI 换皮，而是让第三方 Agent 仅凭 LWT 规范、策略 SDK 和公开 CLI，就能编写一份新的 LWT 策略、加入本地可信目录、参与可验证对局，并留下完整开发证据。S39 复审后立即转 S12 新克隆验收、PPT、现场演示与交付。

## 0. 开工与依据

工作目录 `C:\Users\28641\Desktop\大三上\程序设计实践\大作业`。先读 `AGENTS.md`、`project.md`、`大作业内容.md`、`docs/language-spec.md`、`docs/developer-guide.md`、[S37/S38 联合审查](s37-s38-main-review.md)、[S36 LWA1](snake-strategy-protocol.md)、[S38 决策证据契约](s38-policy-proof-contract.md)及 `app/lwt_snake/arena.py`、`strategy.py`、`game.lwt`、两份 LWT 策略和测试。教师要求与已审查规范是权威；网页只用于设计启发。先记录 `git status -sb`、HEAD、main、origin/main、实时远端、merge-base、CI run 与保护文件。必须从**已审查并集成 S38 的实际最新 main** 建立 `feature/lwt-strategy-workshop`，不要从旧 main 或工作报告推断集成成功。若 S37/S38 尚未完成远端四格或主窗口集成，先反馈证据，不在未审查基线上开工。不重写共享提交、不强推、不关闭 TLS 校验。

设计启发：Robocode 的官方入门把“由使用者编写机器人程序再进入同一竞技场”作为编程游戏核心；本项目应保持 LWT 自己的 LWA1/LWS1 规则和现有录制/验真，不复制其 API、代码或界面。Python 官方子进程文档说明超时后还需回收进程；LWT 脚本的时间限制**不是安全沙箱**，因此仅支持明确选择的**可信本地源码**，不可宣传可安全执行陌生下载的策略。参考：[Robocode 官方介绍](https://robocode.dev/articles/intro.html)、[Python subprocess](https://docs.python.org/3/library/subprocess.html)。

## 1. 用户可见闭环与功能边界

给使用者一个清楚的“写策略 → 检查 → 试跑 → 擂台 → 双层验真 → 解释一步”的路径：

1. 仓库中提供 `app/lwt_snake/strategies/`（或等价、明确的目录）、一个可复制的 LWT 策略模板、一个比 baseline/BFS 有真实算法区别的 Agent 编写示例策略（例如食物方向启发式 + 本步安全过滤，具体由执行者选择，不能事先承诺更高分）。新策略仍是**长驻公开 LWT CLI 程序**，接收 LWA1、输出 LWA1。Python 不计算策略决定、合法性、游戏规则或得分。
2. 提供版本化策略目录 manifest（例如 `strategy-catalog.json`），用户新增策略只需添加 `.lwt` 与一条严格 manifest 项，**无需修改 Python 白名单源码**。内置 `baseline/bfs` 默认仍可直接使用；自定义策略必须用显式 `--catalog` 启用。ID 规范、源文件路径、去重、源码 digest、LWA1 版本、模板限制在编码前冻结。相对路径必须位于受信任的仓库策略目录内，拒绝 `..`、绝对路径、符号链接逃逸、重复 ID、覆盖内置 ID、过大源码、非法 UTF-8。这个边界只是防止误用路径，**不是隔离不可信程序**。
3. 本阶段只支持单文件、无 `import` 的自定义策略，避免 S25 模块依赖闭包使现有源码 digest 失真。用 AST 或静态检查实际拒绝 import，不用字符串扫描伪判；支持文件名含空格/Unicode。对运行前源码严格 UTF-8/LF 规范化求 digest，运行后复核源文件未变；若要快照执行，保存的是同一已检查字节且不破坏路径语义。若运行期间源码变化，整局必须失败并明确指出，而非生成错误归属证据。
4. 增加 `--check-strategy ID --catalog <可信目录文件>` 或等价入口：先运行 LWT 静态检查，再以固定、小而有区分力的 LWA1 帧做真实 CLI 协议/行为烟测，诊断指出第几帧、预期协议字段、实际输出或超时。检查只能证明语法/协议基础和几个场景，不能保证策略永不碰撞或能获胜。可提供 `--init-strategy NAME` 创建模板，但默认不得覆盖已有文件；若这会明显扩大范围，可只提供模板复制说明。
5. `arena` 显式选择 `baseline,bfs,<custom>` 与固定种子后，仍按 S38 v2 的原则分别用新 LWT 游戏进程和新 LWT 策略进程双层验真。自定义策略结果须记录目录 manifest 的版本与摘要、策略 ID/路径/源码摘要以及每局决策、回放摘要。旧 S37 v1 与 S38 v2 固定样例**原样保留且仍可验**；若必须扩展结果结构，用 v3 并实现清楚的向后兼容。验证自定义结果时必须显式提供同一可信本地 catalog，不得从结果 JSON 自动运行任意路径或复制的未知源码。缺 catalog、源码改动、catalog 指向另一文件都必须非零退出。`--explain` 同样执行双层验真后才能展示。

## 2. Agent 独立开发证据

按课程第 4、5 项，把“Agent 真能使用指南编写 LWT 程序”做成可复核实验：先冻结模板、策略 SDK 和任务提示，再给一个**独立上下文**的编程 Agent 一份限定任务（例如第三种策略要在保持合法移动前提下使用与 baseline/BFS 不同的可解释启发式）。它应只收到公开文档、模板与任务，不从执行窗口获得现成策略答案；在隔离分支/工作树提交 LWT 源码和 manifest，记录原始提示、首次静态/协议测试、实际错误、修正、最终命令与输出。执行窗口审查后再正常集成该 LWT 策略。若平台无法观察 Agent 的自动 Skill 选择或逐事件时间线，就明确标“不可观察”，不要声称实测。若无法取得独立 Agent 上下文，至少保留准确的 Agent 对话提示与产出链，不能伪造盲测。

## 3. 编码前契约与验收设计

先写 `docs/s39-strategy-sdk-contract.md` 并单独提交，冻结 CLI、manifest/schema、默认与显式 catalog 行为、路径/大小/时间/子进程边界、结果 v3（若需要）、退出码、兼容性与证明语义。不要把 `--check` 当作运行时安全保证，不把相同 seed 的少量分数说成策略优越性。新策略的运行/验真应仍由真实 `python -m lwt` 完成，进程命令用 argv 数组、`shell=False`，沿用 S36 有界桥接与回收。

验收必须至少覆盖：

- 成功路径：从模板产出第三个 LWT 策略、不改 Python 策略映射即可由 manifest 注册；静态检查和固定协议帧通过；三种策略 × 至少三个 seed 完成有界对局；每局两级证据 true；workers=1/2/4 的逻辑结果及回放/决策字节一致；`--explain` 展示自定义策略一步；所有测试完成后无残留游戏/策略进程。
- 不可信输入与变更：路径逃逸、symlink、绝对路径、非法 ID、重复/覆盖 ID、无效 UTF-8、超大源码、import、坏 manifest、源码运行前后变化、协议坏帧/超时/stderr 洪流、结果中修改 catalog/source digest 或伪造策略归属，都要给稳定非零诊断；不在测试中随意执行仓库外未知脚本。只有白名单默认策略或**明确 opt-in 的可信本地策略**可运行。
- 兼容性：S37 v1 仍只能 game-only；S38 v2 六局双层验真仍通过；新 v3 若存在，验证时不信任自述 flags。原 S35 回放、S36 策略、旧 Python Snake、S10 日志应用均保持原行为。`app/log_report.lwt`、`game.lwt`、原策略、S35/S37/S38 固定原始证据、S10/S11/S28/S29 原始报告、语言解释器/规范/黑盒默认不改；必要修复须独立提交、复现和说明。
- 必要命令：新策略定向测试、`python tools/run_tests.py`、`python tools/check_project_integrity.py`、全量 unittest、严格 GUI runner（若运行则 skip=0）、原日志应用 25 项、S37/S38 定向、三个 LWT 策略 `python -m lwt --check`、compileall、Markdown 链接/围栏、`git diff --check` 和保护路径差异。说明实际 Python/OS；未运行 Linux/3.10 或远端 Actions 时不得写通过。

## 4. 交付与停止条件

推荐分层提交：冻结 SDK/manifest 契约 → 动态可信目录与 checker → v3 验真或兼容改造 → Agent 独立策略及开发证据 → 不变量/故障/兼容测试 → 文档与阶段报告。交付 `docs/strategy-sdk.md`、人类/Agent 快速开始、模板、新 LWT 策略、固定小型对局证据、完整提示与 Agent 开发记录、`docs/s39-strategy-workshop.md`。报告列出完整基线/提交 SHA、原始失败与修正、逐项命令/退出码、每局真实结果、源摘要、并发一致性、保护文件差异、远端及人工验收边界。执行窗口只写“实施完成、待主窗口审查”，不自行合入/推送主线、不开始 S12。

如果自定义策略注册需要破坏 S38 的双层验真，缩为“固定目录内第三策略 + 独立 Agent 生成 + 完整验真”的可靠最小闭环；不要为了展示插件化而把任意结果文件变成自动执行脚本的入口。完成本阶段后停止功能扩张，立即交主窗口复核并转 S12。
