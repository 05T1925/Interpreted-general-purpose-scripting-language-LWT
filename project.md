# LWT 项目上下文

> Agent 当前状态入口。核对日期：2026-11-11。每次开始任务都重新检查 Git 和远端；阶段历史见[仓库工作流](docs/repository-workflow.md)，当前关系见[阶段路线图](阶段执行与审查路线图.md)。

> **当前结论：** S12 已经[主窗口复核](docs/s12-main-review.md)，候选 SHA `e1249f56f1d889c0c6e400a46602e0fe3f7df1ce` 已快进集成到本地 `main`，该精确 SHA 的远端 Actions 四格成功。PPT、交付审计和答辩材料见[S12 执行报告](docs/s12-final-delivery.md)。现场人工 GUI 验收仍未完成；没有据此声称教师验收或最终评分通过。

> **S42（2026-11-07，执行窗口）：** 以 `main = 5027860efc8a1cce342ca13b1434d7724aeeffc4` 为基线，在 `feature/lwt-core-0.2` 分支承接并收尾 LWT 0.2 语言核心增强：dict 映射、throw/finally、交互 REPL、单进程运行时画像，以及 log_report.lwt 的 dict 计数改造（输出字节不变）。基线黑盒 330/330；新增 24 个 throw/finally 黑盒后全量 **354/354**，完整性 `cases=354; matrix_links=401; referenced_cases=304`。执行窗口报告见[S42 执行报告](docs/s42-execution-report.md)。该分支**不推送、不合并、不打标签**；最终 SHA 的 Actions、Python 3.10/Linux 与现场人工 GUI 均为未验证。基线裁决理由（含 `milestone/final-acceptance` 独立文档线）见 S42 报告 §1.1。

> **S43（2026-11-07，执行窗口，任务书编号 S42 确定性并发）：** 用户裁决"叠加在语言核心之上，记为 S43"，从 `feature/lwt-core-0.2 @ a996591` 创建 `feature/deterministic-concurrency`，为 LWT 增加**协作式确定性可重放并发子语言**（`spawn`/`join`/`yield()`/通道，规范 §11）：单令牌 Event 调度、fifo/random:SEED、轨迹绑定与重放篡改拒绝、死锁检测、read_text I/O 批次屏障、46 项并发黑盒 + 19 单测、233 行并发应用（与 log_report 差分等价）、found/absent/tampered 三态证据、诚实 I/O 重叠性能实验、PPT 12→15 页（旧图表 12 数值点未变）。全量黑盒 **400/400**，完整性 `cases=400; matrix_links=445; referenced_cases=348`，确定性 46×10 全稳定。执行窗口报告见 [S43 报告](docs/s42-deterministic-concurrency.md)、[并发契约卡](docs/concurrency.md)、[三态证据](reports/s42-schedules/summary.md)。**不推送、不合并、不打标签**；最终 SHA 的 Actions、Python 3.10/Linux、DAP 协议帧、Agent 盲测与现场人工 GUI 均为未验证。

> **S44（2026-11-07，执行窗口，LWT 执行引擎「可验证加速」）：** 用户**明确授权叠加在未复核的 S43 上**（报告首段已粗体标注「基线未经主窗口复核」），从 `feature/deterministic-concurrency @ 344c255` 创建 `feature/engine-performance`。不改规范 §1–§11 可观察语义、400 项黑盒、46×10 并发确定性，完成：启动惰性化（非 spawn 程序 `sys.modules` 无 `lwt.concurrency`）、精确类型分派 + 运算符集合常量化、INT 字面量解析期预解码、小整数显示快路径；P1-2 实测 <2% 已回滚。同机 A/B：启动 `--help` 624→497 ms（**1.256×**）、hello 611→500 ms（**1.224×**）；纯执行 execute N=5000 三负载 **1.454×/1.552×/2.992×**；S11-v2 分层基准 126 次 oracle 全通过、端到端 LWT/Python 1.48–1.79×（仍慢，口径分开）。覆盖矩阵补 52 个未链接用例至 `referenced_cases=400/400; unreferenced=0`，新增 `--require-all-referenced`。全量黑盒 **400/400**、unittest **632/632**、确定性 46×10 稳定、S28 事件计数不变、保护数据零改动；PPT 15→17 页（旧图表 12 数值点未变，SHA `cb309365…`→`2b0d1df3…`）。执行窗口报告见 [S44 报告](docs/s44-performance.md)、[性能计划](docs/s44-performance-plan.md)、[优化台账](docs/s44-optimization-ledger.md)、[S11-v2 基准](reports/s44-performance/benchmark-v2.md)。**不推送、不合并、不打标签**；最终 SHA 的 Actions、Python 3.10/Linux、Agent 盲测与现场人工 GUI 均为未验证。

