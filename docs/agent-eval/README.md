# Agent 盲测协议（S45 WP3）

> 目的：验证一个**没有本仓库上下文**的新 Agent，只读公开文档后能否独立写出正确的 LWT 程序。执行窗口只准备题目与判分器；**盲测必须由用户在新的无上下文会话中执行**，执行窗口不得用自测冒充 pass@1。

## 1. 题目与判分器

- 题目规格：`docs/agent-eval/tasks.json`（6 题，覆盖 dict top-k、throw/finally、生产者/消费者通道、模块+record+dict、each 浅快照与别名、CLI 参数+文本处理）。
- 判分器：`python tools/run_agent_eval.py`。只做客观检查：`--check` 退出 0、退出码与 stdout 字节精确匹配、多次运行逐字节一致、不含禁止构造。不评价代码风格。

## 2. 盲测会话的隔离规则（交给盲测 Agent）

1. 你只能阅读：`docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/concurrency.md`，以及你被分配的那一道题目（`docs/agent-eval/tasks.json` 中对应条目）。
2. 不得阅读：`lwt/` 源码、`tests/cases/`、`app/`、`docs/agent-eval/submissions/` 下的其它题目，或任何历史阶段报告中的答案/期望。
3. 只能通过公开入口 `python -m lwt` 运行程序；不得用 Python `eval`/`exec` 执行 LWT 源码，也不得改用其他语言直接生成输出。
4. 只使用规范已定义的能力；不要引入浮点、类、闭包、`sleep`/锁/异步等非目标特性。
5. 每个任务写完后先 `python -m lwt --check <文件>`，再运行并核对 stdout 与退出码；最后如实报告命令与结果。

## 3. 提交格式

把每个任务的解答放在：

```text
docs/agent-eval/submissions/<task-id>/program.lwt     # 单文件任务
docs/agent-eval/submissions/<task-id>/main.lwt        # 需要模块时（另加 lib.lwt 等）
```

单文件任务优先用 `program.lwt`；判分器先找 `program.lwt`，再找 `main.lwt`。

## 4. 判分与记录

```powershell
python tools/run_agent_eval.py
```

输出 `reports/s45-acceptance/agent-eval.json` 与 `.md`，包含每题逐项检查与总判定：

- `ALL_PASS`：全部提交且全部通过；
- `PARTIAL`：有失败项（失败项需反推指南/Skill 修订）；
- `NOT_RUN`：没有任何提交（**不能**写成通过）。

若跑 n 个样本、c 个通过，`pass@k = 1 - C(n-c,k)/C(n,k)`；单样本即 pass@1。

## 5. 当前状态

**已执行（S47 首轮 5/6，n=1/题；S48 起用冻结题面 v2 做多样本与 T/C 消融，见 `docs/s48-agent-eval.md`）。**

- 首轮（S47）：6 个全新无上下文子代理会话、6 个独立 detached worktree；5 题通过，1 题因题面未规定 `throw` 消息文本而失败（判为 TASK_DEFECT），澄清题面后单题隔离复跑 1/1，单列不并入首轮。
- 判分器只做客观检查（`--check`、退出码、stdout 字节、重复运行逐字节、禁用构造、模块扫描）；没有提交时如实报 `NOT_RUN`，本仓库不记录伪造的 pass@1。
- 参考解只用于验证判分器本身，验证后已删除；如需复核判分器，可自行写解并运行。
