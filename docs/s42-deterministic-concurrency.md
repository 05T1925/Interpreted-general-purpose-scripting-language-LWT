# S43 执行报告：LWT 确定性可重放并发

> 任务书编号为 S42「确定性并发」；用户裁决本阶段记为 **S43**，并叠加在 S42 语言核心增强（`feature/lwt-core-0.2`）之上。文件名沿用任务书验收清单的 `s42-*` 前缀。本报告是**执行窗口**报告；按任务书边界，本阶段**不推送、不合并、不打标签**，交主窗口复核。状态分层：执行实现 / 主窗口审查 / 合入 main / 远端 CI / 现场人工 GUI 验收分别记录，不能由一个推断另一个。

## 1. 阶段与范围（WP0–WP8 逐条）

| WP | 目标 | 实际完成 |
|---|---|---|
| WP0 | 基线核对 + 三项阻断修补 + 三原型 + 零退化闸门 | 完成：Git 基线记录；`VALID_SPEC_REFS` 注册 `11`/`11.1`–`11.9` 且未知引用仍报错；`test_runner` 补接受 11.x/拒绝 12 回归；矩阵 §2.1 改 §1–§11 并加第 11 节映射；七名字全仓扫描零匹配；基线剖析（`docs/s42-baseline-profile.txt`）；三原型协作式验证（`docs/s42-feasibility.md`）+ 无 spawn 基线计时。**零退化**判定按任务书诚实分期：WP2 接线后在同解释器上实测 1.295×（含 7 次少启动，见 WP6 性能报告）。 |
| WP1 | 规范 §11 冻结 + spawn 词法/语法/AST | 完成：规范 §11.1–11.9 + 同步 §1/2.1/3/6/7；`SPAWN` token、`SpawnExpression` AST、`_atom` 分派（本地/模块限定）；桩实现可跑通；5 条定向单测。 |
| WP2 | 确定性调度核心 + runtime 接线 + CLI + 单测 | 完成：`lwt/concurrency.py`（单令牌 Event 移交、FIFO 队列、splitmix64、I/O 批次屏障、死锁状态机、轨迹绑定/记录/重放）；7 能力接线、`read_text` I/O 调度点、收尾 join、原位置错误传播；CLI 三开关；`tests/test_concurrency.py` **19 项**（PRNG 向量、10× 确定性、线程无泄漏三路径、批次屏障、死锁、轨迹三态）。 |
| WP3 | 45 对黑盒 + 10 次复跑 | 完成：**46 项** `tests/cases/concurrency/`（含任务书一键命令的 `race-lost-update`）；`tools/run_concurrency_determinism.py` 对 46 项各 10 次逐字节比对，`reports/s42-determinism.json` 全稳定；全量黑盒 **400/400**。 |
| WP4 | `--check` spawn 诊断 + 工具边界拒绝 | 完成：`E-SPAWN-001/002`（文本 + JSON）；`--profile`、CLI debugger、DAP 经共享 execute 路径在执行前以 4 拒绝、无部分档案/断点；LSP/observability 补 `SpawnExpression` 遍历。**未单独验证 DAP 协议帧**（见 §6）。 |
| WP5 | 调度探索 + found/absent/tampered 三态 | 完成：`tools/explore_lwt_schedules.py`；`reports/s42-schedules/` 三态齐全（found 200 种子 2 类、absent 200 种子 1 类、tampered 三篡改均 exit 4）；`summary.md`。 |
| WP6 | 并发应用 + 差分等价 + 性能实验 | 完成：`app/concurrent_log_report.lwt`（**233 有效行**）、`docs/s42-app-dev-log.md`、逐字段差分等价 4 fixture PASS、坏文件 recover、多文件 10 次一致；`tools/run_concurrency_benchmark.py` + `reports/concurrency-performance.{json,md}`（4 组、Amdahl 上限、无 CPU 加速宣称）。 |
| WP7 | 指南/Skill/PPT/答辩/盲测 | 完成：开发指南并发章、`docs/concurrency.md` 契约卡、Skill 语言边界 + 3 反模式 + 最小示例、演示脚本 +90 秒、答辩卡 +5 问、PPT **12→15 页**（旧 12 页图表 12 数值点未变）；盲测**如实写"未执行"**（无法新开无上下文会话）。 |
| WP8 | 全量回归 + 收口文档 + 分 WP 提交 | 完成：全量黑盒 400/400、全量 unittest（见 §4）、compileall、`git diff --check`、Markdown 链接围栏、保护路径差异空；`project.md`/`README.md`/路线图/`final-acceptance-checklist.md` + 本报告；每 WP 独立提交、不推送。 |

