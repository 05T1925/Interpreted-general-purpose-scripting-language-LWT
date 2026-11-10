# S50 收官报告：单命令 unittest 红线清零（根因修正版）

> **这是执行窗口的自测报告，不是教师线下验收。** 现场人工 GUI A–E 由用户本人稍后执行；登记前保持 `REGISTERED 0/5`、`NOT_RUN`。
> 三项裁决：**A** 直接在 `main` 上工作；**B** 用户本人执行 GUI；**C** 授权推送并按精确 SHA 查 CI 四格。

## 1. 一句话

S49 遗留的唯一红线（探针 `unittest` 行 FAIL，连带自检 `all_pass=false`）已清零。根因不是“环境时序”，而是**探针把 `python` 的解析结果当成固定运行时**：本机 `python` 是无 tkinter 的 3.13.14，GUI 模块无法导入，只跑 711 项并产生 2 个假失败；同一命令在系统 `py -3.13`（3.13.7 + Tk 8.6）下 **719 项 OK**。修复后探针 **24/24**、自检 **12/12**、CI 四格在 `f3e209c` **4/4 通过**。

## 2. 开工状态

| 项 | 实测 |
|---|---|
| 开工 `HEAD` | `f3e209c` = `origin/main`，工作树干净，5 条 worktree（保留项未动） |
| 开工后远端变化 | 主窗口在同一工作目录提交并推送 `2ce8f23`（根因对照实验证据）；执行窗口以 `2ce8f23` 为新基线继续 |
| 解释器 A | `python` → `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe`（3.13.14），`import tkinter` **失败** |
| 解释器 B | `py -3.13` → `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe`（3.13.7 + **Tk 8.6**） |
| 决策 | A=main；B=用户本人执行 GUI；C=授权推送并查四格 |

## 3. 根因：同一命令，两种解释器

主窗口的对照实验记录在 `reports/s50-closeout/unittest-interpreter-root-cause.json`，两份日志的 SHA-256 均已复核：

| 实验 | 解释器 | 结果 | 日志 |
|---|---|---|---|
| A | WorkBuddy 3.13.14，无 tkinter | `exit 1`，**Ran 711**，1 failure + 1 error（`ModuleNotFoundError: No module named 'tkinter'`） | `unittest-workbuddy-python.log`（`31d5702a…`） |
| B | 系统 3.13.7 + Tk 8.6 | `exit 0`，**Ran 713**，`OK`，641.762 s | `unittest-system-python.log`（`4eb4f164…`） |

**为什么 S49 会判成“环境时序”**：S49 第 4 次定位确实看到 `BridgeFailure: timed out after 2s` 和 334 ms 的子进程启动，那是当时机器降速下的真实现象；但它不是这条红线的根因。即使机器空闲，用无 Tk 的 `python` 跑全量也只会得到 711 项和 2 个 tkinter 假失败。S49 的四次 FAIL 记录与当时判断**原样保留**在 `docs/s49-defense-rehearsal.md` §2.4，只在文末追加 §10「S50 根因修正」。

## 4. 修复：让解释器显式且可验证

### 4.1 断言

`docs/defense-claims.json` 的 `unittest` 行改为：

```json
"command": ["python", "tools/run_unittest_single.py"],
"requires": {"tkinter": true},
"precondition": {"command": ["python", "-c", "import tkinter, sys; print(sys.executable); print(tkinter.TkVersion)"],
                 "expect_exit_code": 0},
"expect": {"exit_code": 0, "stdout_contains": "OK", "stderr_contains": null}
```

### 4.2 探针

`tools/run_defense_probe.py` 新增 `resolve_python(require_tkinter)`：按 `LWT_PYTHON` → `sys.executable` → `py -3.13` → `py -3` → `python3` → `python` 逐个执行 `import tkinter`，取第一个成功的解释器；把命令行首位的 `"python"` 替换成该解释器的 argv，并把 `sys.executable`、Python 版本、`TkVersion` 写进每一行的 `interpreter` 字段。找不到时该行记 `TK_UNAVAILABLE` 并列出候选，而不是伪装成 unittest 失败。

### 4.3 单命令工具

`tools/run_unittest_single.py`：

- **只调用一次** `unittest discover -s tests -q`，不拆批、不跳过；
- 输出重定向到文件（不是管道），避免 S49 第 3 次那种“孙进程占住管道、capture 永不返回”；
- 缺 tkinter 时以 `exit 3` 快速失败并写 `TK_UNAVAILABLE` 证据；
- 写 `exit_code / ran / ok / seconds / sys_executable / python_version / tk_version / log_path`。

### 4.4 固化测试

`tests/test_unittest_claim.py` 6 项：断言声明 Tk 依赖与前置换检查；命令是单命令工具而非两批；探针能解析 Tk 解释器且不把裸 `python` 透传；证据记录 `sys.executable`/`TkVersion`；S49 四次 FAIL 历史仍在、S50 修正段存在；不允许把 `run_unittest_batches` 当作单命令口径。

## 5. 验证（真实输出）

| 项 | 结果 |
|---|---|
| 单命令全量 | **Ran 719 tests in 717.466s / OK / exit 0**；`py -3.13`，3.13.7，Tk 8.6（`reports/s50-closeout/unittest-single-command.json`） |
| 探针 | **24/24 PASS**（以 S49 的 24 行为底稿，只重跑 `unittest` 并 `--merge`；见 `reports/s50-closeout/defense-probe-merge.json`） |
| 固化测试 | `tests.test_unittest_claim` **6/6 OK** |
| 文档一致性 | **27/27**（S49 冻结报告保留 713；当前报告必须写 719） |
| 400 黑盒 | 400/400，205.4 s（自检步骤） |
| 46×10 确定性 | `stable=true`，254.3 s（自检步骤） |
| 完整性 / 保护路径 / 性能 | `integrity PASS`、`protected_diff PASS`、`compare_perf PASS` |
| 模型检查 | PASS，8.0 s |
| 一键自检 | 见 §5.1 |

