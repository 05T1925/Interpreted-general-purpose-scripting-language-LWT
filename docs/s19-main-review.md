# S19 主窗口复检

日期：2026-10-27。结论：**S19 通过审查，带一项低优先级启动契约遗留，已快进合入本地 `main`；未推送。** S12 仍未开始。

## 分支和复核范围

- 阶段分支：`stage/s19-language-lab-robustness`
- 阶段最终提交：`3057df65cef0edcc82ad050462f2fa7991cd28db`
- 基线：`c966f97096fd590a77176c9b18f8f45fee5fed31`
- 主窗口复核后本地 `main` 快进到阶段提交；远端 `origin/main` 仍是旧历史，本轮没有 fetch/push，也没有覆盖本地进度。
- 独立检查覆盖 LF 报告协议修复、语义实验室核心和 UI 生命周期、阶段报告、测试及保护文件。

## 独立运行结果

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests -q` | 268 项通过。 |
| `python tools/run_tests.py` | 黑盒 194/194 通过。 |
| `python tools/check_project_integrity.py` | 194 cases、287 matrix links、194 referenced cases。 |
| `python -m compileall -q lwt tests tools bench app` | 通过。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 246 行有效 LWT。 |
| `git diff --check main...stage/s19-language-lab-robustness` | 通过。 |

独立模拟缺少 Tkinter 的公开启动路径时，`python -m app.language_lab` 输出了可读错误，但进程退出码为 **0**。复现使用子进程将 `tkinter` 标记为不可导入，再以 `runpy` 执行模块入口。错误文字正确，退出码语义有误，见下方 S20 遗留。

## 审查结论

1. **报告拆行修复有效。** `parse_report` 只按 LF 拆分报告，并只去掉协议要求的最终 LF。真实 LWT CLI 回归覆盖 U+0085、U+2028、U+2029、VT、FF；原有固定字段、顺序、计数、示例数和尾随 LF 严格校验保留。
2. **语义实验室边界清楚。** 固定白名单的六个案例经 `sys.executable -m lwt` 运行；显示源码、规范章节、argv、cwd、stdin、stdout、stderr 和退出码。Python 前端没有替代 LWT 求值或日志统计；没有执行任意路径。
3. **异步状态处理有核心测试。** 测试覆盖超时、进程启动失败、Tk/Tcl 初始化失败、切换示例时丢弃旧结果、可重试状态和六个公开 CLI 案例。
4. **保护范围完整。** `app/log_report.lwt`、`tests/test_app.py`、S10 并发原始数据/报告和 S11 性能原始数据/报告相对基线均未改变；没有运行会覆盖它们的生成器。
5. **GUI 仍缺人工验收。** 执行报告明确区分 CLI/无头证据和实际点击。本窗口没有取得可归因的语义实验室布局/交互及工作台、挑战、Snake 的完整桌面观察；相关项目继续标为未验证。

## 遗留问题与优先级

**P2：桌面入口失败返回成功码。** `app/language_lab.py` 的 `__main__` 捕获 `RuntimeError` 后打印诊断但正常返回，因此缺少 Tkinter 或无法创建窗口时，shell 看到 exit 0。S20 应让启动失败返回非零，并用真实子进程测试 stdout/stderr/退出码；正常启动的 GUI 主循环不应被此调整影响。

**P1：GUI 人工验收缺口。** 在可归因的桌面输入环境复核语义实验室选择/运行/结果/错误恢复/关闭，及 S18 工作台、日志侦探挑战和 Snake 的剩余验收矩阵。自动化测试、窗口句柄和 Tk 几何数据不能替代实际输入观察。若环境仍受干扰，停止自动点击并保留未验证状态。

## 集成状态

S19 变更已快进合入本地 `main`，没有推送。复核后基线是 `3057df65cef0edcc82ad050462f2fa7991cd28db`；工作区在审查文档提交前后均保持可核对。下一阶段规划见 [S20 优化规划](s20-optimization-plan.md)。S12 仍为最终收尾。
