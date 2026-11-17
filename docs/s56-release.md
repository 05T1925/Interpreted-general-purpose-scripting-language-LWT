# S56 执行报告：v0.3.0 正式发布、PPT 校准与人机分工证据

> 验收日发布。语言语义、§1–§11、错误消息、退出码、401 项黑盒期望均未改；没有新增 test 方法，unittest 保持 **758**。基线 `1973b54`（S55 最终 tip，四格 CI 4/4）。

## 1. 裁决（本人，2026-11-17）

| 裁决 | 结果 |
|---|---|
| A 分支 | 直接在 `main` 上工作 |
| B 推送 | 授权推送 `main` 与两个附注标签 `v0.1.0`、`v0.3.0`（走 SSH） |
| C GUI A–E | 本轮不执行，保持 `REGISTERED 0/5`、`NOT_RUN` |
| D 命名说明 | 写：PPT 首页副标题追加“（LWT：刘文涛）”，[语言规范](language-spec.md) §1 命名行追加同样说明 |

开工基线（轻量）：文档一致性 / 原生自测门禁 / 交付就绪 / PPT 渲染门禁 53 项 OK；`tools/run_selftest.py`（输出到系统临时目录）38/38；完整性 401 cases、498 links、401 referenced。基线测试改写了已提交的 `reports/s55-selftest/selftest.{json,md}`，已用 `git checkout --` 还原。

## 2. WP1：PPT 校准（7 处文字 + 裁决 D）

PowerPoint COM `TextRange.Replace(find, repl)`（只传两个参数，保留原格式）；`.ps1` 正文纯 ASCII，替换文本经 UTF-8 JSON 传入，路径用参数传入；脚本用完即删。不改版式、不加页。

| 页 | 原文 | 新文 | 字数 |
|---|---|---|---|
| 1 | 最终交付候选 · Windows / Python 3.13.7 · 2026-11-03 | 正式发布 v0.3.0 · Windows / Python 3.13.7 · 2026-11-17 | 45→50 |
| 1 | 解释器、黑盒测试、Agent 编写应用与证据链 | ……证据链（LWT：刘文涛）（裁决 D） | 23→32 |
| 6 | 新克隆 Windows / Python 3.13.7 实测；覆盖矩阵不能替代所有输入空间的证明。 | LWT 原生自测 38/38（expect 用 LWT 编写）；功能清单 77 行逐项打勾；非穷尽证明。 | 49→52 |
| 7 | 246 行有效 LWT | 243 行有效 LWT | 11→11 |
| 15 | 未验证项（Linux/3.10/CI）如实标注 | Linux/3.10 由 CI 四格按精确 SHA 验证 | 23→28 |
| 18 | 3.10 与 Linux 由 CI 记录/未验证 | 3.10 与 Linux 由 CI 四格逐格验证 | 24→24 |
| 20 | S49：T 30/30、C 29/30（观察性）；main 已推送，CI 四格见 S49 报告。 | S48：T 30/30、C 29/30（观察性）；main 已推送，CI 四格按最终 SHA 记录。 | 48→50 |
| 21 | CI 0df0e40 四格通过 | CI 四格按最终 SHA 逐格通过 | 15→17 |

新文的事实出处：243 = `tools/count_lwt_lines.py app/log_report.lwt`（S42 用 dict 重构后的实测值）；38/38 = `tools/run_selftest.py`；77 行 = [功能清单](feature-checklist.md)；T 30/30、C 29/30 属于 [S48 盲测](s48-agent-eval.md)。

渲染（`py -3.13 tools/render_ppt.py --out-dir reports/s56-release`，本机 `python` 没有 PIL）：

| 项 | 结果 |
|---|---|
| 导出 | **21/21**，空白页 **0**，PDF 395,571 B |
| 第 10 页图表 | 方差 1975.09（改前同值），方差 / 墨迹比 / 饱和度均排第 1；XML 交叉校验 **12 个数值点** |
| PPT SHA | `32948385…` → `76e4ea39…`（已写入 manifest） |
| 目视 | 7 张改动页 PNG 由**执行窗口（AI）**逐张查看：无溢出、无裁切、无重叠，第 1 页副标题单行容纳。**本人尚未目视**。只保留这 7 张入库：[`reports/s56-release/ppt-pages/`](../reports/s56-release/ppt-pages/) |