> **S45（2026-11-08，执行窗口，最终交付加固与 Agent 能力实证）：** 用户**明确授权叠加在未复核的 S43/S44 上**（S45 报告首段粗体标注），从 `feature/engine-performance @ f21f474` 创建 `feature/delivery-hardening`。主窗口裁决版本 **0.3.0**，写入 `docs/delivery-manifest.json`；新增 `tests/test_doc_consistency.py` 校验当前状态文档与 manifest 一致（历史报告 allowlist 豁免）。新增 CLI `-h/--help/--version`（exit 0，不执行源码；无参数仍 CliError/4）；`docs/agent-eval/` 6 题 + `tools/run_agent_eval.py` 客观判分器（正式盲测 **NOT_RUN**，不伪造 pass@1）；`tests/test_dap_spawn_rejection.py` 帧级 spawn 拒绝（UTF-8 Content-Length、exit 4、无 stopped、无 stdout 泄漏）；`tools/run_acceptance_selfcheck.py` 一键自检包（`reports/s45-acceptance/`）。**发现并修复真实缺陷**：`send` 向阻塞接收者重复投递同一值（违反 §11.5），修复后 400/400、46×10 稳定、并发单测 21/21。PPT 17→18 页（旧图表 12 点未变，SHA `2b0d1df3…`→`b8c15c03…`）。全量黑盒 **400/400**、unittest 见 S45 报告、确定性 46×10 稳定、保护数据零改动。执行窗口报告见 [S45 报告](docs/s45-final-hardening.md)。**不推送 main、不合并、不打标签**；功能分支按用户授权推送，CI 四格结论单独记录；Python 3.10 未安装、现场人工 GUI 未验证。

> **S46（2026-11-09，执行窗口，并发有界系统探索与反例最小化）：** 用户指示"先复核 S45，再进入 S46"；执行窗口复核 S45（保护数据零 diff、通道修复 `7`→`null`、653 单测、文档一致性 11/11、PPT 18 页/图表 12 点/SHA 一致）后，从 `feature/delivery-hardening @ 252122c` 创建 `feature/concurrency-model-check`。新增工具 API `execute(..., schedule_choices=)`（仅工具使用，非法前缀 exit 4、无挂死）与 `tools/model_check_concurrency.py`：对 8 个小型并发程序的调度选择树做**有界**系统化探索（前缀 BFS、结果分类、贪心最小化、`--schedule-replay` 复核）。clean corpus：8 程序/32 runs/81 决策点/0 violation，8/8 `COMPLETE`；`lost-update` 的 `1`/`2` 两种结果记为 `allowed_outcomes` 并各有可重放 witness。`--mutant duplicate-delivery` 复现 S45 缺陷：4 个通道程序各 1 违反、最小前缀 `[]`、harness 重放 `7\n7\n`；预算耗尽写 `BUDGET_EXHAUSTED`（`--max-runs 1` → 退出 1，绝不写 PASS）。CI 增加模型检查步骤；自检包增加 `model_check`；PPT 18→19 页（旧图表 12 点未变，SHA `b8c15c03…`→`44e9c8bd…`）。全量黑盒 **400/400**、unittest **664/664**、确定性 46×10 稳定、保护数据零改动。报告见 [S46 验证报告](docs/s46-concurrency-verification.md)、[模型检查说明](docs/concurrency-model-check.md)。**不推送 main、不合并、不打标签**；功能分支推送按用户授权，CI 四格按精确 SHA 单独记录；Agent 盲测仍 NOT_RUN、现场人工 GUI 未验证。

