# S31 主窗口复核：VS Code 扩展

复核日期：2026-10-31
结论：**通过，带明确未验证项；可进入功能大阶段集成流程。** 本文不表示 S31 已合入或推送。

## 复核对象与 Git 状态

- 工作分支：stage/s31-vscode-extension
- S31 基线：5cc109a4302212a772a4fe6589cd15d36a55b055
- S31 最终提交：d2571540f50323d0e9be597caeb82575b2df6bcf
- S31 专属实现/测试/报告提交：938d029、21506b1、d257154
- 远端 main 与本地 main：f9db64dabbf55ffcf2510467c544956c2741a855
- S31 和 main 各自含四个/三个基线后的提交，分支分叉。S31 不在远端，未合并。
- 开始复核前阶段工作树干净；复核命令没有改动跟踪文件。无远端写操作。

## 复核重点

S31 通过现有 S27 checker、S29 Language Server、S30 CLI debugger 和普通 CLI 接入编辑器。manifest、TypeScript 工作流、参数数组和 cwd 构造、UTF-8 路径、Extension Host 测试及报告范围已核对。Check 是不执行路径；Run 使用普通 CLI；Debug 是集成终端中的 CLI 调试器，不是 DAP。报告对能力和证据边界描述准确，没有声称原生断点或 Debug UI 已接入。

S31 的三个提交可以保留原始 SHA 合入编辑器集成大阶段。由于 main 在 S31 基线之后已有四个提交，集成时必须处理分叉，不得把 main 误当成可快进到 S31 的祖先。

## 本轮实测

- python tools/run_tests.py：287/287 黑盒通过。
- python -m unittest discover -s tests -q：421 项通过。
- python -m compileall -q lwt tests tools bench app：通过。
- python tools/check_project_integrity.py：287 cases、384 matrix links、287 referenced cases，通过。
- 编辑器目录 npm test：9/9 Node 单测和 3/3 隔离 Extension Host 测试通过。第一次未设置 VSCODE_EXECUTABLE_PATH 时 Host 测试被明确跳过；随后设置为本机 Code.exe 的绝对路径并完整重跑，最终 3 项均执行且通过。报告只采用第二次结果。
- git diff --check 5cc109a...HEAD：通过。
- 文档本地链接与围栏核对：S31 执行报告及本次修改文档无断链或未闭合围栏。
- 远端只读核验：origin/main=f9db64d。Actions run 41183683056 的 Ubuntu/Windows × Python 3.10/3.13 四个 job 全部成功。该 run 不包含 S31。
- 未重新生成 VSIX；此前本地打包结果仍是阶段执行报告中的历史证据。

## 保留的遗留与边界

1. 本地安装 VSIX 的 Code CLI 探针曾超时；人工安装、真实桌面编辑和端到端按键体验没有验证。
2. npm 曾报告 5 个 moderate advisory；production-only audit 因 registry TLS 中断没完成。没有自动升级依赖。
3. S31 自身尚无远端 CI 矩阵。main 上的 Python 四格绿灯不覆盖 S31。
4. Python 3.10/Linux 的 S31 扩展宿主组合未在本轮本机实测；需要功能分支集成后由 CI 验证。
5. GUI/编辑器人工操作仍需在 S12 的可控桌面验收中检查。
6. S31 如实没有 DAP；在 VS Code 中目前没有 gutter 断点、原生 Call Stack/Variables 面板或图形单步。

上述遗留不阻止将已有扩展接入功能大阶段，但必须保留在项目状态和最终交付清单中。
