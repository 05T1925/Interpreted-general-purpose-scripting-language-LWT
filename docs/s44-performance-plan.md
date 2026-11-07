# S44 可验证加速：性能计划与 A/B 协议

> 本文是 S44「LWT 执行引擎可验证加速」的开工计划（WP0）。**基线未经主窗口复核**：用户明确授权叠加在未复核的 S43 最终提交 `344c2559e4453c2d1ff0f63c0c28ce8dd108e238`（`feature/deterministic-concurrency`，7 笔提交，未推送/未合并/无标签）之上；`main = origin/main = 5027860` 不含 S43。S44 从该 SHA 创建 `feature/engine-performance`，不推送、不合并、不打标签。S43 报告见 [S43 执行报告](s42-deterministic-concurrency.md)。

## 1. 目标与非目标

**目标**：在不改变规范 §1–§11 可观察语义、400 项黑盒、46×10 并发确定性的前提下，让解释器启动与求值热路径的加速**可复核**：惰性加载可选子系统、精确类型分派、整数字面量预解码、局部缓存与少量环境/内置优化；用 S11-v2 分层基准证明「快在哪、快多少、为什么」。

**非目标**：不改词法/语法/语义/错误消息/退出码/调度点/轨迹 schema；不新增关键字或内置；不实现字节码 VM；不覆盖任何旧证据；不用 `eval`/`exec` 执行 LWT 源码；不宣称 CI/GUI/教师验收通过；不在 Python 3.10 / Linux / 远端实测（本机不可用时如实写未验证）。

## 2. 开工闸门与基线（WP0）

### 2.1 Git 原文（2026-11-07 16:49–16:52 +0800）

```
git status -sb           = ## feature/deterministic-concurrency（后切到 feature/engine-performance）
git rev-parse HEAD       = 344c2559e4453c2d1ff0f63c0c28ce8dd108e238
git rev-parse main       = 5027860efc8a1cce342ca13b1434d7724aeeffc4
git rev-parse origin/main= 5027860efc8a1cce342ca13b1434d7724aeeffc4
git tag --points-at HEAD = (空)
git worktree list        = 主工作树 @ 344c255；另有 s39-agent-strategy worktree（不触碰）
git log --oneline -12    = 344c255, ca2e563, e9bd715, fa37ec4, 4877aa1, 4d483f8,
                           fbd5532, a996591, 3b59f12, aec6076, 125b4db, 06fad50
```

基线裁决由用户明确授权「叠加在未复核的 S43 上」，因此本报告首段粗体记录"基线未经主窗口复核"。

### 2.2 环境（同机 A/B，不跨机器比）

| 项 | 值 |
|---|---|
| CPU | 13th Gen Intel(R) Core(TM) i9-13980HX；32 逻辑核 |
| 平台 | Windows-11-10.0.26200-SP0；AMD64 |
| Python（基线回归） | 3.13.14 / `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe`（无 tkinter） |
| Python（全量 unittest） | 系统 Python 3.13.7 + Tk，路径 `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe` |
| 电源方案 | Silent（GUID `64a64f24-65b9-4b56-befd-5ec1eaced9b3`） |
| 内存 | 15.6 GB |
| 背景负载 | WorkBuddy、云音乐、Edge WebView、ArmourySocketServer 等常驻；未清零，A/B 差值与中位数为准 |

**同机 A/B 约束**：before/after 使用同一可执行文件、同一 cwd（仓库根）、同一电源模式、同一协议；先跑 before，再改代码，再跑 after；正式样本交错配对以减小时间漂移。绝对数值受背景负载影响，只比较同机相对差值。

### 2.3 四项只读回归（任何一项失败即停）

| 命令 | 预期 | 基线实测 |
|---|---|---|
| `python tools/run_tests.py` | 400/400 | **passed=400 failed=0 total=400**（`concurrency=46/46`），elapsed 282.655s |
| `python tools/check_project_integrity.py` | cases=400; matrix_links=445; referenced_cases=348 | **OK; cases=400; matrix_links=445; referenced_cases=348** |
| `python -m unittest discover -s tests -q`（系统 Python） | 595 项左右 | 见 §6 收口（后台运行中） |
| `python tools/run_concurrency_determinism.py --repeat 10` | 46 项稳定 | **46 cases x 10 runs; stable=True; failures=0** |

