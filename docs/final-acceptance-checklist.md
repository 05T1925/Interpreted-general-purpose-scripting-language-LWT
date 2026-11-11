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
| 8 系统 PPT | [可编辑 PPTX](../slides/LWT介绍.pptx) | 21 页（以 manifest 为准）、渲染逐页查读性（第 10 页原生图表 12 数值点自 S43 起未变） |

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
| 指南 / PPT / 答辩 | 开发指南、`slides/LWT介绍.pptx`、[答辩卡](defense-qa-card.md) | PPT 15→17→18 页、旧图表 12 数值点未变、旧/新 SHA 记录（S45 新 SHA `b8c15c03…`） | 执行实现完成 |
| Agent 盲测 pass@1 | [`docs/s42-agent-blind-test.md`](s42-agent-blind-test.md) | 无上下文会话不可开 → 如实写"未执行"，不自测冒充 | 未执行 |
| 远端精确 SHA 的 CI | 无（本阶段不推送） | 功能分支未推送，Actions 未查询 | 未验证 |

**重要**：以上 S43 行只记录**执行窗口自测**，不替代 **S12 现场人工 GUI A–E 验收**（语义实验室、日志工作台、LWT Snake、S41 Tk 查看器、演示桌面无遮挡与输入归属），也不替代主窗口审查、合入 main、远端 CI 与教师线下验收。执行实现 / 主窗口审查 / 合入 main / 远端 CI / 现场人工 GUI 五项状态分别确认，不能由一项推断另一项。S43 阶段报告见 [s42-deterministic-concurrency.md](s42-deterministic-concurrency.md)。

## S44 可验证加速核对（执行窗口自测，基线未经主窗口复核）

| 课程抓手 / 任务书 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 启动惰性化 P0-1/P0-2 | `lwt/_sched_support.py`、`lwt/{runtime,cli,modules,concurrency}.py` | `tests/test_startup.py` 10 项：非 spawn 无 `lwt.concurrency`、spawn 仍工作、三开关/REPL 不回归；`--help` 1.256×、hello 1.224× | 执行实现完成，待复核 |
| 热路径 P0-3/P0-4 | `lwt/runtime.py`、`lwt/parser.py`、[`lwt/_decimal.py`](../lwt/_decimal.py) | `tests/test_dispatch_completeness.py` 9 项；纯执行 N=5000 1.454×/1.552×/2.992×；6000 位整数精度 | 执行实现完成 |
| 局部优化 P1 | [优化台账](s44-optimization-ledger.md) | P1-2 <2% 已回滚零残留；P1-4 保留；P1-1/P1-3 未做理由在台账 | 执行实现完成 |
| S11-v2 分层基准 | [`reports/s44-performance/benchmark-v2.md`](../reports/s44-performance/benchmark-v2.md)、`tools/benchmark_v2.py` | 126 次 oracle 全通过；端到端/纯执行分列；旧 S11 数据零改动 | 执行实现完成 |
| 门槛判定与覆盖闭环 | `tools/compare_perf.py`、`tools/check_project_integrity.py --require-all-referenced`、[矩阵](test-matrix.md) §4.5.3 | `compare_perf` 全 PASS；`referenced_cases=400/400; unreferenced=0` | 执行实现完成 |
| 全量回归与保护数据 | [S44 执行报告](s44-performance.md) | 400/400 黑盒、632 unittest、46×10 确定性、S28 事件计数；S11/S42/S43 保护数据差异空 | 执行实现完成 |
| Agent 盲测 pass@1 | 无（无法新开无上下文会话） | 如实写"未执行"，不把自测当盲测 | 未执行 |
| 远端精确 SHA 的 CI / Python 3.10 / Linux | 无（本阶段不推送） | 未在这些环境实测 | 未验证 |

**重要（S44）**：用户授权叠加在**未复核的 S43** 之上，本节只记录**执行窗口自测**，**不替代现场人工 GUI A–E 验收**，也不替代主窗口审查、合入 main、远端 CI 与教师线下验收。诊断工具严禁写入 `bench/results.json`、`reports/performance.md` 等 S11/S42/S43 固定证据；本阶段已加输出路径拒绝并核对保护路径差异为空。S44 阶段报告见 [s44-performance.md](s44-performance.md)。

