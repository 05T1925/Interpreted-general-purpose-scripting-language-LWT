# S44 执行报告：LWT 执行引擎「可验证加速」

> 本文是 **S44 执行窗口**报告。按任务书边界，本阶段**不推送、不合并、不打标签**，交主窗口复核。状态分层：执行实现 / 主窗口审查 / 合入 main / 远端 CI / 现场人工 GUI 验收分别记录，不能由一个推断另一个。方法与协议见[性能计划](s44-performance-plan.md)，逐项假设/测量/保留或回滚见[优化台账](s44-optimization-ledger.md)，原始数字见 `reports/s44-performance/` 的新 JSON。

## 0. 基线裁决（首段强制标注）

**基线未经主窗口复核。** 用户明确授权"叠加在未复核的 S43 上"：从 S43 最终提交 `344c2559e4453c2d1ff0f63c0c28ce8dd108e238`（`feature/deterministic-concurrency`，7 笔提交、未推送、未合并、无标签）创建 `feature/engine-performance`。`main = origin/main = 5027860` 不含 S43；`milestone/final-acceptance` 是独立文档线，未纳入；`feature/s39-agent-strategy` worktree 未触碰。工作区干净开工，未 reset、未强推、未改写已共享历史。

## 1. 阶段与范围（WP0–WP7 逐条）

| WP | 目标 | 实际完成 |
|---|---|---|
| WP0 | 闸门、基线只读回归、基线性能测量、计划 | 完成：必读文档全读、Git 原文记录；四项基线回归全过（400/400、完整性 400/445/348、unittest 595/595、46×10 稳定）；`micro_bench.py` 加 `--out`/`--output-prefix`/`--label` 隔离、新增 `tools/measure_startup.py`；基线写 `reports/s44-performance/before/`；[计划](s44-performance-plan.md)。端点定位复现：`lwt.cli` 顶层导入拖入 `lwt.concurrency`（73 ms）及其 `concurrent.futures`/`hashlib`/`json`/`tempfile`。 |
| WP1 | 启动惰性化 P0-1/P0-2 | 完成：新增轻量 `lwt/_sched_support.py`（异常类 + thread-local task id，仅依赖 threading），`concurrency.py` re-export 保持类身份单一；`runtime.py`/`cli.py` 顶层只导入轻量模块，`Scheduler`/`ScheduleTracer`/`source_digest` 延迟到 spawn 分支，`hashlib`/`json`/`tempfile` 入函数内/`TYPE_CHECKING`；`modules.py` 仅 `include_hashes=True` 导 hashlib。`tests/test_startup.py` 10 项；启动 A/B 达标。 |
| WP2 | 热路径 P0-3/P0-4 | 完成：`_execute_statement`(12 类)/`_evaluate`(13 类) 顶层 AST 分派 `isinstance` → 精确 `type() is`（无子类、未知类型断言保留、扫描函数不变），`_evaluate_binary` 运算符集合提为模块 `frozenset`；新增依赖无关 `lwt/_decimal.py`，INT 字面量解析期预解码；`tests/test_dispatch_completeness.py` 9 项节点分派完整性；纯执行 A/B 三负载全部 ≥1.45×。 |
| WP3 | 局部优化 P1 | 完成：P1-2（`resolve` 哨兵）实测 <2% 且有回归迹象 → **回滚、零残留**；P1-4（小整数 `str(int)` 快路径）实测 N=5000 +3.5%~16.4%、6000 位精度保持 → **保留**；P1-1/P1-3 按台账理由未做。最终 after 证据重测。 |
| WP4 | S11-v2 基准 | 完成：`tools/benchmark_v2.py`（不改旧输出路径）、`bench/dict_counts.py`（与 LWT 同算法同输出、`oracle` 独立）、`tools/compare_perf.py`（门槛判定、只读）；3 负载 × 3 规模 × 2 预热 × 7 正式 = 126 次正式、逐字节 oracle 全通过；`reports/s44-performance/benchmark-v2.{json,md}` 分层（端到端 / 纯执行）。 |
| WP5 | 回归 + 覆盖闭环 | 完成：400/400 黑盒、595+ unittest、46×10 确定性、S28 固定 profile 事件计数、`--check`/`--profile`/debugger/DAP/LSP 不回归、compileall、`git diff --check`；覆盖矩阵补 52 个未链接用例 → `referenced_cases=400/400; unreferenced=0`，`check_project_integrity.py` 加 `--require-all-referenced`/`--exempt`；`tests/test_perf_tools.py` 17 项（schema/oracle/配对/输出路径防护）。 |
| WP6 | 文档/PPT/答辩 | 完成：本文、`s44-performance-plan.md`、`s44-optimization-ledger.md`；答辩卡 +6 问、演示脚本 +45 秒、PPT 追加 1–2 页（旧 15 页与第 10 页图表 12 数值点保留，记录旧/新 SHA）；统一版本/状态标识文字。 |
| WP7 | 收口 | 全量回归、状态文档更新、按 WP 分提交、停止写入交主窗口复核。 |