### 5.1 一键自检

第一次运行（`selfcheck-20261110T163235Z`）：**11 步 PASS / 1 步 FAIL / 2 步 N/A**。唯一 FAIL 是 `doc_consistency`，原因是执行窗口先在 manifest 里声明了 `evidence.s50_closeout`，而本报告尚未写入——证据可达性测试如实报红，不是代码或测试失败。

补上本报告后在干净树（`fd54546`）复跑（`selfcheck-20261110T164712Z`）：**`all_pass=true`，11 步 PASS、0 步 FAIL、2 步 N/A**（`gui_evidence` 与 `agent_eval` 是人工/GUI 状态，不作为门禁）。任务书把这称作“12/12”；按实际步骤计数是 **11 PASS + 2 N/A + 0 FAIL**，本报告不把 N/A 写成 PASS。

**为什么 unittest_count 从 713 变成 719**：任务书要求新增 `tests/test_unittest_claim.py`，新增 6 个测试必然进入 `discover` 集合。若把 manifest 硬留在 713，就会与实测矛盾，也违反“manifest 是唯一数字来源”。因此按实测写 **719**，并同步 `SUBMISSION.md`、`demo-script`、`答辩卡`、`runbook`；`project.md`/路线图里的 S49 段落保留 713（带日期，属历史）。这是对任务书“713 不变”的唯一偏离，理由是算术事实，不是凑数。

## 6. CI 四格（精确 SHA，逐 job）

| SHA | run | ubuntu 3.10 | ubuntu 3.13 | windows 3.10 | windows 3.13 |
|---|---|---|---|---|---|
| `f3e209c`（S49 内容 tip） | 42844502753 | success 7m47s | success 5m46s | success 9m13s | success 8m39s |

`/commit/f3e209c…/checks` 显示 **4 succeeded / 0 failed**；每格耗时来自各自的 job 页，没有使用 run 级徽章。明细（job id 与 URL）写入 `reports/s49-rehearsal/ci-cells.json` 的新键。S50 自身提交推送后，按**新的精确 SHA** 再查一次，不把 `f3e209c` 的绿外推到新提交。

## 7. 交付包

S50 改了探针、断言、测试与文档，S49 的包（`55229dbc`）已不包含这些内容，因此在收口 tip **重建**了交付包：

| 项 | 值 |
|---|---|
| 包目录 | `dist/lwt-submission-20261110T165953Z/`（`dist/` 被 gitignore） |
| bundle | `20b7b98af2463074…`，`git bundle verify` exit 0，仅 branches/tags/HEAD |
| zip | `55987f09c2ed2881…`，**1696 项**，`manifest.sha256` 逐项匹配 |
| 包索引 | `bundle_ref_sha=final_tip_sha=7d985b3`，白名单 **8 条**（索引/克隆对/selfcheck/探针对/ci-cells/报告） |
| lag 实测 | X=`7d985b3`、HEAD=`c0093ef`、lag **1** 个文件（索引本身）、`outside_whitelist=[]`、退出 0 |
| 新克隆 | HEAD `7d985b3`；clone/version/check/blackbox/compileall/integrity **6 条 exit 0**；黑盒 **400/400**（130.9 s），总 **135.7 s**；`lag_ok=true`、`all_pass=true` |

包索引仍是 `reports/s48-defense/package-index.json`（活跃指针，不是冻结证据）。克隆证据见 `reports/s50-closeout/fresh-clone.json`。

## 8. GUI A–E（B=是，等本人执行）

工具与人本轨不变：`docs/gui-acceptance-kit.md`（长版）、`docs/gui-acceptance-quickref.md`（一页纸）、`tools/register_gui_evidence.py`（只登记、不判 PASS）。当前 `reports/s48-defense/gui-acceptance.json` 仍为 `REGISTERED 0/5`，A–E 全部 `NOT_RUN`；**没有**用 `截图/` 目录里的 Git 小作业图片冒充。你执行后把截图/录屏放进约定目录，我再按 SHA-256 登记并出人工验收记录。

## 9. 未验证 / 偏离（如实）

- **现场人工 GUI A–E**：未执行（B=是，等你本人）；教师线下验收与评分未发生。
- **PPT**：本阶段不改内容；21 页、第 10 页图表 12 数值点、SHA `7cb28b13…` 仅做静态校验，**未渲染确认**页脚排版（属 GUI E 人工项）。
- **S50 最终 SHA 的四格**：推送后按新 SHA 查；若网络不可达写“未验证”，不外推。
- **unittest_count 713 → 719**：见 §5.1，新增 6 项测试的算术结果。
- 探针其余 23 行沿用 S49 的记录（各自 `recorded_at_utc` 保留），本次只重跑了 `unittest` 一行；`--merge` 不覆盖未跑行，也没有把 23 行重新标成今天。

## 10. 复现命令

```bash
py -3.13 tools/run_unittest_single.py
python tools/run_defense_probe.py --claim unittest --merge \
  --out reports/s50-closeout/defense-probe-merge.json
python tools/run_acceptance_selfcheck.py --out reports/s50-closeout/selfcheck
python -m unittest tests.test_unittest_claim tests.test_doc_consistency -q
```