## 2. 基线与 Git

- **基线 SHA**：`feature/lwt-core-0.2 @ a996591`（含上一轮 S42 语言核心 6 笔未推送提交），用户裁决"叠加在语言核心之上，记为 S43"；`main = origin/main = 5027860`（`git fetch --all --prune` 后 `merge-base --is-ancestor main origin/main` exit=0，无远端新提交）。任务书假设的 `milestone/final-acceptance @ f1b7fa9` 是独立文档线，**未纳入**本基线。
- **分支**：`feature/deterministic-concurrency`（从 `a996591` 创建）。
- **工作区**：最终 `git status -sb` = `## feature/deterministic-concurrency`（干净）。
- **提交序列**（按 WP 分组，完整 SHA 见各笔 commit）：① `fbd5532` `fix(concurrency): pass WP0 gate and register spec 11`；② `4d483f8` `feat(concurrency): freeze spec 11 and add spawn syntax`；③ `4877aa1` `feat(concurrency): implement deterministic scheduler and channels`；④ `fa37ec4` `test(concurrency): add 46 black-box cases and determinism evidence`；⑤ `e9bd715` `feat(concurrency): add concurrent app and schedule-exploration witnesses`；⑥ `ca2e563` `docs(concurrency): add guide, contract card, defense material and benchmark`；⑦ 收口提交（本报告，SHA 由主窗口 `git log -1` 核对，正文不预写自身 SHA）。
- **远端**：**未推送**；无远端最终 SHA，Actions 未查询，不沿用候选 `e1249f5` 的历史四格结论。

## 3. 语义决策与偏离（第 5 节契约的每一处差异）

| 契约条款 | 实现 | 偏离/原因/影响 | 是否写入规范 |
|---|---|---|---|
| §5.4 `fifo` = "选择任务编号最小的就绪任务" | 真 **FIFO 队列**（`spawn`/`yield` 入队尾、队首出队） | WP0 原型证明：若取"就绪集合最小编号"，低编号任务 yield 后持续自我调度、饿死其它任务（挂死）。**精确化**为"同一批初始 spawn 按编号入队，此后 FIFO"；保证确定性且避免饥饿。影响：与字面不同，但语义更符合"协作式让步"意图。 | 是，§11.4 + `s42-feasibility.md` §6 |
| §6 令牌移交骨架（Condition + notify_all） | 每任务 `threading.Event` 显式令牌 + `RLock` Condition | WP0 实测裸 Condition 移交在本机 Windows 有 lost-wakeup 竞态（带打印可跑、无打印挂死）；Event 是粘滞的，不受通知丢失影响。WP2 又发现 `send`/`wake_receiver` 嵌套加锁需 `RLock`（`Lock` 自死锁，已修）。两者都是**实现稳健性**，语义不变。 | 是，§11.4 不变量 I1/I3 + 可行性报告 |
| §5.4 自带 PRNG | splitmix64，`below(n) = next_u64() % n` | 规范给出算法与 seed 1/7/42 各 10 向量，`tests/test_concurrency.py` 固定断言；不用 `random`、不依赖字典序/线程 id。无实质偏离。 | 是，§11.4 |
| §5.8 I/O 批次屏障 | done-callback 把完成 I/O 任务按编号入队尾；就绪空且有 pending I/O 时 `cond.wait` 等批次 | 与契约一致；"任务 A 阻塞 join + B io_pending + C 可运行"定向测试（`test_io_pending_batch_does_not_mask_as_deadlock`）证明不误判死锁。 | 是，§11.8 |
| §5.6 诊断与退出码 | 死锁 `RuntimeError`/3、任务错误原位置重抛、无人 join 收尾抛出 | 与契约一致；`_drain_tasks` 区分"已 join（用户已 recover）"与"未 join"，避免二次抛出。 | 是，§11.6/§11.7 |
| §5.10 `--profile`/debugger/DAP | 执行前 `CliError`/4，无部分档案/断点 | CLI `--profile` 在 preflight 前拒绝；debugger/DAP 走 execute 共享拒绝路径。**DAP 协议帧未单独验证**（见 §6）。 | 是，§11.8 |
| 差分等价（增强版 §2/WP6） | 并发应用单文件输出 = 串行输出（剥离 `=== FILE ===` 块头） | 多文件摘要无法与单次串行调用逐字节相同，冻结**逐字段映射**（每块正文 ↔ 单文件串行输出），4 fixture 逐字节 PASS。 | 是，`docs/s42-app-dev-log.md` §3 |

