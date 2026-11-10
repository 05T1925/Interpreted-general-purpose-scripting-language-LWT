# S49 答辩彩排与验收一致性收敛报告

> **基线未经主窗口复核（S43–S48）。** 本报告记录执行窗口自测与**本地彩排**；彩排不是教师线下验收，验收结论由教师现场判定。
> 三项裁决：**A** 从 `0df0e40` 建 `feature/defense-rehearsal` 隔离；**B** 授权推送 `main` 并按精确 SHA 查 CI 四格；**C** 现场人工 GUI A–E **不由**执行窗口代劳（保持 `REGISTERED 0/5`、`NOT_RUN`）。另经确认清理 60 个 S48 临时 worktree。

## 1. 开工闸门与 Git 原始记录

| 项 | 实测 |
|---|---|
| 开工时 `git status -sb` | `## main...origin/main`（干净，无领先/落后） |
| `git rev-parse HEAD main origin/main` | `0df0e40026ef59becd5cc2599d400ede36e90215`（三者相同） |
| `git log --oneline -8` | `0df0e40` / `446ed4d` / `724dc7c` / `371f113` / `f46ff08` / `e8d64b5` / `bfda042` / `bdde5d9` |
| `git worktree list \| wc -l` | 65（主工作树 + 60 个 `lwt-s48-*` + 3 个 `lwt-s9-blind-*` + `s39-agent-strategy`） |
| 包索引 | `bundle_ref_sha=bfda042`、`final_tip_sha=bfda042`、白名单 5 条 |
| 分支 | `feature/defense-rehearsal`（从 `0df0e40` 切出，不直接写 `main`）；**待推送**，合入 `main` 后按精确 SHA 查 CI 四格 |

## 2. 基线只读回归（`0df0e40`）

| 命令 | 结果 |
|---|---|
| `python tools/run_tests.py` | **400/400**，`elapsed=281.0s`，11 类分类统计齐全 |
| `python -m unittest discover -s tests -q` | 695 项；首跑 `1181.9s` 有 2 个 error（同一 arena 用例的两个子进程脚本），非 GUI 批 `669` 项 `1055.3s` 仍为 1 failure + 1 error；根因与修复见 §2.1，修复后结果见 §2.2 |
| `python tools/run_concurrency_determinism.py --repeat 10 --out reports/s49-rehearsal/baseline-determinism.json` | `stable=True; failures=0`（46 项 × 10） |
| `python tools/check_project_integrity.py --require-all-referenced` | `cases=400; referenced_cases=400; unreferenced=0; exempt=0` |
| `python tools/compare_perf.py --format json` | 退出 0（`all_pass` 由后续探针 `compare-perf` 断言复核） |
| `python -m unittest tests.test_doc_consistency -q` | 基线上为 16/16；S49 扩到 27 项后见 §4 |
| `python tools/run_defense_probe.py --all --skip-heavy` | 基线 21/21 PASS（记录见 `reports/s48-defense/defense-probe.json`） |

### 2.1 那 2 个 error：根因与最小修复（披露）

失败集中在同一个用例 `ArenaTests.test_faults_keep_verified_prefix_and_release_children`，两个子测试分别是“坏 stdout”和“sleep 5 s”。堆栈显示真正抛错的位置是**应用侧**：

```
app/lwt_snake/strategy.py: close()
  process.wait(timeout=1)  ->  TimeoutExpired
  -> BridgeFailure: ... timed out after 1 seconds
  -> ArenaError: baseline/4: fresh LWT strategy close: ...
  -> 断言 case['game_verified'] 为 False
```

**量化**：本机冷启动 `python -u -m lwt app/lwt_snake/strategy_baseline.lwt` 并立刻 EOF，5 次耗时 `0.586 / 0.549 / 0.554 / 0.546 / 0.564 s`——空闲时已逼近 1 s。**安静环境复跑基线全量：695/695 OK（950.0 s）**，说明失败是负载相关抖动而非必然回归；两次失败（`1181.9s` 的 2 个 error、非 GUI 批 `1055.3s` 的 1 failure + 1 error）都发生在同时跑其它长任务时，同一用例单跑 2/2 通过。

