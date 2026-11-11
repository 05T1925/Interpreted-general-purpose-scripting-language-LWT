# S51 报告：教师第一屏一致性收官与现场零翻车预案

> 执行窗口自测报告，不替代教师线下验收。裁决：**A** 直接在 `main`；**B** 本轮不执行 GUI A–E（保持 `REGISTERED 0/5`、`NOT_RUN`）；**C** 授权推送并逐格查 CI。

## 1. 一句话

修掉了“文档自称当前、却写着过期结论”的漏洞：`README.md` 的 **632 项 / 未推送 / 待主窗口复核** 与 `project.md` 的过期核对日期已消除；`test_doc_consistency` 从“带日期即历史”的粗放豁免升级为**当前状态断言优先**；同时交付现场 5 条必跑命令、降级路径与 PPT 静态校验边界。

## 2. 开工状态与基线

| 项 | 实测 |
|---|---|
| Git | `HEAD = main = origin/main = 8a5f2a1`，工作树干净，5 条 worktree，0 测试遗留 |
| manifest | 400 黑盒 / 719 unittest / 21 页 / PPT `7cb28b13…`（S51 后为 721，见 §5） |
| 400 黑盒 | **400/400**，`elapsed=291.994s`，11 类分类齐全 |
| 文档一致性（旧规则） | **27/27 绿**——但这是“漏洞下的绿”：`README:215` 自称当前状态却写 632，被日期正则放过 |
| 完整性 / 性能 | `cases=400; referenced_cases=400; unreferenced=0`；`compare_perf` exit 0 |
| 探针（非 heavy） | **20/21**，唯一失败是 `bundle-index`：命令仍读 S49 的 `fresh-clone.json`（bundle_ref `55229dbc`），而索引已到 `7d985b3` → `MISS`（S50 遗留，S51 已修） |
| 自检（--skip-heavy） | FAIL，唯一 FAIL 是 `git` 步骤；原因见 §2.1 的过程事故 |

### 2.1 过程事故（如实披露并已修复）

基线按任务书跑 `run_defense_probe.py --all --skip-heavy` 时**没有带 `--out`**，探针默认写入 `reports/s48-defense/defense-probe.json`，覆盖了 S48 的冻结证据（该次只有 20/21）。发现后立即：

1. 用 `git show HEAD:<path>` 还原两份文件（内容与 HEAD 一致，`24/24`）；
2. `git add` 刷新 stat 缓存，`git status` 干净；
3. 重跑探针时显式指定 `--out reports/s51-closeout/baseline-probe.json`。

这违反了“不覆盖旧证据”的红线，但没有把覆盖后的内容当作证据使用；S48 文件已恢复为提交态，S51 的新结果只写 `reports/s51-closeout/`。

## 3. WP1：当前状态硬伤与豁免收紧

### 3.1 红（真实输出）

新增 `test_no_stale_current_status_with_date` 并收紧 `_has_historical_marker` 后，`tests.test_doc_consistency` 共 **4 项失败**：

| 失败 | 原因 |
|---|---|
| `test_no_stale_current_status_with_date` | `README.md:215` 自称“当前状态（S44，2026-11-07）”却写 `632 项`、`未推送` |
| `test_push_status_matches_origin` | `README.md:3` 写“S42–S49 **待主窗口复核**”，且漏 S50 |
| `test_no_unpushed_claim_as_current_status` | 同上 |
| `test_no_stale_287_as_current_case_base` | `README:215` 因“当前状态”不再被日期豁免，连带命中句尾的 `287` 引述（改写时一并去掉） |

### 3.2 规则改动

```python
CURRENT_CLAIM_RE = re.compile(
    r"^\s*>?\s*\*\*当前(?:状态|基数|版本|集合|结论)"
    r"|^\s*>?\s*当前(?:状态|基数|版本|集合|结论)\s*[（(:：]"
)

def _has_historical_marker(line):
    if CURRENT_CLAIM_RE.search(line):
        return False          # 当前状态断言优先于日期
    return (marker or date or stage_row)
```

正则**锚定行首**：`project.md` 里“校验当前状态文档与 manifest 一致”是对测试对象的描述，不是仓库状态声明，不能被误判。

### 3.3 “仅靠日期豁免”的逐行分类（实测）

用同一扫描逐行分类，实际只有 **1 行**是“日期豁免的计数行”：

| 行 | 分类 | 处理 |
|---|---|---|
| `project.md:19` | 真历史（S49 阶段段，含 `S49（2026-11-10` 与“当时”语义） | 保留 |
| `README.md:215` | **过期当前结论** | 改写为 S51 当前状态（400 / 721 / 21 / 已推送），S44 性能数字标为 S44 历史结论 |
| `README.md:3` | **过期当前结论**（待复核 + 漏 S50） | 改为“S42–S50 已执行完成并合入 main，`main` 已推送；GUI 待本人” |
| `project.md:3` | 过期核对日期 | `2026-11-09` → `2026-11-11` |
| `docs/language-spec.md:1` | **过期当前结论**（S42–S44 待复核） | 改为“S1–S44 语言能力已实现并合入 main” |
| `docs/defense-qa-card.md:38` | 真历史（解释 S42–S46 当时为何未合） | 补“当时”显式标记 |

