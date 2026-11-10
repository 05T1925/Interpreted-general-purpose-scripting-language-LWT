# S48 执行报告：证据链自洽、指南有效性实证与现场验收就绪

**基线未经主窗口复核（S43/S44/S45/S46/S47）。** 按任务书裁决 A 直接在 `main` 上工作（S47 已推 main，HEAD `5a61ab9`）；裁决 B1：冻结题面 v2，T/C 两组 × 5 样本共 60 个独立会话；裁决 C：用户本人执行现场 GUI A–E，执行窗口只交工具与清单；裁决 D：授权推送 main 并查精确 SHA 的 CI 四格。未打标签。

## 1. 工作包与状态

| WP | 内容 | 状态 |
|---|---|---|
| WP0 | 三处 P0 修补：bundle 自引用、当前状态文档矛盾、提交包可达性 | 完成（先红后绿留证） |
| WP1 | 指南消融 A/B + 60 会话盲测 + Wilson/pass@k + 失败分析 | 完成（T 30/30、C 29/30） |
| WP2 | 现场人工 GUI A–E 验收包 + 登记工具 + 自检步骤 | 工具完成；人工状态 **NOT_RUN** |
| WP3 | 24 条可质询断言 + 现场探针 + 离线证据台 HTML | 完成（probe 结论见 §5） |
| WP4 | 报告、manifest、PPT 20→21、清单/演示/答辩、自检、回归 | 完成，见 §6–§8 |

## 2. WP0：三处 P0 修补

### WP0-1 bundle 自引用

- 问题：S47 的 bundle 截止 `224e4ae`，最终 tip `5a61ab9`，落后 2 笔；旧流程没有校验“bundle 是否包含最终 tip”。
- 修补：`tools/build_submission.py` 增加 `--final-tip`、`--allow-ref-lag`、`--package-index`。打包后解析 `git bundle list-heads` 的 `refs/heads/main`，与最终 tip 比较；不一致时打印 `X..Y` 的 log 并以退出码 2 拒绝，除非显式 `--allow-ref-lag`。
- 自引用逃逸：bundle 无法包含“记录 bundle 的那一笔”。在内容 tip `76bb4fb` 打包，提交 `reports/s48-defense/package-index.json`（`bundle_ref_sha=76bb4fb`、`final_tip_sha`、`diff_whitelist=[索引文件]`），得到 `dcb0b1e`。
- 验证：`tools/verify_fresh_clone.py --package-index` 记录 clone HEAD `76bb4fb`、工作区 HEAD `dcb0b1e`、`lag_paths=['reports/s48-defense/package-index.json']`、`lag_ok=true`、6 条命令 exit 0、黑盒 **400/400**（186.2 s，总 159.5 s）。首版验证曾把 `final_tip` 取成索引里的建包时 SHA，导致 lag 恒为空；已修正为对比工作区 HEAD，并在报告中如实保留这次自纠。

### WP0-2 当前状态文档语义矛盾

- 修正：`docs/defense-qa-card.md` 的“Agent 盲测 = NOT_RUN”改为 S47 5/6 + S48 主口径；`docs/agent-eval/README.md` §5 改为“已执行”；`docs/demo-script.md` 移除过期的未执行与分支状态表述；`SUBMISSION.md` 的包路径改为入库索引。
- 只读证据：`reports/s47-submission/agent-eval.json` 的过期 `note` 不改写，新增 `reports/s48-defense/agent-eval-s47-derivation.json` 记录原始 overall 与修正说明，并在 SUBMISSION 指向。
- 测试闭环：`tests/test_doc_consistency.py` 新增 `SemanticStatusConsistencyTests`——manifest 记录 PARTIAL/PASS 时，当前状态文档不得再把 NOT_RUN 作为当前结论；交付面文档不得出现“未推送”；`submission_bundle` 必须指向入库索引。**先红 3 项，修完转绿 15/15**。历史段落按行级标记（日期、“当时”、“本阶段”、路线图阶段行）豁免。

### WP0-3 提交包可达性

`SUBMISSION.md` 第 7 项改为“包由 `tools/build_submission.py` 生成于 `dist/`，索引见 `reports/s48-defense/package-index.json`”，说明 `dist/` 不入库的原因，并加“离线提交件需现场生成或携带 dist/”提示。`manifest.submission_bundle` 指向索引。

## 3. WP1：指南消融与 60 会话盲测

预注册协议 `docs/agent-eval/tasks-v2.json`（任何 S48 会话前冻结）。每组每题 n=5：

| 组 | 文档 | 样本 | 通过 | pass@1 | Wilson 95% CI | pass@5 |
|---|---|---:|---:|---:|---|---:|
| T（完整） | 规范 + 指南 + Skill + 并发卡 | 30 | 30 | **1.000** | [0.886, 1.000] | 1.000 |
| C（消融） | 仅规范 | 30 | 29 | **0.967** | [0.833, 0.995] | 0.967 |

**T − C = +0.033**，近似 95% 区间 **[−0.031, +0.098]**（含 0）。

