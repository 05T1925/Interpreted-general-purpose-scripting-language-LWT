# Git 分支与主线整理记录

核对日期：2026-10-31。此文档记录用户授权的仓库整理；远端状态应以实时查询为准。

## 统一命名

| 类型 | 规则 | 用途 |
|---|---|---|
| 功能开发 | `feature/<功能>` | 一个功能大阶段，允许包含多个 S 任务及提交 |
| 维护整理 | `maintenance/<目的>` | 文档、仓库流程、构建维护 |
| 定向修复 | `fix/<问题>` | 审查发现的具体缺陷 |
| 已完成边界 | `milestone/<功能>` | 稳定指向大阶段历史提交，便于复现和比较 |

名称用小写英文和连字符，不用 `codex` 前缀。S 编号用于报告和提交定位；旧 `stage/sNN-*` 仅保留为本地历史审查指针，不逐一推送，也不再作为默认新分支模式。

## 五个大阶段指针

| 分支 | 覆盖重点 | 指向的已有提交 |
|---|---|---|
| `milestone/language-core` | S1–S7 规范、解释器与基础语义 | `4f11b80cc900f64dfa02c9cb2c9f16f81b2d971d` |
| `milestone/course-deliverables` | S8–S14 测试、Agent 指南和应用、性能与质量审计 | `f2dda1f7085b7c6dc56aa90cb490c4cc9b1c4e33` |
| `milestone/interactive-apps` | S15–S22 GUI、工作台、教学交互与回归 | `761ce331b0257fe0128a6ba9b190c2ba6f9f30e1` |
| `milestone/language-extensions` | S23–S26 测试充分性、循环控制、模块、错误恢复 | `9006119fc6c98f151244ef06608d72730da1071e` |
| `milestone/developer-tools` | S27–S30 检查、档案、LSP 与调试器 | `5cc109a4302212a772a4fe6589cd15d36a55b055` |

这些分支是已有线性历史中的命名检查点，不额外复制提交。`feature/editor-integration` 已从整理后的主线创建，用于 S31；创建分支不代表扩展已经实现。S12 是最终验收交付阶段。

## 本次集成核对

- 整理前，本地 `main` 为 `aadb8f7a2348dad3205c523d4ab1cb4ad5bda063`，包含到 S22；只读 `ls-remote` 显示远端 `main` 为 `de608f7fbf50946715d370df014657169eb8f26d`（S4）。默认 Schannel TLS 握手失败；Git OpenSSL 后端的一次只读查询成功，随后 fetch 因 TLS 意外 EOF 失败。
- 检查确认 `origin/main` 是原本地 `main` 的祖先；本地 `main` 依次是 S23、S24、S25、S26、S27、S28、S29、S30 阶段 tip 的祖先。没有分叉或冲突。
- 在候选 tip 的 Windows CPython 3.13.7 上，`python -m unittest discover -s tests -q` 为 421 项通过；`python tools/run_tests.py` 为 287/287；完整性为 287 cases、384 matrix links、287 referenced cases；`git diff --check main..HEAD` 通过。
- 用户授权后，依次以 `git merge --ff-only` 将 S23 `999cc78`、S24 `5f899d9`、S25 `5e694a2`、S26 `9006119`、S27 `e9fa8f4`、S28 `6aa198a`、S29 `744d0ca`、S30 `5cc109a` 纳入本地 `main`。全部是快进，未 squash、rebase 或改写提交。
- 本次整理没有单独生成各 S 的主窗口审查结论；它们的完整阶段报告和待补审查事项仍须在 S12 前核对。主线包含提交是 Git 事实，不自动等同于功能验收、远端 CI 或人工 GUI 验收。

## 远端同步规则与结果

推送前重新只读查询 `origin/main`，确认它仍是本地 `main` 的祖先。使用正常 `git push origin main` 和按需 `git push origin milestone/<功能>`；绝不使用强推、`--force-with-lease`、禁用证书校验或用远端旧 tip 覆盖本地。远端变化、TLS/鉴权失败时保留本地结果并报告。推送后的 SHA 和分支核对结果追加在此节。

2026-10-31 推送核验：正常快进推送后，实时 `ls-remote` 显示远端 `main=42695ea6ecfbbf2400c6a8cc3fce1737bf64d4ea`；五个 `milestone/*` 分支均与上表 SHA 一致。`feature/editor-integration` 也已创建并推送，起点同为 `42695ea6ecfbbf2400c6a8cc3fce1737bf64d4ea`。本节的结果是同步当时的快照；此后以实时远端查询为准。远端 Actions 和新克隆验收仍待 S12 核验。
