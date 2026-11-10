# S48 Agent 盲测与指南消融（主口径）

> 预注册协议：[`docs/agent-eval/tasks-v2.json`](agent-eval/tasks-v2.json)（**任何 S48 会话开始前冻结**）。v1（`tasks.json`）保留为历史：它的首轮 5/6 与事后澄清单题复跑**不并入**本报告统计。
> 基线：`d9daedd`（任务书裁决 A：在 `main` 上工作）。执行窗口只准备任务与判分器；60 个样本全部由**独立无上下文子代理会话**完成。

## 1. 设计

| 项 | 值 |
|---|---|
| 题目 | 6 道（词频 top-k、throw/finally、通道生产消费、模块+record+dict、each 浅快照与别名、CLI 参数+文本） |
| 组 | **T（完整）**：语言规范 + 开发指南 + SKILL + 并发契约卡；**C（消融）**：仅语言规范 |
| 样本 | 每组每题 **n=5**，共 **60 个独立会话** |
| 隔离 | 每题每个样本一个全新 detached worktree；worktree 内移走 `docs/agent-eval`（含期望输出）、`tests/`、`app/`、`reports/`、`tools/`、`.github`；只发题面卡（`TASK.md`，无期望输出）+ 该组允许文档 + 隔离规则 |
| 判分 | `tools/run_agent_eval.py --tasks tasks-v2.json --group T\|C --samples 5`：`--check`、退出码、stdout 字节、5 次逐字节一致、禁用构造、多模块扫描；只判客观项 |
| 统计 | `tools/agent_eval_stats.py`：Wilson 95% CI、pass@k = 1 − C(n−c,k)/C(n,k)；单测用独立公式复算 |

**随机化**：批次按样本序号推进，T 与 C 交错（T1→T2→…→T5，C1→C3→…→C5），每批 6 题并发；会话开始时间与依据见各样本的 `report.md`。

## 2. 结果（主口径）

| 组 | 样本 | 通过 | pass@1 | Wilson 95% CI | pass@5 |
|---|---:|---:|---:|---|---:|
| T（完整） | 30 | 30 | **1.000** | [0.886, 1.000] | 1.000 |
| C（仅规范） | 30 | 29 | **0.967** | [0.833, 0.995] | 0.967 |

**T − C = +0.033**，近似 95% 区间 **[−0.031, +0.098]**（含 0）。

分题（T / C 通过数，各 5 样本）：

| 题 | T | C |
|---|---:|---:|
| cli-args-text-processing | 5/5 | 5/5 |
| dict-word-frequency-topk | 5/5 | 5/5 |
| each-snapshot-alias | 5/5 | 4/5 |
| module-record-dict-mix | 5/5 | 5/5 |
| producer-consumer-channel | 5/5 | 5/5 |
| throw-finally-cleanup | 5/5 | 5/5 |

## 3. 失败分析

- **C 组唯一失败**：`each-snapshot-alias` sample-4，实际 `iterations 3\n9\ntrue\n`，期望 `iterations 3\nb.value 9\nb == alias true\n`。题面明确要求带标签的输出行，判为 **OUTPUT_FORMAT_MISMATCH**，不是语言语义错误。
- T 组 0 失败。

## 4. 指南修订闭环

**未触发修订。** 没有 T 组失败；唯一 C 组失败是题面已写明的输出格式，不是指南/Skill 缺事实。按 S48 任务书“若 T 组也无差异，如实写‘本样本下未测得增量’，不制造改动、不夸大结论”，本轮不做指南改动。

这同时是一个**诚实的天花板效应**：6 道题都较小，规范本身足以完成，额外指南的增量在这组样本上不可检出。

## 5. 与 S47 的关系

| 轮次 | 协议 | n/题 | 结果 | 用途 |
|---|---|---:|---|---|
| S47 首轮 | v1（throw 消息未定） | 1 | 5/6 = 0.833 | 历史，暴露题面缺陷 |
| S47 澄清复跑 | v1 单题 | 1 | 1/1 | 单列，不并入 |
| **S48 主口径** | **v2 冻结** | **5** | **T 30/30、C 29/30** | 本报告，含区间与消融 |

## 6. 隔离与偏差（如实）

- 每个样本的 worktree 在创建后核验：`docs/agent-eval/tasks.json`、`tests/`、`tools/` 均不存在；判分前由执行窗口统一收集到 `docs/agent-eval/submissions-v2/<group>/<task>/sample-N/`。
- 60 份 `report.md` 均含隔离声明；`reports/s48-defense/session-receipts.json` 记录每份的基线 SHA、文件清单与报告 SHA-256。
- **偏差**：少数报告披露了证据采集时的 `/tmp` 重定向或仅列目录名的 `ls`；没有报告声明读取过 `lwt/` 源码、`tests/`、`app/` 或任何期望输出。这些偏差没有被用来判定任务正确性。
- **无法独立验证**：子代理的“未读”是自报；执行窗口能验证的是 worktree 构造与提交产物。这是本设计的边界，不写成“已证明隔离”。

## 7. 限制

- **观察性对照，不是因果证明**：模型与路由未观测，单平台、6 道小题，两组都接近上限。
- n=5/题 的 Wilson 区间很宽；pass@5 为 0.967/1.000，不能外推到其他题集或模型。
- 未做跨模型复现；未做人工二次判分（判分器只查客观项）。