**处理（预防性健壮性修复，非为通过测试）**：0.55 s 的实测余量只剩 45%，任何并发负载都会越界。把 `close()` 的固定 1 s 等待改为跟随 bridge 自身的 `timeout`（默认 5 s）：

```python
process.wait(timeout=max(1.0, float(self.timeout)))
```

- 改动范围：`app/lwt_snake/strategy.py` 一行（+3 行注释），**不改**语言 §§1–11、错误消息、退出码、调度点、轨迹 schema，**不改** `tests/cases/` 与任何断言。
- 影响：策略进程退出更宽容，不再因机器负载误判“策略失败”；`StrategyBridge` 的默认行为（5 s）与其它路径一致。
- 验证：修复后 S49 树全量分批结果见 §2.2；同一用例单跑仍 2/2 通过；基线（未含本修复）安静复跑也是 695/695。
- **没有**把失败测试改为 skip、没有放宽 `game_verified` 断言、没有改 `timeout=.2` 的故障注入参数。

### 2.2 修复后的全量结果（S49 树）

`unittest.defaultTestLoader.discover('tests')` 统计为 **713 项**（695 + 文档 11 + 交付结构 7）。执行窗口的后台任务在约 20 分钟会被宿主回收（表现为日志只剩一行 `CounterfactualError: total deadline exceeded ...`，不是用例失败），因此把同一集合拆成两批执行并求和：

| 运行 | 范围 | 结果 |
|---|---|---|
| 基线 `0df0e40` 单进程全量 | 695 项 | **OK**，`950.0 s` |
| S49 树 · 非 GUI 45 个模块 | 687 项 | **OK**，`835.8 s` |
| S49 树 · GUI 5 个模块 | 26 项 | **OK**，`101.2 s`（复跑第二次；第一次 `151.6 s` 也 OK） |
| **合计** | **687 + 26 = 713** | 与 `discover` 的 713 一致，0 failure / 0 error |
| 基线非 GUI 批（对照） | 669 项 | `1055.3 s`，1 failure + 1 error（同一 arena 用例，负载下超时） |

分批是**执行环境的 20 分钟上限**导致的等价覆盖，不是跳过用例：两批合起来正好是 `discover` 的全部 713 项，且没有任何 `skip`。报告不把“两批通过”写成“单命令一次跑完”。

### 2.4 全量 unittest 断言的执行状态（如实）

`docs/defense-claims.json` 的 `unittest` 断言要求“一条命令跑全量”。在本机它**没有跑成绿色**，三次真实尝试：

| 次 | 结果 | 用时 | 说明 |
|---|---|---|---|
| 1 | FAIL（exit 1） | `1201.0 s` | 全量 713 项，1 个失败（当时 GUI 45 s 阈值尚未修） |
| 2 | FAIL（exit 1） | `1466.8 s` | 阈值修好后仍 exit 1；探针只保留输出前 600 字符，失败名不可见 |
| 3 | 挂起后被终止 | — | 子进程持有 stdout/stderr 管道，`subprocess.run(capture_output=True)` 等不到 EOF；探针本身卡住，手动终止 |

**第 4 次定位（`--failfast`，2026-11-10 20:30）**：全量跑到第 452 项时，失败用例是 `ArenaTests.test_v2_policy_tampering_and_explanation`，堆栈为 `BridgeFailure: timed out after 2s waiting for request 000001`——策略子进程 2 秒内没回应 INIT。同一时段实测「空 `python -c pass` 子进程」需 **334 ms**（正常约 60–100 ms），机器已明显降速；该轮 452 项耗时 `2570 s`，而此前 687 项只用 `835.8 s`。这是**环境时序**导致的 2 s 超时，不是语言/应用回归，也不再通过调大测试阈值来“修绿”。

