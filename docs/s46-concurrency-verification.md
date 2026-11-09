# S46 执行报告：LWT 并发有界系统探索与反例最小化

**基线未经主窗口复核（S43/S44/S45）。** 按用户指示"先复核 S45，再进入 S46"，执行窗口先完成 S45 复核（Git/保护路径/通道修复/653 单测/文档一致性/PPT/CI 记录均一致），随后从 S45 最终提交 `252122c` 创建 `feature/concurrency-model-check`。未推送 main、未合并、未打标签。

## 1. 工作包（WP0–WP7）

| WP | 内容 | 状态 |
|---|---|---|
| WP0 | 工具契约草案 `docs/concurrency-model-check.md`；术语=有界系统化探索，非形式化证明；corpus 独立于 `tests/cases` | 完成 |
| WP1 | 工具 API `Scheduler(..., schedule_choices=)` / `execute(..., schedule_choices=)`；非法前缀走 `ScheduleReplayMismatch` → 退出 4、唤醒全部等待者；默认 None 零变化 | 完成 |
| WP2 | `tools/model_check_concurrency.py`：前缀 BFS、去重、结果分类、outcome witness、贪心最小化、`--schedule-replay` 复核、`BUDGET_EXHAUSTED` | 完成 |
| WP3 | `tests/concurrency-model/` 8 程序 + `.model.json`；`lost-update` 用 `allowed_outcomes` 记录允许分歧 | 完成 |
| WP4 | `--mutant duplicate-delivery` 复现 S45 缺陷；clean=0、mutant=4 违反、最小前缀 `[]`、harness 重放复现 `7\n7\n` | 完成 |
| WP5 | CI 增加模型检查步骤；`run_acceptance_selfcheck.py` 增加 `model_check`（预算耗尽=Fail） | 完成 |
| WP6 | 文档/PPT/答辩/演示/manifest/清单 | 完成 |
| WP7 | 报告、E2E 回归、按 WP 提交 | 完成 |

## 2. 基线与 Git

| 项 | 值 |
|---|---|
| 开工 HEAD | `252122c491cb57fb254f4bc367ae30e2f8b5b562`（`feature/delivery-hardening`，S45 tip，工作树干净） |
| `main` / `origin/main` | `5027860efc8a1cce342ca13b1434d7724aeeffc4`（不含 S42–S45） |
| 新分支 | `feature/concurrency-model-check` @ `252122c` |
| S45 复核结论 | 工作树干净；保护路径 `f21f474..252122c` 零 diff；通道最小复现 `7`→`null`；`test_doc_consistency` 11/11；完整性 400/400 unref=0；`compare_perf` all_pass；PPT 18 页/图表 12 点/SHA 匹配；CI 记录 run 42497482254 四格 success |

基线只读回归（S46 改动前）：黑盒 **400/400**；unittest **653/653 OK**（783.211 s）；确定性 **46×10 stable=True, failures=0**（独立 `--out`，`reports/s42-determinism.json` 零改动）；完整性 `cases=400; referenced_cases=400; unreferenced=0`；`compare_perf all_pass=true`；文档一致性 11/11。

## 3. 环境

| 项 | 值 |
|---|---|
| 平台 | Windows-11-10.0.26200-SP0；AMD64 |
| 计时/黑盒 Python | CPython 3.13.14 |
| unittest Python | CPython 3.13.7 + Tk |
| 本机其他解释器 | 3.11.16（compileall/hello/check 通过）；无 3.10 |

## 4. 运行证据（命令 / 退出码 / 关键输出）

