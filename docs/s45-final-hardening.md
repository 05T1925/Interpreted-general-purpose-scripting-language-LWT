# S45 执行报告：LWT 最终交付加固与 Agent 能力实证

> 本文是 **S45 执行窗口**报告。按任务书边界，本阶段**不推送 main、不合并、不打标签**；功能分支推送经用户明确授权，仅用于核验精确 SHA 的 CI 四格。状态分层：执行实现 / 主窗口审查 / 合入 main / 远端 CI / 现场人工 GUI 验收分别记录，不能由一个推断另一个。

## 0. 基线裁决（首段强制标注）

**基线未经主窗口复核（S43/S44）。** 用户明确授权继续叠加：从 S44 最终提交 `f21f4745518e53c48e577402baf8c188e4d1505b`（`feature/engine-performance`，5 笔提交、未推送、未合并、无标签）创建 `feature/delivery-hardening`。其基线 S43 `344c255` 同样未复核；`main = origin/main = 5027860` 不含 S43/S44。`milestone/final-acceptance` 是独立文档线，未合并；`feature/s39-agent-strategy` worktree 未触碰。工作区干净开工，未 reset、未强推、未改写已共享历史。

**版本裁决**：主窗口裁决为 **0.3.0**（S42 语言核心与 S43 并发子语言为新增语言特性，S44 为性能与导入结构；按语义化版本升次版本）。写入 `docs/delivery-manifest.json`，执行窗口不自行二选一。

## 1. 工作包（WP0–WP7）

| WP | 内容 | 实际完成 |
|---|---|---|
| WP0 | 基线回归、版本裁决、交付清单、文档一致性测试 | 完成：六项基线回归全过（400/400、unittest 见 §4、46×10、完整性 400/400 unreferenced=0、compare_perf all_pass=true、保护路径空）；`docs/delivery-manifest.json`（0.3.0、400、unittest 计数、18 页、PPT SHA、29 个保护路径、证据索引）；`tests/test_doc_consistency.py` 11 项（先红后绿，历史报告 allowlist 豁免）。 |
| WP1 | 统一版本与状态文字 | 完成：`lwt/__init__.py` 0.3.0 + 真实能力 docstring；规范标题「LWT 0.3.0 正式语言规范（S1–S44 已实现；S42–S44 待主窗口复核）」并删过期「S24–S27 等待审查」；developer-guide、test-matrix 同步；README 顶部状态与快速开始、S12 已完成、当前基数 400；project.md 日期/632/未复核；checklist 18 页/632；s44 报告 §6 595→632（§4 的 595 基线保留）。历史报告 s12–s44 旧数字未改。 |
| WP2 | CLI `--help`/`--version` | 完成：`-h`/`--help`/`--version` 单独出现时早退、退出 0、不执行源码；无参数仍 CliError/4；`--` 后的同名参数仍属程序实参。规范 §6、指南、README、project 命令入口更新；`tests/test_cli.py` 新增 6 项。S45 启动重测写 `reports/s45-acceptance/startup.*`（三命令全 exit 0）。 |
| WP3 | Agent 盲测任务与判分器 | 完成：`docs/agent-eval/tasks.json` 6 题（dict top-k、throw/finally、生产者消费者通道、模块+record+dict、each 快照与别名、CLI+文本）；`tools/run_agent_eval.py` 只做客观检查（`--check` 0、退出码+stdout 字节、5 次逐字节、禁止构造）；`docs/agent-eval/README.md` 记录隔离协议。执行窗口用参考解验证判分器 6/6 ALL_PASS 后**删除参考解**；正式盲测 **NOT_RUN**，未填 pass@1。 |
| WP4 | DAP 帧级 + 跨平台 | 完成：`tests/test_dap_spawn_rejection.py` 2 项，真实 `python -m lwt.dap_server` 子进程、手写封帧、UTF-8 `Content-Length`（含中文文件名）、`configurationDone` 后 exit 4、无 stopped/断点、无 debuggee stdout 泄漏、适配器 exit 0。本机无 Python 3.10（`py -0` 只有 3.13/3.12/3.11），3.11.16 补跑兼容验证；CI 见 §5。 |
| WP5 | 一键验收自检包 | 完成：`tools/run_acceptance_selfcheck.py` 一条命令跑 Git/HEAD、保护路径 diff、完整性、黑盒、确定性（独立 `--out`，不碰 S42 证据）、compare_perf、文档一致性、PPT 静态检查（zip/xml 数页数与图表数值点、SHA）、Agent eval 状态；输出 `reports/s45-acceptance/selfcheck-<UTC>.{json,md}` 并打印人工 GUI 清单；失败写 FAIL、跳过写 SKIP。 |
| WP6 | PPT/答辩/演示对齐 | 完成：PPT 17→**18 页**（新增「八项交付物 → 证据与一条命令」），旧第 10 页原生图表 **12 数值点未变**，旧 SHA `2b0d1df3…` → 新 `b8c15c03…` 记入 manifest；清单 18 页/632/400 一致；demo-script 重排为 8–10 分钟主线（语言→400 黑盒→S11/S44 性能→并发→Agent 应用→策略证据→交付自检）保留 CLI 后退；答辩卡 +6 问。 |
| WP7 | 收口 | 全量回归、状态文档、按 WP 分提交、停止写入交主窗口复核。 |