> **S48（2026-11-10，执行窗口，证据链自洽与现场验收就绪）：** 按裁决 A 在 `main` 工作、B1 冻结题面 v2 做 T/C 消融、C 由用户本人执行 GUI、D 授权推送。WP0 三处 P0：bundle 自引用用 `package-index.json` 显式声明（X=`76bb4fb`、Y=`dcb0b1e`、lag 仅索引）；`tests/test_doc_consistency.py` 新增语义断言并先红后绿；SUBMISSION 第 7 项指向入库索引。WP1：60 个独立会话，T 30/30=1.000（Wilson 0.886–1.000）、C 29/30=0.967（0.833–0.995），T−C=+0.033 [−0.031,+0.098]，唯一失败为输出格式，未触发指南修订。WP2：GUI A–E 验收包 + 登记工具（当前 REGISTERED 0/5、NOT_RUN）。WP3：24 条断言 + 现场探针（非 heavy 21/21 PASS）+ 离线 HTML。PPT 20→21 页（旧图表 12 点未变，SHA `90369685…`→`0be34afa…`）；unittest 685。全量黑盒 400/400、46×10 稳定、保护数据零改动。报告见 [S48 报告](docs/s48-defense-readiness.md)、[S48 盲测](docs/s48-agent-eval.md)。**未验证**：现场人工 GUI、教师线下验收；盲测为观察性、区间含 0。

> **S49（2026-11-10，执行窗口，答辩彩排与验收一致性收敛）：** 裁决 A 从 `0df0e40` 建 `feature/defense-rehearsal`、B 授权推送并查四格、C 由用户本人执行 GUI（本轮未执行，保持 `REGISTERED 0/5`）。WP0：重算包索引 lag，发现 `docs/demo-script.md` 在白名单外（退出 1），S48 报告加日期化复核段；CI 四格按 `724dc7c`/`446ed4d`/`0df0e40` 逐 job 解析——**`724dc7c` 四格失败**（文档一致性抓到过期分支状态），后两者四格通过；清理 60 个 `lwt-s48-*` worktree（116.5 MB，0 失败，剩 5 条）。WP1：文档一致性 16→27 项，先红 5 项后转绿；行级段豁免经“禁用后命中 8 行”反证必要。WP2：21 页逐页讲稿 `docs/defense-runbook.md` + 映射 `docs/defense-pages.json`；`tools/rehearse_defense.py` 实跑随机 5 条 5/5、第 1–5 页 6/6，另有 dry-run/offline 32 条证据。WP3：`docs/gui-acceptance-quickref.md` 一页纸 + CLI 降级轨（Snake 协议回放已实跑一致），GUI 仍 NOT_RUN。PPT 21 页只改第 18–21 页页脚状态文案（`0be34afa…`→`7cb28b13…`，第 10 页图表 12 点未变）；unittest 713。报告见 [S49 报告](docs/s49-defense-rehearsal.md)。**未验证**：现场人工 GUI、教师验收、PPT 页脚渲染效果。

> **S50（2026-11-11，执行窗口，单命令 unittest 红线清零）：** 根因是解释器选择，不是环境时序——`python` 指向无 tkinter 的 3.13.14，GUI 模块无法导入，只跑 711 项；系统 `py -3.13`（3.13.7 + Tk 8.6）同命令 **719 项 OK（717.5 s）**。断言改为 `requires.tkinter` + 前置检查 + `tools/run_unittest_single.py`，探针解析并记录 `sys.executable`/`TkVersion`；探针 **24/24**，自检 **all_pass=true**（11 PASS / 2 N/A / 0 FAIL），`f3e209c` 四格全绿。S49 的四次 FAIL 历史保留，只追加根因修正段。**未验证**：现场人工 GUI A–E、教师验收、PPT 页脚渲染。报告见 [S50 报告](docs/s50-closeout.md)。

