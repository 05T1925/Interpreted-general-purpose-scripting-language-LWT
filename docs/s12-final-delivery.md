# S12 最终交付候选执行报告

日期：2026-11-03。状态：**执行窗口已形成候选，等待主窗口审查**。本报告不代表已合入 main、最终 SHA 的远端 CI 四格成功或线下人工验收通过。

## 1. 基线与审查边界

开工 `git status -sb` 为干净的 `main...origin/main`；`HEAD`、本地 `main`、`origin/main` 及实时 `git ls-remote origin refs/heads/main` 均为 `79284f001eb2421be1455aa547a073103329b907`。远端 URL 为 `https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT.git`。从这一已审查主线创建 `milestone/final-delivery`，保留历史；没有 reset、rebase、强推、改写 main 或启动新功能阶段。首笔提交 `57ae184834fede4931cdc9b8d72badd3bf671783` 增加可编辑 PPT。后续文档提交和最终 HEAD 以本分支 `git log -3 --format=%H` 核对；提交不能可靠地在自身正文中预写自身 SHA。

第二笔提交 `507cb53897ca3b15ddbb7282414d89c25ed46ef7` 增加演示脚本、问答卡和验收清单。权威顺序为[课程原文](../大作业内容.md)、[正式语言规范](language-spec.md)、当前公开 CLI 与测试，再参考阶段计划/报告。S23–S30 仅按现存证据表述；不能由提交位于 main 推定各阶段都经独立主窗口审查。

## 2. 八项交付差距审计

| 作业提交物 | 当前文件与实测证据 | 本轮状态 |
|---|---|---|
| 1 语法规则 | [正式规范](language-spec.md)；最小/模块/错误示例 | 已存在；新克隆 CLI 与示例相符 |
| 2 解释器源码 | [`lwt/`](../lwt/)；`python -m lwt`、`--check`、模块与 RuntimeError | 已存在并实测 |
| 3 完整黑盒 | [`tests/cases/`](../tests/cases/)、[覆盖矩阵](test-matrix.md)、runner | 新克隆 287/287；完整性 287/384/287 |
| 4 性能报告 | [S11 报告](../reports/performance.md)、[raw](../bench/results.json) | 历史正式 run 的 120 试次、60 配对、12 次 warm-up 与六组表格重核；本轮未重跑基准 |
| 5 人/AI 指南 | [开发指南](developer-guide.md)、[策略 SDK](strategy-sdk.md)、[`../.agents/skills/`](../.agents/skills/) | 入口已存在；策略 checker 在新克隆实测 |
| 6 Agent LWT 应用与记录 | [日志程序](../app/log_report.lwt)、[LWT 游戏](../app/lwt_snake/game.lwt)、[日志开发记录](agent-dev-log.md)、[独立策略记录](s39-agent-record.md) | 有效 LWT 分别 246、313 行；真实 CLI/双层验真通过 |
| 7 Git 历史 | main 及 S41 审查祖先、阶段分支提交 | 已保留；本阶段尚未合入 main |
| 8 系统 PPT | [可编辑 12 页 PPTX](../slides/LWT介绍.pptx) | 已生成、渲染逐页检查并在本机 PowerPoint 打开；现场讲解待验收 |

课程评分五部分为解释器 20、黑盒 20、性能 10、指南 20、Agent LWT 应用 30 分。课程应用的日志读取/解析/统计以及新游戏的移动、碰撞、食物、计分由 LWT 源码承担；Python/Tkinter 做进程、协议、录制、显示。原 Python Snake 是独立演示，不能充当 LWT 应用。

## 3. 仓库外新克隆验收

远端 `main` 直接克隆到 `C:\Users\28641\AppData\Local\Temp\lwt-s12-fresh-20261103`，新克隆 `HEAD=79284f001eb2421be1455aa547a073103329b907`。环境：Windows NT 10.0.26200.0、Python 3.13.7、Tk 8.6.15。新克隆未使用原工作区的未跟踪文件；Python 运行只依赖仓库与标准库，VS Code 扩展在新克隆中按 lockfile 执行 `npm ci`（npm 可使用全局下载缓存）。以下均是**本轮在新克隆实际执行**，0 为正常成功码。