> 注：`run_concurrency_determinism.py` 默认覆盖 `reports/s42-determinism.json`（S43 保护证据）。本次基线回归后已用 `git checkout --` 还原该文件，S43 证据零改动。WP5 回归须沿用「回归后还原」或给该工具加独立输出路径，不把受保护文件留痕。

### 2.4 基线性能测量（先于任何解释器代码改动）

基线产物写在 `reports/s44-performance/before/`，由 `tools/micro_bench.py` 的 `--out` / `--output-prefix` / `--label` 与新增 `tools/measure_startup.py` 生成；S42 的 `reports/runtime-profile.{json,md}` 与 S43 的 `reports/concurrency-performance.*` 均未改动。

- `tools/measure_startup.py`（2 预热 + 10 正式，交错配对）：`python-pass` 中位数 **365.370 ms**、`python -m lwt --help` **624.170 ms**、`python -m lwt examples/guide/hello.lwt` **611.217 ms**；`help − pass ≈ 258.800 ms`（LWT 包导入 + CLI 解析上界）。**`--help` 当前返回退出码 4**（`FileError: cannot read source file`），但同样触发完整导入链，已逐命令记录退出码并保持跨预热/正式稳定。
- `tools/micro_bench.py`（2 预热 + 7 正式，纯 `parse` / `execute` 阶段；本进程内、同一 AST）：见 `reports/s44-performance/before/runtime-profile.json`；N=5000 时 execute：arithmetic **32.504 ms**、array_scan **110.945 ms**、dict_counts **176.090 ms**（本机本次，协议与 S42 的 3 预热/20 次不同，绝对数不直接比 S42）。

### 2.5 已确认证据的协议复现（不重复怀疑）

- `lwt.concurrency` 顶层拖入 `concurrent.futures`（cum 53.8 ms）、`hashlib`（9.0 ms）、`json`、`tempfile`、`threading`；`lwt.cli` 累计导入 **234 ms**（本机 `-X importtime`，受负载影响）。`import lwt.runtime` 后 `sys.modules` 含 `lwt.concurrency` 与上述全部重模块。**这解释了 P0-1/P0-2 的结构性收益**：非并发程序不应为这些模块付费。
- S11 正式报告：`bench/results.json` 的 LWT/Python 端到端中位数比 2.7–5.0×，且明确写「S11 未实施解释器性能优化」。
- S42 画像：execute 占绝对主导（array_scan N=5000 execute 129.993 ms vs parse 1.860 ms）。
- S43 基线剖析：`_execute_statement` 累计 0.484 s、`_evaluate` 0.383 s、`isinstance` 1,272,726 次 0.117 s。
- S43 性能报告：`python -c pass` 300.039 ms、`python -m lwt --help` 571.218 ms（本机本次略高，见 §2.4）。

## 3. 优化假设台账（每项独立提交、独立前后测量）

| ID | 改动 | 预期 | 风险 | 必过闸门 |
|---|---|---|---|---|
| P0-1 | `runtime.py`/`cli.py` 不再顶层导入 `lwt.concurrency`；错误类移轻量模块；仅 spawn/调度开关时加载 | 非 spawn 启动省 100–200 ms | 中 | 非 spawn 程序 `sys.modules` 无 `lwt.concurrency`；spawn/三开关仍工作 |
| P0-2 | typing 仅注解名移 `TYPE_CHECKING`；`hashlib`/`json`/`tempfile` 改函数内导入；`modules` 仅 `include_hashes=True` 导 hashlib | 启动省 50–150 ms | 低 | `-X importtime` 前后比；`--check`/`--profile`/`--repl` 全过 |
| P0-3 | `_execute_statement`/`_evaluate` 用 `type(node)` 分派表替代长 `isinstance` 链；未知类型保留原断言；钩子顺序不变 | 纯执行 +10–25% | 中 | 400/400；46×10；S28 固定事件计数不变 |
| P0-4 | 解析期把 INT 字面量预解码进 `LiteralExpression.value`，执行期不调 `parse_decimal_integer` | 纯执行 +5–15% | 低 | 6000 位整数、前导零、负数用例不变 |
| P1-1 | 缓存 record 字段集合 | 记录负载 +3–10% | 低 | record 字段顺序/重复/缺失用例 |
| P1-2 | `Environment.resolve` 一次 `dict.get`+哨兵；函数调用直用 `global_environment` | +2–5% | 低 | 作用域/遮蔽/初始化顺序用例 |
| P1-3 | 内置函数名分派表驱动（保留原 arity/type 错误消息） | +3–8% | 低 | 内置边界用例 |
| P1-4 | `format_decimal_integer` 安全小整数走 `str(int)`；标识符 `sys.intern` | +1–5% | 低 | 任意精度/Unicode/显示用例 |