> **S51–S54（2026-11-11，执行窗口，按课件口径收尾）：** 四阶段主题依次为——**S51 教师第一屏一致性**（修 `README.md` 的自称"当前状态（S44）"却写 632 项/未推送/未复核、阶段列表漏项、`project.md` 核对日期过期；把 `test_doc_consistency` 的"日期即历史"豁免收紧为"当前状态断言优先"，先红 4 项后转绿；补 `docs/onsite-runbook.md` 现场预案与 PPT 静态校验边界）；**S52 第 8 章覆盖与性能维度**（补 `test-matrix` 的 `### §8` 全表与 20 个零 `spec_refs` 小节映射 + 门禁测试；新增 `tools/measure_memory_profile.py` 测 P95/P99 与峰值内存，array_scan 51→208 KB、压力扫描 72→200→690 KB 单调，S11/S44 冻结文件零 diff；课件 4.4/5.5/第 8 章口径进答辩卡）；**S53 变异探针与 Agent 接口**（`audit_semantic_mutants.py` 从 9 条扩到 18 条并修复 1 条因 S42 改动失效的锚点，18/18 killed；`docs/agent-friendly-interface.md` 按课件 4.4 逐条对照 CLI 设计；`lwt/mcp_server.py` 标准库 JSON-RPC 2.0 协议级实现 8/8；`docs/platform-submission.*` + `check_platform_bundle.py`，解压后 400/400，`uploaded=false`）；**S54 PPT 真渲染与键序盲区闭环**（`tools/render_ppt.py` 用 PowerPoint COM 只读渲染 **21/21 页、0 空白**、PDF 395,794 B、第 10 页方差/墨迹比/饱和度三项第一且有 12 个数值点 XML 交叉校验，消掉连续五阶段的"未渲染"遗留；新增 `dict-display-insertion-order` 用例使"S53 自曝的 dict 键序盲区"闭环，黑盒 400→**401**、变异探针 18→**19 全杀**、PPT 四页文案 400→401 并重渲染，SHA `7cb28b13…`→`809320b2…`；`tools/gui_preflight.py` 只读启动预检 4/4 窗口出现）。总门槛：**401 黑盒 / 752 unittest（`py -3.13` + Tk 8.6）/ 19 条探针全杀 / 自检 all_pass（11 PASS、2 N/A）/ 文档一致性全绿 / 保护路径零 diff**。报告见 [S51](docs/s51-first-screen.md)、[S52](docs/s52-course-alignment.md)、[S53](docs/s53-mutation-interface.md)、[S54](docs/s54-closeout.md)。**未验证**：现场人工 GUI A–E（`REGISTERED 0/5`、`NOT_RUN`）、逐页目视排版、教师线下验收与评分、教学云平台上传（`uploaded=false`）。

> **S55（2026-11-12，执行窗口，用 LWT 测试 LWT 与功能清单逐项打勾）：** 复核课程第 8 章后发现两处口径缺口并补齐——① 仓库原有 427 个黑盒 `.lwt` 程序，但**断言在 Python 侧比对期望输出**，没有课程示例那种"用 LWT 写 `expect`、逐项打印 `[PASS]`、末尾给总数"的原生自测；② 覆盖矩阵映射的是规范小节，**没有"功能清单逐项打勾"**。新增 `tests/selftest/lwt_selftest.lwt`（38 项，`fn expect` 由 LWT 实现，覆盖任务 1 五项基本功能 + dict/错误恢复/模块/并发/通道/字符串工具等特色功能）与 `tests/selftest/selftest_helper.lwt`（模块导入项），一条命令 `python tools/run_selftest.py` 输出 38 行 `[PASS]` 与 `38/38 全部通过`，并写 `reports/s55-selftest/selftest.{json,md}`；新增 `docs/feature-checklist.md` 用两张表（五项基本功能 22 行、特色功能 18 行）把每个功能项对应到自测项名字、黑盒用例与规范节并逐项打勾；新增 `tests/test_lwt_selftest.py` 6 项门禁（必须全绿、名字唯一、清单存在且 ≥30 行打勾、脚本不得出现宿主语言痕迹、工具拒绝把黑盒用例当自测脚本、工具必须写出证据）。黑盒 401 与 §1–§11 覆盖不变；unittest 752→**758**（新增 6 项）；`docs/delivery-manifest.json` 增 `evidence.s55_*`，`unittest_count=758`；README 阶段列表与当前状态、答辩卡、演示脚本、最终清单同步。**未验证**：现场人工 GUI A–E、逐页目视排版、教师线下验收与评分、教学云平台上传。

## 目标与课程评分

依据[作业原文](大作业内容.md)，交付 LWT 解释型通用脚本语言及解释器、完整黑盒测试、LWT/Python 性能比较、人类与 Agent 开发指南、至少 200 行的 Agent 编写 LWT 应用及开发记录、Git 历史、介绍 PPT 和线下答辩。评分为解释器 20、测试 20、性能 10、指南 20、LWT 应用 30 分。

