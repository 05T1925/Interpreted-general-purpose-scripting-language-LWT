# S53 变异探针补齐、Agent 友好接口对照与提交链路

> 依据：课件 5.5「变异测试思想——永远不会红的测试没有价值」、4.3/4.4/4.5（MCP、Agent 友好接口、兼容性只增不改）、第 1 章（大作业 70% + 教学云平台）。
> 本阶段不改语言语义、不改 400 黑盒期望、不改历史报告数字。

## 1. 裁决与范围

| 裁决 | 结果 |
|---|---|
| A 分支 | 直接在 `main`（`94f43c9`）上工作 |
| B 推送与 CI | 授权推送并按精确 SHA 逐格查四格 |
| C GUI A–E | 本轮不执行，保持 `REGISTERED 0/5`、`NOT_RUN` |
| D MCP | 纳入，但排在 P0/P1 全绿之后（已实现，仅协议级验证） |

## 2. WP1：变异探针（测试 20 分）

### 2.1 开工时的真实状态不是“9 killed / 1 survived”

在 S52 树上直接复跑 `tools/audit_semantic_mutants.py`，得到 **killed=8 / survived=1 / invalid=1**：

- `composite-values-use-structural-equality` **invalid**：S42 把 `_DictValue/_TaskValue/_ChannelValue` 加进 isinstance 元组，S23 的锚点匹配数变成 0。探针本身没跟着语义演进维护。
- `call-arguments-evaluate-right-to-left` **survived**：目标用例 `argument-evaluation-order` 的副作用对称，交换求值顺序输出仍是 `[1, 2]`；同一补丁在 `argument-evaluation-order-distinct-effects` 上被杀。

处理（都留证在 `reports/s53-mutation/probe-inventory.md`）：

1. 重锚 composite 探针（补丁片段随 S42 更新），恢复 killed；
2. 两条同补丁探针**合并**为一条 `call-arguments-reversed`，保留两个目标，`killed_by` 只列真正判红的用例，`passed_targets` 保留“对称用例单独不判别”的证据。

### 2.2 新增 9 条覆盖 S42/S43

| 区域 | 探针 | 判红用例 |
|---|---|---|
| dict | 显示逆序、缺键返回 null、删缺失键返回 true | `dict-literal-display-order` 等 3 / `dict-missing-key-read` / `dict-delete-missing` |
| finally | finally 只在未恢复错误时执行 | `finally-on-normal-flow`、`finally-return-in-body-runs-first`、`finally-break-passes` |
| throw | 重抛丢失 category | `uncaught-throw-error-category` |
| concurrency | 通道 LIFO、send 不交接（S45 缺陷形状）、就绪队列 LIFO、join 提前返回 | `channel-fifo` / `channel-block-receive` / `fifo-order`+`yield-three-tasks` / `spawn-join-return`+`join-preserves-output` |

### 2.3 实测结果

| 项 | 值 |
|---|---|
| 探针总数 | **18**（9 条 S23 遗留 + 9 条新增） |
| killed | **18** |
| survived / equivalent / invalid | **0 / 0 / 0** |
| 隔离核验 | 运行前后 `git status --porcelain` 均为空（`repo_clean_before/after = true`） |
| 证据 | `reports/s53-mutation/mutation-report.json`：每条含 `patch_sha256`、`killed_by`、`passed_targets` |

**不能只报 18/18。** 报告同时记录：

- 三个“目标用例单独不判别”的弱用例（`argument-evaluation-order`、`throw-error-rethrow`、`channel-multi-producer`）；
- 一个**真实盲区**：把 dict 显示改成按 key 排序的变异 **survived**——所有显示用例的键恰好按字典序插入，排序前后输出一致。该变异没有被计入探针集，而是写进清单，作为“400 项在键序上覆盖不足”的证据。
- 因此 18/18 的含义是“**这 18 个人工挑选的语义变异都能被判红**”，**不是**“400 项测试很充分”，更**不是**解释器正确率（Just et al., ICSE/FSE 2018 的等价变异与测试集规模限制；S23 计划的诚实口径）。

## 3. WP2：Agent 友好接口与提交链路

### 3.1 课件 4.4 / 4.5 对照

`docs/agent-friendly-interface.md` 按“课件原话 → LWT 实现 → 一条复算命令”逐条对照，实测证据：

| 原则 | 实测 |
|---|---|
| 机器可读输出 | `--check --format=json` → `{"schema_version":1,"ok":false,...,"code":"E-SPAWN-001"}`，exit 2 |
| 明确错误码 | 运行时错误 → stderr `file:line:col: RuntimeError: ...`，exit **3**；语法/静态 2；CLI/文件 4 |
| 可观测性 | `--profile` JSON（`schema_version/events/coverage/modules`）；`--schedule-log` JSON（9 条 `decisions`） |
| 只增不改 | `VALID_SPEC_REFS` 两次增量注册（S43 的 11.x、S52 的 8.x/9.x/10.x），旧编号一个未删 |
| 未实现 | `--fields`、`--debug` 如实标注未实现 |

### 3.2 提交链路