## 2. 基线与 Git

- **基线 SHA**：`344c2559e4453c2d1ff0f63c0c28ce8dd108e238`（未复核 S43），用户授权叠加。
- **分支**：`feature/engine-performance`（从 `344c255` 创建）。
- **提交序列**（按 WP 分组）：① WP0 `40932c0` `perf(engine): establish S44 baseline and A/B tooling`；② WP1+WP2 `27a0a6b` `perf(engine): lazy scheduler import and hot-path dispatch`（runtime.py 的 WP1/WP2 改动交织，合并为一笔并在 commit message 分列）；③ WP3 `639d0e3` `perf(engine): P1-4 small-int format fast path; roll back P1-2`；④ WP4+WP5 `ce41635` `perf(engine): S11-v2 layered benchmark and coverage closure`；⑤ WP6+WP7 `（收口提交，SHA 由主窗口 git log -1 核对，正文不预写自身 SHA）`。
- **远端**：**未推送**；无远端最终 SHA，Actions 未查询，不沿用旧 SHA 的四格结论。
- **工作区**：最终 `git status -sb` = `## feature/engine-performance`（干净）。

## 3. 环境与同机 A/B 协议

| 项 | 值 |
|---|---|
| 采集时间 | 2026-11-07 16:52–（UTC+8） |
| CPU | 13th Gen Intel(R) Core(TM) i9-13980HX；32 逻辑核 |
| 平台 | Windows-11-10.0.26200-SP0；AMD64；15.6 GB RAM |
| Python（计时/黑盒） | 3.13.14 WorkBuddy 内置 `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe`（无 tkinter） |
| Python（全量 unittest） | 系统 3.13.7 + Tk，`C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe` |
| 电源方案 | Silent（GUID `64a64f24-65b9-4b56-befd-5ec1eaced9b3`） |
| 背景负载 | WorkBuddy、云音乐、Edge WebView、ArmourySocketServer 等常驻；未清零 |

**协议**：同一台机器、同一 Python 可执行文件、同一电源模式、同一 cwd（仓库根）；先跑 before、再改代码、再跑 after；正式样本交错配对减小时间漂移；每次记录 argv/cwd/退出码/stdout·stderr SHA/`elapsed_ns`/源 SHA/Git SHA/环境；只比较同机相对差值，绝不跨机器比。一次并发跑黑盒+确定性导致 2 个 error-recovery 用例 5 s 超时（398/400），单用例重跑与无并发负载的全量重跑均 **400/400**，确认为 CPU 争用的假失败，非代码回归。

## 4. 运行证据（命令 / 退出码 / 关键输出）

