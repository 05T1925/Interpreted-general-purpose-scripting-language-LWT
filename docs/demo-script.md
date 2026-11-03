# LWT 答辩演示脚本（候选版）

从仓库根目录运行。建议提前打开 [系统介绍 PPT](../slides/LWT介绍.pptx)，准备 Python 3.13 和终端。所有命令均使用公开 CLI；固定证据保持只读。现场按教师要求调整顺序。预计主流程 5–8 分钟，其中策略证据链约 3–5 分钟；新进程重验耗时随机器变化。

## 主流程

| 时间 | 操作与讲解 | 命令或证据 |
|---|---|---|
| 0:00–0:35 | 说明课程五项评分与八项提交物。LWT 用 `record`、`when/otherwise`、`each`、`emit` 组合语法。 | [课程要求](../大作业内容.md)、[正式规范](language-spec.md) |
| 0:35–1:05 | 跑最小程序，说明源码经 lexer、parser、AST 和树遍历运行。再演示可定位的除零错误。 | `python -m lwt examples/guide/hello.lwt`；`python -m lwt examples/language_lab/division_by_zero.lwt`（退出 3） |
| 1:05–1:40 | 展示一键黑盒和覆盖矩阵。现场时间不足可展示已记录的新克隆完整输出，再抽跑用例，不把旧记录说成现场运行。 | `python tools/run_tests.py`；`python tools/check_project_integrity.py`；[矩阵](test-matrix.md) |
| 1:40–2:20 | 展示 LWT 日志分析器对坏行、等级和关键字的处理。Python 工作台只解析报告并绘图。 | `python -m lwt app/log_report.lwt -- app/fixtures/sample.log`；加 `--level WARN --keyword retry --top 2` |
| 2:20–2:55 | 展示 Agent 策略模板、独立产出记录和真实协议检查。 | [SDK](strategy-sdk.md)、[Agent 记录](s39-agent-record.md)；`python -m app.lwt_snake.arena --check-strategy mobility-lookahead --catalog app/lwt_snake/strategies/strategy-catalog.json` |
| 2:55–4:30 | 依次验 S39 原局、S41 自动差异和 S40 一步分支。说明双方收到的是**同一已验证观察前缀**；第一处分歧只在给定清单、排序及预算内成立。 | 下方“证据链命令” |
| 4:30–5:20 | 复制固定见证到仓库外临时目录，只改副本的反馈字段，展示拒绝。原始 `reports/` 不改。 | 下方“篡改拒绝” |
| 5:20–6:15 | PPT 说明 S11 六组端到端性能中位数、S10 独立进程一致性边界、Git/CI 与未验证项。 | [性能报告](../reports/performance.md)、[并发说明](app-concurrency.md) |
| 6:15–7:00 | 若桌面归属明确，选一条已预检 GUI 操作；否则执行 CLI 后退并说明人工输入法/视觉项未验证。 | `python -m app.language_lab` 或 `python -m app.lwt_snake.counterfactual_ui` |

## 策略证据链命令

```powershell
python -m app.lwt_snake.arena --verify reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.witness --verify reports/s41-found --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual --explain reports/s41-found/analysis --catalog app/lwt_snake/strategies/strategy-catalog.json
```

第一条用全新 LWT 游戏和策略进程重算九局，预期 `Verified 9 matches: game and policy decisions.`；第二条预期 `found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs`；第三条解释 baseline `R/SPACE` 与 BFS `D/FOOD` 在同一局面各自推进一步的真实游戏结果。完整证据见 [S39 结果](../reports/s39-demo/result.json)、[S41 见证](../reports/s41-found/witness.json)与 [S40 分支](../reports/s41-found/analysis/analysis.json)。原结果哈希、策略源码摘要和分支回放均在验真时重新核对。它证明固定输入和当前源码下可复算的决策与一步效果，不认证历史执行主体，也不证明策略整体优劣。

## 篡改拒绝（仅临时副本）

```powershell
$tmp = Join-Path $env:TEMP 'lwt-s12-demo-tamper'
if (Test-Path -LiteralPath $tmp) { throw '目标已存在，请换一个临时目录名' }
Copy-Item -LiteralPath reports/s41-found -Destination $tmp -Recurse
$p = Join-Path $tmp 'agent-feedback.json'
$j = Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
$j.question = 'tampered in temporary copy'
$j | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $p -Encoding UTF8
python -m app.lwt_snake.witness --verify $tmp --catalog app/lwt_snake/strategies/strategy-catalog.json
```

预期退出 3 并指出反馈证据不匹配。若固定 schema 不含 `question` 字段，应改为复制仓库内已提交的 [S41 篡改样例](../reports/s41-tampered/agent-feedback.json)到临时副本同名位置；切勿修改仓库固定证据。演示前实际执行并核对本段命令，不能仅凭文档推测结果。

## 无 GUI 后退

无需桌面、网络或第三方 GUI 库即可运行上面的 CLI。展示游戏规则时使用 `python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-parent.json`；展示语言模块时使用 `python -m lwt examples/modules/main.lwt`。GUI/Tk 自动测试证明控件回调集成，不能代替现场真实鼠标、键盘、焦点和视觉检查。