| 命令 | 退出码 | 关键输出 |
|---|---|---|
| `python tools/run_tests.py`（S46 改动后） | 0 | `passed=400 failed=0 total=400`（见 §7） |
| `python -m unittest discover -s tests -q`（S46 改动后） | 0 | `Ran 664 tests ... OK`（S45 的 653 + 新增 11；首次运行受遗留符号链接测试文件干扰，清理后干净重跑） |
| `python tools/run_concurrency_determinism.py --repeat 10 --out reports/s46-concurrency-model/baseline-determinism.json` | 0 | `46 cases x 10 runs ... stable=True; failures=0` |
| `python tools/model_check_concurrency.py --corpus tests/concurrency-model --max-runs 300 --time-budget 90 --require-clean` | 0 | `programs=8 runs=32 violations=0 budget_exhausted=0 invalid_prefixes=0 thread_leaks=0 replay_failures=0`；8/8 `COMPLETE`；6.97 s |
| 同上 `--mutant duplicate-delivery --expect-violation --max-runs 200` | 0 | `violations=4`；4 个通道程序各 1；最小前缀 `[]`；replay `matches=true`；9.76 s |
| 同上 `--max-runs 1 --require-clean`（预算自测） | 1 | `budget_exhausted=3`、`all_pass=false`；**未写 PASS** |
| `python -m unittest tests.test_concurrency_model -q` | 0 | `Ran 11 tests ... OK`（17.099 s） |
| `python tools/check_project_integrity.py --require-all-referenced` | 0 | `cases=400; referenced_cases=400; unreferenced=0` |
| `python tools/compare_perf.py --format json` | 0 | `all_pass: true` |
| `python -m unittest tests.test_doc_consistency -q` | 0 | `Ran 11 tests ... OK` |

## 5. 探索数据

### clean corpus（`reports/s46-concurrency-model/summary.json`）

| 指标 | 值 |
|---|---|
| 程序数 | 8 |
| 执行次数 | 32（预算上限 300/程序） |
| 发现前缀 | 32 |
| 决策点（`len(ready)>1`） | 81 |
| 最大决策深度 | 6 |
| 结果类 | 9（8 程序，`lost-update` 2 类） |
| 违反 | **0** |
| 预算耗尽 / 非法前缀 / 线程泄漏 / 重放失败 | 0 / 0 / 0 / 0 |
| 总判定 | `all_pass=true`（8/8 `COMPLETE`） |

`lost-update` 的两类结果 `1\n`、`2\n` 均被记录，`2\n` 的首个 witness 前缀为 `[1, 1]`，两条 outcome 轨迹均经公开 CLI 重放 `matches=true`。这不是违规：模型用 `allowed_outcomes` 明确允许两种结果。

### mutant（`reports/s46-concurrency-model/mutant/summary.json`）

| 程序 | 违反 | 最小前缀 | 输出 | 重放 |
|---|---:|---|---|---|
| `channel-exactly-once` | 1 | `[]` | `7\n7\n`（正确应为 `7\nnull\n`） | `tool-harness-duplicate-delivery`，matches=true |
| `channel-blocked-then-queued` | 1 | `[]` | `1,1,2\n` | 同上 |
| `channel-close-drain` | 1 | `[]` | `1\n1\n2\n` | 同上 |
| `channel-fifo-three` | 1 | `[]` | `1123\n` | 同上 |
| 其余 4 个程序 | 0 | — | — | — |

最小前缀为空是正确结果：`spawn` 不是调度点，主任务先运行到阻塞 `receive`，生产者才 `send`；默认 fifo 已经能触达"交接 + 重复入队"。`--schedule-replay` 使用同一轨迹格式和同一 CLI 入口，但因故障是合成注入、干净进程无法复现，工具以**进程内 harness** 注入后重放，证据 `replay.mode` 明确标注 `tool-harness-duplicate-delivery`，不冒充产品复现。

### 预算与非法前缀

- `--max-runs 1`：8 次执行、3 个程序 `BUDGET_EXHAUSTED`，`all_pass=false`，`--require-clean` 退出 1。预算耗尽不会写成 PASS。
- 非法前缀（`schedule_choices=(99,)`）：`CliError: choice 0: 99 not in ready [1, 2]`，退出 4，无挂死，`threading.enumerate()` 无 `lwt-task`/`lwt-io` 线程（单测固定）。

## 6. 与 46 项黑盒 / 200 种子的对比

S45 的重复投递缺陷在 **46 项并发黑盒**下未暴露：没有任何一项在"接收者已阻塞"之后再 `receive` 一次（S45 报告 §6）。S43 的 **200 种子**随机探索只覆盖 `race-lost-update` 与 `ordered-aggregate` 两个程序（`docs/s42-deterministic-concurrency.md` §4），同样不含该形状。