## S45 最终交付加固核对（执行窗口自测；基线未经主窗口复核 S43/S44）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 版本与交付清单 | [`docs/delivery-manifest.json`](delivery-manifest.json) | 版本 0.3.0（主窗口裁决）；`lwt.__version__`、`--version`、规范标题、README 由 `tests/test_doc_consistency.py` 校验一致 | 执行实现完成 |
| CLI `--help`/`--version` | `lwt/cli.py`、[规范](language-spec.md) §6、[指南](developer-guide.md) | 二者 exit 0；无参数仍 CliError/4；`--` 后的 `--help` 属于程序实参；`tests/test_cli.py` 6 项 | 执行实现完成 |
| Agent 盲测 | [任务](agent-eval/tasks.json)、[协议](agent-eval/README.md)、`tools/run_agent_eval.py` | 6 题 + 客观判分器；参考解验证 ALL_PASS 后删除；正式盲测须用户新会话，当前 **NOT_RUN** | 未执行（不伪造 pass@1） |
| DAP 协议帧级 spawn 拒绝 | `tests/test_dap_spawn_rejection.py` | 真实 `python -m lwt.dap_server` 子进程；`Content-Length` 按 UTF-8 字节；exit 4；无 stopped/断点；无 stdout 泄漏 | 执行实现完成 |
| 一键验收自检包 | `tools/run_acceptance_selfcheck.py` | 一条命令跑 Git/保护路径/完整性/黑盒/确定性/性能门槛/文档一致性/PPT 静态检查，输出 `reports/s45-acceptance/selfcheck-*.{json,md}` | 执行实现完成 |
| 文档一致性 | `tests/test_doc_consistency.py` | 当前状态文档不含旧版本号、旧 unittest 计数、旧黑盒基数、旧 PPT 页数与「S12 未完成」类过期状态；历史报告 allowlist 豁免 | 执行实现完成 |
| PPT 最终对齐 | [`slides/LWT介绍.pptx`](../slides/LWT介绍.pptx) | 18 页；第 10 页原生图表 12 数值点未变；新 SHA `b8c15c03…` 记入 manifest | 执行实现完成 |
| Python 3.10 / Linux / CI | 无（3.10 未安装；Linux 仅 Actions） | 本机 3.11.16 与 3.13.x 实测；功能分支已推送并在报告记录精确 SHA 四格 | 见 S45 报告 |
| 现场人工 GUI A–E | 无 | 自检包打印清单，不自动化、不声称通过 | 未验证 |

**重要（S45）**：以上只记录**执行窗口自测**。用户明确授权叠加在**未复核的 S43/S44** 之上（S45 报告首段已粗体标注），因此本清单不替代主窗口审查、合入 main、教师线下验收与现场人工 GUI A–E。S45 报告见 [s45-final-hardening.md](s45-final-hardening.md)。

