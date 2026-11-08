# S45 Agent 盲测结果（客观判分）

> Blind eval must be run by the user in a new context-free session. NOT_RUN means no submission was found; it is never reported as a pass.

- 生成时间（UTC）：2026-11-08T15:00:33Z
- 题目总数：6；已提交：0；通过：0
- 总判定：**NOT_RUN**
- pass@1：未执行（无提交）

| 题目 | 状态 | 检查 |
|---|---|---|
| dict-word-frequency-topk | NOT_SUBMITTED | 未提交 |
| throw-finally-cleanup | NOT_SUBMITTED | 未提交 |
| producer-consumer-channel | NOT_SUBMITTED | 未提交 |
| module-record-dict-mix | NOT_SUBMITTED | 未提交 |
| each-snapshot-alias | NOT_SUBMITTED | 未提交 |
| cli-args-text-processing | NOT_SUBMITTED | 未提交 |

## 判分口径

- 只做客观检查：`--check` 退出 0、退出码与 stdout 字节匹配、多次运行逐字节一致、未使用禁止构造；不评价代码风格。
- `NOT_SUBMITTED` 表示没有提交目录；`NOT_RUN` 表示盲测未执行，不填 pass@1。