课程应用包括 app/log_report.lwt（S42 dict 计数改造后 243 行有效 LWT，输出字节不变）以及 app/lwt_snake/game.lwt（313 行有效 LWT）。Python/Tkinter 前端、原 Python 贪吃蛇和编辑器插件是展示/开发工具；LWT Snake 的 Python 部分负责桥接、回放控制与绘图，规则仍由 LWT 计算。

## 当前 Git 快照

S31 的原始执行窗口位于 `stage/s31-vscode-extension`，最终提交为 `d2571540f50323d0e9be597caeb82575b2df6bcf`。复核后以保留两侧历史的正常合并集成到 `feature/editor-integration`，合并提交为 `ddf1759fa4239eabc15488730917daec990da390`；S31 原有三个实现/测试/报告提交均仍在祖先历史。

S32 从 `ddf1759fa4239eabc15488730917daec990da390` 开始，在 `feature/editor-integration` 完成；最终实现 SHA `236d94f92f402d0ef50333e518e6167711960b8b` 已经主窗口复核并快进进入本地 `main`。S32 执行窗口曾遇 Schannel TLS 握手失败；主窗口网络恢复时已正常推送功能分支，并核实精确 SHA 的 Actions 四格成功。远端 `main` 后续状态仍要实时查询。见 [执行报告](docs/s32-native-dap.md)及[主窗口复核](docs/s32-main-review.md)。

S0–S30 已在 main 的历史中；S23–S30 是按用户授权纳入本地主线，但其阶段报告保留当时状态，不能只凭祖先关系宣称各阶段都曾单独审查。当前聚合回归和历史审查范围见[仓库工作流](docs/repository-workflow.md)及[S31 主窗口复核](docs/s31-main-review.md)。

## 远端 CI 快照

2026-10-31 基线 `f9db64d` 的 Actions run 41183683056 四格成功。S31 集成提交 `ddf1759` 的 [run 41190959253](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41190959253) 四格成功；S32 精确提交 `236d94f` 的 [run 41200279217](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41200279217) 也四格成功。S41 审查修正提交 `10e6a82` 的 [run 41481213153](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41481213153) 四格成功。push 和 Actions 结论分开记录；本次状态文档提交的 CI 需另行核对。此前 42695ea、c2228d3、e9d3f10 上的红叉是 unittest 失败；跨平台测试断言在 f9db64d 修正。

## 阶段状态

