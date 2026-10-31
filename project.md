# LWT 项目上下文

> Agent 当前状态入口。核对日期：2026-10-31。本文按当前工作树记录；每次开始任务都重新检查 Git 和远端。阶段历史与提交关系见[仓库工作流](docs/repository-workflow.md)，总览见[阶段路线图](阶段执行与审查路线图.md)。

## 目标与课程评分

依据[作业原文](大作业内容.md)，交付 LWT 解释型通用脚本语言及解释器、完整黑盒测试、LWT/Python 性能比较、人类与 Agent 开发指南、至少 200 行的 Agent 编写 LWT 应用及开发记录、Git 历史、介绍 PPT 和线下答辩。评分为解释器 20、测试 20、性能 10、指南 20、LWT 应用 30 分。

课程应用主体是 app/log_report.lwt（246 行有效 LWT）；Python/Tkinter 前端、贪吃蛇和编辑器插件是展示/开发工具，不能替代 LWT 应用，也不应夸大为课程必需语言功能。

## 当前 Git 快照

S31 的原始执行窗口位于 `stage/s31-vscode-extension`，最终提交为 `d2571540f50323d0e9be597caeb82575b2df6bcf`。复核后以保留两侧历史的正常合并集成到 `feature/editor-integration`，合并提交为 `ddf1759fa4239eabc15488730917daec990da390`；S31 原有三个实现/测试/报告提交均仍在祖先历史。

当前任务从本地 main/feature 基线 `ddf1759fa4239eabc15488730917daec990da390` 开始，在 `feature/editor-integration` 完成 S32。S32 实现和测试提交分别为 `33eca1d` 与 `4ad6422`；文档/报告提交及完整最终 SHA 见 [S32 执行报告](docs/s32-native-dap.md)。S32 不合入 main。上次成功核实的 origin/main 与 origin/feature/editor-integration 均指向 ddf1759；本轮后续 `git ls-remote` 因 Schannel TLS 握手失败，未取得更新的实时位置。不得用本页快照替代新的 git 查询。

S0–S30 已在 main 的历史中；S23–S30 是按用户授权纳入本地主线，但其阶段报告保留当时状态，不能只凭祖先关系宣称各阶段都曾单独审查。当前聚合回归和历史审查范围见[仓库工作流](docs/repository-workflow.md)及[S31 主窗口复核](docs/s31-main-review.md)。

## 远端 CI 快照

2026-10-31 基线 `f9db64d` 的 Actions run 41183683056 四格成功。随后 S31 集成提交 `ddf1759` 的 `feature/editor-integration` Actions run 41190959253 四格成功，验证了与 main 合流后的准确 tree/SHA，详见 [run 41190959253](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41190959253)。S32 尚未远端验证；push 和 Actions 结论分开记录。此前 42695ea、c2228d3、e9d3f10 上的红叉是 unittest 失败；跨平台测试断言在 f9db64d 修正。

## 阶段状态

- S0–S30：提交在 main；各阶段的范围和证据索引见[阶段路线图](阶段执行与审查路线图.md)。S23–S30 的历史状态文字不等同于本次逐阶段独立审计。
- S31：VS Code 扩展已通过主窗口复核（带明确未验证项），保留原提交并集成到 main；合并提交 `ddf1759fa4239eabc15488730917daec990da390`。人工 VSIX 安装/完整桌面操作和依赖线上 advisory 复核仍未验证。历史审查见[S31 主窗口复核](docs/s31-main-review.md)。
- S32：已在 `feature/editor-integration` 实现原生 DAP，等待主窗口审查。CPython 3.13.7 下语言黑盒 287/287、全量 unittest 442 项、项目完整性、编译、S30 28 项回归、本阶段 21 项 DAP 测试、VS Code Node 11 项与 Extension Host 4 项均通过；Extension Host skip 为 0。当前分支尚未远端验证；人工 VSIX 安装/桌面调试 UI 未执行。完整提交、命令和保护文件证据见[S32 执行报告](docs/s32-native-dap.md)。
- S12：保留为最后交付阶段，在 S31/S32 审查与集成后执行新克隆验收、兼容性/CI、GUI 现场预检、PPT、答辩和交付；见[S12 规划](docs/s12-final-delivery-plan.md)。

## 常用验证入口

- 普通 LWT 程序：python -m lwt examples/guide/hello.lwt
- 静态检查：python -m lwt --check examples/modules/main.lwt
- 黑盒：python tools/run_tests.py
- 完整性：python tools/check_project_integrity.py
- Python 全量：python -m unittest discover -s tests -q
- VS Code 扩展：进入 editors/vscode-lwt 后执行 npm ci 与 npm test；Extension Host 需要设置 VSCODE_EXECUTABLE_PATH 指向 Code.exe。
- Agent LWT 应用：python -m lwt app/log_report.lwt -- app/fixtures/sample.log
- 有效 LWT 行数：python tools/count_lwt_lines.py app/log_report.lwt

语言开发工具边界见[正式规范](docs/language-spec.md)、[静态检查](docs/static-checker.md)、[Language Server](docs/language-server.md)、[调试器](docs/debugger.md)和[VS Code 扩展](docs/vscode-extension.md)。发生冲突时以作业原文、正式语义和当前实测证据为准。
