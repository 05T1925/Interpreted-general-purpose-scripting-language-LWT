# S32 主窗口复核：原生 DAP

日期：2026-10-31。结论：**通过，带人工编辑器验收遗留；已按既有授权快进合入本地 `main`。** S32 实现提交为 `236d94f92f402d0ef50333e518e6167711960b8b`，基线为 S31 集成提交 `ddf1759fa4239eabc15488730917daec990da390`。

## 核查与本轮验证

- 核对阶段分支、四层提交、S31 祖先关系及 `main...HEAD` 差异。S32 的修改集中在 DAP codec/server、共享调试控制层、VS Code 集成与相应测试/说明；`lwt/runtime.py`、语言规范、287 项黑盒、S10/S11/S28/S29 固定证据相对基线无差异。
- 本轮复跑 `python -m unittest tests.test_dap_protocol tests.test_dap_engine tests.test_dap_subprocess tests.test_debugger -q`：49 项通过，退出码 0。
- 本轮设置本机 `VSCODE_EXECUTABLE_PATH` 后运行扩展目录 `npm test`：Node 11/11、真实 Extension Host 4/4，通过且无 skip。Host 的 DAP 测试命中源码断点，取栈/变量并继续收到输出和结束事件。
- `git diff --check main...HEAD` 通过；保护路径差异为空。阶段报告记录的 287/287 黑盒、442 项全量 unittest、VSIX 打包等是执行窗口结果，本轮没有重复全部命令。
- `git push origin feature/editor-integration` 于本轮正常成功。对应精确 SHA `236d94f` 的 [Actions run 41200279217](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41200279217) 在 Ubuntu/Windows × Python 3.10/3.13 四格全部成功。先前执行报告中的 TLS 握手失败是当时的真实记录，本轮网络恢复后已重新核实。

## 判断与遗留

实现使用真实 DAP 请求/事件与 S30 调试钩子，保留 CLI 调试入口；断点、步进、调用栈、只读变量、输入输出隔离及取消边界均有自动证据。没有发现需要阻断集成的可复现缺陷。

人工安装 VSIX、真实键鼠 F5、断点 gutter 视觉与焦点行为仍未验证。VSIX 打包有许可证和未 bundle 的工具警告；这不影响本次本地打包成功，但最终交付应补齐许可证文件并核对分发包。本轮已将 `docs/test-matrix.md` 中 S8 时“远端 Actions 尚未触发”的历史状态标明时间范围，避免误读成当前状态。

S23–S30 的逐阶段独立审查记录不完整；本轮的聚合测试与 CI 不替代逐项历史审查。S12 应保留新克隆、PPT、GUI/编辑器现场预检及最终远端核验。后续可按用户本轮新要求规划 S33 测试工作台，作为语言语义冻结后的开发工具功能阶段。
