# 现场验收零翻车预案（S51 一页纸）

> **验收窗口**：最近一次为 **11/17（周二）**；课件写“12 月 28 日周二”，但 2026-12-28 实为**周一**——以教师当周通知为准，不自行推断。
> 用途：线下 60–90 分钟验收的**执行清单**，不是教师评分记录。GUI A–E 当前 `REGISTERED 0/5`、`NOT_RUN`；本页只准备材料与降级路径，不代替本人验收。
> 逐页口播与追问见 [defense-runbook.md](defense-runbook.md)；断言与命令见 [defense-index.html](defense-index.html)。

## 1. 时间编排（60–90 分钟）

| 时段 | 内容 | 材料 |
|---|---|---|
| 0–5 | 开场：课程五项评分、八项交付物、当前身份 | `SUBMISSION.md` 第一屏 |
| 5–25 | PPT 1–10 页：语言与解释器、401 黑盒、性能 | `slides/LWT介绍.pptx` + runbook 1–10 |
| 25–40 | **现场跑 5 条命令**（见 §3） | 终端 |
| 40–55 | PPT 11–17 页：并发、S46 模型检查、S47/S48 盲测 | runbook 11–17 |
| 55–70 | 应用演示：日志分析器 / Snake 协议回放 | `app/log_report.lwt`、`app/lwt_snake/` |
| 70–85 | 随机质询：老师任选断言 id | `docs/defense-claims.json`、证据台 |
| 85–90 | 收口：未验证项与边界（GUI、教师评分、PPT 渲染） | 本页 §5 |

时间不足 8 分钟：只讲六段主线（PPT 1/3/5/8/11/20），取舍表见 [demo-script.md](demo-script.md)。

## 2. 解释器陷阱（最先说，避免老师复现出 711）

> **全量 unittest 请用 `py -3.13`（3.13.7 + Tk 8.6）。** 本机 `python` 是 WorkBuddy 内置 3.13.14，**没有 tkinter**：GUI 测试模块在 import 阶段失败，只跑 711 项并出现 2 个假失败。根因与两份日志见 `reports/s50-closeout/unittest-interpreter-root-cause.json`。

```bash
py -3.13 tools/run_unittest_single.py     # 期望：752 项 OK（S51 后为 752，以 manifest 为准）
```

## 3. 必现场跑的 5 条命令

| # | 命令 | 预期输出（摘要） | 失败时展示的降级证据 |
|---|---|---|---|
| 1 | `python -m lwt examples/guide/hello.lwt` | `hello, LWT` 与 `42`，exit 0 | `tests/cases/` 中 hello 用例 + `python tools/run_tests.py --filter hello` |
| 2 | `python tools/run_tests.py` | `passed=401 failed=0 total=401`（约 3–5 分钟） | 已提交的 S51 基线日志 `reports/s51-closeout/`；缩短为 `--filter cli-errors` |
| 3 | `python tools/run_concurrency_determinism.py --repeat 10` | `stable=True; failures=0`（46×10） | `reports/s42-determinism.json`（历史 46×10 逐字节结果） |
| 4 | `python -m lwt --version` | `lwt 0.3.0`，exit 0 | `docs/delivery-manifest.json` 的 version 字段 |
| 5 | `python tools/run_acceptance_selfcheck.py --skip-heavy --out reports/onsite/selfcheck` | `selfcheck: PASS`，12 PASS / 2 N/A / 0 FAIL（含 LWT 原生自测 38/38） | 最近一次 `reports/s51-closeout/selfcheck/` JSON（`all_pass=true`） |

> 第 2、3 条是 heavy：若现场只剩 2 分钟，**只展示已记录证据**，不要现场重跑；不要把“没跑”说成“通过”。

## 4. 降级路径表

| 场景 | 降级做法 | 证据 |
|---|---|---|
| GUI 打不开 / 无显示 | 走 [gui-acceptance-quickref.md](gui-acceptance-quickref.md) 的 CLI 轨（语义实验室、日志、Snake 协议、S41、PPT 静态） | 各场景的已提交 JSON/MD |
| 无网络 | 只用本地 bundle 与已提交证据；不现场 clone/pull | `reports/s48-defense/package-index.json`、`reports/s50-closeout/fresh-clone.json` |
| 解释器无 Tk（711 项） | 改用 `py -3.13`；或直接展示 `unittest-single-command.json`（752 OK，Tk 8.6） | `reports/s50-closeout/` |
| 时间不足 | 保留六段主线，跳过 9/13/15/19 页 | [demo-script.md](demo-script.md) 取舍表 |
| PPT 排版被质疑 | 说明只做静态校验（21 页 / 12 数值点 / SHA），**未渲染**；属 GUI E 人工项 | `reports/s51-closeout/ppt-static.json` |
| Snake 无法开窗 | 协议回放：`python -m lwt app/lwt_snake/game.lwt < app/lwt_snake/demo.commands`，与 `demo.expected` 逐行比对（仅 CRLF） | `app/lwt_snake/demo.expected` |

## 5. 边界（必须如实说）

- 现场人工 GUI A–E 未执行：`REGISTERED 0/5`、`NOT_RUN`；工具与速查就绪，等你本人执行后才登记。
- 教师线下验收与评分未发生；本页不是验收结论。
- PPT 只做静态校验，**未渲染确认**页脚排版。
- Agent 盲测是 60 会话的观察性对照（T 30/30、C 29/30，区间含 0），不是因果证明。
- 有界模型检查覆盖 8 个 clean + 4 个 mutant 程序，不是形式化证明。

## 6. 追问索引（按断言 id）

| 老师问 | 断言 id | 一条命令 |
|---|---|---|
| 语言能跑吗 | `hello` / `version` | `python -m lwt examples/guide/hello.lwt` |
| 测试真有 401 项 | `blackbox` / `integrity` | `python tools/run_tests.py` |
| 并发真的确定 | `determinism` / `diff-eq` | `python tools/run_concurrency_determinism.py --repeat 10` |
| 性能不是吹的 | `compare-perf` / `s11` | `python tools/compare_perf.py` |
| 全量测试怎么跑 | `unittest` | `py -3.13 tools/run_unittest_single.py` |
| 文档和代码一致吗 | `doc-consistency` | `python -m unittest tests.test_doc_consistency -q` |
| 交付包能克隆吗 | `bundle-index` / `fresh-clone` | `python tools/verify_fresh_clone.py --package-index reports/s48-defense/package-index.json` |
| CI 到底过没过 | `fresh-clone` / `ppt` | `reports/s49-rehearsal/ci-cells.json`（逐格） |