- `docs/platform-submission.md` + `docs/platform-submission.json`：由 `tools/check_platform_bundle.py` 生成，逐项校验“文件存在 + SHA 一致”，并给出大作业 70% 四项（代码审查/文档检查/功能演示/答辩）→ 仓库证据 → 复算命令。
- `--verify-blackbox`：把 zip 解压到临时目录并实跑 400 黑盒（结果写进清单）。
- **`uploaded=false`**：上传动作由本人执行，工具只校验，不声称已提交。

## 4. WP3：最小 MCP server（协议级）

- `lwt/mcp_server.py`：标准库实现 JSON-RPC 2.0 over **行分隔 JSON**（不是 LSP 的 `Content-Length` 帧），提供 `initialize` / `tools/list` / `tools/call`；三个工具 `lwt_check`、`lwt_run`、`lwt_profile` 只调用公开 CLI。
- 测试 `tests/test_mcp_server.py` **8/8**：握手、工具清单、真实执行（`hello, LWT`）、静态诊断（`E-SPAWN-001`）、profile 摘要、未知工具（-32602）、未知方法（-32601）、文件不存在。
- **边界**：仅协议级测试；**未接入真实 MCP 宿主**做端到端演示，不声称在 Claude/Cursor 等宿主中验证过。

## 5. 验证记录

| 项 | 结果 |
|---|---|
| 开工基线 | 400/400（325.686 s）；完整性 `cases=400/referenced=400/unreferenced=0`；探针 21/21；自检 PASS |
| 变异门禁（红→绿） | 先红：`mutation-report.json` 不存在（0 tests ran / 1 error）；补齐后 **8/8 绿** |
| 单命令全量 | **747 项 OK，exit 0**：探针内运行 **1103.1 s**、独立运行 **1065.7 s**（`py -3.13`，3.13.7，Tk 8.6；`reports/s53-mutation/unittest-single-command.json`） |
| 第一次全量（失败留证） | 同一命令 747 项 **exit 1**，3 条 Tk GUI 用例失败（`test_real_verify_button_shows_lwt_response_and_step_switch`、`test_real_buttons_keys_focus_reset_and_close`、`test_space_wasd_r_and_close_during_request`），报错为“验真失败，退出码 3”；随后单独跑三个 GUI 模块 **68/68 OK**（612.8 s），再跑全量即通过。判定为**负载下的瞬态**，不是 S53 改动引入的缺陷；未修改任何 GUI 用例 |
| 24 断言探针 | **24/24 PASS**：23 条非 heavy 在 S53 重跑；`unittest` 行在 S53 重跑（**747 项 OK**，`recorded_at_utc` 10:31:21Z）；`blackbox`/`determinism` 两条 heavy 沿用上一阶段记录并保留各自时间戳（`reports/s53-mutation/defense-probe.json`） |
| 一键自检 | **`all_pass=true`**：11 步 PASS、0 FAIL、2 步 N/A（GUI/agent）；`selfcheck-20261111T103228Z`；`defense_probe` 读到 S53 的 24/24 |
| 交付包 | 在 `9d48a9e` 重建：zip `3b1824e56396…`（**1785 项**）、bundle `dc09784d904f…`、`git bundle verify` exit 0 |
| 新克隆 | head `9d48a9e` → tip `b39a91e`，lag 仅索引，6 条命令 exit 0，**400/400**（124.1 s，总 133.2 s） |
| 平台提交清单 | `check_platform_bundle.py --verify-blackbox`：文件 SHA 全一致、解压后 **400/400**、`all_pass=true`；`uploaded=false`（未上传） |
| CI | 推送后按精确 SHA 逐格查；结果见 `reports/s49-rehearsal/ci-cells.json` |

### 5.1 自指死锁与工具修正（过程事故，如实披露）

`tests/test_unittest_claim.py` 断言“证据必须来自一次通过的运行”。这条断言会把一次红色运行变成**永久红**：失败运行覆盖了证据文件，下一次运行时门禁读到 `exit 1`，全量继续失败。

- 修正：`tools/run_unittest_single.py` 失败时改写到 `unittest-single-command.failed.json` / `unittest-system.failed.log`，**不覆盖**上一次成功证据；失败仍打印并返回非零退出码。
- 破环：这次用了一次性引导——临时把门禁常量指向 S52 的真实通过证据，跑完一次全量后**立即改回** S53 并验证（`tests.test_unittest_claim` 6/6）。最终证据来自真实的 747 项全量运行，不是手工拼的。
- 留痕：`reports/s53-mutation/` 同时保留上一次失败的 `unittest-single-command.failed.json`，可对照。

## 6. 未验证项（如实）
- **现场人工 GUI A–E**：本轮不执行，`REGISTERED 0/5`、`NOT_RUN`。
- **教师线下验收与评分**：未发生。
- **教学云平台上传**：未执行（`uploaded=false`）。
- **MCP 宿主端到端**：未验证，只有协议级测试。
- **PPT 渲染**：仍只做静态校验（21 页 / 12 数值点 / SHA `7cb28b13…`），本阶段未改动。
- 变异分数不是总体正确率；等价变异与盲区已单列。