- S0–S30：提交在 main；各阶段的范围和证据索引见[阶段路线图](阶段执行与审查路线图.md)。S23–S30 的历史状态文字不等同于本次逐阶段独立审计。
- S31：VS Code 扩展已通过主窗口复核（带明确未验证项），保留原提交并集成到 main；合并提交 `ddf1759fa4239eabc15488730917daec990da390`。人工 VSIX 安装/完整桌面操作和依赖线上 advisory 复核仍未验证。历史审查见[S31 主窗口复核](docs/s31-main-review.md)。
- S32：原生 DAP 已通过主窗口复核、快进进入本地 `main`；精确提交的远端 CI 四格成功。执行窗口报告黑盒 287/287、全量 unittest 442 项；主窗口复跑 DAP 与 S30 定向 49 项及 VS Code Node 11 项／Extension Host 4 项。人工 VSIX 安装和桌面调试 UI 未执行。详见[执行报告](docs/s32-native-dap.md)与[审查记录](docs/s32-main-review.md)。
- S33：黑盒 runner 选择与 UTF-8/Base64 JSON 契约、VS Code Test Explorer Run/Debug profile 已通过主窗口复核并集成到本地 `main`；修复批量错误终态，精确功能分支 SHA 的远端 CI 四格通过。人工鼠标/键盘编辑器验收仍未验证。详见[主窗口复核](docs/s33-main-review.md)及[执行报告](docs/s33-testing-workbench.md)。
- S34：LWT Snake 已合入本地 `main`；原主窗口发现的时钟饿死和失焦问题均在 S35 修复，复现及修复证据见[两轮审查](docs/s35-main-review.md)。
- S35：可验证回放和接管已通过主窗口复核、合入本地 `main`，功能分支精确 SHA 的远端 CI 四格成功。格式见[回放契约](docs/snake-replay-format.md)；人工桌面操作仍未验证。
- S36：LWT 策略助手、提示与串行自动驾驶已通过主窗口复核、合入本地 `main`；功能分支精确提交的 CI 四格成功。见[审查记录](docs/s36-main-review.md)、[冻结协议](docs/snake-strategy-protocol.md)和[执行报告](docs/s36-strategy.md)。
- S37/S38：双策略擂台、v2 游戏与决策双层验真、逐步解释已通过[联合复审](docs/s37-s38-main-review.md)并合入本地 `main`；精确功能分支的 CI 四格通过。旧 v1 只可 game-only。见[执行报告](docs/s37-arena.md)、[S38 报告](docs/s38-policy-proof.md)。
- S39：可信本地策略目录、独立 Agent 新 LWT 策略与 v3 双层验真已通过[主窗口复核](docs/s39-main-review.md)，功能分支精确提交的远端 CI 四格成功；见[报告](docs/s39-strategy-workshop.md)和[SDK](docs/strategy-sdk.md)。
- S40：可验证的多策略同局面比较与单步反事实实验已通过[主窗口复核](docs/s40-main-review.md)并进入本地 main；精确功能分支 CI 四格成功；见[契约](docs/s40-counterfactual-contract.md)和[执行报告](docs/s40-counterfactual-lab.md)。
- S41：Agent 策略差异自动发现与可复现反馈已通过[主窗口复核](docs/s41-main-review.md)并进入本地 main；原始执行证据见[报告](docs/s41-witness-discovery.md)。
- S12：候选 `e1249f56f1d889c0c6e400a46602e0fe3f7df1ce` 已通过主窗口复核并快进集成到本地 `main`；候选精确 SHA 的 Actions 四格成功。现场人工 GUI 验收保留为未完成项，详见[S12 主窗口复核](docs/s12-main-review.md)和[执行报告](docs/s12-final-delivery.md)。

## 常用验证入口

- 版本/帮助：python -m lwt --version；python -m lwt --help
- 普通 LWT 程序：python -m lwt examples/guide/hello.lwt
- 静态检查：python -m lwt --check examples/modules/main.lwt
- 黑盒：python tools/run_tests.py
- 完整性：python tools/check_project_integrity.py
- Python 全量：python -m unittest discover -s tests -q
- VS Code 扩展：进入 editors/vscode-lwt 后执行 npm ci 与 npm test；Extension Host 需要设置 VSCODE_EXECUTABLE_PATH 指向 Code.exe。
- Agent LWT 应用：python -m lwt app/log_report.lwt -- app/fixtures/sample.log
- 并发 LWT 应用：python -m lwt app/concurrent_log_report.lwt -- app/fixtures/sample.log app/fixtures/showcase.log
- 并发确定性 10×：python tools/run_concurrency_determinism.py --repeat 10
- 调度探索：python tools/explore_lwt_schedules.py --program tests/cases/concurrency/race-lost-update.lwt --seeds 1..200 --out reports/s42-schedules/found/lost-update
- 并发性能实验：python tools/run_concurrency_benchmark.py --files 8 --size-mb 2 --repeats 7
- S44 启动 A/B：python tools/measure_startup.py --out reports/s44-performance/before/startup.json --repeats 10 --warmups 2
- S44 纯执行 A/B：python tools/micro_bench.py --out reports/s44-performance/before --repeats 7 --warmups 2
- S44 门槛判定：python tools/compare_perf.py（只读 before/after JSON，启动+纯执行全 PASS 退 0）
- S44 S11-v2 分层基准：python tools/benchmark_v2.py --sizes 100,1000,5000 --repeats 7 --warmups 2
- S44 覆盖闭环：python tools/check_project_integrity.py --require-all-referenced（应 unreferenced=0）
- 有效 LWT 行数：python tools/count_lwt_lines.py app/log_report.lwt（并发应用：app/concurrent_log_report.lwt）

语言开发工具边界见[正式规范](docs/language-spec.md)、[静态检查](docs/static-checker.md)、[Language Server](docs/language-server.md)、[调试器](docs/debugger.md)、[VS Code 扩展](docs/vscode-extension.md)和[S33 测试工作台报告](docs/s33-testing-workbench.md)。发生冲突时以作业原文、正式语义和当前实测证据为准。
