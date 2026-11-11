# LWT 提交入口（教师版）

> 版本 **0.3.0** ｜ 黑盒 **400** ｜ unittest **721** ｜ PPT **21 页**
> 默认分支 `main` 与本交付分支同一提交；分支/CI 的精确 SHA 见 `docs/s47-final-submission.md`。
> 本文件由 `tools/build_submission.py` 生成，数字取自 `docs/delivery-manifest.json`。

## 三分钟验收路径

```bash
python -m lwt --version                     # lwt 0.3.0
python tools/run_tests.py                   # Black-box tests: passed=400 failed=0
python tools/run_acceptance_selfcheck.py    # Git/保护路径/完整性/黑盒/确定性/性能/文档/PPT/模型检查
```

然后打开 `slides/LWT介绍.pptx`（21 页）。所有命令在仓库根目录执行；Python 3.10+ 标准库，无第三方运行时依赖。

> **解释器陷阱（现场复现必读）**：全量 unittest 必须用 `py -3.13`（3.13.7 + **Tk 8.6**）。本机 `python` 是 WorkBuddy 内置 3.13.14，**没有 tkinter**：GUI 测试模块在 import 阶段就失败，只会跑 **711** 项并出现 2 个假失败，不是语言缺陷。根因、两份日志与哈希见 `reports/s50-closeout/unittest-interpreter-root-cause.json`；`docs/defense-claims.json` 的 unittest 行也声明了 `requires.tkinter`。

> 离线提交件：bundle/zip 位于 `dist/`（默认 gitignore，不入库），索引见 `reports/s48-defense/package-index.json`。老师 clone 仓库后若 `dist/` 为空，请现场运行 `python tools/build_submission.py`，或直接携带 `dist/` 目录。

## 提交内容 1–8（对应课程要求）

| # | 提交内容 | 分值 | 仓库位置 | 一条验证命令 | 证据 | 状态 |
|---|---|---|---|---|---|---|
| 1 | LWT 语法规则文档 | — | `docs/language-spec.md` | `python -m lwt --version` | 规范 §1–§11；版本号由 manifest 统一 | 完成 |
| 2 | 解释器源程序 | 20 | `lwt/` | `python -m lwt examples/guide/hello.lwt` | `tests/cases/` 400 项 | 完成 |
| 3 | 完整黑盒测试集 | 20 | `tests/cases/` | `python tools/run_tests.py` | 400/400；矩阵 `referenced_cases=400/400` | 完成 |
| 4 | 性能测试报告 | 10 | `reports/performance.md、bench/results.json` | `python tools/compare_perf.py` | S11 正式报告 + S44 分层对照 | 完成 |
| 5 | 开发指南（人 + AI） | 20 | `docs/developer-guide.md、.agents/skills/lwt-app/SKILL.md` | `python -m lwt --check examples/modules/main.lwt` | S42–S46 已按指南实现 | 完成 |
| 6 | Agent 应用与开发记录 | 30 | `app/log_report.lwt、app/concurrent_log_report.lwt、app/lwt_snake/game.lwt、docs/agent-dev-log.md` | `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 有效行数 243 / 233 / 313（`tools/count_lwt_lines.py`） | 完成 |
| 7 | Git 历史 | — | `dist/ 内的 lwt-history.bundle、lwt-history.graph.txt` | `python tools/build_submission.py`（索引 `reports/s48-defense/package-index.json`） | bundle 含全部 branches/tags/HEAD；verify=0；索引记录截止 SHA | 完成 |
| 8 | 系统介绍 PPT | — | `slides/LWT介绍.pptx（21 页）` | 打开 `slides/LWT介绍.pptx` | 第 10 页原生图表 12 数值点自 S43 起未变 | 完成 |

合计 100 分：解释器 20 + 自动测试 20 + 性能 10 + 语法/指南 20 + Agent 应用 30。

## 五段证据摘要

| 主题 | 可复算数字 | 源文件 |
|---|---|---|
| S11 性能 | 六组端到端中位数，LWT/Python 2.7–5.0×（明确未做解释器优化） | `reports/performance.md`、`bench/results.json` |
| S43 并发 | 46 项并发黑盒、46×10 逐字节确定、found/absent/tampered 三态 | `docs/s42-deterministic-concurrency.md`、`reports/s42-schedules/` |
| S44 加速 | 纯执行 N=5000：1.454× / 1.552× / 2.992×；启动 1.256× / 1.224× | `docs/s44-performance.md`、`reports/s44-performance/` |
| S46 模型检查 | clean 8 程序 / 32 runs / 0 violation；mutant 4 violation、最小前缀 `[]` | `reports/s46-concurrency-model/` |
| S48 Agent 盲测 | 60 会话（6 题 × T/C 两组 × 5 样本）：T **30/30**、C **29/30**；T−C=+0.033，95% 区间 [−0.031, +0.098] | `reports/s48-defense/ablation.json`、`docs/s48-agent-eval.md` |

## 未验证项（如实）

- 现场人工 GUI A–E 验收未执行（语义实验室、日志工作台、LWT Snake、S41 查看器、PPT 逐页播放、桌面无遮挡/输入归属）。
- 教师线下验收与评分未发生。
- Agent 盲测为 60 会话的观察性对照（6 题 × 2 组 × 5 样本）；T−C 区间含 0，不是因果证明。
- CI 结论按精确 SHA 记录；功能分支与 `main` 的 CI 分开写，不互相推断。

## 交付包

- `lwt-history.bundle`：`git bundle --branches --tags HEAD`，含全部分支/标签与历史（排除临时 worktree refs）；`git bundle verify` 见 `reports/s48-defense/package-index.json`。
- `lwt-submission.zip`：HEAD 跟踪树 + 本文件 + bundle；`manifest.sha256` 逐文件摘要。
- 包不入库：`dist/` 被 gitignore，入库的是索引 `reports/s48-defense/package-index.json`（记录 bundle 截止 SHA 与允许的差异白名单）。
- 重新生成：`python tools/build_submission.py --package-index reports/s48-defense/package-index.json`；新克隆验证：`python tools/verify_fresh_clone.py --package-index reports/s48-defense/package-index.json`。
- S47 盲测派生说明：`reports/s47-submission/agent-eval.json` 的 `note` 是历史快照，与后续执行状态不一致；以 `reports/s48-defense/agent-eval-s47-derivation.json` 为准（记录原始 overall、失败题判定与澄清单列）。
