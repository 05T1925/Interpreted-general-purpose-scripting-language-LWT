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

见 [human-agent-collaboration.md](human-agent-collaboration.md)：六个环节 × 三种角色；第 3 章 3.4 五类决策逐项列本人实际做过的决策（“发起 PR”与“最终评审”如实写未发生）；**9 条**复核抓到 AI 错误的实例，每条都打开原文件核对后给出文件与小节。任务书候选“S48 报告写 16/16、实测 15/16”在全仓找不到对应原文，**未列入**。“是不是 Vibe Coding”的回答：代码层面接近，本人没有逐行审；质量靠可复算证据，决策保留在本人。答辩卡新增一问，runbook 第 7 页降级证据加链接。

## 5. WP3：附注标签与发布

顺序（避开“包里要记录包自身”的循环）：WP1、WP2、WP4 内容全部提交为 X → `v0.1.0` 补打在 `5027860`（已核对 `__version__ == "0.1.0"`）、`v0.3.0` 打在 X → 在 X 之后重建提交包并提交索引 Y → 推送 `main` 与两个标签。标签不能包含记录它自己 SHA 的内容，所以本节与第 6 节的具体 SHA、包与克隆数字在打标签之后追加，不在 `v0.3.0` 指向的提交里。

**回滚方案（第 6 章 6.2）**：

- 发布有问题时，老师可 `git checkout 1973b54`：S55 最终 tip，四格 CI 4/4。S56 没有改 `lwt/` 运行时代码，语言行为与 `1973b54` 相同，差别只在 PPT 文案、文档、CHANGELOG 和测试常量。
- 需要修复时，从 `v0.3.0` 拉分支修复，再打 `v0.3.1`；**不移动、不删除、不强推**已推送的标签。

## 6. 包、克隆、CI 与自检

打标签之后追加。

## 7. 未验证项（如实）

- 现场人工 GUI A–E：未执行，`REGISTERED 0/5`、`NOT_RUN`。
- PPT 改动页：只有执行窗口（AI）看过 PNG，本人尚未目视。
- 教学云平台上传：本人动作，`uploaded=false`。
- GitHub Release：没有 token，不建；**标签即发布点**。
- 教师线下验收：尚未发生。
