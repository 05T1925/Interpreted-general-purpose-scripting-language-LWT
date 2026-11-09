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

| 项 | 实测值 |
|---|---|
| 包目录 | `dist/lwt-submission-20261109T162142Z/`（`dist/` 已 gitignore） |
| bundle | `lwt-history.bundle`，SHA-256 `8d29bec743c38f3b...`；`git bundle verify` 退出 0；仅 branches/tags/HEAD（**0 个 worktree refs**） |
| zip | `lwt-submission.zip`，SHA-256 `7835693f0fc138aa...`，1368 项，`testzip` 通过；`manifest.sha256` 覆盖除自身外全部 1367 项且逐项匹配 |
| SUBMISSION.md | SHA-256 `be407c575a524538...` |
| 新克隆 | HEAD `bd3fb7f9ce178057afaec7e84f1eaa831e80e07f`（= main = feature）；clone/version/check/blackbox/compileall/integrity **6 条命令全部 exit 0**；黑盒 **400/400**（178.6 s），总 185.1 s |

**环境性 flake（如实记录）**：第一次新克隆出现 `spawn-join-null` 5 s 超时（输出已完整 `ran\nnull\n`），同一 bundle 第二次克隆 400/400。随后在主工作区高频复现：`run_tests --case spawn-join-null` 20 次、直接运行 30 次全部通过（最慢 1.7 s）。判断为克隆后杀毒/磁盘首次扫描导致的启动慢，而非产品缺陷；未修改 5 s 超时或放宽用例。

## 6. WP3：main 收敛（B1）

- FF 前：`main = 5027860`；FF 目标：`feature/concurrency-model-check`（线性链，`main` 是祖先）。
- 第一次 FF：`5027860..336e736`（36 提交），普通推送 `git push origin main` 成功，main = `336e736c45f3822977d8c0cc5aca82c6bde0cc21`。
- 第二次 FF（bundle refs 修复）：`336e736..7ce4431`，main = `7ce4431c5095a4fc92b8ab951d1800d43ebf8582`；证据提交后还会再 FF 一次，最终 SHA 由主窗口 `git log -1` 核对。
- **main 的 CI**：run [42591148360](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/42591148360)（`LWT tests` #46，`336e736`）**success 7m59s**，四格：
  - `ubuntu-latest / Python 3.13` success 4m24s；`ubuntu-latest / Python 3.10` success 4m36s；
  - `windows-latest / Python 3.13` success 7m55s；`windows-latest / Python 3.10` success 7m07s。
- 口径：这是 **main 的 CI**（不再是功能分支）；后续仅文档/证据的提交会再触发一次 run，若结论不同会单独记录，不把本次 success 外推到新 SHA。
- **main 最新两次 run**（均在 `main` 分支，四格全 success）：
  - `bd3fb7f`（自检证据提交）：run [42654006456](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/42654006456)，四格 success。
  - `446bd2d`（最终包哈希提交，重构包前的内容 tip）：run [42654883479](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/42654883479)，四格 success：ubuntu 3.13 7m04s、ubuntu 3.10 7m48s、windows 3.13 6m04s、windows 3.10 9m42s。
  - 其后仅剩“打包哈希回填”这一笔文档提交；它不改变代码/测试/PPT，CI 结论不外推，最终 SHA 由主窗口 `git log -1` 核对。

## 7. 保护数据

- **S47 自身**：`git diff --stat 252122c..main -- <保护路径>` 为空；PPT 第 10 页原生图表 12 数值点未变（19→20 页仅追加一页）。
- **main FF 带入的历史改动**：`5027860..main` 会显示 `tests/cases` 从 354→400、`app/log_report.lwt` 的 S42 dict 改造（提交 `aec6076`）、46 项并发用例（提交 `fa37ec4`）与 S42/S43 证据。这些是**已记录的历史提交**，不是 S47 覆盖；`main` 与 `feature/concurrency-model-check` 在 FF 后同树（`git diff main..feature` 为空）。
- S47 新证据只写 `reports/s47-submission/`、`docs/agent-eval/submissions/`、`dist/`（忽略）；`dist/` 不进入 Git。

## 8. 未验证项

- 现场人工 GUI A–E、教师线下验收。
- Agent 盲测 n=1/题，pass@1 非统计显著；隔离为规则+干净 worktree，不是 OS 沙箱。
- 本机 Python 3.10 / Linux（由 CI 覆盖，非本地）。
- CI 结论按精确 SHA；功能分支与 main 的 CI 分开记录。

## 9. 状态分层

| 状态 | 结论 |
|---|---|
| 执行实现 | 完成（WP0–WP5） |
| 执行窗口自测 | 400/400、677/677 unittest、46×10、盲测 5/6、提交包与新克隆验证；一键自检 **PASS**（10 步 PASS，agent_eval 如实 N/A）：`reports/s47-submission/selfcheck/selfcheck-20261109T100932Z.{json,md}` |
| 主窗口审查 | 未开始（S43–S47 均未复核） |
| 合入 main | B1 执行后见 §6 |
| 远端 CI | 见 §6 |
| 现场人工 GUI | 未验证 |
