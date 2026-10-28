# S22 主窗口复核

日期：2026-10-28。结论：**S22 通过主窗口复核，已快进合入本地 `main`；没有推送。** 真实桌面人工操作仍未验证；S21 的 A/B/C 现场清单继续留给最终演示预检。

## 基线与合入

- 基线：`1919861652266edd75ce278736d71958eb90cd62`，S21 最终提交 `d7ca188168cd449027de546b61f78670c29e08ca` 为其祖先。
- 阶段分支：`stage/s22-gui-regression`。
- 最终提交：`761ce331b0257fe0128a6ba9b190c2ba6f9f30e1`。
- 分层提交：`790146aeec52e3551ae523eae18175379e468006`（Tk 控件测试与测试接缝）、`652ef58213c4ba2be988b3d51b70ab0392475e98`（Linux/Xvfb CI）、`761ce331b0257fe0128a6ba9b190c2ba6f9f30e1`（报告与状态同步）。
- 主窗口确认阶段分支从本地已审查 `main` 快进；当前本地 `main` 与 S22 阶段 tip 同为 `761ce33`，工作区干净。
- 执行窗口的 `git ls-remote` 因 TLS/Schannel 握手错误退出 1；远端当前 tip 与远端 Actions 未核实。审查窗口未推送、未尝试绕过 TLS，也未将本地跟踪分支状态当作实时远端事实。

## 独立复核

主窗口在 Windows 11、Python 3.13.7、Tk 8.6.15 上重跑：

| 检查 | 独立结果 |
|---|---|
| `python tools/run_gui_integration.py --require-no-skips` | exit 0；10/10 通过；0 fail、0 skip；Tk display available。 |
| `python -m unittest discover -s tests -q` | exit 0；286 项通过。 |
| `python tools/run_tests.py` | exit 0；194/194 黑盒通过。 |
| `python tools/check_project_integrity.py` | exit 0；194 cases、287 matrix links、194 referenced cases。 |
| `python -m compileall -q lwt tests tools bench app` | exit 0。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | exit 0；246 行有效 LWT。 |
| 阶段基线保护路径 diff | exit 0；六个 S10/S11 保护文件、`lwt/`、规范、黑盒矩阵/用例无差异。 |
| Workflow YAML | 可解析；Ubuntu/Windows × Python 3.10/3.13 四格保留；Linux GUI 步骤在 Xvfb 下强制零 skip。 |
| `git diff --check 1919861...761ce33` | 通过。 |
| 全仓 Markdown | 38 份文件、598 个本地链接；缺失 0、未闭合围栏 0。 |

测试实际创建 Tk/Ttk 控件、驱动事件绑定并推进事件循环；至少一条路径经真实公开 LWT CLI 子进程完成。针对 runner、timer 和系统文件选择器的注入边界有明确记录。未发现可稳定复现的产品缺陷，S22 没有产品逻辑修复。

## 证据限制与交接

- 10 项控件集成测试和 Tk 几何检查不证明物理鼠标/键盘、输入法、桌面焦点/窗口管理器或视觉可读性；人工桌面操作本轮未执行。
- 远端 Actions 没有本阶段运行记录；Python 3.10 与四格远端状态仍待最终候选提交验证。
- 无性能/并发证据生成器运行；`app/log_report.lwt`、S10 CLI 契约和 S10/S11 raw 内容保持不变。
- 这些剩余工作均可在最终 S12 交付阶段完成，无需再建一个 GUI 产品阶段。

执行报告见 [S22 报告](s22-gui-regression.md)，阶段规划见 [S22 计划](s22-gui-regression-plan.md)。
