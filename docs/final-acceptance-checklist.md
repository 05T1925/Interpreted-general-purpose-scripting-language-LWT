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
- [ ] 主窗口核对最终 SHA 的 Ubuntu/Windows × Python 3.10/3.13 四格 Actions。
- [ ] 主窗口审查提交、远端同步、线下验收与教师实际要求。