## 2. 基线与 Git

- **基线**：`f21f474`（S44 最终，未复核），用户授权叠加；版本 0.3.0 由主窗口裁决。
- **分支**：`feature/delivery-hardening`。
- **提交**：按 WP 分组（详见 §8；收口提交 SHA 由主窗口 `git log -1` 核对，正文不预写自身 SHA）。
- **远端**：功能分支经用户授权推送，精确 SHA 与 CI 结论单独记录于 §5；不推送 main、不合并、不打标签。

## 3. 环境

| 项 | 值 |
|---|---|
| CPU / 内存 | 13th Gen Intel(R) Core(TM) i9-13980HX；32 逻辑核 / 15.6 GB |
| 平台 | Windows-11-10.0.26200-SP0；AMD64 |
| Python（计时/黑盒） | 3.13.14 WorkBuddy 内置（无 tkinter） |
| Python（unittest） | 3.13.7 + Tk（系统） |
| Python（跨版本补充） | 3.11.16（Astral/uv 构建，`C:\Users\28641\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none\python.exe`） |
| Python 3.10 | **未安装**（`py -0` 无 3.10；`python3.10` 不在 PATH） |
| 电源 | Silent |

## 4. 运行证据（命令 / 退出码 / 关键输出）

| 命令 | 退出码 | 关键输出 |
|---|---:|---|
| `python tools/run_tests.py`（基线） | 0 | `passed=400 failed=0 total=400` |
| `python tools/check_project_integrity.py --require-all-referenced` | 0 | `cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0` |
| `python tools/compare_perf.py --format json` | 0 | `all_pass: True`（启动 + 纯执行全 PASS） |
| `python tools/run_concurrency_determinism.py --repeat 10 --out reports/s45-acceptance/s45-determinism.json` | 0 | `46 cases x 10 runs; stable=True; failures=0`；`reports/s42-determinism.json` 零改动 |
| `python -m unittest discover -s tests -q` | 0 | 见 §4.1（最终计数） |
| `python -m lwt --help` / `-h` / `--version` | 0 / 0 / 0 | 用法摘要；`lwt 0.3.0` |
| `python -m lwt`（无参数） | 4 | `CliError: expected a source path`（既有行为不变） |
| `python -m unittest tests.test_cli` | 0 | 114 项（含新增 6 项 help/version） |
| `python -m unittest tests.test_doc_consistency` | 0 | 11 项（当前状态文档不含旧版本号/旧计数/过期状态，历史 allowlist 生效） |
| `python -m unittest tests.test_dap_spawn_rejection` | 0 | 2 项（UTF-8 帧、exit 4、无 stopped、无 stdout 泄漏） |
| `python -m unittest tests.test_concurrency` | 0 | 21 项（含新增 2 项通道精确一次） |
| `python tools/run_agent_eval.py` | 0 | `NOT_RUN (submitted 0/6, passed 0)`（未伪造） |
| `python tools/run_acceptance_selfcheck.py` | 0 | 见 §4.2（最终自检包） |
| Python 3.11.16：compileall / `--version` / hello / `--check` / 21 项定向单测 | 0 | 全过 |
| `git diff --check` / compileall / Markdown 链接 | 0 | 全过；保护路径差异空 |

### 4.1 全量 unittest

`Ran 653 tests in 749.987s ... OK`（系统 Python 3.13.7+Tk；S44 的 632 + 文档一致性 11 + CLI help/version 6 + DAP 帧 2 + 通道精确一次 2）。

### 4.2 一键自检包