**结论**：不把该断言写成 PASS。全量的等价证据是 §2.2 的两批 **713/713**（687 + 26，0 failure / 0 error，均已 `OK`，且在机器降速前测得）。探针记 `FAIL`，报告、答辩卡与自检输出都按“单命令未跑成、两批全绿、原因是环境时序”陈述。

### 2.3 第二个阈值：GUI 收敛上限 45 s

单进程全量（`713` 项，`1247.1 s`）里仍有 1 个失败：`CounterfactualTkTests.test_load_real_s41_witness_with_button_and_reverify` 的 `Tk worker did not settle within bounded event loop`。单跑复现 **2/3 失败**（每次约 61 s），根因是该用例把“验证 `reports/s41-found`（32 步、每分支一个 LWT 进程）”的收敛上限定成 **45 s**，而本机实测 50–60 s。

处理：把这一处的上限改为 **120 s** 并注明它是**挂起检测**、不是性能断言（仍要求 worker 收敛，仍断言 `扫描 2/32` 与 `LWA1|000002|MOVE|D|FOOD`）。改后该模块 2/2 OK，GUI 批 26/26 OK（101.2 s）。同样**没有**删断言、没有 skip。

## 3. WP0：包索引诚实化、CI 四格、环境债务

### 3.1 包索引：S48 声明对 HEAD 已过期（实测）

`tools/check_package_lag.py` 用 `git diff --name-only bfda042..HEAD` 重算：

| HEAD | lag 文件 | 白名单内 | 白名单外 | 退出码 |
|---|---:|---:|---:|---:|
| `0df0e40`（S49 开工） | 5 | 4 | **1**（`docs/demo-script.md`） | **1** |

结论：S48 的索引只覆盖到 `e8d64b5` 一带；主窗口后续修改 `docs/demo-script.md` 后，索引声明已过期。已在 `docs/s48-defense-readiness.md` 加**带日期的 S49 复核段**（不改写 S48 原结论），并把“领先 15/16 笔”这类一次性数字改成“以 `git rev-list --count` 实测为准”。S49 在最终 tip 重建包后 `outside_whitelist=[]`（见 §7）。

### 3.2 CI 四格（精确 SHA，逐 job 解析）

匿名 REST API 限流（`core 0/60`，重置后仍被共享出口 IP 用尽），本机无 `gh`、无 `GH_TOKEN`。改用**公开 HTML** 的两个来源交叉核对：`/commit/<sha>/checks`（四行 job 名 + `This job succeeded/failed` 标签）与 `/actions/runs/<run>/job/<job_id>`（单 job 的结论与耗时）。**没有用 run 级 success 徽章推断任何一格。**

| SHA | run | ubuntu 3.10 | ubuntu 3.13 | windows 3.10 | windows 3.13 |
|---|---|---|---|---|---|
| `724dc7c` | 42788506291 | **failed** 6m41s | **failed** 6m58s | **failed** 7m21s | **failed** 4m41s |
| `446ed4d` | 42788879562 | success 6m08s | success 5m51s | success 9m22s | success 6m23s |
| `0df0e40` | 42789221823 | success 7m46s | success 6m27s | success 5m51s | success 5m55s |

`724dc7c` 的失败原因**已复现**：在该提交的临时 worktree 里跑 `tests.test_doc_consistency`，唯一失败是 `docs/s48-defense-readiness.md:123` 的“S48 当时未推送、CI 未验证……领先 15 笔”这类**过期分支状态 + 一次性数字**——正是 S49 WP1 要消灭的中间态表述。`446ed4d` 修掉后四格转绿。

证据：`reports/s49-rehearsal/ci-cells.json`（含每格 job id 与 URL、`warning: 不使用 run 级徽章`）。

### 3.3 环境债务

