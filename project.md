# LWT 项目上下文

> Agent 当前状态入口。核对日期：2026-10-31。本文按当前工作树记录；每次开始任务都重新检查 Git 和远端。阶段历史与提交关系见[仓库工作流](docs/repository-workflow.md)，总览见[阶段路线图](阶段执行与审查路线图.md)。

## 目标与课程评分

依据[作业原文](大作业内容.md)，交付 LWT 解释型通用脚本语言及解释器、完整黑盒测试、LWT/Python 性能比较、人类与 Agent 开发指南、至少 200 行的 Agent 编写 LWT 应用及开发记录、Git 历史、介绍 PPT 和线下答辩。评分为解释器 20、测试 20、性能 10、指南 20、LWT 应用 30 分。

课程应用主体是 app/log_report.lwt（246 行有效 LWT）；Python/Tkinter 前端、贪吃蛇和编辑器插件是展示/开发工具，不能替代 LWT 应用，也不应夸大为课程必需语言功能。

## 当前 Git 快照

本次核对时工作树位于 stage/s31-vscode-extension，S31 最终提交为 d2571540f50323d0e9be597caeb82575b2df6bcf。该分支起于 S30 检查点 5cc109a4302212a772a4fe6589cd15d36a55b055，含三个 S31 专属提交。

本地 main、origin/main 和 origin/feature/editor-integration 当前均为 f9db64dabbf55ffcf2510467c544956c2741a855。S31 与 main 尚未集成：相对 S31 基线，main 有 4 个后续提交，S31 有 3 个专属提交，两侧分叉。S31 提交尚未推送。不得用本页快照替代新的 git 查询。

S0–S30 已在 main 的历史中；S23–S30 是按用户授权纳入本地主线，但其阶段报告保留当时状态，不能只凭祖先关系宣称各阶段都曾单独审查。当前聚合回归和历史审查范围见[仓库工作流](docs/repository-workflow.md)及[S31 主窗口复核](docs/s31-main-review.md)。

## 远端 CI 快照

2026-10-31 只读核对 origin/main 为 f9db64d。GitHub Actions run 41183683056 在该 SHA 的 Ubuntu/Windows × Python 3.10/3.13 四个任务均成功：[run 41183683056](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41183683056)。这只证明该 main SHA 的 CI，不覆盖未合入的 S31 分支或后续代码。此前 42695ea、c2228d3、e9d3f10 上的红叉是 unittest 失败；跨平台测试断言在 f9db64d 修正，push 与 Actions 结论应分开表述。

## 阶段状态

- S0–S30：提交在 main；各阶段的范围和证据索引见[阶段路线图](阶段执行与审查路线图.md)。S23–S30 的历史状态文字不等同于本次逐阶段独立审计。
- S31：VS Code 扩展实现已在本分支复核。Windows Python 3.13.7 上黑盒 287/287、unittest 421 项、扩展 Node 单测 9/9 和 Extension Host 3/3 通过。主窗口结论为“通过，带明确未验证项”；S31 尚未合入 main。人工 VSIX 安装/完整桌面操作、依赖线上 advisory 复核、S31 分支远端 CI 未验证。细节见[S31 主窗口复核](docs/s31-main-review.md)。
- S32：提议实现 LWT 原生 VS Code Debug Adapter Protocol（DAP）接入，尚未开始；设计与派发提示见[S32 规划](docs/s32-native-dap-plan.md)。S32 属于编辑器集成大阶段，不新增 LWT 语言语法。
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
