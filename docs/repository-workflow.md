# Git 分支、主线与远端同步记录

核对日期：2026-10-31。远端引用会变化；每次合并或推送前重新查询，不把本文快照当作实时状态。

> **后续状态更新：** S32 执行时 Schannel TLS 失败是真实的历史事件；主窗口复核时网络恢复，`feature/editor-integration` 正常推送至 `236d94f92f402d0ef50333e518e6167711960b8b`，对应 [Actions run 41200279217](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41200279217) 的 Ubuntu/Windows × Python 3.10/3.13 四格均成功。S32 已快进合入本地 `main`；最终远端位置仍须以实时 Git 查询为准。见 [S32 主窗口复核](s32-main-review.md)。新增 S33 计划使用 `feature/testing-workbench` 大阶段分支；实施与集成尚未发生。本文下方旧“当前”段落为当时快照。

## 命名与用途

| 前缀 | 用途 |
|---|---|
| feature/<功能> | 跨多个 S 编号的功能大阶段 |
| maintenance/<目的> | 文档、工作流或仓库维护 |
| fix/<问题> | 有明确复现的定向修复 |
| milestone/<功能> | 稳定标记已完成的大阶段历史 |

统一用小写英文和连字符，不以 codex 开头。S 编号用于工作报告、审查和提交标题；无需每个 S 单独创建或推送分支。旧 stage/sNN-* 分支是历史阶段指针，保留用于追溯。

## 当前远端与分支图谱

本次通过 git ls-remote 核对的远端分支：

- origin/main 与 origin/feature/editor-integration：f9db64dabbf55ffcf2510467c544956c2741a855
- origin/milestone/course-deliverables：f2dda1f7085b7c6dc56aa90cb490c4cc9b1c4e33
- origin/milestone/developer-tools：5cc109a4302212a772a4fe6589cd15d36a55b055
- origin/milestone/interactive-apps：761ce331b0257fe0128a6ba9b190c2ba6f9f30e1
- origin/milestone/language-core：4f11b80cc900f64dfa02c9cb2c9f16f81b2d971d
- origin/milestone/language-extensions：9006119fc6c98f151244ef06608d72730da1071e

本工作树当前位于 stage/s31-vscode-extension，最终提交 d2571540f50323d0e9be597caeb82575b2df6bcf。S31 从 5cc109a4302212a772a4fe6589cd15d36a55b055 建立，含三个独有提交。当前 main 比 S31 基线多四个提交，S31 比基线多三个提交；两侧分叉。S31 未推送。主线不能快进至 S31；集成必须显式保留两侧历史。

## 历史审计范围

- 当前 main 有 158 个提交；已核对全图提交顺序、S0–S30 阶段报告索引、五个里程碑指针、主线与远端引用。
- S23–S30 已按用户授权进入本地 main；当时没有为每一阶段单独形成主窗口代码审查记录。主线包含提交本身不等于每阶段都有独立验收。
- 本轮在 S31 工作树重跑完整黑盒和单元测试，并复核 S31 的 manifest、workflow、测试、阶段报告与分支差异；这证明集成后的当前代码通过这些测试，不代表重新逐行审阅 S0–S30 的每条历史改动。
- `git log --check --format= --all` 会因已有历史行尾空格返回非零：`docs/s21-gui-acceptance.md` 的 Markdown 硬换行和课程原文 `大作业内容.md` 中的空白行。当前文档修改集的 `git diff --check` 通过；没有为清除此历史检查结果改写课程原文或旧报告。
- 完整 S31 审查结论和限制见 [S31 主窗口复核](s31-main-review.md)。

## 之前 GitHub 红叉的结论

Git commit/push 和 GitHub Actions 是两种结果。2026-10-31 API 核验的最新 main SHA 为 f9db64d；Actions run 41183683056 成功，Ubuntu/Windows × Python 3.10/3.13 四个任务全部成功：[run 41183683056](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41183683056)。

更早的 42695ea、c2228d3、e9d3f10 对应 Actions 失败，但这些提交的 push 均成功。四格均在 unittest 阶段失败，问题是平台相关测试断言：模块 ImportError 文案以及 Windows 规范化文件 URI。修复提交 f9db64d 放宽稳定断言、使用规范化 URI；其后的远端矩阵通过。不可把旧 SHA 的红叉写成推送失败，也不可把 f9db64d 的绿灯外推到未合入分支。

## S31 到功能大阶段的集成方法

S31 主窗口复核已通过并带明确遗留。下一次集成前必须再次确认 main、origin/main、feature/editor-integration 与 stage/s31-vscode-extension 的真实指向、工作区状态和祖先关系。

由于 S31 与当前 main 分叉，推荐在 feature/editor-integration 上从最新 main 开始，用保留原提交的正常非快进合并集成 S31；不要 cherry-pick 后误称原始 SHA 未变，也不要 reset、rebase 或强推。解决冲突后复核文档状态、运行相关回归，再让 main 快进到经过审查的功能分支 tip。任何远端变化、冲突或验证失败都保留本地提交并报告，不猜测、不覆盖。

S32 若获用户派发，仍属于编辑器集成大阶段，可继续使用 feature/editor-integration，不必新建 stage/s32 分支。S12 仍是最后交付阶段。推送只用正常 push；推送后再以 git ls-remote 与 Actions run SHA 核对远端事实。

## S31 集成与 S32 执行快照（2026-10-31）

S31 主窗口复核通过（带明确未验证项）后，按正常非快进合并保留两侧提交：S31 原始实现/测试/报告提交 `938d029`、`21506b1`、`d257154`，以及文档更正提交 `007c774` 均在祖先历史中；集成提交为 `ddf1759fa4239eabc15488730917daec990da390`。该提交将本地和远端 `main`、`feature/editor-integration` 汇合，S31 原提交未 squash、未重写。集成前后的黑盒/单元测试、完整性、Extension Host、VSIX 与 Actions 见 [S32 执行报告](s32-native-dap.md)。

S32 在 `feature/editor-integration` 继续完成，未合入 main。S32 最终实现 SHA、分层提交和测试报告以 [S32 执行报告](s32-native-dap.md)为准。S32 执行期间 `git ls-remote --heads origin main feature/editor-integration stage/s31-vscode-extension` 只读复核和 `git push origin feature/editor-integration` 均因 Schannel TLS 握手失败而未完成；此前成功核实的两条主分支均指向 `ddf1759`。网络错误不是远端分支未变化的证据，远端 SHA/Actions 保持未验证，详见阶段报告。