| 项 | 结果 |
|---|---|
| 待清理 | 60 个 `lwt-s48-*`，合计 **116.5 MB**（清单见 `reports/s49-rehearsal/worktrees-removed.txt`） |
| 执行 | `git worktree remove --force` 逐个移除，**60/60 成功、0 失败** |
| 清理后 `git worktree list` | **5 条**：主工作树、3 个 `lwt-s9-blind-*`、`s39-agent-strategy`（均未改动） |
| 残留 | `%TEMP%\s48-trash\`（S48 为隔离从 worktree 移出的 `tests/app/reports/tools` 副本）未在授权范围内，保留并列为本项已知债务 |

## 4. WP1：文档一致性补齐（先红后绿）

新增 11 项断言（`tests/test_doc_consistency.py` 16 → 27）：

1. **manifest 单一来源**：`unittest`/`黑盒`/`页数` 三类数字，只要出现在当前状态文档（README、SUBMISSION、project、demo-script、答辩卡、清单、规范、指南、矩阵、并发卡、agent-eval README、runbook、GUI 速查）就必须等于 manifest。
2. **中间态数字扫描**：`595/632/664/677/685` 与 `17–20 页` 只允许出现在**可证明是历史**的行。
3. **推送状态正反向**：`origin/main == HEAD` 时不得把过期的分支状态当作当前结论；反之必须有一条当前文档写明“待推送”。
4. **数字→证据可达**：`SUBMISSION.md` 八项表格里的路径必须存在、`python -m lwt --help` 必须可执行；24 条断言的 `evidence_path` 必须存在。

### 4.1 红（修复前，真实输出）

- `test_unittest_counts_match_manifest`：`docs/defense-qa-card.md:31` 仍写 `unittest 664`。
- `test_no_intermediate_unittest_counts_as_current`：同上。
- `test_ppt_pages_match_manifest` / `test_no_intermediate_ppt_pages_as_current`：`docs/final-acceptance-checklist.md:14` 的当前表格写 `19 页`。
- `test_s49_report_quotes_current_manifest_counts`：报告尚不存在。
- 合计 **5 项失败**（`Ran 27 tests ... FAILED (failures=5)`）。

**行级段豁免是必要的，不是遮羞布**：把 `_stage_section_lines()` 临时替换为空实现后，同一扫描命中 **8 行**，其中 6 行位于 `## S43/S44/S45/S46/S47/S48` 冻结段（`51/67/85/100/114/85`），真实违规只有 `checklist:14` 与 `qa:31` 两行。恢复段实现后仍保留这 2 行，说明豁免没有连带掩盖当前值。

### 4.2 绿

- `checklist:14` → `21 页（以 manifest 为准）`；`qa:31` → 当前计数 + S48 三个 SHA 的 CI 结论。
- 新增 `docs/defense-runbook.md`、`docs/defense-pages.json`、`docs/gui-acceptance-quickref.md`，并补齐 S49 报告。
- 结果：**27/27 通过**；`tests/test_delivery_readiness.py` 从 6 项扩到 13 项也全绿（见 §5.3）。

## 5. WP2：21 页逐页讲稿与随机质询彩排

### 5.1 讲稿

`docs/defense-runbook.md` 每页含：页码与标题、≤3 句口播、1–2 个追问与一句话回答、断言 ID、现场命令/降级证据、模式（**现场跑 / 只展示 / 口播**）。机器可读映射在 `docs/defense-pages.json`（21 页，32 条页-断言对），讲稿、HTML、彩排器三方共用，测试断言三者一致。

必须现场跑的页：1/3/4/5/6/8/11/14/15/16/18/20/21；只展示：9/10/17/19；口播：2/7/12/13。

### 5.2 证据台

`tools/build_defense_index.py` 重生成 `docs/defense-index.html`：24 个 `#claim-<id>` 锚点 + 21 个 `#page-N` 锚点 + 页码导航；命令用 POSIX 引号（`python -c '...'` 可复制）；状态取自最近一次探针；单文件、零外链。S48 版本里的 `class='{cls}'` 模板残留与缺引号命令已消失。

