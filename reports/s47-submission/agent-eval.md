# S45 Agent 盲测结果（客观判分）

> Blind eval must be run by the user in a new context-free session. NOT_RUN means no submission was found; it is never reported as a pass.

- 生成时间（UTC）：2026-11-09T08:26:14Z
- 题目总数：6；已提交：6；通过：5
- 总判定：**PARTIAL**
- pass@1：0.8333333333333334

| 题目 | 状态 | 检查 |
|---|---|---|
| dict-word-frequency-topk | PASS | check_exit_zero=PASS, no_forbidden_constructs=PASS, exit_code_matches=PASS, stdout_matches=PASS, deterministic_bytes=PASS |
| throw-finally-cleanup | PASS | check_exit_zero=PASS, no_forbidden_constructs=PASS, exit_code_matches=PASS, stdout_matches=PASS, deterministic_bytes=PASS |
| producer-consumer-channel | FAIL | check_exit_zero=PASS, no_forbidden_constructs=PASS, exit_code_matches=PASS, stdout_matches=FAIL, deterministic_bytes=PASS |
| module-record-dict-mix | PASS | check_exit_zero=PASS, no_forbidden_constructs=PASS, exit_code_matches=PASS, stdout_matches=PASS, deterministic_bytes=PASS |
| each-snapshot-alias | PASS | check_exit_zero=PASS, no_forbidden_constructs=PASS, exit_code_matches=PASS, stdout_matches=PASS, deterministic_bytes=PASS |
| cli-args-text-processing | PASS | check_exit_zero=PASS, no_forbidden_constructs=PASS, exit_code_matches=PASS, stdout_matches=PASS, deterministic_bytes=PASS |

## 判分口径

- 只做客观检查：`--check` 退出 0、退出码与 stdout 字节匹配、多次运行逐字节一致、未使用禁止构造；不评价代码风格。
- `NOT_SUBMITTED` 表示没有提交目录；`NOT_RUN` 表示盲测未执行，不填 pass@1。