`tests/test_ppt_render.py` 只改常量：当前证据优先读 S56，回退 S55、S54；门禁 5/5。

## 3. WP2：CHANGELOG

[CHANGELOG.md](../CHANGELOG.md) 按 Keep a Changelog 1.1.0：中文、新版本在前、ISO 日期、顶部 `[Unreleased]`、Added / Changed / Fixed 分组、文末 compare 链接；不是 `git log` 摘抄。每个数字的出处：

| 数字 | 出处 |
|---|---|
| 0.1.0 日期 2026-11-06 | 提交 `5027860` 的提交时间（S12 main 同步记录） |
| 287 黑盒 | [S12 交付报告](s12-final-delivery.md)：新克隆 287/287 |
| 401 黑盒 | [manifest](delivery-manifest.json) `blackbox_cases` |
| 启动 1.256× / 1.224× | [S44 性能报告](s44-performance.md) 启动表 |
| 纯执行 1.45–2.99× | [S44 优化台账](s44-optimization-ledger.md) P0 最终 after，N=5000：1.454× / 1.552× / 2.992× |
| 38 项原生自测、77 行清单 | [S55 报告](s55-selftest.md)、[功能清单](feature-checklist.md) |
| MCP 3 个工具 | `lwt/mcp_server.py`：`lwt_check` / `lwt_run` / `lwt_profile` |

Fixed 只列产品缺陷：S45 的通道重复投递。测试与工具链修正写在 Changed，并注明“不是产品缺陷”。0.2 单独说明：S42 内部里程碑（`feature/lwt-core-0.2`），包内版本号当时仍是 0.1.0（`a996591` 中 `__version__ == "0.1.0"`），未单独发布，所以**不打 `v0.2.0`**。

同步：README 首段加 CHANGELOG 链接；`tools/build_submission.py` 第 7 项“Git 历史”证据列补“附注标签 v0.1.0 / v0.3.0 + CHANGELOG.md”并重新生成 SUBMISSION.md；`tests/test_delivery_readiness.py` 在已有方法里追加断言（CHANGELOG 存在、含 `## [0.3.0]` 与 `## [Unreleased]`、版本号与 manifest 和 `lwt/__init__.py` 一致、README 首屏链接 CHANGELOG）。

## 4. WP4：人机分工证据表

见 [human-agent-collaboration.md](human-agent-collaboration.md)：六个环节 × 三种角色；第 3 章 3.4 五类决策逐项列本人实际做过的决策（“发起 PR”与“最终评审”如实写未发生）；**11 条**复核抓到 AI 错误的实例（第 10、11 条是标签后发现的），每条都打开原文件核对后给出文件与小节。任务书候选“S48 报告写 16/16、实测 15/16”在全仓找不到对应原文，**未列入**。“是不是 Vibe Coding”的回答：代码层面接近，本人没有逐行审；质量靠可复算证据，决策保留在本人。答辩卡新增一问，runbook 第 7 页降级证据加链接。

## 5. WP3：附注标签与发布

顺序（避开“包里要记录包自身”的循环）：WP1、WP2、WP4 内容全部提交为 X → `v0.1.0` 补打在 `5027860`（已核对 `__version__ == "0.1.0"`）、`v0.3.0` 打在 X → 在 X 之后重建提交包并提交索引 Y → 推送 `main` 与两个标签。标签不能包含记录它自己 SHA 的内容，所以本节与第 6 节的具体 SHA、包与克隆数字在打标签之后追加，不在 `v0.3.0` 指向的提交里。