| 命令 | 退出码 | 关键输出 / 结论 |
|---|---:|---|
| `python tools/run_tests.py`（基线） | 0 | `passed=400 failed=0 total=400`；`concurrency=46/46` |
| `python tools/check_project_integrity.py`（基线） | 0 | `cases=400; matrix_links=445; referenced_cases=348` |
| `python -m unittest discover -s tests -q`（系统 Python，基线） | 0 | `Ran 595 tests ... OK`（783.7 s） |
| `python tools/run_concurrency_determinism.py --repeat 10`（基线） | 0 | `46 cases x 10 runs; stable=True; failures=0` |
| `python tools/measure_startup.py --out reports/s44-performance/before/... --repeats 10 --warmups 2` | 0 | pass 365.370 / help 624.170 / hello 611.217 ms |
| `python tools/micro_bench.py --out reports/s44-performance/before --repeats 7 --warmups 2` | 0 | execute N=5000：arithmetic 32.504 / array_scan 110.945 / dict_counts 176.090 ms |
| `python tools/measure_startup.py --out reports/s44-performance/after/... --repeats 10 --warmups 2` | 0 | pass 343.209 / help 496.773 / hello 499.503 ms；`--help − pass` 258.8→153.6 ms |
| `python tools/micro_bench.py --out reports/s44-performance/after --repeats 7 --warmups 2`（最终代码） | 0 | execute N=5000：22.349 / 71.474 / 58.847 ms |
| `python tools/benchmark_v2.py --sizes 100,1000,5000 --repeats 7 --warmups 2` | 0 | 126 次正式 oracle 全通过；端到端 LWT/Python 1.479–1.793× |
| `python tools/compare_perf.py` | 0 | 启动两项与纯执行三负载门槛全 PASS，`all_pass=true` |
| `python tools/check_project_integrity.py --require-all-referenced` | 0 | `cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0` |
| `python -m unittest tests.test_startup -q` | 0 | `Ran 10 tests ... OK`（非 spawn 不加载 concurrency 等） |
| `python -m unittest tests.test_dispatch_completeness -q` | 0 | `Ran 9 tests ... OK`（AST 分派完整性 + 6000 位整数） |
| `python -m unittest tests.test_perf_tools -q` | 0 | `Ran 17 tests ... OK`（schema/oracle/配对/路径防护） |
| `python -m unittest tests.test_execution_profile -q` | 0 | `Ran 19 tests ... OK`；S28 固定 profile 的事件序列/计数/函数命中不变（含 `function_call`/`function_return`/`statement`/`decision`/`recover` 顺序与 `sequence` 连续） |
| `python -m unittest discover -s tests -q`（最终代码） | 0 | `Ran 632 tests in 630.378s ... OK`（修复 1 个 argparse 回归后；含新增 `test_library_call_ignores_unittest_argv`） |
| `python tools/run_tests.py`（最终代码） | 0 | `passed=400 failed=0 total=400` |
| `python tools/run_concurrency_determinism.py --repeat 10`（最终代码） | 0 | `stable=True; failures=0` |
| `python -m lwt app/concurrent_log_report.lwt -- sample.log showcase.log` | 0 | 与 `log_report.lwt` 单文件逐字节差分等价（S43 不回归） |
| `git diff --check` / `compileall` / Markdown 链接 | 0 | 全通过；保护路径差异空 |

### 4.1 before/after 核心表

**启动**（新进程墙钟中位数，ms）：

| 命令 | before | after | 提升 | 门槛 |
|---|---:|---:|---:|---|
| `python -c pass` | 365.370 | 343.209 | 1.065× | （基线自身波动） |
| `python -m lwt --help` | 624.170 | 496.773 | **1.256×** | ≥15% ✓ |
| `python -m lwt examples/guide/hello.lwt` | 611.217 | 499.503 | **1.224×** | ≥10% ✓ |
| `--help − pass`（LWT 导入开销） | 258.800 | 153.564 | −105.236 ms | 结构性收益 |

> 注：`python -m lwt --help` 当前返回退出码 4（`FileError: cannot read source file`，CLI 无 `--help` 实现）；该测量仍触发完整包导入 + CLI 解析路径，`measure_startup.py` 逐命令记录退出码并保持跨预热/正式稳定。**不**为测启动而新增 `--help` 功能（超出 S44 红线）。

**纯执行 execute**（micro_bench 同进程分层，中位数 ms；不含启动/导入）：

| 负载 | N | before | after | 提升 |
|---|---:|---:|---:|---:|
| arithmetic | 1000 | 7.066 | 4.733 | 1.493× |
| arithmetic | 5000 | 32.504 | 22.349 | **1.454×** |
| array_scan | 1000 | 24.455 | 15.834 | 1.544× |
| array_scan | 5000 | 110.945 | 71.474 | **1.552×** |
| dict_counts | 1000 | 15.801 | 10.528 | 1.501× |
| dict_counts | 5000 | 176.090 | 58.847 | **2.992×** |