### 5.3 彩排（本地，不是教师验收）

`tools/rehearse_defense.py` 支持 `--pages/--random/--dry-run/--offline/--timeout/--allow-heavy`，每条记录起止时间、真实退出码、是否超时、证据路径；超时记 `TIMEOUT`，不写“基本通过”。

| 彩排 | 计划 | 结果 | 文件 |
|---|---:|---|---|
| 随机 5 条（seed 49，60 s/条） | 5 | **PASS 5 / FAIL 0 / TIMEOUT 0**（9.6 s） | `rehearsal-20261110T093924Z.{json,md}` |
| 第 1–5 页（60 s/条） | 6 | **PASS 6 / FAIL 0**（3.6 s） | `rehearsal-20261110T093935Z.{json,md}` |
| 全 21 页 `--dry-run` | 32 | 全部 `PLANNED`（0 s） | `rehearsal-20261110T093944Z-dry-run.*` |
| 全 21 页 `--offline` | 32 | 全部 `SKIPPED_OFFLINE`（0 s） | `rehearsal-20261110T093945Z-offline.*` |

**如实说明**：heavy 断言（400 黑盒约 281 s、全量 unittest 约 20 min、46×10）在 60 s 时间盒下必然 `TIMEOUT`；现场这几页应改为“只展示已记录证据”，或用 `--allow-heavy` 单独排练。本轮**没有**用 60 s 去跑 heavy 制造假 FAIL。

### 5.4 一键自检的预期状态

`tools/run_acceptance_selfcheck.py` 的 `defense_probe` 步骤读取 `reports/s49-rehearsal/defense-probe.json`，按“有 FAIL 行即 FAIL”判定。由于上述 `unittest` 行是 FAIL，**自检整体会是 FAIL**（其余步骤 PASS）。报告不把它写成 PASS；这正是 S48 定下的“任一步 FAIL 就整体 FAIL，不写基本通过”。

## 6. WP3：GUI A–E 双轨（按裁决 C=否）

- 人本轨：`docs/gui-acceptance-kit.md`（长版）+ `docs/gui-acceptance-quickref.md`（一页纸：3 步启动 / 3 个必看 / 异常处理 / CLI 降级 / 截图命名）。
- CLI 降级轨（已验证可执行）：
  - A 语义实验室 → `python -m lwt examples/language_lab/division_by_zero.lwt`（退出 3、定位到行列）
  - B 日志工作台 → `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2`
  - C Snake → `diff <(tr -d '\r' < app/lwt_snake/demo.expected) <(python -m lwt app/lwt_snake/game.lwt < app/lwt_snake/demo.commands | tr -d '\r')`（**已实跑一致**，仅 CRLF 差异）
  - D S41 查看器 → 读 `reports/s41-found/witness.json` + `python -m unittest tests.test_lwt_snake_counterfactual -q`
  - E PPT → `python tools/run_defense_probe.py --claim ppt`（21 页 / 12 数值点）
- **状态不变**：`reports/s48-defense/gui-acceptance.json` 仍为 `REGISTERED 0/5`，A–E 全部 `NOT_RUN`；登记工具只登记、不判 PASS。未挪用 `截图/` 目录里与本项目无关的 Git 小作业截图。

## 7. WP4：收口

### 7.1 manifest 与 PPT

| 项 | 值 |
|---|---|
| unittest_count | **713**（S49 实测；S48 的 695 + 文档 11 + 交付结构 7） |
| ppt_pages / ppt_sha256 | **21** / `7cb28b13948942b7a4b1b8fb64fb68e8aba04ab627188272a8b55c367355878c`（旧 `0be34afa…`） |
| PPT 改动 | 仅第 18–21 页页脚状态文案（695/21/已推送/CI 结论）；**不新增页**；第 10 页原生图表 **12 数值点未变** |
| evidence.s49_rehearsal / s49_ci | `docs/s49-defense-rehearsal.md` / `reports/s49-rehearsal/ci-cells.json` |

