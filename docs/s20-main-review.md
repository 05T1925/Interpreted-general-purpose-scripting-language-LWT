# S20 主窗口复检

日期：2026-10-27。结论：**S20 通过审查，带桌面 GUI 未验证项，已快进合入本地 `main`；未推送。** S12 仍未开始。

## 分支和审查范围

- 阶段分支：`stage/s20-teaching-demo-acceptance`
- 阶段最终提交：`1387fb6f395c43c06cf63ed7be6a4f0900bd73e4`
- 基线：本地已审查 `main` 的 `44f85e9b2b3a1c3c12e57f66d0adb286588ffbf6`
- 主窗口审查后，阶段分支已快进合入本地 `main`。S20 执行报告记录当时 `origin/main` 落后本地阶段历史；本审查没有推送，也没有用远端旧历史覆盖本地成果。
- 审查覆盖入口退出码修复、预测会话状态、固定示例的公开 CLI 结果、测试、报告和保护范围。

## 主窗口独立验证

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -q` | 276 项通过。 |
| `python tools/run_tests.py` | 语言黑盒 194/194 通过。 |
| `python tools/check_project_integrity.py` | 194 cases、287 matrix links、194 referenced cases。 |
| `python -m compileall -q lwt tests tools bench app` | 通过。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 246 行有效 LWT。 |
| `git diff --check main...stage/s20-teaching-demo-acceptance` | 通过。 |
| 六个保护文件对比 S20 基线 | 无差异。 |

全量 unittest 包含 S20 入口子进程、语义实验室、S18 报告解析、日志侦探、Snake 和 S10 应用测试。独立复核没有重新运行并发或性能生成器。

## 审查结论

1. **启动退出契约已修复。** Tkinter 导入失败和 Tcl 初始化失败经模块入口输出 stderr 诊断并返回非零；无头成功 shim 返回 0；未预期 UI 异常保留 traceback。四种情形均有子进程测试。
2. **预测和 CLI 结果明确分开。** 六个固定案例先选择并提交预测，再运行真实 `sys.executable -m lwt`。用户预测反馈、实际 stdout/stderr/退出码和固定语言解释分别显示。预期除零被呈现为 RuntimeError 诊断。
3. **会话重置和异步结果处理有测试。** 切换、重置、错误重试、过期 revision 和关闭状态均有无头覆盖；worker 不直接更新 Tk 控件。
4. **语言和课程应用边界保持清楚。** 没有修改 LWT 解释器、正式规范、黑盒矩阵、日志统计逻辑或保护的 S10/S11 证据。预测答案来自固定教学数据，未在 Python 复制执行语言语义。
5. **桌面交互仍未验证。** S20 执行窗口观察到目标窗口被其他应用遮挡后停止操作。本窗口也没有取得可归因的点击/键盘 GUI 证据。所有窗口实际交互仍按报告列为未验证，不以 276 项测试或应用启动替代。

## 下一步

S20 已完成其代码和自动化验收目标，遗留集中在真实桌面体验。下一步 S21 应以桌面操作验收为主，只有发现可复现问题时才做最小修复，不再增加新功能。S21 完成后进入最终 S12。详细计划见 [S21 规划](s21-gui-acceptance-plan.md)。