N=5000 三负载全部 ≥1.45×（门槛 ≥2/3 负载 ≥15%），任何负载无回归。parse 阶段也有小幅下降（P0-4 预解码在解析期多一次解码，但消除了 lexeme 停留，实测 parse 中位数基本持平或略降）。

## 5. 分层解释：快在哪、快多少、为什么

S44 把端到端拆成**四段**，避免把端到端倍率说成纯执行倍率：

1. **启动/导入**：`python -c pass` vs `python -m lwt --help` 中位数差 —— **−105.2 ms**（258.8→153.6 ms），来自切断 `lwt.concurrency` 顶层导入链（`concurrent.futures` 53.8 ms、`hashlib` 9.0 ms、`json`/`tempfile` 在干净解释器上的成本）。非 spawn 程序 `sys.modules` 无 `lwt.concurrency`（`tests/test_startup.py` 断言）。
2. **解析 parse**：micro_bench `parse` 阶段（N=5000 约 0.8 ms），本次基本持平；P0-4 在解析期多一次 INT 解码，但消除了运行期重复解析。
3. **纯执行 execute**：micro_bench `execute` 阶段 —— 三负载 **1.45–2.99×**。来自三个叠加效应：①`type() is` 精确分派替代长 `isinstance` 链；②运算符集合常量化消除每次调用的 set 分配（5000 次循环里被放大）；③INT 字面量预解码消除循环内 `parse_decimal_integer` 的字符串分块；④P1-4 小整数 `str(int)` C 快路径（dict_counts 循环内 `str(key)` 高频收益最大）。
4. **端到端**：`benchmark_v2` 新进程墙钟 LWT/Python **1.479–1.793×**（Python 参考约 306–325 ms，LWT 约 454–553 ms）。**仍比 Python 慢**；慢在解释器节点分派、对象分配与包导入的结构性成本；S44 优化的是前 3 段，不把端到端倍率与纯执行倍率混用。

**为什么合成实验低估了实际收益**：P0-3 设计前的合成微实验（100 万次单次分派）显示 `type() is` 在偏斜负载下仅快约 2%；真实 micro_bench 显示组合收益达 1.45–2.99×。原因是合成实验未测到递归调用中 set 字面量分配与字面量重解析的**累积效应**——它们在 5000 次循环里被放大数十万次。这印证了"逐项实测"的必要性，也说明设计实验与产品测量口径不同（台账已记录）。

## 6. 交付位置（需求 → 测试映射）

| 课程抓手 / 任务书 | 交付 | 文件 / 映射 |
|---|---|---|
| 解释器 20 / WP1–3 | 惰性导入 + 精确分派 + 字面量预解码 + 小整数快路径 | `lwt/_sched_support.py`、`lwt/_decimal.py`、`lwt/{runtime,cli,modules,parser,concurrency}.py` |
| 测试 20 / WP1/2/3/5 | 启动断言、AST 分派完整性、性能工具测试、覆盖闭环 | `tests/test_startup.py`(10)、`tests/test_dispatch_completeness.py`(9)、`tests/test_perf_tools.py`(17)、`docs/test-matrix.md` §4.5.3、`tools/check_project_integrity.py --require-all-referenced` |
| 性能 10 / WP0/4 | S11-v2 分层基准 + 门槛判定 | `tools/benchmark_v2.py`、`tools/measure_startup.py`、`tools/compare_perf.py`、`bench/dict_counts.py`、`reports/s44-performance/{before,after}/*`、`benchmark-v2.{json,md}` |
| 指南 20 / WP6 | 方法/计划/台账/答辩/演示 | `docs/s44-performance.md`、`s44-performance-plan.md`、`s44-optimization-ledger.md`、`docs/concurrency.md`(S43)、`docs/defense-qa-card.md`、`docs/demo-script.md` |
| 证据闭环 / WP0/5 | 全量回归 + 保护路径 | 400/400 黑盒、595 unittest、46×10 确定性、S28 事件计数（见 §4） |
| 收口 / WP7 | 状态与清单 | `project.md`、`README.md`、`阶段执行与审查路线图.md`、`docs/final-acceptance-checklist.md`、本报告 |

## 7. 已知问题与未验证项

