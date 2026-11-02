# LWT 项目上下文

> Agent 当前状态入口。核对日期：2026-11-02。每次开始任务都重新检查 Git 和远端；阶段历史见[仓库工作流](docs/repository-workflow.md)，当前关系见[阶段路线图](阶段执行与审查路线图.md)。

> **当前结论：** S36 的 LWT 策略、提示和自动驾驶已通过[主窗口审查](docs/s36-main-review.md)，保留原提交快进合入本地 `main`；精确功能分支提交 `3bf7effa4fc3bf9a1c2f117e174a7a5a1c0182f0` 的 [Actions 四格通过](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41388553619)。主分支远端同步及其 CI 须以实际新 SHA 单独核实。用户要求在 S12 前增加最后一个有界应用阶段 S37，完整派发见[策略擂台规划](docs/s37-strategy-arena-handoff.md)。人工键鼠/视觉仍未验证；S12 最终交付未开始。

## 目标与课程评分

依据[作业原文](大作业内容.md)，交付 LWT 解释型通用脚本语言及解释器、完整黑盒测试、LWT/Python 性能比较、人类与 Agent 开发指南、至少 200 行的 Agent 编写 LWT 应用及开发记录、Git 历史、介绍 PPT 和线下答辩。评分为解释器 20、测试 20、性能 10、指南 20、LWT 应用 30 分。

课程应用包括 app/log_report.lwt（246 行有效 LWT）以及 app/lwt_snake/game.lwt（313 行有效 LWT）。Python/Tkinter 前端、原 Python 贪吃蛇和编辑器插件是展示/开发工具；LWT Snake 的 Python 部分负责桥接、回放控制与绘图，规则仍由 LWT 计算。

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
- S34：LWT Snake 已合入本地 `main`；原主窗口发现的时钟饿死和失焦问题均在 S35 修复，复现及修复证据见[两轮审查](docs/s35-main-review.md)。
- S35：可验证回放和接管已通过主窗口复核、合入本地 `main`，功能分支精确 SHA 的远端 CI 四格成功。格式见[回放契约](docs/snake-replay-format.md)；人工桌面操作仍未验证。
- S36：LWT 策略助手、提示与串行自动驾驶已通过主窗口复核、合入本地 `main`；功能分支精确提交的 CI 四格成功。见[审查记录](docs/s36-main-review.md)、[冻结协议](docs/snake-strategy-protocol.md)和[执行报告](docs/s36-strategy.md)。
- S37：已规划 LWT 双策略、可复现有界擂台及全新进程回放核验，尚未实施；见[完整派发提示](docs/s37-strategy-arena-handoff.md)。
- S12：保留为 S37 后的最后交付阶段，执行新克隆验收、兼容性/CI、GUI 现场预检、PPT、答辩和交付；见[S12 规划](docs/s12-final-delivery-plan.md)。

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
