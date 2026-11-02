# LWT 项目上下文

> Agent 当前状态入口。核对日期：2026-11-01。本文按当前工作树记录；每次开始任务都重新检查 Git 和远端。阶段历史与提交关系见[仓库工作流](docs/repository-workflow.md)，总览见[阶段路线图](阶段执行与审查路线图.md)。

> **2026-11-02 主窗口更新：** S34 两项问题随 S35 修复并已独立复核；S35 产品审查未发现阻断问题，另以 `7ced2a8` 单独稳定时钟回归测试。全量 481 项和黑盒 287/287 为测试修正前的本窗口通过记录；修正后定向 1/1 与严格 GUI 19/19 通过，全量未再跑。精确分支 SHA 的远端 CI、人工桌面、Python 3.10/Linux 需另核对。[复核证据](docs/s35-main-review.md)。用户要求再规划一个实质应用能力，[S36 LWT 策略助手提示](docs/s36-strategy-handoff.md)已备；S12 仍是最终交付阶段。下方旧段落为历史快照，不能覆盖此更新。

> **S35 执行状态（2026-11-01）：** 已先独立修复移动时钟与失焦测试前置条件，再完成事务录制、严格文件保存、真实 LWT 验证、交互复盘和前缀接管；实施完成，等待主窗口审查。当前功能分支保留 main 之外的既有历史；开工远端查询遇 TLS 失败，随后成功只读实查 main 仍为 `9d562b717ba82fc322ff152e6e1b7d5ff4b5c36c`；不复制旧快照。实际结果见 [S35 报告](docs/s35-replay.md)。S12 未开始。

> **此前主窗口复核（2026-11-01，历史）：** S34 需修复复审：连续 TURN 可饿死移动时钟，失焦测试整组运行失败而单跑通过；见 [S34 主窗口复核](docs/s34-main-review.md)。当前功能分支 `feature/lwt-snake-game` 的产品 tip 为 `f87e8b8`，其后为本轮审查/规划文档；未合入、未推送。实时远端 main 为 `9d562b7`。S35 仅规划为“先修复、再录制/验证/回放/接管”，完整 [派发提示](docs/s35-replay-handoff.md)已有内部修复门槛。S12 未开始。历史执行结果不等于本轮审查结论。

## 目标与课程评分

依据[作业原文](大作业内容.md)，交付 LWT 解释型通用脚本语言及解释器、完整黑盒测试、LWT/Python 性能比较、人类与 Agent 开发指南、至少 200 行的 Agent 编写 LWT 应用及开发记录、Git 历史、介绍 PPT 和线下答辩。评分为解释器 20、测试 20、性能 10、指南 20、LWT 应用 30 分。

课程应用包括 app/log_report.lwt（246 行有效 LWT）以及 S34 新增 app/lwt_snake/game.lwt（执行窗口统计 313 行有效 LWT，需修复复审）。Python/Tkinter 前端、原 Python 贪吃蛇和编辑器插件是展示/开发工具；新 LWT Snake 的 Python 部分仅作桥接与绘图。

## 当前 Git 快照

S31 的原始执行窗口位于 `stage/s31-vscode-extension`，最终提交为 `d2571540f50323d0e9be597caeb82575b2df6bcf`。复核后以保留两侧历史的正常合并集成到 `feature/editor-integration`，合并提交为 `ddf1759fa4239eabc15488730917daec990da390`；S31 原有三个实现/测试/报告提交均仍在祖先历史。

S32 从 `ddf1759fa4239eabc15488730917daec990da390` 开始，在 `feature/editor-integration` 完成；最终实现 SHA `236d94f92f402d0ef50333e518e6167711960b8b` 已经主窗口复核并快进进入本地 `main`。S32 执行窗口曾遇 Schannel TLS 握手失败；主窗口网络恢复时已正常推送功能分支，并核实精确 SHA 的 Actions 四格成功。远端 `main` 后续状态仍要实时查询。见 [执行报告](docs/s32-native-dap.md)及[主窗口复核](docs/s32-main-review.md)。

