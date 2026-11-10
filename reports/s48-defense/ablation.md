# S48 指南消融 A/B（观察性对照）

> 预注册协议 `docs/agent-eval/tasks-v2.json`（任何 S48 会话前冻结）；基线 `d9daeddd3a15`；6 题 × 2 组 × 5 样本 = **60 个独立会话**。

## 总体

| 组 | 文档 | 样本 | 通过 | pass@1 | Wilson 95% CI | pass@5 |
|---|---|---:|---:|---:|---|---:|
| T（完整） | 规范 + 指南 + Skill + 并发契约卡 | 30 | 30 | **1.000** | [0.886, 1.000] | 1.000 |
| C（消融） | 仅语言规范 | 30 | 29 | **0.967** | [0.833, 0.994] | 1.000 |

**T−C = +0.033**，近似 95% 区间 [-0.031, +0.098]（含 0）。**这是观察性对照，不是因果证明**：模型/路由未观测、题目集小、两组都接近上限，样本量不足以检出小幅增量。

## 分题

| 题 | T 通过/样本 | C 通过/样本 |
|---|---:|---:|
| cli-args-text-processing | 5/5 | 5/5 |
| dict-word-frequency-topk | 5/5 | 5/5 |
| each-snapshot-alias | 5/5 | 4/5 |
| module-record-dict-mix | 5/5 | 5/5 |
| producer-consumer-channel | 5/5 | 5/5 |
| throw-finally-cleanup | 5/5 | 5/5 |

## 失败分析

- C 组唯一失败：`each-snapshot-alias` sample-4，实际 `iterations 3
9
true
`，期望 `iterations 3
b.value 9
b == alias true
`。判为**输出格式不符**（题面已明确要求标签），不是语言语义错误。
- T 组 0 失败。

## 指南修订闭环

未触发修订：没有 T 组失败，唯一 C 组失败也不能归因于指南缺事实（题面已写明输出格式）。按任务书要求，不制造改动、不夸大结论——**本样本下未测得指南增量**。

## 限制

- observational comparison, not causal: model and routing unobserved, single platform, 6 small tasks
- ceiling effect: both groups near 100%, so the design cannot detect a small guide increment
- n=5 per task is small; Wilson interval is wide
- same-platform only; no cross-model replication