**保留/回滚规则**：每项独立提交、独立前后测量；中位数提升 <2% 且无结构性收益的回滚，台账写「未保留」。不得把所有改动塞进一个提交后再找原因。

## 4. 指标与阈值（第 6 节验收口径）

- **启动**：非 spawn 程序不得加载 `lwt.concurrency`；`--help` 中位数提升 ≥15%；`hello` 提升 ≥10%。未达标先定位导入链，不改小测试程序制造假象。
- **纯执行**（N=5000，3 负载至少 2 个）：中位数提升 ≥15%；任何负载不得回归 >5%。未达标回滚未证明改动，写负结果。
- **端到端**（S11-v2）：分开展示启动、解析、执行；端到端提升 ≥10%（2/3 负载）为亮点但不作为唯一门槛；进程启动噪声不明显时如实解释。
- **语义**：400/400、46×10 稳定、S28 固定事件计数一致、`--profile`/debugger/DAP/LSP 不回归、`git diff` 保护路径为空。
- **证据**：所有新数字来自新 JSON、可命令复算；不复制旧数、不混用 microbench `execute` 与 S11 端到端。

## 5. A/B 协议与保护数据

- 同一台机器、同一 Python 可执行文件、同一电源模式；先 before 再改代码再 after；正式样本交错配对。
- 记录每次 argv、cwd、exit code、stdout/stderr hash、`elapsed_ns`、source SHA、Git SHA、Python/CPU/平台/电源/背景负载。
- 新结果只写 `reports/s44-performance/{before,after}/` 与 `reports/s44-performance/benchmark-v2.{json,md}`、`startup.{json,md}`。
- **只读保护**：`bench/results.json`、`reports/performance.md`、`reports/app-concurrency.json`、`docs/app-concurrency.md`、`reports/app-lwt-profile.*`、`reports/lsp-smoke.json`、`reports/runtime-profile.*`（S42）、`reports/concurrency-performance.*`（S43）、`reports/s42-*`、`reports/s37..s41-*`、`tests/cases/**`、`app/log_report.lwt`、`app/lwt_snake/game.lwt`、策略/回放、PPT 旧 12 页图表数据。`measure_startup.py` 与 `micro_bench.py` 已加保护路径拒绝/独立输出目录。

## 6. 工作包与证据索引

| WP | 内容 | 证据/产物 |
|---|---|---|
| WP0 | 闸门、基线、计划、工具隔离 | 本文；`reports/s44-performance/before/{startup,runtime-profile}.{json,md}` |
| WP1 | 启动惰性化 P0-1/P0-2 | `tests/test_startup.py`；before/after startup |
| WP2 | 热路径 P0-3/P0-4 | AST 分派完整性测试；micro_bench 3×2 A/B |
| WP3 | 局部优化 P1-1–P1-4 | 逐项独立提交 + 台账 |
| WP4 | S11-v2 基准 | `tools/benchmark_v2.py`、`bench/dict_counts.py`、`tools/compare_perf.py`、`reports/s44-performance/benchmark-v2.{json,md}` |
| WP5 | 回归 + 覆盖闭环 | 400/400、595+、46×10、S28、覆盖矩阵、`tests/test_perf_tools.py` |
| WP6 | 文档/PPT/答辩 | `docs/s44-performance.md`、`docs/s44-optimization-ledger.md`、答辩卡/演示/PPT |
| WP7 | 收口 | 全量回归、状态文档、按 WP 提交、停止写入 |

## 7. 停止规则

1. 400 黑盒任一回归、46×10 任一不稳定、S28 固定事件计数变化 → 立即停，修复后再继续。
2. 保护文件出现 diff → 立即停并报告。
3. 某项优化中位数提升 <2% 且无结构性收益 → 回滚，不保留。
4. 启动验收未达标 → 先定位导入链，不进入 S11-v2 收口。
5. 纯执行目标未达标 → 停，提交负结果与原因分析，不扩大范围、不改 workload。
6. 无法在 Python 3.10/Linux/CI 验证 → 明确写「未验证」，不声称通过。