| 命令（仓库根目录，扩展命令在 `editors/vscode-lwt/`） | 退出码与关键结果 |
|---|---|
| `python -m lwt examples/guide/hello.lwt` | 0；`hello, LWT`、`42` |
| `python -m lwt --check --format=json examples/modules/main.lwt` | 0；`ok=true, files_checked=3, diagnostics=[]` |
| `python -m lwt examples/modules/main.lwt` | 0；`demo:2` |
| `python -m lwt examples/language_lab/division_by_zero.lwt` | 3；`2:8: RuntimeError: division by zero` |
| `python tools/check_project_integrity.py` | 0；287 cases、384 matrix links、287 referenced cases |
| `python tools/run_tests.py` | 0；287/287，9 类别，45.739 秒 |
| `python -m unittest discover -s tests -q` | 0；522/522，485.799 秒 |
| `python -m compileall -q lwt tests tools bench app` | 0；无诊断 |
| `python -m unittest discover -s tests -p test_app.py -q` | 0；25/25 |
| `python tools/run_gui_integration.py --require-no-skips` | 0；真实 Tk 控件合成事件 26/26，fail=0 skip=0，72.059 秒 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0；246 有效行 |
| `python tools/count_lwt_lines.py app/lwt_snake/game.lwt` | 0；313 有效行 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 0；total 7、valid 6、malformed 1、matched 6；ERROR/INFO/WARN 各 2 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | 0；matched 1、WARN 1、cache 1 |
| `python -m lwt --check app/lwt_snake/game.lwt` 及三份策略源码 | 四条均 0；每条 `Check passed: 1 source file(s).` |
| `python -m app.lwt_snake.arena --check-strategy mobility-lookahead --catalog app/lwt_snake/strategies/strategy-catalog.json` | 0；静态/LWA1 烟测通过；三条正常帧分别 R/SPACE、L/SPACE、NONE/TRAPPED，错误帧与 EOF 符合预期 |
| `python -m app.lwt_snake.replay --verify app/lwt_snake/replays/demo-parent.json` | 0；Verified 10 transactions |
| `python -m app.lwt_snake.arena --verify reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json` | 0；九局 `game_verified=true`、`policy_verified=true`；Verified 9 matches |
| `python -m app.lwt_snake.counterfactual --verify reports/s40-divergence --catalog app/lwt_snake/strategies/strategy-catalog.json` | 0；baseline/4 step 2 与三条一步分支通过 |
| `python -m app.lwt_snake.witness --verify reports/s41-found --catalog app/lwt_snake/strategies/strategy-catalog.json` | 0；`found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs` |
| 同一命令验 `reports/s41-none` | 0；`found=false scanned=1/1`，只说明预算内未发现 |
| 同一命令验 `reports/s41-tampered` | 3；`WitnessError: agent feedback evidence mismatch` |
| `python -m app.lwt_snake.counterfactual --explain reports/s41-found/analysis --catalog ...` | 0；baseline R/SPACE 与 bfs D/FOOD；两条分支均 score 10→10、phase RUNNING |
| `python -m lwt.debugger --help` | 0；列出 break、step、next、finish、locals 等 |
| `python -m lwt.debugger --commands examples/debugger/session.txt --program-stdin examples/debugger/program-input.txt examples/debugger/main.lwt` | 0；在 `math helpers.lwt:2` 命中断点，`demo:5` |
| `npm ci` | 0；安装 180 包；审计提示 5 项 moderate advisory，未擅自升级依赖 |
| `npm run test:unit` | 0；18/18 Node 测试 |
| `npm run test:host`（未指定 Code.exe） | 0 但**跳过**，原因是自动路径未找到 `Code.exe`；此结果不计通过 |
| `VSCODE_EXECUTABLE_PATH=E:\APP\VS编译\VS code\Microsoft VS Code\Code.exe` 后 `npm run test:host` | 0；真实 Extension Host 7/7（含 DAP 断点）；自动宿主测试不等于人工编辑器验收 |
| 临时目录复制 `reports/s41-found`，只改 `agent-feedback.json.question`，再 `witness --verify` | 3；反馈证据不匹配；仓库固定原件未改 |

静态检查四条完整命令依次为 `python -m lwt --check app/lwt_snake/game.lwt`、`python -m lwt --check app/lwt_snake/strategy.lwt`、`python -m lwt --check app/lwt_snake/strategy_baseline.lwt`、`python -m lwt --check app/lwt_snake/strategies/mobility-lookahead.lwt`，均退出 0。S41 篡改的精确 PowerShell 步骤见[演示脚本](demo-script.md)；本轮已按该步骤在独立临时目录执行。

已运行的全量 unittest 包含 LSP、S30 CLI 调试器、S32 DAP 及 S39–S41 定向回归。未运行会改写固定 `reports/lsp-smoke.json` 的生成命令。`npm ci` 的 advisory 是依赖提示，本阶段未进行许可证或依赖升级决策。

## 4. S11 与 S10 原始数据审计