| 标签 | 标签对象 | 指向提交 | 核对 |
|---|---|---|---|
| `v0.1.0` | `f99b6f851aca` | `5027860efc8a1cce342ca13b1434d7724aeeffc4`（S12 main 同步） | 该提交 `__version__ == "0.1.0"` |
| `v0.3.0` | `0d9e4b3dda6b` | `b551f7eeae0a8093562149026845a011670ca562`（X） | 该提交 `__version__ == "0.3.0"` |

- 两个都是附注标签（`git cat-file -t` 为 `tag`，记录打标签者、时间与说明）；没有打 `v0.2.0`。
- 推送：先 `main`（`40c56a8`），等 `40c56a8` 四格 4/4 后再推两个标签，均走 SSH；`git ls-remote --tags` 能看到 `refs/tags/v0.1.0`、`refs/tags/v0.3.0` 及其 `^{}`。
- 在 Y 上 `git describe --tags` 输出 `v0.3.0-1-g40c56a8`。
- 没有 token，不建 GitHub Release；**标签即发布点**。

**回滚方案（第 6 章 6.2）**：

- 发布有问题时，老师可 `git checkout 1973b54`：S55 最终 tip，四格 CI 4/4。S56 没有改 `lwt/` 运行时代码，语言行为与 `1973b54` 相同，差别只在 PPT 文案、文档、CHANGELOG 和测试常量。
- 需要修复时，从 `v0.3.0` 拉分支修复，再打 `v0.3.1`；**不移动、不删除、不强推**已推送的标签。

## 6. 包、克隆、CI 与自检（打标签之后追加）

### 6.1 发布包与验证

| 项 | 结果 |
|---|---|
| 发布包 | 在 X（= `v0.3.0`）打包，权威数字见[包索引](../reports/s48-defense/package-index.json)：zip `a437ac84cbec…`、**1894 项**；bundle `b660c61fbfaa…`，`git bundle verify` 退出 0；`list-heads` 含 `refs/heads/main = b551f7e`、`refs/tags/v0.1.0`、`refs/tags/v0.3.0`、`HEAD` |
| 包索引提交 Y | `40c56a8`；当时 `check_package_lag` lag=1、outside=0 |
| 干净克隆 | [fresh-clone.json](../reports/s56-release/fresh-clone.json)：clone HEAD `b551f7e` → tip `40c56a8`，6 条命令退出 0，黑盒 **401/401**（127.9 s，总 133.4 s）；另从同一 bundle 克隆，`git tag -l` 为 `v0.1.0 v0.3.0`，`git describe --tags` 为 `v0.3.0` |
| 平台包 | `check_platform_bundle.py --verify-blackbox`：每个 SHA 一致，解压后 **401/401**，`all_pass=true`，`uploaded=false` |
| 401 黑盒（工作区） | `python tools/run_tests.py` **401/401**，165.8 s |
| 单命令全量（本地） | `py -3.13 tools/run_unittest_single.py --out-dir reports/s56-release`：**758 项 OK，退出 0，871.1 s**，Python 3.13.7、Tk 8.6（[证据](../reports/s56-release/unittest-single-command.json)） |
| 快速自检 | `--skip-heavy` 在 `be3e5f5` 上 `all_pass=true`（[selfcheck](../reports/s56-release/selfcheck/)）。第一次运行只因克隆与平台证据尚未提交而在 `git` 步失败，该输出已丢弃，在干净树上重跑 |
| unittest 计数 | `py -3.13` discover **758**，未新增 test 方法 |
| 保护路径 / `lwt/` | 相对 `1973b54` 零差异 |

### 6.2 CI 四格（按精确 SHA，REST check-runs，[ci-cells.json](../reports/s56-release/ci-cells.json)）

| 提交 | 角色 | 触发 | 结论 | 用时（u3.10 / u3.13 / w3.10 / w3.13） |
|---|---|---|---|---|
| `1973b54` | S55 最终 tip、回滚点 | 分支推送 | **4/4 success** | 465 / 268 / 555 / 484 s |
| `d784867` | WP1 PPT 校准 | 分支推送 | **4/4 success** | 376 / 302 / 533 / 290 s |
| `b551f7e` | **`v0.3.0` 指向的提交** | **标签推送** | **0/4，四格 failure** | 475 / 342 / 415 / 384 s |
| `40c56a8` | Y：v0.3.0 的包索引 | 分支推送 | **4/4 success** | 318 / 427 / 575 / 466 s |