- 唯一失败：C 组 `each-snapshot-alias` sample-4 输出 `iterations 3\n9\ntrue\n`，题面要求带标签的 `b.value 9` / `b == alias true`，判为 **OUTPUT_FORMAT_MISMATCH**，不是语言语义错误。
- **未触发指南修订**：没有 T 组失败，C 组失败也不能归因于指南缺事实。按任务书要求不制造改动，如实写“本样本下未测得增量”。
- 诚实边界：两组接近上限（天花板效应）、n=5/题、单平台；这是观察性对照，不是因果证明。

详见 [S48 Agent 盲测报告](s48-agent-eval.md)、`reports/s48-defense/ablation.{json,md}`、`session-receipts.json`（60 条）。

## 4. WP2：现场 GUI A–E

- `docs/gui-acceptance-kit.md`：A 语义实验室、B 日志工作台、C LWT Snake、D S41 只读查看器、E PPT 逐页播放 + 桌面无遮挡/输入归属；每项给出启动命令、步骤、预期、失败判据、截图命名与预计耗时；沿用 S21“遮挡或输入不可归因立即停止”规则。
- `evidence/gui/`（入库目录）+ `tools/register_gui_evidence.py`：只登记文件、字节数、SHA-256、时间戳与缺项；**不自动判 PASS**。
- 当前状态：`reports/s48-defense/gui-acceptance.json` = **REGISTERED 0/5**，A–E 全部 `NOT_RUN`；`PASS` 必须由用户本人现场确认。自检包 `gui_evidence` 步骤只报计数。

## 5. WP3：可质询证据台

- `docs/defense-claims.json`：**24 条**断言，覆盖版本/`--help`/hello/`--check`、400 黑盒、完整性、unittest、46×10、S11 性能、S44 启动与纯执行、S46 clean/mutant、S48 盲测与区间、包索引/新克隆、DAP 拒绝、差分等价、非 spawn 不加载并发、compare_perf、PPT 21 页/12 点、文档一致性、调度记录→重放 round-trip。
- `tools/run_defense_probe.py`：`--claim <id>` 单条、`--random N` 随机抽问、`--all` 全量（`--skip-heavy` 跳过三条长命令）；逐条记录真实退出码与 stdout/stderr，失败写 **FAIL**，不写“基本通过”。
- 结果：非 heavy **21/21 PASS**；**全量 24/24 PASS**（heavy 三条也真实执行）。
- 诚实记录：全量首跑时 `unittest` 在 Tk 用例 `test_space_wasd_r_and_close_during_request` 上超时（单独跑 3/3、独立全量 695/695 均通过），判为事件循环在高负载下的抖动；随后用系统 Python 单独重跑该断言并 `--merge` 合并，逐行保留 `recorded_at_utc`，不是把失败改成通过。`--merge` 的语义是“只替换本次重跑的 id”，报告与工具均写明。
- `docs/defense-index.html`：单文件、无 CDN/无外部字体、浅深色自适应；按交付物分组，命令可一键复制，打开即用。

## 6. 收口计数与 PPT

| 项 | 值 |
|---|---|
| unittest | **695**（S47 的 677 + 文档语义 4 + 统计/多样本判分 8 + 交付结构 6） |
| PPT | **21 页**（20→21，新增「指南消融与现场可质询验收」；旧第 10 页原生图表 **12 数值点未变**） |
| PPT SHA-256 | `0be34afacb4b889e...`（旧 `90369685...`） |
| manifest | `unittest_count=685`、`ppt_pages=21`、`submission_bundle=reports/s48-defense/package-index.json`、`agent_eval_status` 含 n 与 Wilson 区间 |
| 文档一致性 | 16 项（新增 S48 报告计数一致性，先红后绿） |

## 7. 保护数据

`git diff 5a61ab9..HEAD -- <29 个保护路径>`（S11/S42/S43/S44/S45/S46/S47 原始证据、`tests/cases/**`、两个既有应用）为空；S48 只写 `reports/s48-defense/`、`docs/agent-eval/submissions-v2/`、`evidence/gui/`、`dist/`（忽略）。历史阶段报告的旧数字未改。

## 8. 未验证项（如实）

- **现场人工 GUI A–E**：`REGISTERED 0/5`，全部 `NOT_RUN`；工具与清单已就绪，执行必须由用户本人在无遮挡桌面完成。
- **教师线下验收**未发生。
- 盲测为**观察性**对照：模型/路由未观测、6 道小题、n=5/题、单平台；T−C 区间含 0，不能写成“指南有效/无效”的因果结论。
- 子代理“未读禁止目录”是自报；执行窗口能验证 worktree 构造与产物，不能证明其内部注意力。少数报告披露 `/tmp` 重定向或仅列目录名的 `ls`，已记录在 `docs/s48-agent-eval.md`。
- Python 3.10/Linux 本地未跑（由 CI 覆盖）；CI 结论按精确 SHA 记录。

## 9. 提交与 CI

- 提交序列与最终 SHA：见本报告所在提交；`git log --oneline 5a61ab9..HEAD` 可复核。
- CI：推送后按精确 SHA 查询四格，结论单独记录，不把“推送成功”当“CI 通过”。