S0–S30 已在 main 的历史中；S23–S30 是按用户授权纳入本地主线，但其阶段报告保留当时状态，不能只凭祖先关系宣称各阶段都曾单独审查。当前聚合回归和历史审查范围见[仓库工作流](docs/repository-workflow.md)及[S31 主窗口复核](docs/s31-main-review.md)。

## 远端 CI 快照

2026-10-31 基线 `f9db64d` 的 Actions run 41183683056 四格成功。S31 集成提交 `ddf1759` 的 [run 41190959253](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41190959253) 四格成功；S32 精确提交 `236d94f` 的 [run 41200279217](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41200279217) 也四格成功。push 和 Actions 结论分开记录。此前 42695ea、c2228d3、e9d3f10 上的红叉是 unittest 失败；跨平台测试断言在 f9db64d 修正。

## 阶段状态

- S0–S30：提交在 main；各阶段的范围和证据索引见[阶段路线图](阶段执行与审查路线图.md)。S23–S30 的历史状态文字不等同于本次逐阶段独立审计。
- S31：VS Code 扩展已通过主窗口复核（带明确未验证项），保留原提交并集成到 main；合并提交 `ddf1759fa4239eabc15488730917daec990da390`。人工 VSIX 安装/完整桌面操作和依赖线上 advisory 复核仍未验证。历史审查见[S31 主窗口复核](docs/s31-main-review.md)。
- S32：原生 DAP 已通过主窗口复核、快进进入本地 `main`；精确提交的远端 CI 四格成功。执行窗口报告黑盒 287/287、全量 unittest 442 项；主窗口复跑 DAP 与 S30 定向 49 项及 VS Code Node 11 项／Extension Host 4 项。人工 VSIX 安装和桌面调试 UI 未执行。详见[执行报告](docs/s32-native-dap.md)与[审查记录](docs/s32-main-review.md)。
- S33：黑盒 runner 选择与 UTF-8/Base64 JSON 契约、VS Code Test Explorer Run/Debug profile 已通过主窗口复核并集成到本地 `main`；修复批量错误终态，精确功能分支 SHA 的远端 CI 四格通过。人工鼠标/键盘编辑器验收仍未验证。详见[主窗口复核](docs/s33-main-review.md)及[执行报告](docs/s33-testing-workbench.md)。
- S34：已实施，主窗口结论为需修复复审。独立定向 13 项中 12 通过、1 失焦失败；单独重跑该项通过。另独立复现转向饿死 TICK 缺陷；黑盒 287/287、完整性检查通过。详见[主窗口记录](docs/s34-main-review.md)，不要将[历史执行报告](docs/s34-lwt-snake.md)的全绿结果当成本轮通过。
- S35：实施完成，等待主窗口审查；独立修复门槛提交后交付真实事务录制/文件/新进程验证/复盘/指定前缀接管。见[实施报告](docs/s35-replay.md)及[格式说明](docs/snake-replay-format.md)。S34 两项已由执行窗口修复并验证，仍待主窗口复审；未合入 main。
- S12：保留为最后交付阶段，在游戏阶段修复、审查与集成后执行新克隆验收、兼容性/CI、GUI 现场预检、PPT、答辩和交付；见[S12 规划](docs/s12-final-delivery-plan.md)。

## 常用验证入口

- 普通 LWT 程序：python -m lwt examples/guide/hello.lwt
- 静态检查：python -m lwt --check examples/modules/main.lwt
- 黑盒：python tools/run_tests.py
- 完整性：python tools/check_project_integrity.py
- Python 全量：python -m unittest discover -s tests -q
- VS Code 扩展：进入 editors/vscode-lwt 后执行 npm ci 与 npm test；Extension Host 需要设置 VSCODE_EXECUTABLE_PATH 指向 Code.exe。
- Agent LWT 应用：python -m lwt app/log_report.lwt -- app/fixtures/sample.log
- 有效 LWT 行数：python tools/count_lwt_lines.py app/log_report.lwt

语言开发工具边界见[正式规范](docs/language-spec.md)、[静态检查](docs/static-checker.md)、[Language Server](docs/language-server.md)、[调试器](docs/debugger.md)、[VS Code 扩展](docs/vscode-extension.md)和[S33 测试工作台报告](docs/s33-testing-workbench.md)。发生冲突时以作业原文、正式语义和当前实测证据为准。