最终证据提交自身的四格不写回仓库（写回就会产生新 SHA），在执行交接里报告。

### 6.3 `v0.3.0` 标签提交的 CI 为什么红（如实）

- 现象：工作流 `on: push` 不区分分支和标签，推送标签后 GitHub 对 `b551f7e` 又跑了一次四格，四格全红。作业日志要管理员权限，匿名 API 返回 403，没读到。
- 本地复现：按 `actions/checkout` 对标签的做法造一个检出（`git init`、`fetch --depth=1 +refs/tags/v0.3.0`、detached checkout，没有任何 `refs/heads/*`），`tests.test_submission_bundle` 的 `test_build_produces_verifiable_bundle_and_zip` 失败：`tools/build_submission.py` 的 S48 守卫从 bundle 里读 `refs/heads/main`，读到 `None`，输出 `REF LAG: bundle main None != final tip …` 并返回 2。在同一个模拟检出里用 `py -3.13` 跑全量：**758 项中只有这 1 条失败**（另有 1 项 skip，`-q` 输出不显示名称），日志见 [tag-checkout-unittest.log](../reports/s56-release/tag-checkout-unittest.log)。
- 结论：这是打包工具对 CI 检出环境的假设（默认总有本地 `main`），不是产品缺陷。内容相同、只多一个包索引文件的 `40c56a8` 走分支推送，四格 4/4 绿。
- 裁决（本人，2026-11-17）：**只记录，不发 v0.3.1**；标签不移动、不删除、不强推；今天不改代码。修复方向（留给 v0.3.1）：bundle 里没有 `refs/heads/main` 时改用 bundle 的 `HEAD` 核对最终 tip。
- 对 PPT 的影响：第 21 页“CI 四格按最终 SHA 逐格通过”指 `main` 的最终 SHA；标签触发的那一次是红的，答辩卡已加对应问答。

### 6.4 发布后的包滞后（如实）

包停在 `v0.3.0`。写 X 时我没有把 S56 的标签后证据路径加进打包白名单，所以之后的证据提交让 `check_package_lag` 出现白名单外文件：`reports/s56-release/fresh-clone.{json,md}`、`reports/s56-release/selfcheck/…`，以及本次收口新增的 S56 报告、CI 与全量证据。为了让发布包与标签一致，**不重打包**。截至 S56 收口（`878dc05`），`git diff --stat v0.3.0..HEAD -- lwt app tools tests` 为空；S56.1 热修之后，`tools/run_acceptance_selfcheck.py`、`tools/build_defense_index.py`、`tests/test_delivery_readiness.py` 与 `docs/defense-claims.json` 有改动（见 §8），`lwt/`、`app/` 仍与 `v0.3.0` 零差异。

### 6.5 已知残留

`app/lwt_snake/strategies/test-fc2a5aed8f1246459baf75667cb5b803.lwt` 是 S55 提交 `9f867eb` 误入库的测试产物，`1973b54` 与 `v0.3.0` 中都有；它不在策略目录 `strategy-catalog.json` 里。代码已冻结，本轮没有删除，留给 v0.3.1。

## 7. 未验证项（如实）

- 现场人工 GUI A–E：未执行，`REGISTERED 0/5`、`NOT_RUN`。
- PPT 改动页：只有执行窗口（AI）看过 PNG，本人尚未目视。
- 教学云平台上传：本人动作，`uploaded=false`。
- GitHub Release：没有 token，不建；**标签即发布点**。
- `v0.3.0` 标签提交本身的四格 CI：**失败**（见 §6.3），根因已在本地复现，未修复。
- 教师线下验收：尚未发生。

## 8. S56.1 热修：答辩断言 fresh-clone 恒红（2026-11-17，不发版）