## S46 并发有界系统探索核对（执行窗口自测；基线未经主窗口复核 S43/S44/S45）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 工具 API | `lwt/concurrency.py`、`lwt/runtime.py` | `execute(..., schedule_choices=)` 仅工具使用；默认 None 时 400 黑盒/46×10 零变化；非法前缀 exit 4、无挂死、无线程泄漏 | 执行实现完成 |
| 模型检查器 | `tools/model_check_concurrency.py` | 前缀 BFS + 结果分类 + 贪心最小化 + `--schedule-replay` 复核；预算耗尽写 `BUDGET_EXHAUSTED` | 执行实现完成 |
| corpus 与不变量 | `tests/concurrency-model/`（8 程序 + `.model.json`） | 通道精确一次/FIFO/close 排空、join 错误重抛、死锁、后代收尾、`lost-update` 允许分歧；**不在** `tests/cases/`，黑盒仍 400 | 执行实现完成 |
| clean 探索 | `reports/s46-concurrency-model/summary.json` | 8 程序/32 runs/81 决策点/最大深度 6；violations=0、budget_exhausted=0、thread_leaks=0；8/8 `COMPLETE` | 执行实现完成 |
| mutant 自测 | `reports/s46-concurrency-model/mutant/` | `duplicate-delivery`：4 个通道程序各 1 违反；最小前缀 `[]`；harness 重放 `7\n7\n`；边界：合成故障注入，不是产品 bug | 执行实现完成 |
| 预算/非法前缀 | `tests/test_concurrency_model.py`（11 项） | `--max-runs 1` → `BUDGET_EXHAUSTED` 且退出 1；非法前缀 `choice 0: 99 not in ready [1, 2]`、exit 4、无线程 | 执行实现完成 |
| CI 步骤 | `.github/workflows/tests.yml` | 四格矩阵不变，新增 `--max-runs 300 --time-budget 90 --require-clean` 一步 | 执行实现完成（CI 结论见 S46 报告） |
| 一键自检 | `tools/run_acceptance_selfcheck.py` | 新增 `model_check` 步骤（`--model-budget`）；预算耗尽记 FAIL，不写 PASS | 执行实现完成 |
| PPT / manifest | `slides/LWT介绍.pptx`、`docs/delivery-manifest.json` | 19 页；旧第 10 页图表 12 数值点未变；SHA `44e9c8bd…`；unittest 664 | 执行实现完成 |
| 现场人工 GUI A–E | 无 | 不自动化、不声称通过 | 未验证 |

**重要（S46）**：以上只记录**执行窗口自测**；基线 S43/S44/S45 未经主窗口复核，本清单不替代主窗口审查、合入 main、远端 CI 与现场人工 GUI 验收。Agent 盲测仍为 `NOT_RUN`。S46 报告见 [s46-concurrency-verification.md](s46-concurrency-verification.md)。

## S47 提交可达性与盲测核对（执行窗口自测；基线未经主窗口复核 S43–S46）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 教师入口 | `SUBMISSION.md` | 8 项提交内容逐项列出分值/路径/一条命令/证据/状态；README 第一段链接到它 | 执行实现完成 |
| Agent 盲测 | `docs/s47-agent-eval.md`、`docs/agent-eval/submissions/`、`reports/s47-submission/agent-eval.{json,md}` | 6 题 × 6 个全新子代理会话 × 独立 worktree；首轮 5/6（pass@1=0.833），唯一失败为题面欠定；澄清后单题复跑通过（补充证据） | 已完成（n=1/题） |
| 判分器字段覆盖 | `tools/run_agent_eval.py`、`tests/test_agent_eval.py` | `stdin`/`args`/`check_required`/`deterministic_runs`/`forbidden_constructs`/pass@1 分母；7 项测试 | 执行实现完成 |
| 提交包 | `tools/build_submission.py`、`dist/lwt-submission-<UTC>/` | `SUBMISSION.md` + `lwt-history.bundle`（verify/list-heads）+ zip（`manifest.sha256` 自洽） | 执行实现完成 |
| 新克隆验证 | `tools/verify_fresh_clone.py`、`reports/s47-submission/fresh-clone.{json,md}` | 从 bundle 克隆到空目录，跑 version/check/400 黑盒/compileall/完整性，逐条记录退出码 | 执行实现完成 |
| main 收敛 | Git 历史 | B1：`main` FF 到本分支并普通推送；精确 SHA 与 CI 四格见 S47 报告 §6 | 见 S47 报告 |
| PPT / manifest | `slides/LWT介绍.pptx`、`docs/delivery-manifest.json` | 20 页；旧第 10 页图表 12 数值点未变；SHA 与 unittest 计数写入 manifest | 执行实现完成 |
| 现场人工 GUI A–E | 无 | 不自动化、不声称通过 | 未验证 |

**重要（S47）**：以上只记录**执行窗口自测**。基线 S43–S46 未经主窗口复核；本清单不替代主窗口审查、教师线下验收与现场人工 GUI。Agent 盲测为单样本，pass@1 不是统计显著结论。报告见 [s47-final-submission.md](s47-final-submission.md)。