## 4. 运行证据（命令 / 退出码 / 关键输出 / 结论）

| 命令 | 退出码 | 关键输出 / 结论 |
|---|---:|---|
| `python tools/run_tests.py` | 0 | `passed=400 failed=0 total=400`；`concurrency=46/46`（目录 46 个用例）、既有 354 零回归 |
| `python tools/check_project_integrity.py` | 0 | `cases=400; matrix_links=445; referenced_cases=348` |
| `python -m unittest discover -s tests -q`（系统 Python 3.13.7 + Tk） | 0 | `Ran 595 tests in 678.039s ... OK`（含 19 项并发单测、既有 GUI/策略/工具测试，0 失败） |
| `python -m unittest tests.test_concurrency -q` | 0 | `Ran 19 tests ... OK`（6.2s） |
| `python tools/run_concurrency_determinism.py --repeat 10` | 0 | `46 cases x 10 runs; stable=True; failures=0` |
| `python -m lwt --schedule=random:7 --schedule-log …trace-1.json tests/cases/concurrency/race-lost-update.lwt` | 0 | 生成轨迹，含全部绑定字段 |
| `python -m lwt --schedule-replay …trace-1.json <同上>` | 0 | stdout 逐字节相同（输出 `1`） |
| 三种篡改（chosen/source_sha256/expected_stdout_sha256）重放 | 均 4 | `CliError`，消息指出字段/决策点；`tampered-log.json` `all_rejected=true` |
| `python tools/explore_lwt_schedules.py --program <race> --seeds 1..200` | 0 | `200 seeds -> 2 classes`，trace reproduced=True |
| `python tools/explore_lwt_schedules.py --program <ordered> --seeds 1..200` | 0 | `200 seeds -> 1 class`，trace reproduced=True |
| `python -m lwt app/concurrent_log_report.lwt -- sample.log showcase.log` | 0 | 2 个按输入顺序的块；差分等价 4 fixture PASS；多文件 10 次一致 |
| `python tools/count_lwt_lines.py app/concurrent_log_report.lwt` | 0 | `233`（≥200） |
| `python tools/run_concurrency_benchmark.py --files 8 --size-mb 2 --repeats 7` | 0 | LWT 串行/并发 1.295×（主要来自少启动 7 进程）、Python 线程 0.828×（热缓存下更慢）；见 `reports/concurrency-performance.md` |
| `python -m lwt --check <spawn 目标不存在>` | 2 | `StaticError[E-SPAWN-001]`，JSON 模式亦含 |
| `python -m lwt --profile … <spawn 程序>` / `python -m lwt.debugger <spawn 程序>` | 4 | `CliError: profile and debugger do not support spawn`，无部分档案 |
| `git diff --check` / Markdown 链接围栏 / `compileall` | 0 | 全通过；保护路径差异空 |

