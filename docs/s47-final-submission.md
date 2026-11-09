# S47 执行报告：提交可达性、Agent 能力实证与一键交付包

**基线未经主窗口复核（S43/S44/S45/S46）。** 按用户裁决 A，S47 从 `6bc4b21`（= `origin/feature/concurrency-model-check`，S46 tip）继续；用户裁决 B 为 **B1（FF 合入 main 并推送）**，裁决 C 为 **①（独立子代理会话跑盲测）**。未打标签；main 的推送在 §6 单独记录。

## 1. 工作包（WP0–WP5）

| WP | 内容 | 状态 |
|---|---|---|
| WP0 | 基线只读回归；Git 原文；三项裁决（A/B1/C①）；判分器字段核对 | 完成 |
| WP1 | 6 题独立子代理盲测 + 客观判分 + 失败归因 + 题面修订复跑 + `tests/test_agent_eval.py` | 完成 |
| WP2 | `tools/build_submission.py`、`SUBMISSION.md`、bundle、zip、`tools/verify_fresh_clone.py`、`tests/test_submission_bundle.py` | 完成 |
| WP3 | B1：`main` FF 到本分支并普通推送，查精确 SHA 四格 | 完成/见 §6 |
| WP4 | `docs/s47-agent-eval.md`、本报告、manifest、README/清单/演示/答辩、PPT 19→20 页（20 页） | 完成 |
| WP5 | 自检包新增提交包/盲测步骤；全量回归；干净树收口 | 完成 |

## 2. 基线与 Git

| 项 | 值 |
|---|---|
| 开工 HEAD | `6bc4b21b336d89932de709f5c4cca4beb47702f8`（工作树干净） |
| main / origin/main | `5027860efc8a1cce342ca13b1434d7724aeeffc4` |
| main..HEAD | 32 提交；`main` 是 HEAD 祖先；FF 可行 |
| 默认分支 | `origin/HEAD -> main`（`git remote show origin` 的 `HEAD branch: main`） |
| 保护数据 | `252122c..HEAD` 保护路径 diff 为空（S46 收口时已核对） |

基线只读回归：黑盒 **400/400**；unittest **664/664 OK**；确定性 **46×10 stable=True, failures=0**（独立 `--out`，S42 证据未覆盖）；完整性 400/400 unref=0；`compare_perf all_pass=true`；文档一致性 11/11。

## 3. WP1：真实 Agent 盲测

详见 [S47 Agent 盲测报告](s47-agent-eval.md)。

- 6 题 × 6 个全新子代理会话 × 独立 detached worktree（基线 `6bc4b21`）；worktree 内删除 tasks.json/测试/应用，只留白名单文档与解释器。
- 首轮（冻结题面）：**5/6 通过，pass@1 = 0.833**。唯一失败 `producer-consumer-channel` 的原因是**题面未规定 `throw` 的消息文本**（oracle 却要求 `caught:task failed`），属 TASK_DEFECT。
- 修订题面（只改 prompt，oracle 不变）后，用**新的**隔离会话复跑该题：`PASS`，证据 `reports/s47-submission/agent-eval-clarified.json`（1/1，标注 post-hoc，不并入首轮）。
- 6 题均 0 运行失败；5 题 0 修订，1 题 1 次非功能性改名。**未触发指南修订**（失败不归因于指南，不制造改动）。
- 判分器补齐 `check_required`（此前未读取）、模块文件禁用词扫描、pass@1 分母（通过数/全部题数）；`tests/test_agent_eval.py` 7 项全过。

## 4. WP2：一键提交包

| 产物 | 说明 |
|---|---|
| `SUBMISSION.md` | 仓库根；8 项提交内容 → 分值/路径/一条验证命令/证据/状态；三分钟验收路径；五段证据摘要；未验证项 |
| `lwt-history.bundle` | `git bundle create --all`；`verify` 与 `list-heads` 留证 |
| `lwt-submission.zip` | `git archive HEAD` 跟踪树 + SUBMISSION.md + bundle；`manifest.sha256` 逐文件摘要 |
| `build.json` / `dist/latest.json` | 构建记录与指针（`dist/` 已 gitignore） |
| `reports/s47-submission/fresh-clone.{json,md}` | 从 bundle 新克隆后逐命令退出码与 400/400 结果 |

`tools/build_submission.py` 只读保护证据，不写 `bench/`、`reports/`、`tests/cases/`、应用源码。`tests/test_submission_bundle.py` 5 项：8 项路径存在、bundle verify、zip 摘要自洽、构建不修改保护证据、缺 bundle 退出 2。

## 5. 收口数据（实测）

（收口时填：bundle/zip SHA-256、条目数、fresh-clone 五条命令退出码与 400/400、自检 PASS 文件。）

## 6. WP3：main 收敛（B1）

（收口时填：FF 前/后 SHA、`git push origin main` 输出、精确 SHA、CI run 与四格耗时。）

## 7. 保护数据

`bench/results.json`、`reports/performance.md`、S10/S28/S29/S37–S46 固定证据、`reports/s42-*`、`tests/cases/**`、`app/log_report.lwt`、`app/lwt_snake/game.lwt`、PPT 第 10 页图表 12 数值点：全部零改动。S47 新证据只写 `reports/s47-submission/`、`docs/agent-eval/submissions/`、`dist/`（忽略）。

## 8. 未验证项

- 现场人工 GUI A–E、教师线下验收。
- Agent 盲测 n=1/题，pass@1 非统计显著；隔离为规则+干净 worktree，不是 OS 沙箱。
- 本机 Python 3.10 / Linux（由 CI 覆盖，非本地）。
- CI 结论按精确 SHA；功能分支与 main 的 CI 分开记录。

## 9. 状态分层

| 状态 | 结论 |
|---|---|
| 执行实现 | 完成（WP0–WP5） |
| 执行窗口自测 | 400/400、677/677 unittest、46×10、盲测 5/6、提交包与新克隆验证、自检 PASS |
| 主窗口审查 | 未开始（S43–S47 均未复核） |
| 合入 main | B1 执行后见 §6 |
| 远端 CI | 见 §6 |
| 现场人工 GUI | 未验证 |