正式 S11 run ID 为 `291bd4e2-8a3e-4de6-be86-46b62980e656`，历史 Git SHA 为 `c6f38a0e9ee796c9ac82498599d91da542ae325a`；120 个正式 trial 的输出验证全为 pass，60 对有效配对、12 次 warm-up。用当前 `tools.benchmark.formal_summaries` 从原始 ns 重算，六组中位数均与报告表格一致（ms，LWT / Python）：arithmetic N=100 `108.117 / 39.187`、1000 `107.483 / 37.394`、5000 `129.590 / 38.389`；array_scan N=100 `111.168 / 40.837`、1000 `129.359 / 38.826`、5000 `182.926 / 36.707`。四份源文件的 SHA-256 与**历史测量提交的 Git 内容**逐一匹配；当前工作树文件字节摘要与 raw 不同，不能把该 run 说成当前源码新测量。正式报告和原始 JSON 保持不变。

计时从 `subprocess.run` 前到进程返回后，含新进程启动、Python/LWT 导入、LWT 词法/语法分析、程序执行与输出等待；不代表纯解释器执行速度。本机小样本不能外推其他硬件或平台。S10 `reports/app-concurrency.json` 记录固定只读输入在 1、2、4 个独立进程下各 5 次，errors=0；`app_source_sha256` 与其历史源提交内容一致，当前 Git blob 未变，工作树字节差异来自签出换行。该证据不说明 LWT 线程或 GUI 并行吞吐。本轮没有运行正式性能或并发生成器。

## 5. PPT、演示与桌面证据

[PPTX](../slides/LWT介绍.pptx)共 12 页；内容为课程映射、语法、流水线、语义、黑盒、指南与应用、日志输出、Snake/S39–S41、S11 原生可编辑图表、并发与工具、现场顺序。图表 12 个数字点来自 S11 正式 run 的六组中位数，每组每语言 10 次，单位 ms。使用本地 Artifact Tool 导出并逐页渲染 12 张预览，逐页检查文字、裁切与图表；结构、布局、字体和原生图表内嵌数据校验通过，PPTX SHA-256 为 `0e680d17d0b0f09315a6519b15c9516ee04dac34df7dc8e42ea771c797b5fe5d`。本机 PowerPoint 已打开文件并显示 12 页，不等于已完成现场讲解。

[演示脚本](demo-script.md)给 5–8 分钟主线、无 GUI 后退与临时副本篡改命令；[问答卡](defense-qa-card.md)覆盖解释器、语义、测试、性能、并发、Agent 和见证范围。

桌面物理交互：本轮启动语义实验室，首次观察到窗口已有“预测已提交、程序已运行”的状态，但这些动作并非本执行窗口发送；输入归属不清，因此立即停止后续自动点击。没有把此画面计为人工通过。语言实验室、日志工作台、LWT Snake 手动/自动/回放、S41 查看器、焦点/缩放/输入法和真实视觉体验均列为**现场未验证**。Tk 26/26 与 PowerPoint 打开是不同证据层；前者仅控件合成事件，后者仅文件可打开/可见。现场预检清单见[最终核对表](final-acceptance-checklist.md)。

## 6. CI、保护和交接

工作流 `.github/workflows/tests.yml` 仍配置 Ubuntu/Windows × Python 3.10/3.13 四格、15 分钟 job。S41 审查 SHA 的四格历史成功不能替代 S12 最终 SHA。首次只读 GitHub API 查询受到匿名速率限制；按实际最终 SHA 和 run URL 逐格复核。Python 3.10 是历史最低兼容目标，2026 年已不作为推荐部署版本；本轮本机仅 Python 3.13.7。

阶段分支首轮推送已成功，远端 `main` 当时仍为 `79284f001eb2421be1455aa547a073103329b907`。随后从远端 `milestone/final-delivery` 再次独立克隆到 `C:\Users\28641\AppData\Local\Temp\lwt-s12-candidate-20261103`，确认该时点的 `c602396bbc3537f6ceb63d49e6d81f7d5013876c` 与 PPT、演示脚本均可取得，工作区干净。该首轮 SHA 的 [Actions run 41572388182](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41572388182) 在查询时仍为 `In progress`；报告补充提交会产生新的最终 SHA，应以**最终 SHA 的新 run** 逐格复核，不能沿用此 run 的结论。

保护路径对 `main...HEAD` 须保持空差异：`lwt/`、[正式规范](language-spec.md)、`tests/cases/`、[测试矩阵](test-matrix.md)、`app/log_report.lwt`、`app/lwt_snake/game.lwt`、三份策略、S35–S41 固定结果、`reports/app-concurrency.json`、`docs/app-concurrency.md`、`bench/results.json`、`reports/performance.md`、S28 profile 与 S29 smoke。没有更改语言语义、游戏规则或固定原始证据。

主窗口下一步：复核提交与 PPT 数字、核对阶段分支精确 SHA Actions 四格、决定是否快进合入 main；在输入归属明确的桌面完成[现场清单](final-acceptance-checklist.md)。线下教师验收、最终标签与发布由主窗口依课程实际流程处理；本执行窗口不推送 main、不打标签。