`python tools/run_acceptance_selfcheck.py` → **PASS**，产物 `reports/s45-acceptance/selfcheck-20261108T154909Z.json/.md`：git PASS（HEAD `0b58739`、分支 `feature/delivery-hardening`、工作树干净）、protected_diff PASS（空）、integrity PASS（cases=400, referenced=400, unref=0）、blackbox PASS（400/400）、determinism PASS（stable=True, failures=0，独立输出 `reports/s45-acceptance/s45-determinism.json`）、compare_perf PASS（all_pass=true）、doc_consistency PASS（11 项）、ppt PASS（18 页、图表 12 数值点、SHA `b8c15c03…`）、agent_eval N/A（NOT_RUN，明确不当作通过）。

## 5. 远端 CI（精确 SHA 单独记录）

（收口推送后填：精确 SHA、run 链接、四格结论；失败则记录失败格与修复/未修，不把 push 成功当 CI 通过。）

## 6. 本轮发现并修复的真实缺陷

**通道重复投递（违反规范 §11.5）**：`send` 原实现先把值追加进队列，再把同一个值直接注入阻塞接收者，导致下一个 `receive` 又取到同一元素。最小复现：

```lwt
fn produce(ch) { send(ch, 7); close(ch); }
let ch = channel();
let t = spawn produce(ch);
emit str(receive(ch));   # 7
emit str(receive(ch));   # 修复前 7（错误），修复后 null
join(t);
```

既有 46 项并发黑盒没有任何一项在"接收者已阻塞"后再收一次，所以此前未暴露。修复为「有阻塞接收者时直接交接、不入队」，并新增 `tests/test_concurrency.py::ChannelExactlyOnceTests` 2 项回归。修复后：全量黑盒 400/400、46×10 稳定、并发单测 21/21。这是**让实现符合已冻结规范**，不是改变 §1–§11 语义。

## 7. 交付位置（需求 → 证据）

| 任务书 | 交付 | 位置 |
|---|---|---|
| 版本与清单 | manifest + 文档一致性测试 | `docs/delivery-manifest.json`、`tests/test_doc_consistency.py` |
| CLI help/version | 早退分支 + 测试 + 启动重测 | `lwt/cli.py`、`tests/test_cli.py`、`reports/s45-acceptance/startup.*` |
| Agent 盲测 | 6 题 + 判分器 + 协议 | `docs/agent-eval/`、`tools/run_agent_eval.py`、`reports/s45-acceptance/agent-eval.*` |
| DAP 帧 | 真实子进程帧测试 | `tests/test_dap_spawn_rejection.py` |
| 一键自检 | 自检包 | `tools/run_acceptance_selfcheck.py`、`reports/s45-acceptance/selfcheck-*` |
| PPT/答辩/演示 | 18 页、主线脚本、+6 问 | `slides/LWT介绍.pptx`、`docs/demo-script.md`、`docs/defense-qa-card.md` |

## 8. 提交与保护数据

- 按 WP 分组提交（SHA 由主窗口核对）；工作区最终 `git status -sb` 干净。
- **保护数据零改动**：`bench/results.json`、`reports/performance.md`、`reports/app-concurrency.json`、`docs/app-concurrency.md`、`reports/app-lwt-profile.*`、`reports/lsp-smoke.json`、`reports/runtime-profile.*`、`reports/concurrency-performance.*`、`reports/s42-*`、`tests/cases/**`、`app/log_report.lwt`、`app/lwt_snake/game.lwt`、策略/回放、PPT 旧第 10 页图表 12 数值点。S45 新证据全部写 `reports/s45-acceptance/`。
- **历史报告旧数字未改**：`docs/s12-*` … `docs/s44-*` 的历史快照保留；只改当前状态文档，旧值由 `tests/test_doc_consistency.py` 的 allowlist 显式豁免。

## 9. 未验证项

- **Agent 盲测 pass@1**：未执行（NOT_RUN）。需用户开新的无上下文会话运行；执行窗口不伪造。
- **Python 3.10**：本机未安装，未实测；3.11.16/3.12/3.13 已实测（3.12 启动器路径损坏，未能运行，如实记录）。
- **Linux**：仅 GitHub Actions；本地无法验证。
- **现场人工 GUI A–E**：未验证（语义实验室、日志工作台、LWT Snake、S41 查看器、PPT 逐页播放、桌面无遮挡/输入归属）。
- **DAP 其他边界**：本轮只补 spawn 拒绝的帧级证据；断点/单步的帧级覆盖沿用既有测试。
- **CI**：见 §5；未跑过的组合不声称通过。

## 10. 状态分层

- **执行实现**：完成（本窗口）——**待主窗口复核**。
- **主窗口审查**：未开始。
- **合入 main**：未发生。
- **远端 CI**：见 §5（仅功能分支，非 main）。
- **现场人工 GUI**：未验证。
- **教师验收 / 最终评分**：不声称。
