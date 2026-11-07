# S12 最终交付核对清单

状态：执行窗口候选清单；主窗口审查、合入 main、远端精确 SHA CI 与现场人工验收分别确认。实测详情见 [S12 执行报告](s12-final-delivery.md)。

| 课程提交物 | 仓库位置 | 本轮检查方式 |
|---|---|---|
| 1 语法规则 | [正式规范](language-spec.md) | 与最小程序、模块、错误和黑盒矩阵核对 |
| 2 解释器 | [`lwt/`](../lwt/) | 新克隆 `python -m lwt`、`--check`、模块与定位错误 |
| 3 完整黑盒 | [`tests/cases/`](../tests/cases/)与[矩阵](test-matrix.md) | `python tools/run_tests.py`、完整性检查 |
| 4 性能报告 | [S11 报告](../reports/performance.md)与[raw](../bench/results.json) | 原始 run、120 正式试次、六组统计、历史源摘要 |
| 5 人/AI 指南 | [开发指南](developer-guide.md)、[策略 SDK](strategy-sdk.md)、`.agents/skills/` | 新克隆按入口运行、相对链接检查 |
| 6 Agent LWT 应用/记录 | [日志应用](../app/log_report.lwt)、[LWT 游戏](../app/lwt_snake/game.lwt)、[开发记录](agent-dev-log.md) | 有效行数、真实 CLI、S39–S41 复验 |
| 7 Git 历史 | `git log --oneline --decorate` | 祖先、阶段分支、远端与工作区分别核对 |
| 8 系统 PPT | [可编辑 PPTX](../slides/LWT介绍.pptx) | 12 页导出、渲染逐页查读性 |

## 现场预检

- [ ] 语义实验室：预测、运行、解释、重置、窗口缩放、输入法与焦点。
- [ ] 日志工作台：WARN/retry/top=2、原始报告、文件错误后恢复。
- [ ] LWT Snake：方向键、提示、自动驾驶、失焦、录制/回放/接管。
- [ ] S41 只读 Tk 查看器：载入本地见证、重新验真、切换/关闭。
- [ ] 演示桌面无遮挡、输入归属清楚；无法确保时用 [CLI 脚本](demo-script.md)。
- [x] 主窗口核对候选精确 SHA `e1249f56f1d889c0c6e400a46602e0fe3f7df1ce` 的 Ubuntu/Windows × Python 3.10/3.13 四格 Actions（run [41572881428](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41572881428)，全部成功）。
- [x] 主窗口审查候选提交、快进集成到本地 `main` 并正常推送；推送后远端 `main` 与本地 `HEAD` 一致。
- [ ] 完成现场人工 GUI 检查，并按教师实际要求确认线下验收与最终归档。

## S43 确定性并发（执行窗口完成，待主窗口审查）

| 课程抓手 / 任务书 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 并发子语言（规范 §11） | [正式规范](language-spec.md)、[`lwt/concurrency.py`](../lwt/concurrency.py)、[契约卡](concurrency.md) | 19 项并发单测 + 46 项黑盒；`--check`/`--profile`/debugger 工具边界 | 执行实现完成，待复核 |
| 46 并发黑盒 + 确定性 | [`tests/cases/concurrency/`](../tests/cases/concurrency/)、[矩阵](test-matrix.md) §11 | `run_tests.py`（全量 400/400）、`run_concurrency_determinism.py --repeat 10` | 执行实现完成 |
| 三态见证 | [`reports/s42-schedules/`](../reports/s42-schedules/) | found 200 种子 2 类、absent 200 种子 1 类、tampered 三篡改均 exit 4 | 执行实现完成 |
| 并发应用（30 分抓手） | [`app/concurrent_log_report.lwt`](../app/concurrent_log_report.lwt)、[开发记录](s42-app-dev-log.md) | 233 有效行、4 fixture 差分等价、坏文件 recover、10 次确定 | 执行实现完成 |
| 诚实性能实验 | [`reports/concurrency-performance.md`](../reports/concurrency-performance.md) | 4 组对照、Amdahl 上限、不宣称 CPU 加速 | 执行实现完成 |
| 指南 / PPT / 答辩 | 开发指南、`slides/LWT介绍.pptx`、[答辩卡](defense-qa-card.md) | PPT 12→15 页、旧图表 12 数值点未变、旧/新 SHA 记录 | 执行实现完成 |
| Agent 盲测 pass@1 | [`docs/s42-agent-blind-test.md`](s42-agent-blind-test.md) | 无上下文会话不可开 → 如实写"未执行"，不自测冒充 | 未执行 |
| 远端精确 SHA 的 CI | 无（本阶段不推送） | 功能分支未推送，Actions 未查询 | 未验证 |

**重要**：以上 S43 行只记录**执行窗口自测**，不替代 **S12 现场人工 GUI A–E 验收**（语义实验室、日志工作台、LWT Snake、S41 Tk 查看器、演示桌面无遮挡与输入归属），也不替代主窗口审查、合入 main、远端 CI 与教师线下验收。执行实现 / 主窗口审查 / 合入 main / 远端 CI / 现场人工 GUI 五项状态分别确认，不能由一项推断另一项。S43 阶段报告见 [s42-deterministic-concurrency.md](s42-deterministic-concurrency.md)。