### 7.2 包索引与克隆（S49 重建后，实测）

| 项 | 值 |
|---|---|
| 包目录 | `dist/lwt-submission-20261110T121801Z/`（`dist/` gitignore） |
| bundle | `550ed0689ec0...`，`git bundle verify` = 0，仅 branches/tags/HEAD |
| zip | `17d56d55abf7...`，**1654 项**，`testzip` 通过，`manifest.sha256` 逐项匹配 |
| 包索引 | `bundle_ref_sha=957b9cb`、`final_tip_sha=957b9cb`、白名单 7 条（索引/克隆对/selfcheck 目录/探针对/报告） |
| lag 实测 | `tools/check_package_lag.py`：X=`957b9cb`、HEAD=`6d1685d`、lag **1** 个文件（索引本身）、`outside_whitelist=[]`、退出 0 |
| 新克隆 | HEAD `957b9cb`；clone/version/check/blackbox/compileall/integrity **6 条 exit 0**；黑盒 **400/400**（233.3 s），总 **242.0 s**；`lag_ok=true` |

说明：包在内容 tip `957b9cb` 生成，索引提交 `6d1685d` 是其后唯一一笔；再往后的克隆/自检/报告提交全部在 `diff_whitelist` 内，由 `check_package_lag` 每次重算。

## 8. CI 四格与失败复盘

按裁决 B 推送 `main` 并按精确 SHA 查四格。方法同 §3.2：公开 HTML 的 `/commit/<sha>/checks` 与单 job 页，**不用 run 级徽章**。

| SHA | 内容 | 四格 | 结论 |
|---|---|---|---|
| `724dc7c` | S48 记录推送失败 | 4/4 **failed** | 文档一致性抓到过期的分支状态与一次性笔数 |
| `446ed4d` | 修复该表述 | 4/4 success | — |
| `0df0e40` | S48 收口 | 4/4 success | — |
| `1f52eaf` | S49 第一次打包（Tk 阈值修复后） | 4/4 **failed** | 证据台缓存了未入库的探针状态，干净检出下生成器回落到 S48 状态 → HTML 比对失败 |
| `6d1685d` | 去缓存 + 第二次打包 | 4/4 **failed** | `defense-claims` 指向 `reports/s49-rehearsal/fresh-clone.json`，而该文件在 `8d32a19` 才入库 |
| 最终 SHA | 见仓库 `git log -1` | 见 `reports/s49-rehearsal/ci-cells.json` | 推送后按同一方法查；若网络不可达则写“未验证” |

**失败复盘（可复现，不靠猜）**：用 `git clone . <tmp> && git checkout <sha>` 模拟 CI 的干净检出，在 `6d1685d` 上跑 `tests.test_doc_consistency tests.test_delivery_readiness`，两个用例报 `defense claims point at missing evidence: ['reports/s49-rehearsal/fresh-clone.json', ...]`；同一克隆切到含该证据的 `ec5a395` 后 **40/40 OK**。这就是两次红灯的完整因果链，已由后续提交修掉。

## 9. 未验证项（如实）

- **现场人工 GUI A–E**：`REGISTERED 0/5`、全部 `NOT_RUN`；工具、速查与 CLI 降级已就绪，但**没有**本人现场证据。
- **教师线下验收与评分**：未发生。
- **PPT 页脚视觉效果**：只做了 XML 文本替换与页数/图表数值校验，未逐页渲染截图确认排版不溢出（属 GUI E 人工项）。
- **S49 最终 SHA 的 CI 四格**：推送后按精确 SHA 查；若网络/API 不可达，写“未验证”，不用徽章推断。
- 彩排是本地脚本化演练，**不替代**教师现场提问与评分。
