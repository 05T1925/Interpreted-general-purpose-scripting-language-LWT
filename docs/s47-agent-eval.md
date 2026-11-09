# S47 Agent 盲测报告（LWT 0.3.0）

> 协议：6 道题各开**一个全新子代理会话**（不继承主对话历史），在独立 detached worktree 中完成；执行窗口只发题目 prompt 与允许文档路径，不发期望输出。判分器只做客观检查（`--check`、退出码、stdout 字节、5 次逐字节一致、禁用构造）。

## 1. 隔离基线

| 项 | 值 |
|---|---|
| 代码基线 | `6bc4b21b336d89932de709f5c4cca4beb47702f8`（= `origin/feature/concurrency-model-check`） |
| worktree | 每题一个 `git worktree add --detach ... HEAD`，共 6 个；不触碰 S9 的 3 个 detached worktree 与 `s39-agent-strategy` |
| worktree 清理 | 删除 `docs/agent-eval`（含 tasks.json/其他提交）、`tests/`、`app/`、`reports/`、`tools/`、`bench/`、`.github/`，只留 `lwt/`、白名单文档、`examples/`、`.agents/skills/lwt-app/SKILL.md`；每题提交目录独立创建 |
| 发送内容 | 单题 prompt、`allowed_docs` 路径、隔离规则；**不发** tasks.json 全文（避免泄漏 `expected_stdout`） |
| 隔离声明 | 6 份 `report.md` 均声明未读 `lwt/` 源码、`tests/`、`app/`、`reports/`、其他题目或期望输出；仅做过目录名列举；未联网 |

## 2. 首轮结果（冻结题面，主口径）

命令：`python tools/run_agent_eval.py --out reports/s47-submission/agent-eval.json`

| 题目 | 结果 | 检查 | 首次尝试/修订 |
|---|---|---|---|
| `dict-word-frequency-topk` | **PASS** | check/stdout/exit/deterministic/forbidden 全过 | 0 失败、0 修订（20 组自测） |
| `throw-finally-cleanup` | **PASS** | 全过 | 0 失败、0 修订 |
| `producer-consumer-channel` | **FAIL** | `stdout_matches` 失败：实际 `sum 6\ncaught:boom\n`，期望 `sum 6\ncaught:task failed\n` | 0 运行失败；1 次非功能性改名 |
| `module-record-dict-mix` | **PASS** | 全过 | 0 失败、0 修订 |
| `each-snapshot-alias` | **PASS** | 全过 | 0 失败、0 修订 |
| `cli-args-text-processing` | **PASS** | 全过 | 0 失败、0 修订（15 次运行） |

- 提交 6/6，通过 5/6，总判定 `PARTIAL`。
- **pass@1 = 5 / 6 = 0.833**（单样本；公式 `pass@1 = 通过题数 / 全部题数`）。
- 判分器字段覆盖：`tests/test_agent_eval.py` 7 项，覆盖 `stdin`、`args`（fixture 约定）、`check_required`、`deterministic_runs`、`forbidden_constructs`（含模块文件扫描）、`NOT_RUN`、pass@1 分母。

## 3. 失败归因：题面缺陷，不是 Agent/指南失败

`producer-consumer-channel` 的题面只写"再启动一个会 throw 的任务"，**没有规定错误消息文本**，而 oracle 要求 `caught:task failed`。盲测 Agent 写成 `throw "boom"`，输出 `caught:boom`——按题面无法推出 oracle。

- 分类：**TASK_DEFECT（题面欠定）**，不是 guide/Skill 缺陷。
- 修订：`docs/agent-eval/tasks.json` 中该题 prompt 明确"错误消息必须是 `task failed`（即 `throw "task failed";`），输出 `caught:task failed`"；oracle 不变。diff 仅 2 行（note + 该 prompt）。
- 复跑：新建第 7 个 detached worktree 与**全新子代理会话**，用澄清后的题面重做；结果 `PASS`（`sum 6\ncaught:task failed\n`），判分证据 `reports/s47-submission/agent-eval-clarified.json`（1/1，单独标注 post-hoc）。
- 首轮 5/6 保留为**主口径**；澄清后的 1/1 只作补充证据，不合并成"首轮 6/6"。

## 4. 指南修订闭环

- 6 题中 5 题首轮通过，唯一失败是题面欠定而非指南缺失；**未触发指南/Skill/并发契约卡修订**（不制造改动）。
- 观察到的正面证据：盲测 Agent 仅凭 `language-spec.md`/`developer-guide.md`/`SKILL.md`/`concurrency.md` 即可完成 dict 排序、throw/finally、spawn+channel、模块+record+dict、each 快照、args+read_text 六类任务，且 6 题均 0 运行失败。
- 后续若要提高：可把"错误消息必须与题面一致"写进指南的"按题面逐字输出"反模式；本轮未观察到其他失败，故不改。

## 5. 未验证项

- 每题只跑 1 个样本（n=1），pass@1 是点估计，不是统计显著的能力结论；pass@k 无法由单样本外推。
- 盲测隔离是"干净 worktree + 新上下文 + 规则约束 + 事后声明"，不是操作系统级沙箱；无法证明 Agent 未偷看未列入黑名单的通用文档（但 worktree 内已删除 tasks.json/测试/应用）。
- 未测多轮对话、工具受限模式或更小模型。

## 6. 复现

```bash
python tools/run_agent_eval.py --out reports/s47-submission/agent-eval.json
python -m unittest tests.test_agent_eval -q
```

产物：`docs/agent-eval/submissions/<task-id>/{program.lwt|main.lwt+lib.lwt,report.md}`、`reports/s47-submission/agent-eval.{json,md}`、`reports/s47-submission/clarified/producer-consumer-channel/`。
