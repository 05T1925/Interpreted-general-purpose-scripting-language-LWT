# S39 独立 Agent 编写第三份 LWT 策略的证据

日期 2026-11-02。执行窗口在提交 `9c93420bb2156033e7ebb35558b10057d56d1e98` 冻结 [SDK](strategy-sdk.md)、[契约](s39-strategy-sdk-contract.md)和[模板](../app/lwt_snake/strategies/strategy-template.lwt)后，向**不继承本窗口对话上下文**的编程 Agent 派发以下原始任务。它只被授权阅读列出的公开材料，不阅读原 BFS/baseline 源码。其工作树和提交可独立检查；平台未提供可观察的自动 Skill 选择或逐事件时间线，因此不宣称这两项已实测。

## 原始派发提示

> 你是独立上下文的 LWT 策略编程 Agent。工作来源仓库 C:\Users\28641\Desktop\大三上\程序设计实践\大作业，公开材料已经冻结在提交 9c93420bb2156033e7ebb35558b10057d56d1e98。只阅读并使用以下公开材料：docs/language-spec.md、docs/developer-guide.md、docs/snake-strategy-protocol.md、docs/s39-strategy-sdk-contract.md、docs/strategy-sdk.md、app/lwt_snake/strategies/strategy-template.lwt，以及必要时运行公开 python -m lwt。不要阅读已有 strategy.lwt、strategy_baseline.lwt 或执行窗口的实现/测试；不要向执行窗口询问现成算法代码。请在隔离 Git 工作树和独立分支 feature/s39-agent-strategy 上，编写一份与 baseline/BFS 思路有区别、可解释的完整单文件 LWT 策略，放在 app/lwt_snake/strategies/，并为它添加 strategy-catalog.json 的严格 manifest 项（规范化源码 SHA-256）。仅修改这两个文件。自己运行静态检查和适当公开 CLI 协议烟测，记录原始命令、首次错误与修正（如无错误如实说）。提交你的文件，向我报告工作树路径、分支、完整 SHA、算法说明、实际测试命令/输出、限制。创建工作树请使用可用的 create_worktree 工具，基于 9c93420 提交；工具若改变你的默认 cwd，后续明确使用返回路径。不要合并、推送或修改主工作树。

## 实际过程和首次证据

1. `create_worktree` 工具拒绝：聊天工作区根目录为上层 `程序设计实践`，Git 仓库位于其子目录 `大作业`，该工具要求 sourceRoot 恰为工作区根。执行窗口通知 Agent 保留限制记录，并允许用 Git 原生命令 `git worktree add -b feature/s39-agent-strategy <仓库外新路径> 9c93420...`；隔离工作树为 `C:\Users\28641\Desktop\大三上\程序设计实践\s39-agent-strategy`。没有修改主工作树。
2. 冻结基底尚无执行窗口之后实现的 `--check-strategy`；Agent 首次运行该公开入口得到 `unrecognized arguments: --check-strategy ... --catalog ...`，exit 1。Agent 如实记录而没有称检查通过。它改用 `python -m lwt --check app/lwt_snake/strategies/mobility-lookahead.lwt`，首次即输出 `Check passed: 1 source file(s).`。两组真实 `python -u -m lwt` 长驻协议烟测 exit 0、stderr 空；包含正常移动、吃食物、坏版本/非 ASCII/错误序号和坏快照后同序号重试。
3. Agent 在首次协议烟测前自行发现 BAD_SNAPSHOT 曾错误消费序号，改为仅在有效快照后递增，并以坏快照后重试 `000002` 的实际输出验证。首个提交 `a7c115a62f6902465e75a99d4ca21992ca3cdf00` 只新增 [策略源码](../app/lwt_snake/strategies/mobility-lookahead.lwt)和一条 [manifest](../app/lwt_snake/strategies/strategy-catalog.json) 项。策略使用局部两步出口数、直接吃食物和曼哈顿距离，稳定 U/R/D/L 破平局，不使用 BFS；它不保证长期安全或普遍更高分。

## 执行窗口复核与二次修正

执行窗口审阅首提交后以保留原提交的 cherry-pick 集成，运行新 `--check-strategy`，首次 exit 1：错误版本帧序号 `000001` 可辨认，但源码回 `LWA1|ERR|000000|BAD_FRAME`；检查器期望 `...|000001|BAD_FRAME`。执行窗口没有放宽检查器，而将该真实失败及 [LWA1 序号规则](snake-strategy-protocol.md)反馈给同一独立 Agent。二次原始反馈为：

> 执行窗口已把你首个提交 cherry-pick 集成并运行新的公开检查命令：`python -m app.lwt_snake.arena --check-strategy mobility-lookahead --catalog app/lwt_snake/strategies/strategy-catalog.json`。首次结果 exit 1：`smoke malformed frames 1-2 expected BAD_FRAME/BAD_SEQUENCE; actual b'LWA1|ERR|000000|BAD_FRAME\nLWA1|ERR|000002|BAD_SEQUENCE\n'`。S36 LWA1 协议规定“无法辨认序号用 000000”；此错误版本帧中 `000001` 可辨认。请在你的隔离工作树/分支依据公开协议自行做最小修正，更新 manifest 规范化源码摘要，运行静态/协议验证，另提交一个修复提交并报告完整 SHA 与实际结果。只改策略和 manifest，不改执行窗口检查器或主工作树。

Agent 在隔离分支追加提交 `86ba3d29487afb47da05d7e4048e624b76df5c6b`，仍只改上述两个文件。新规范化源码 SHA-256 `6123507d1dec3d3079aa6d5d3072184a87816545971e63198dde702567a61404`；再次 `python -m lwt --check` 通过，五帧长驻烟测 stdout 依次包含 `BAD_FRAME(000001)`、`BAD_SEQUENCE(000002)`、正常移动、`BAD_FRAME(000000)`、正常移动，exit 0、stderr 空。执行窗口分别 cherry-pick 两个原提交到 S39 分支，生成新的父提交 SHA（见[阶段报告](s39-strategy-workshop.md)），再运行 `--check-strategy` 得到静态与五帧协议检查通过。此后真实擂台、v3 双层验真和并发一致性由执行窗口负责，不属于独立 Agent 最初基底的测试结果。

课程第 4 项所需 Agent 指南与第 5 项所需 Agent LWT 应用因此有一条可追溯的“公开文档 → 独立产出 → 首次失败 → 人工审阅反馈 → 修正 → 真实运行”链。`app/log_report.lwt`（246 有效行）与 `game.lwt`（313 有效行）仍是满足课程应用规模的原有证据；本策略 203 物理行、仓库工具实测 156 有效行，只是额外扩展，不替代课程应用的行数论证。