任务书预估 8 行；实测按“计数/页数 + 日期 + 非阶段段”口径只有 1 行，另 3 行是**状态词**而非计数。这里按实测写，不凑 8 行。

### 3.4 绿

- `tests.test_doc_consistency`：**28/28 OK**（新增 1 项）。
- 当前状态文档不再出现 632 / 未推送 / 待主窗口复核（历史报告原样保留）。

## 4. WP2：教师第一屏与解释器陷阱

- `README.md` 顶部：S42–S50 已合入 `main`、400 / 721 / 21、`main` 已推送；当前状态段改为 S51 口径。
- `SUBMISSION.md`：由 `tools/build_submission.py` 从 manifest 生成，新增**解释器陷阱**提示：全量 unittest 必须用 `py -3.13`（3.13.7 + Tk 8.6）；本机 `python` 无 tkinter，会得 711 + 2 个假失败，并指向 `reports/s50-closeout/unittest-interpreter-root-cause.json`。
- `docs/defense-qa-card.md`：新增 2 问（README 为何曾写 632、711 怎么复现）。
- 固化：`tests/test_delivery_readiness.FirstScreenTests` 断言 README 前 6 行、SUBMISSION 前 8 行、checklist 的 S50 段数字与 manifest 一致，且两份教师入口都写明 `py -3.13` 与 `tkinter`。

## 5. 计数：719 → 721

S51 新增 2 项固化测试（`test_no_stale_current_status_with_date`、`FirstScreenTests`），带 Tk 的 `py -3.13` 下 `discover` 实测 **721**。按 manifest 单一来源同步 `SUBMISSION`、`demo-script`、答辩卡、runbook、README；S50 报告/路线图里的 719 保留为历史。全量单命令结果见 §6。

## 6. 验证（待回填项以最终 JSON 为准）

| 项 | 结果 |
|---|---|
| 单命令全量 | **721 项 OK，exit 0，897.9 s**（`py -3.13`，3.13.7，Tk 8.6；`reports/s51-closeout/unittest-single-command.json`） |
| 探针 | **24/24 PASS**：21 条非 heavy 在 S51 重跑；`blackbox`/`determinism`/`unittest` 三行沿用 S50 的 heavy 记录（代码路径未变，各自保留 `recorded_at_utc`），其中 `unittest` 行记录的是 S50 的 719 次运行，S51 的 721 次见上一行 |
| 一键自检 | **`all_pass=true`**：11 步 PASS、0 FAIL、2 步 N/A（GUI/agent）；`selfcheck-20261111T032418Z` |
| PPT 静态 | **21 页 / 12 数值点 / SHA `7cb28b13…` / zip 完整**；`render_check=false`（未渲染） |
| 彩排 | `--random 5 --seed 51`：**4 PASS + 1 TIMEOUT**（`determinism` 在 60 s 时间盒内必然超时，heavy 断言；不是缺陷） |
| 交付包 | 在 `1404f1e` 重建：bundle `c56609cb13a8…`、zip `0462cba56f3a…`、**1725 项**、verify 0 |
| 新克隆 | head `1404f1e` → tip `dfc1ee8`，lag 仅索引，6 条命令 exit 0，**400/400**（193.8 s，总 201.8 s） |
| CI | 推送后按精确 SHA 逐格查；结果写入 `reports/s49-rehearsal/ci-cells.json` |

## 7. 未验证 / 边界（如实）

- **现场人工 GUI A–E**：本轮不执行，保持 `REGISTERED 0/5`、`NOT_RUN`；只交付 [onsite-runbook.md](onsite-runbook.md) 与降级路径。
- **教师线下验收与评分**：未发生。
- **PPT 页脚渲染**：只做 zip/XML 静态校验（21 页、12 数值点、SHA、zip 完整性），本机只有 PIL、无 LibreOffice/python-pptx；**没有伪造渲染截图**。
- 彩排 4 PASS + 1 TIMEOUT，不写成 5/5；彩排不替代教师验收。

## 8. 复现命令

```bash
python tools/run_tests.py                                    # 400/400
py -3.13 tools/run_unittest_single.py                       # 721 OK
python -m unittest tests.test_doc_consistency tests.test_delivery_readiness -q
python tools/run_defense_probe.py --all --skip-heavy --out reports/s51-closeout/defense-probe.json
python tools/run_acceptance_selfcheck.py --out reports/s51-closeout/selfcheck
```
