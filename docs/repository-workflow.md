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
| `milestone/course-deliverables` | S8–S11、S13–S14 测试、Agent 指南和应用、性能与质量审计；S12 最终验收尚未执行 | `f2dda1f7085b7c6dc56aa90cb490c4cc9b1c4e33` |
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

2026-10-31 推送核验：先将 `main` 和 `feature/editor-integration` 推至 `42695ea6ecfbbf2400c6a8cc3fce1737bf64d4ea`，五个 `milestone/*` 分支按上表 SHA 建立；随后将远端 `main` 与 `feature/editor-integration` 正常快进至 `c2228d3fb40dc7bc0d64d5634ad0aacca0ac674a`，用于记录最终远端同步状态。最后一次推送后远端核验到这两个分支均为 `c2228d3`，五个里程碑分支仍与上表 SHA 一致。此处只记录 Git 引用；远端 Actions 和新克隆验收仍待 S12 核验。后续以实时远端查询为准。

## 2026-10-31 GitHub Actions 失败复核

提交 `42695ea`、`c2228d3`、`e9d3f10` 推送本身均成功；GitHub 页面上的红叉是 Actions 结果，不是 Git 提交或推送失败。相关失败 run 的四格矩阵都在完整 unittest 步骤退出码 1；此前的完整性检查、287 项语言黑盒测试和 Linux GUI 集成步骤均通过。最新失败详情可在[Actions 运行列表](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions)查看。

日志揭示了两项测试断言问题：`tests/test_modules.py` 把模块路径错误消息的词序写死，但不同 OS/Python 给出 `ImportError: invalid module path ...` 或 `ImportError: module path ... is not a readable file`；`tests/test_lsp_server.py` 把 definition 返回 URI 与输入 URI 作字面相等比较，但 Windows 临时目录的 8.3 短路径会被规范化成完整路径。LSP 规范和实现都要求返回规范化 URI。修复分支 `fix/ci-cross-platform-assertions` 已放宽错误断言为稳定类别/主题检查，并把 LSP 期望值改为 `Path.resolve(strict=False).as_uri()`。

在 Windows CPython 3.13.7 上，两个失败测试定向复验通过，全量 unittest **421 项通过**。提交修复后，应再检查当前 `main` SHA 的四格 Actions；本机测试不能替代 Linux、Python 3.10 和 Windows CI 结果。