## S48 证据自洽与现场验收就绪核对（执行窗口自测；基线未经主窗口复核 S43–S47）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| bundle 自引用 | `tools/build_submission.py`、`reports/s48-defense/package-index.json` | `--final-tip/--allow-ref-lag/--package-index`；bundle `76bb4fb`、最终 tip `dcb0b1e`、lag 仅索引文件；`verify_fresh_clone --package-index` 同时验证 X 与 Y | 执行实现完成 |
| 当前状态文档自洽 | `tests/test_doc_consistency.py`（16 项） | 语义断言：manifest 记录 EXECUTED 时不得再写 NOT_RUN 为当前结论；交付面不得出现过期的分支状态表述；submission_bundle 指向入库索引；先红后绿 | 执行实现完成 |
| 指南消融 + 盲测 | `docs/s48-agent-eval.md`、`reports/s48-defense/ablation.*`、`docs/agent-eval/submissions-v2/` | 60 个独立会话：T 30/30（Wilson 0.886–1.000）、C 29/30（0.833–0.995）；T−C=+0.033 [−0.031,+0.098]；未触发指南修订 | 执行实现完成 |
| GUI A–E 验收包 | `docs/gui-acceptance-kit.md`、`tools/register_gui_evidence.py`、`evidence/gui/` | 只登记材料与 SHA-256，不自动判 PASS；当前 REGISTERED 0/5 | 工具完成，人工 NOT_RUN |
| 可质询证据台 | `docs/defense-claims.json`（24 条）、`tools/run_defense_probe.py`、`docs/defense-index.html` | `--claim/--random/--all` 真实子进程；非 heavy 21/21 PASS；HTML 离线可开 | 执行实现完成 |
| PPT / manifest | `slides/LWT介绍.pptx`、`docs/delivery-manifest.json` | 21 页；第 10 页图表 12 数值点未变；SHA `0be34afa…`；unittest 685 | 执行实现完成 |
| 现场人工 GUI | 无 | 不自动化、不声称通过 | 未验证 |

**重要（S48）**：以上只记录执行窗口自测；S43–S47 未经主窗口复核，本清单不替代主窗口审查、教师线下验收与现场人工 GUI。S48 报告见 [s48-defense-readiness.md](s48-defense-readiness.md)。

## S49 答辩彩排与一致性收敛核对（执行窗口自测；基线未经主窗口复核 S43–S48）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 21 页逐页讲稿 | `docs/defense-runbook.md`、`docs/defense-pages.json` | 每页含口播要点、追问与一句话回答、断言 ID、现场命令与降级证据；`tests/test_delivery_readiness.py` 校验 21 页齐全且断言 ID 有效 | 执行实现完成 |
| 随机质询彩排 | `tools/rehearse_defense.py`、`reports/s49-rehearsal/` | `--pages/--random/--dry-run/--offline/--timeout`；随机 5 条真实执行并留 JSON+MD；彩排 ≠ 教师验收 | 执行实现完成 |
| 文档一致性 | `tests/test_doc_consistency.py`（27 项） | manifest 单一来源（unittest/黑盒/页数）、S44–S48 旧计数与旧页数扫描、推送状态正反向、证据路径可达；先红后绿 | 执行实现完成 |
| CI 四格 | `reports/s49-rehearsal/ci-cells.json` | 按 `724dc7c`/`446ed4d`/`0df0e40` 逐格记录 OS × Python、结论、耗时；`724dc7c` 四格失败（文档一致性抓到过期表述） | 执行实现完成 |
| 包索引复核 | `tools/check_package_lag.py`、`reports/s49-rehearsal/package-lag*.json` | 以 `git diff --name-only X..HEAD` 重算并分类；S48 索引对 0df0e40 有 1 个白名单外文件，S49 重建后 outside=0 | 执行实现完成 |
| GUI A–E 双轨 | `docs/gui-acceptance-quickref.md`、`tools/register_gui_evidence.py` | 一页纸速查 + CLI 降级轨；登记仍为 `REGISTERED 0/5`，不自动判 PASS | 工具完成，人工 NOT_RUN |
| PPT / manifest | `slides/LWT介绍.pptx`、`docs/delivery-manifest.json` | 21 页；第 18–21 页仅改页脚状态文案；第 10 页图表 12 数值点未变；SHA `0be34afa…`→`7cb28b13…` | 执行实现完成 |
| 现场人工 GUI A–E | 无 | 不自动化、不声称通过 | 未验证 |