> 注：`race-lost-update` 是在一次 399 项全量批次后加入的第 46 个并发用例；加入后 `python tools/run_tests.py --category concurrency` 实测 **46/46**，`--list-json` 的 inventory 亦为 46 且含该 id，完整性 `cases=400`（354 既有 + 46 并发）。最终全量 400 项数字以 §4.1 的收口运行为准。

### 4.1 全量 unittest

用系统 Python 3.13.7 + Tk 8.6 跑 `python -m unittest discover -s tests -q`：`Ran 595 tests in 678.039s ... OK`，**0 失败、0 错误**（11m19s）。比 S42 语言核心分支的 569 项多 26 项（19 项并发单测 + 7 项相关 runner/CLI 测试）。本执行窗口另单独验证：19 项并发单测（6.2s）、329 项针对性单测（CLI/LSP/debugger/profile/runner/concurrency）通过。**注意**：上一轮 S42 的基线全量曾出现一个 Tk GUI 测试（`test_load_real_s41_witness_with_button_and_reverify`）的环境性超时，本轮全量 595 OK 未复现该问题，说明它是间歇性环境时序，与本阶段代码无关；两轮均如实记录。Bash 默认 `python` 是 WorkBuddy 内置 3.13.14（无 tkinter），全量 unittest 以系统 Python 3.13.7 为准。

## 5. 交付位置（需求 → 测试映射）

| 课程抓手 / 任务书 | 交付 | 文件 / 映射 |
|---|---|---|
| 解释器 20 / WP1–2 | 并发子语言 7 能力 + 单令牌调度 + 死锁 + I/O 重叠 | `lwt/concurrency.py`、`lwt/{lexer,parser,ast_nodes,runtime,cli,analyzer,language_service,observability}.py`；规范 §11；19 单测 |
| 测试 20 / WP3 | 46 并发黑盒 + 确定性 46×10 | `tests/cases/concurrency/`、`tools/run_concurrency_determinism.py`、`reports/s42-determinism.json`；矩阵 §11 表 |
| 性能 10 / WP6 | 诚实四组 I/O 重叠实验 + Amdahl | `tools/run_concurrency_benchmark.py`、`reports/concurrency-performance.{json,md}` |
| 指南 20 / WP1/7 | §11 规范、契约卡、指南、Skill、答辩 | `docs/language-spec.md` §11、`docs/concurrency.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/demo-script.md`、`docs/defense-qa-card.md`、`slides/LWT介绍.pptx` |
| 应用 30 / WP6 | 233 行并发应用 + 差分等价 | `app/concurrent_log_report.lwt`、`docs/s42-app-dev-log.md` |
| 证据闭环 / WP0/5 | 可行性闸门 + 三态见证 | `docs/s42-feasibility.md`、`docs/s42-baseline-profile.txt`、`reports/s42-schedules/`（found/absent/tampered + summary） |
| 收口 / WP8 | 状态与清单 | `project.md`、`README.md`、`阶段执行与审查路线图.md`、`docs/final-acceptance-checklist.md`、本报告 |

## 6. 已知问题与未验证项