裁决（本人）：E 今天热修；B 授权 SSH 推送 `main`，不推任何标签；控制台允许最小改 `tools/build_defense_index.py`。不改 `lwt/`、`app/`、`tests/cases/`、`slides/`，不改版本号与标签，不重打包，不新增 test 方法。

### 8.1 发现与根因

- 发现：规划复核窗口（AI）实跑 `run_defense_probe.py --all --skip-heavy`，21 条中 20 PASS、1 FAIL，只有 `fresh-clone` 失败。
- 根因：断言命令里写死了 `bb==400`（S48 提交 `682fdd9` 写入）。S54 提交 `ce5be00` 把黑盒加到 401 后，这条断言一直输出 `MISS`。S54 同步计数时，执行窗口漏掉了命令字符串里的这个字面量。
- 为什么一直显示通过：自检的 `_step_defense_probe` 只读 `reports/s53-mutation/defense-probe.json`（2026-11-11 生成，24/24，早于 S54），而且结果里不带记录路径和时间；离线证据台不显示任何状态，页脚还指向 S49 的探针文件。
- 修前复现：`py -3.13 tools/run_defense_probe.py --claim fresh-clone` → `FAIL`，退出码 0，stdout `MISS`。

### 8.2 修复（先红后绿）

| 步骤 | 内容 | 结果 |
|---|---|---|
| 防复发 | `tests/test_delivery_readiness.py` 已有方法 `test_evidence_paths_exist` 内追加：实跑 fresh-clone 断言命令，stdout 须含 `OK` | 修前红：`'OK' not found in 'MISS\n'`；修后绿 |
| 断言 | `docs/defense-claims.json` 只改 fresh-clone：期望值读 `docs/delivery-manifest.json` 的 `blackbox_cases`，输出带实际数字与证据路径；`evidence_path` 改指 `reports/s56-release/fresh-clone.json`；claim 文本不动 | `OK blackbox=401/401 reports/s56-release/fresh-clone.json` |
| 自检 | `_step_defense_probe` 优先读 `reports/s56-hotfix/defense-probe.json`；结果带 `source`、`generated_at_utc`，读到旧记录时标 `fallback_to_older_record` | 见 §8.4 |
| 证据台 | `tools/build_defense_index.py` 每条断言加“记录状态（非现场）”列，显示状态与 `recorded_at_utc`；页脚写出记录路径与生成时间，并注明它是历史记录 | fresh-clone 显示 `PASS · 2026-11-17T02:26:26Z` |

### 8.3 留证（[defense-probe.json](../reports/s56-hotfix/defense-probe.json)）

- `--all --skip-heavy`：**21/21 PASS**。
- `--claim blackbox --claim determinism --merge` 写入同一文件：**23/23 PASS**，生成于 2026-11-17T02:32:29Z。blackbox `passed=401 failed=0 total=401`（148.2 s）；determinism 46 项 × 10 次，`stable=True failures=0`。
- `unittest` 重型断言**没有重跑**：它会改写 S54 证据和对应门禁。全量证据引用 S56 本地运行 [unittest-single-command.json](../reports/s56-release/unittest-single-command.json)：`py -3.13`，758 项 OK，871.1 s。证据台上这一条显示 `UNRUN`。

### 8.4 门禁与边界

- `py -3.13` discover **758**（未新增 test 方法）；`tests.test_delivery_readiness`、`tests.test_doc_consistency` 42 项 OK；完整性 401 cases、498 links、401 referenced；Markdown 链接 0 断链；compileall 通过；`build_defense_index.py --check` up to date。
- `git diff 878dc05 -- lwt app tests/cases slides` 为空。
- 快速自检 `--skip-heavy` 在提交后的干净树上运行，输出到系统临时目录，不写回仓库；结果见执行交接。
- 未做：平台提交包仍是 `v0.3.0` 的包，里面是修前的 `docs/defense-claims.json`（fresh-clone 写死 400）、旧自检与旧证据台；本轮不重打包、不打标签。