**重要（S49）**：以上只记录执行窗口自测与本地彩排；S43–S48 未经主窗口复核，本清单不替代主窗口审查、教师线下验收与现场人工 GUI。报告见 [s49-defense-rehearsal.md](s49-defense-rehearsal.md)。

## S50 单命令 unittest 红线清零（执行窗口自测；基线未经主窗口复核 S43–S49）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 根因对照实验 | `reports/s50-closeout/unittest-interpreter-root-cause.json` | 同一命令两种解释器：无 Tk 的 3.13.14 → 711 项 + 2 个 tkinter 失败；`py -3.13`（3.13.7+Tk 8.6）→ 713 OK；日志 SHA-256 双份核对 | 主窗口实测 |
| 断言解释器口径 | `docs/defense-claims.json` | `requires.tkinter` + `import tkinter` 前置检查 + 单命令工具；探针解析 Tk 解释器并记录 `sys.executable`/`TkVersion` | 执行实现完成 |
| 固化测试 | `tests/test_unittest_claim.py` | 6 项：断言声明、非两批口径、探针解析/替换、证据字段、S49 历史保留与 S50 修正段 | 6/6 通过 |
| 探针 | `reports/s50-closeout/defense-probe-merge.json` | 以 S49 的 24 行为底稿，只重跑 `unittest` 并合并；`719` 项 `OK`、`exit 0`、`717.5 s` | **24/24 PASS** |
| 一键自检 | `reports/s50-closeout/selfcheck/` | `git/protected_diff/integrity/blackbox/determinism/compare_perf/doc_consistency/ppt/model_check/submission/defense_probe` 全 PASS；GUI/agent N/A | **all_pass=true**（11 PASS / 2 N/A / 0 FAIL） |
| CI 四格 | `reports/s49-rehearsal/ci-cells.json` | `f3e209c`（run 42844502753）逐 job：ubuntu 3.10 7m47s、ubuntu 3.13 5m46s、windows 3.10 9m13s、windows 3.13 8m39s，4 succeeded | 4/4 通过 |
| PPT | `slides/LWT介绍.pptx` | 本阶段不改内容；21 页、第 10 页图表 12 数值点、SHA `7cb28b13…` 静态校验 | 未改动 |
| 现场人工 GUI A–E | 无 | 用户本人稍后执行；登记前保持 `REGISTERED 0/5`、`NOT_RUN` | 未验证 |

**重要（S50）**：以上为执行窗口自测；不替代主窗口复核、教师线下验收与现场人工 GUI。报告见 [s50-closeout.md](s50-closeout.md)。

## S51 教师第一屏一致性与现场预案（执行窗口自测；基线未经主窗口复核 S43–S50）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 当前状态硬伤 | `README.md`、`project.md`、`docs/language-spec.md` | 旧计数、过期分支状态、过期核对日期全部消除；S44 与 S49/S50 数字标为历史 | 已修 |
| 日期豁免收紧 | `tests/test_doc_consistency.py` | `CURRENT_CLAIM_RE` 当前状态断言优先于日期；先红 4 项后 28/28 绿 | 28/28 |
| 教师第一屏 | `README.md` 前 6 行、`SUBMISSION.md` 前 8 行、`checklist` S50 段 | 400 / 721 / 21 与 manifest 一致；解释器陷阱写入教师入口 | 固化通过 |
| 现场预案 | `docs/onsite-runbook.md` | 60–90 分钟编排、5 条必跑命令 + 预期 + 降级路径、追问断言索引 | 工具就绪 |
| 彩排 | `reports/s51-closeout/rehearsal-s51.json` | `--random 5 --seed 51`：4 PASS + 1 TIMEOUT（heavy `determinism`，60 s 盒） | 如实记录 |
| PPT 静态边界 | `reports/s51-closeout/ppt-static.json` | 21 页 / 12 数值点 / SHA `7cb28b13…` / zip 完整；`render_check=false` | 静态通过，未渲染 |
| 现场人工 GUI A–E | 无 | 本轮不执行，保持 `REGISTERED 0/5`、`NOT_RUN` | 未验证 |