因此差距是**形状覆盖**而非"种子太少"：一旦 corpus 含有该形状，默认 fifo 就能触发。S46 的贡献是：

1. 把不变量写进 `.model.json`，对**每个**发现的调度前缀判定，而不是只看随机采样的输出类；
2. 对违反给出可重放的最小前缀，便于定位到具体调度点；
3. 对允许的分歧（`lost-update`）显式建模，避免把正常分歧误报为 bug。

**不夸大**：本工具没有在"同一程序上比 200 种子更强"的意义上证明随机抽样不足；它证明的是"有界枚举 + 明确不变量"能稳定捕获该缺陷形状，并给出最小 witness。

## 7. 实现改动（只加工具 API）

- `lwt/concurrency.py`：`Scheduler(..., schedule_choices=None)`；`_choose()` 在前缀范围内强制选择，非法选择抛 `ScheduleReplayMismatch("choice <i>: ... not in ready [...]")`，沿用 `switch()` 现有的 `fail_replay` 唤醒路径（`replay_error` + 全任务 `token.set()`），不会挂死。
- `lwt/runtime.py`：`execute(..., schedule_choices=None)` 仅透传；决策回填从成功分支移到 `finally`，使死锁/非法前缀也能拿到已发生的决策（CLI 只在 exit 0 写轨迹，行为不变）。
- 未新增关键字/内置/语法；未改 §1–§11 可观察行为、错误消息、退出码、调度点、轨迹 schema。
- `--help`/`--check`/`--profile`/`--repl`/`--schedule*` 零变化；非 spawn 程序仍不加载 `lwt.concurrency`（`tests/test_startup.py` 10 项）。

## 8. 保护数据

`bench/results.json`、`reports/performance.md`、S10/S28/S29/S37–S45 固定证据、`reports/s42-*`、`tests/cases/**`、`app/log_report.lwt`、`app/lwt_snake/game.lwt`、PPT 旧图表 12 数值点：**全部零改动**。S46 新证据只写 `reports/s46-concurrency-model/`；确定性基线用独立 `--out`，S42 证据未被覆盖。

## 9. 未验证项

- **Agent 盲测 pass@1**：仍为 `NOT_RUN`（S45 的 6 题与判分器未变；需用户开新的无上下文会话执行）。不阻塞 S46，不伪造。
- **现场人工 GUI A–E**：自检包只打印清单，未自动化、未声称通过。
- **Linux 本地 / Python 3.10 本地**：本机无 3.10；S46 的 CI 结论只在推送功能分支后按精确 SHA 记录（见 §10）。
- **有界探索本身**：`COMPLETE` 只表示已发现前缀全部跑完，不是所有调度的形式化证明；无堆状态去重、无每 run 硬超时（受信 corpus）。
- **进程性干扰（如实记录）**：S46 首次全量 unittest 有 1 项 `test_lwt_snake_workshop` 失败，原因是上一轮基线测试在 `app/lwt_snake/strategies/` 留下 0 字节 `test-<uuid>.lwt`（Windows 上符号链接测试的清理遗留），workshop CLI 扫描到该文件后退出 1。把遗留移到 Git 外 `tmp/` 后该用例单独通过；随后在干净树上重跑全量，结论见 §4。该遗留与 S46 代码无关，但说明跑全量前需要清理 `strategies/test-*.lwt`。

## 10. 提交与 CI

- 分支 `feature/concurrency-model-check`，基线 `252122c`；提交按 WP 分组（见 `git log`）。最终 SHA 与 CI 四格在推送后由主窗口核对。
- 推送策略：功能分支推送需用户授权；未推送时 CI 写"未验证"，不把本地 Windows 通过外推为 Linux/3.10 通过。

## 11. 状态分层

| 状态 | 结论 |
|---|---|
| 执行实现 | 完成（WP0–WP7） |
| 执行窗口自测 | 400/400、664 unittest、46×10、clean 0 violation、mutant 4 violation + replay、预算/非法前缀测试通过 |
| 主窗口审查 | **未开始**（基线 S43/S44/S45 与 S46 均未复核） |
| 合入 main | 未合入 |
| 远端 CI | 推送后按精确 SHA 记录；未推送则未验证 |
| 现场人工 GUI | 未验证 |