- **未验证（如实标注）**：Python 3.10 / Linux / 远端 CI（本机不可用或未推送）、远端最终 SHA 的 Actions 四格、Agent 盲测 pass@1（无法新开无上下文会话，不把自测当盲测）、DAP 协议帧级拒绝（沿用 S43 共享 execute 路径）、冷 page cache 端到端、纯 I/O 重叠隔离测量（S43 遗留）、P1-1 record 字段缓存与 P1-3 内置表驱动的收益（冻结 workload 无 record / 改动风险大于边际收益，见台账）。
- **设计边界（非缺陷）**：P0-3 采用 `type() is` 精确链而非任务书建议的 `type→handler` 表 —— 合成实验显示表在偏斜负载下最慢（81 ms vs 44 ms），理由与数据见台账。P1-2 因 <2% 收益已回滚。一项黑盒契约随 P0-4 有意变更：INT 字面量 `value` 从 `None` 变为解析期预解码值（`tests/test_parser.py` 适配，`tests/cases/**` 零改动）。
- **双 WP 合并提交**：WP1 与 WP2 的 `runtime.py` 改动交织无法干净拆分，合并为 `27a0a6b` 一笔，commit message 分列两 WP；其余按 WP 分组。
- **全量回归中发现并修复 1 个真实回归**：给 `tools/check_project_integrity.py` 加 `--require-all-referenced` 时，初版 `main()` 直接调用 `parser.parse_args()` 读取 `sys.argv`，导致既有 `tests/test_project_integrity.py::test_command_reports_failure_to_stderr_and_returns_nonzero` 以 `main(self.root)` 库内调用时被 unittest 的 argv（含 `-q`）触发 `SystemExit: 2`（631 项中 1 ERROR）。修复为 `main(repo_root, argv=None)`：`argv=None` 表示库/测试调用，传空列表给 argparse；`__main__` 入口显式传 `sys.argv[1:]`；并新增 `test_library_call_ignores_unittest_argv` 防回归。修复后 25 项相关单测通过、全量 unittest 重跑见 §4。这印证了"全量回归不可省"。
- **保护数据**：`bench/results.json`、`reports/performance.md`、`reports/app-concurrency.json`、`docs/app-concurrency.md`、`reports/app-lwt-profile.*`、`reports/lsp-smoke.json`、`reports/runtime-profile.*`(S42)、`reports/concurrency-performance.*`(S43)、`reports/s42-*`、`reports/s37..s41-*`、`tests/cases/**`、`app/log_report.lwt`、`app/lwt_snake/game.lwt`、策略/回放、PPT 旧 12 页图表数据差异均为空。基线确定性回归曾覆盖 `reports/s42-determinism.json`（仅计时数值），已用 `git checkout --` 还原，S43 证据零改动。
- **PPT**：追加 2 页（S44 优化前后），总 17 页；旧 15 页与第 10 页原生图表 12 数值点未改（数值 `[108.117,107.483,129.590,111.168,129.359,182.926]` / `[39.187,37.394,38.389,40.837,38.826,36.707]` 前后一致）；旧 SHA `cb30936516931f11906b2eec17329f42a8ed4ec5f9bf5489a0492060faf5c69d` → 新 SHA `2b0d1df33664d21cfc14ff110edbf1d45e415aee55db53b2ead646a75a954be3`。
- **测试遗留清理**：全量 unittest 中 `tests/test_lwt_snake_workshop.py` 的符号链接测试在 `app/lwt_snake/strategies/` 留下 2 个 0 字节 `test-<uuid>.lwt`（S42/S43 同类遗留，`addCleanup` 在进程正常退出前未覆盖该路径）。执行窗口将其**移到工作区 `tmp/lwt_s44_test_leftovers/`（Git 外，可恢复），未删除、未提交**；`app/lwt_snake/` 工作树差异为空。这是既有测试行为，与本阶段无关。

## 8. 状态分层

- **执行实现**：完成（本窗口，证据见 §4）——**待主窗口复核**。
- **主窗口审查**：未开始（本报告交主窗口）。
- **合入 main**：未发生（本阶段不推送、不合并）。
- **远端 CI（最终 SHA）**：未查询（本阶段不推送，无远端最终 SHA）。
- **现场人工 GUI 验收**：未验证（本阶段 CLI/文档/PPT 证据不替代现场 A–E 项）。
- **教师验收 / 最终评分**：不属于本执行窗口，不声称。
