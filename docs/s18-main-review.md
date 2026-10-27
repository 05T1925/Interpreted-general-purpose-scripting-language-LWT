# S18 主窗口复核

日期：2026-10-27。结论：**带非阻断遗留通过**。阶段最终提交 `f7b543065b1ae883c339ced535960541a73d716a` 已从本地 `main` 的 `8be88474316238532294f6bb7e83b0cdb8ebfdb5` 快进合入；未推送。S12 未开始。

## 独立证据

- 阶段分支基线和工作区干净状态已核对；15 个变更文件集中在报告视图、Tk 工作台、测试、演示数据和文档。`app/log_report.lwt`、`tests/test_app.py`、S10 并发记录及 S11 性能原始数据/报告与基线无差异。
- Windows Python 3.13.7 实跑：全量 unittest **256 项通过**，LWT 黑盒 **194/194**，完整性检查 **194 cases / 287 links / 194 referenced cases**，`compileall` 通过，LWT 应用仍 **246 行**，阶段差异无空白错误。
- 实际启动了工作台窗口并看到文件路径、筛选表单、查询按钮和数据来源说明；在 Level 输入 `WARN`、Keyword 输入 `retry` 后，状态变为等待新查询。继续操作 Top 时桌面工具检测到同机其他输入并中断，本窗口没有把组合查询 GUI 流程记作手动通过。阶段报告此前已实际点击默认查询；组合过滤的 CLI/无头测试通过。

## 可复现的非阻断缺陷

`app/log_report_view.py` 的 `parse_report()` 使用 `raw.splitlines()`。Python 的 `splitlines()` 除 LF 外也会在 U+0085、U+2028、U+2029 等字符处分行；LWT 日志格式仅以 LF 划分逻辑行，其他字符可以出现在合法消息字段。[Python 字符串文档](https://docs.python.org/3/library/stdtypes.html#str.splitlines)列出该差异。

本窗口在临时 UTF-8 文件写入一条 `t|INFO|app|alpha\u2028beta\n`，公开 `python -m lwt` CLI 成功输出包含原样 U+2028 的完整报告；同一文件交给 `analyze_workbench()` 时抛出 `AnalyzerError`，提示匹配示例数量不符。普通日志和现有 256 项测试不受影响，但工作台会误拒绝这类合法 Unicode 内容。**S19 第一项必须用真实 CLI 回归用例修复，仅按报告协议中的 LF 拆行；不得改变 LWT 日志语义或删去严格校验。**

## 留存边界与下一步

S18 的默认查询、组合过滤 CLI、纯报告契约和核心异步状态满足阶段目标，故带上述少见 Unicode 边界遗留合入。GUI 的组合查询、原始报告按钮、错误恢复、文件选择、最小窗口实际拖拽以及 S17 的部分 Snake 按键/焦点场景仍无完整可归因桌面验收。S19 先修上述缺陷并补实测，再做[语言实验室与高价值展示规划](s19-optimization-plan.md)。最终新克隆、远端 CI/Python 3.10、PPT 和发布仍属于 S12。