**重要（S51）**：以上为执行窗口自测；不替代主窗口复核、教师线下验收与现场人工 GUI。报告见 [s51-first-screen.md](s51-first-screen.md)。

## S52 课程口径覆盖与性能维度（执行窗口自测；基线未经主窗口复核 S43–S51）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| §8 覆盖矩阵 | `docs/test-matrix.md` | §8.1–8.8 逐行列真实用例；§9/§10/§11 补到小节级；§8.6/§11.9 标设计决策 | 完成 |
| 覆盖门禁 | `tests/test_course_coverage_matrix.py` | 先红 20 缺口后 5/5；`VALID_SPEC_REFS` 注册 16 个新小节；runner 35/35；**S52 当时** 400 黑盒 / 731 unittest / 21 页 | 完成 |
| 用 LWT 测试 LWT | `README.md`、`docs/test-matrix.md`、`SUBMISSION.md` | 426 个 `*.lwt` / 400 JSON；runner 只驱动公开 CLI；测试固化 | 完成 |
| 性能补充 | `reports/s52-course-align/performance-space.{json,md}` | P50/P95/P99 + peak_bytes + 压力 N=1000/5000/20000；S11/S44 零改动 | 完成（Ubuntu RSS 未验证） |
| 课件口径 | `docs/s52-course-alignment.md`、答辩卡 +4 问、SUBMISSION 任务表 | 第 8 章任务 1–5 / 提交 8 项 / 评分 5 项逐条对照；11/17 窗口提醒 | 完成 |
| 现场人工 GUI A–E | 无 | 本轮不执行，保持 `REGISTERED 0/5`、`NOT_RUN` | 未验证 |

**重要（S52）**：以上为执行窗口自测；不替代主窗口复核、教师线下验收与现场人工 GUI。报告见 [s52-course-alignment.md](s52-course-alignment.md)。

## S53 变异探针、接口对照与提交链路（执行窗口自测；基线未经主窗口复核 S43–S52）

| 交付项 | 仓库位置 | 本轮检查方式 | 状态 |
|---|---|---|---|
| 变异探针 | `tools/audit_semantic_mutants.py`、`reports/s53-mutation/mutation-report.json` | 18 条（S42/S43 新增 9 条）；killed **18**、invalid **0**；每条有 `patch_sha256` 与 `killed_by` | 18/18 |
| 隔离与还原 | `reports/s53-mutation/mutation-report.json` | 只在 `TemporaryDirectory` 副本打补丁；运行前后 `git status --porcelain` 为空 | `repo_clean=true` |
| 诚实边界 | `reports/s53-mutation/probe-inventory.md` | 三个“目标用例单独不判别”的弱用例 + 一个真实盲区（按 key 排序的显示变异存活） | 已记录 |
| Agent 友好接口 | `docs/agent-friendly-interface.md` | 课件 4.4/4.5 逐条对照，每条给复算命令；`--fields`/`--debug` 标注未实现 | 完成 |
| MCP | `lwt/mcp_server.py`、`tests/test_mcp_server.py` | 行分隔 JSON-RPC 2.0；`initialize`/`tools/list`/`tools/call`；协议级 **8/8** | 已实现，未做宿主端到端 |
| 平台提交清单 | `docs/platform-submission.md`、`tools/check_platform_bundle.py` | 文件存在 + SHA 一致 +（可选）解压后 400 黑盒；`uploaded=false` | 工具通过，未上传 |
| 当前计数 | `docs/delivery-manifest.json` | **400 黑盒 / 747 unittest / 21 页**；S52 报告保留 731 作为冻结快照 | 已同步 |
| 现场人工 GUI A–E | 无 | 本轮不执行，保持 `REGISTERED 0/5`、`NOT_RUN` | 未验证 |

**重要（S53）**：以上为执行窗口自测；不替代主窗口复核、教师线下验收与现场人工 GUI。变异分数不是总体正确率。报告见 [s53-mutation-interface.md](s53-mutation-interface.md)。