- **未验证（如实标注）**：Python 3.10 本机实测、Linux 实测、远端最终 SHA 的 Actions 四格（本阶段未推送）、Agent 盲测 pass@1/pass^k（无法新开无上下文会话，见 `docs/s42-agent-blind-test.md`）、DAP 协议帧级别的 spawn 拒绝（只验证了共享 execute 拒绝路径）、冷 page cache / 网络挂载 I/O 重叠、纯 I/O 重叠的隔离测量（1.295× 主要来自少启动进程，见性能报告）。
- **设计边界（非缺陷）**：非抢占、无任务取消/超时、无界通道、无 `sleep`/锁/原子变量、CPU 不加速、`--profile`/调试器明确拒绝、fifo 用真队列（§11.4）、PRNG 自带算法。
- **已修复的真实缺陷**：① WP0 原型暴露 fifo"最小编号"饥饿 → 改真 FIFO 队列；② WP0 裸 Condition 令牌移交 lost-wakeup → 改 Event 显式移交；③ WP2 `send`/`wake_receiver` 嵌套 `Lock` 自死锁 → 改 `RLock`（曾导致 `channel-block-receive` 挂死）；④ 无 spawn 程序调用 `yield()`/`channel()` 触发 `assert scheduler` traceback → 扩展并发构造检测；⑤ 重放篡改 `chosen` 导致子任务线程异常被吞而进程挂死 → `fail_replay` 唤醒全部等待者并以 `CliError`/4 传播。
- **测试断言适配**：46 用例生成期发现 `tests/test_cli.py` 的用户函数 `fn join` 与新内建 `join` 冲突 → 改名 `combine`（保留 S5 实参求值顺序意图）；2 个用例 tags 重复 → `lifecycle`；均不改变断言目的。
- **PPT**：旧 12 页与第 10 页原生图表 12 数值点未改；旧 SHA `0e680d17d0b0f09315a6519b15c9516ee04dac34df7dc8e42ea771c797b5fe5d` → 新 SHA `cb30936516931f11906b2eec17329f42a8ed4ec5f9bf5489a0492060faf5c69d`（15 页）。
- **保护数据**：S10/S11/S28/S29/S12 原始文件、`app/log_report.lwt`、`app/lwt_snake/game.lwt` 差异为空；所有新报告用新文件名。
- **测试遗留清理**：全量 unittest 中 `tests/test_lwt_snake_workshop.py` 的符号链接测试在 `app/lwt_snake/strategies/` 留下 1 个 0 字节 `test-<uuid>.lwt`（`addCleanup` 在进程正常退出前未覆盖该路径）。执行窗口将其**移到工作区 `tmp/`（Git 外，可恢复），未删除、未提交**；`app/lwt_snake/` 工作树差异为空。这是既有测试的行为，与本阶段无关（上一轮 S42 亦有同类残留 4 个）。

## 7. Agent 开发记录摘要

- **提示与授权**：用户派发 S42 并发任务书（含强制修订版）；执行窗口发现基线冲突（当前在含 6 笔 S42 语言核心提交的 `feature/lwt-core-0.2`，非任务书假设的干净 main），停止写入并请用户裁决；用户选"叠加在语言核心之上，记为 S43"后建分支开工。
- **产出与修正**：先做 WP0 三原型（协作式 generator 模型）暴露 fifo 饥饿与 Condition 竞态 → 写成规范 §11.4 的精确化与 Event 移交方案；WP2 接线后用 faulthandler 定位 `channel-block-receive` 挂死为嵌套锁自死锁 → `RLock`；WP3 生成 46 用例时逐条断言语义（非盲目录入），发现并修 5 个真实缺陷 + 2 处用例数据错误；WP5 用 200 种子探索得到 found 2 类 / absent 1 类 / tampered 全拒；WP6 写 233 行并发应用并逐字节差分等价验证；WP7 追加 3 页 PPT 并校验图表 12 点未变。
- **人工审查边界**：以上均为执行窗口自测，**不**等同主窗口审查；盲测未执行、不把自测当盲测；CI/GUI/教师验收分层记录。

## 8. 状态分层

- **执行实现**：完成（本窗口，证据见 §4）——**待主窗口复核**。
- **主窗口审查**：未开始（本报告交主窗口）。
- **合入 main**：未发生（本阶段不推送、不合并）。
- **远端 CI（最终 SHA）**：未查询（本阶段不推送，无远端最终 SHA）。
- **现场人工 GUI 验收**：未验证（沿用 S12 桌面限制；本阶段新增 CLI/FAQ/PPT 证据不替代现场 A–E 项）。
- **教师验收 / 最终评分**：不属于本执行窗口，不声称。
