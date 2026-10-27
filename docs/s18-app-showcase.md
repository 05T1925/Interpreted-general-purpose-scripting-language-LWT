# S18 应用展示与证据路径

状态：S18 阶段分支实施完成，等待主窗口审查。本文是答辩演示准备，不是最终 PPT，也不代表 S12 已完成。

## 教师要求与可复核证据

| 教师评分关注点 | 本项目证据 | 边界 |
|---|---|---|
| Agent 用 LWT 编写完整应用 | [日志分析器 LWT 源码](../app/log_report.lwt)，按 [计数工具](../tools/count_lwt_lines.py) 实测 246 行有效 LWT；支持记录解析、坏行、组合过滤、统计、排序与固定报告 | [Snake](../app/snake_game.py) 是独立 Python/Tkinter 附加演示，不计作第二个 LWT 应用 |
| 应用可运行、可检查 | [25 项公开 CLI 契约测试](../tests/test_app.py)；默认与过滤命令及固定期望输出见 [应用说明](../app/README.md)、[sample.expected.txt](../app/fixtures/sample.expected.txt) | GUI 不能代替 CLI 契约测试 |
| 同一输入可并发读取 | [固定输入并发方法与解释](app-concurrency.md)、[逐进程原始记录](../reports/app-concurrency.json) | 证明独立进程同时读取；不声称 LWT 有线程或并行加速 |
| 可交互展示 LWT 结果 | [日志侦探入口](../app/log_detective.py)、[工作台界面](../app/log_workbench_ui.py)、[严格报告模型](../app/log_report_view.py)；筛选条件、实际 argv、原始 stdout 可逐项追溯 | Python 只发起 CLI、校验报告、渲染、管理五题挑战；不读原始日志做业务统计 |
| Agent 开发过程可追溯 | [开发记录](agent-dev-log.md)、[S18 阶段报告](s18-workbench.md)、Git 分层提交 | 记录提示、生成内容和人工复核；不将未运行步骤写成结果 |

## 三分钟现场顺序

1. **0:00–0:30**：从仓库根运行 `python app/log_detective.py`。指出“数据由 LWT 程序计算”，窗口有“分析工作台”与“五题挑战”两个选项卡。
2. **0:30–1:10**：默认 `sample.log` 点击“运行 LWT 查询”；读出 Total 7、Valid 6、Malformed 1、Matched 6，以及 ERROR/INFO/WARN 各 2。点击“查看此次原始报告”，逐项对照图表和 stdout。
3. **1:10–1:50**：Level 填 `WARN`、Keyword 填 `retry`、Top 填 `2`，重新查询。读出匹配 1、`WARN|1`、`cache|1` 和 retry 示例；展示 argv 中的独立参数。清空 Keyword 或点击级别条再查询，说明不会在 Python 中自行过滤。
4. **1:50–2:25**：选择 [丰富演示日志](../app/fixtures/showcase.log)，运行默认查询，再使用 WARN/retry/Top 2；观察 Unicode、坏行和模块排行。此 fixture 的两条 retry 缓存记录使匹配数为 2。
5. **2:25–3:00**：切到“五题挑战”，完成一题、展示报告入口；快速指出 [LWT 源码](../app/log_report.lwt) 的 246 行、[25 项 CLI 测试](../tests/test_app.py) 与 [并发证据](app-concurrency.md)。明确独立贪吃蛇是 Python/Tkinter 附加演示。

## 无 GUI 后退方案

若现场 Tkinter 或桌面不可用，从仓库根逐字运行：

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log
python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2
python -m lwt app/log_report.lwt -- app/fixtures/showcase.log
python -m lwt app/log_report.lwt -- app/fixtures/showcase.log --level WARN --keyword retry --top 2
python -m unittest discover -s tests -p "test_app.py" -v
python tools/count_lwt_lines.py app/log_report.lwt
```

样例默认报告匹配 6，组合过滤匹配 1；丰富 fixture 默认报告 12/11/1/11，组合过滤匹配 2。可直接对照原始 stdout，不依赖 Python 图表。
