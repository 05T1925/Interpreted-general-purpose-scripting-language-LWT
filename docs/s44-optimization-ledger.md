# S44 优化台账：假设、测量、保留/回滚

> 每项改动独立测量；中位数提升 <2% 且无结构性收益的回滚。所有数字来自 `reports/s44-performance/` 的新 JSON 或明确标注的合成实验，**不**复制 S11/S42/S43 的旧数。口径见 [S44 计划](s44-performance-plan.md)。基线为 `344c255`（未复核 S43），分支 `feature/engine-performance`，未推送。

## 决策实验（先于产品改动）

### P0-3 分派方式：type 精确链 vs type→handler 表（合成实验，非产品代码）

在动手改 `_execute_statement`/`_evaluate` 前，用纯 Python 微实验（100 万次分派，7 次中位数）比较三种方式，避免盲目选择：

| 分布 | `isinstance` 链 | `type() is` 链 | `type→dict` 表 |
|---|---:|---:|---:|
| 均匀（10 类各 10%） | 136.780 ms | 86.661 ms | **50.059 ms** |
| 偏斜（90% 首分支） | 43.997 ms | 43.234 ms | 81.405 ms（最慢） |

**结论与取舍**：任务书 P0-3 建议"分派表"，但合成实验显示 dict 表在偏斜负载下反而最慢（固定 `dict.get` 开销 > 首分支命中）。真实 LWT 负载是偏斜的（Literal/Variable 在前部），因此：

1. **保留** `type(x) is T` 精确链（均匀快 1.58×、偏斜略快约 2%，零语义变化，AST dataclass 无子类）；
2. **不**采用 `type→dict` handler 表（偏斜回归风险）；
3. 补充 hoist 热路径 set 字面量（`_evaluate_binary` 的运算符集合），消除每次调用的集合分配。

这是对任务书措辞的**结构性偏离**，理由已在此记录；实现仍满足"精确类型分派"的意图，且由 `tests/test_dispatch_completeness.py` 保证节点类型分派完整。

## 改动台账

### P0-1 惰性加载调度器（WP1，已提交）

| 项 | 内容 |
|---|---|
| 假设 | `runtime.py`/`cli.py` 顶层导入 `lwt.concurrency` 拖入 `concurrent.futures`/`hashlib`/`json`/`tempfile`；非 spawn 程序不应付费 |
| 改动 | 新增轻量 `lwt/_sched_support.py`（异常类 + thread-local task id，仅依赖 threading）；`concurrency.py` re-export；`runtime.py`/`cli.py` 顶层只导入轻量模块，`Scheduler`/`ScheduleTracer`/`source_digest` 延迟到 spawn 分支；`Future` 移 `TYPE_CHECKING`；删除 runtime 未使用的 `import threading` |
| 闸门 | 非 spawn 程序 `sys.modules` 无 `lwt.concurrency` ✓（`tests/test_startup.py` 3 项）；spawn 仍输出正确 ✓；`--check`/`--profile`/`--repl`/三调度开关 ✓；S28 事件顺序不变（见 WP5 回归） |
| 启动 before/after | `--help` 624.170 → 496.773 ms（**1.256×，+25.6%**，达标 ≥15%）；`hello` 611.217 → 499.503 ms（**1.224×，+22.4%**，达标 ≥10%）；`help−pass` 258.8 → 153.564 ms（LWT 导入开销 −105.2 ms） |
| 保留/回滚 | **保留**（启动两项均超阈值，结构性收益明确） |

### P0-2 延迟重模块导入（WP1，已提交）

| 项 | 内容 |
|---|---|
| 假设 | `hashlib`/`json`/`tempfile`/typing 仅注解名可在函数内/`TYPE_CHECKING` 导入 |
| 改动 | `cli.py` 的 `hashlib` 移入 `_run_schedule`、`json`/`tempfile` 移入 profile 写函数、`ScheduleTracer`/`source_digest` 延迟导入；`modules.py` 的 `hashlib` 仅 `include_hash=True` 时导入；`runtime.py` 用 `TYPE_CHECKING` |
| 实测说明 | 本机 WorkBuddy 解释器在**裸 `python -c` 启动时已注入** `json`/`tempfile`，故这两项在本机 A/B 中无可测收益；但改动正确、零风险，在干净 CPython 上有收益 |
| 闸门 | `-X importtime`：`lwt.cli` 累计 234 → 152 ms（含 P0-1 贡献）；非重路径命令零新增重模块 ✓ |
| 保留/回滚 | **保留**（结构性收益，闸门全过） |

### P0-3 精确类型分派 + hoist 集合字面量（WP2，进行中）

| 项 | 内容 |
|---|---|
| 假设 | 精确 `type() is` 替代 AST 顶层 `isinstance` 链；运算符集合提为模块常量避免每次分配 |
| 改动 | `_execute_statement`(12 类)/`_evaluate`(13 类) 顶层 AST 分派 `isinstance` → `type() is`；`_unsupported_*` 扫描函数保持 `isinstance`（非热路径）；`_evaluate_binary` 的 3 个运算符 set + 数值原始类型 set 提为 `frozenset` 常量；未知类型 `AssertionError` 保留 |
| 闸门 | `tests/test_dispatch_completeness.py`（节点分派完整性 + 未知断言 + 值类型谓词未误改）；400/400 黑盒；46×10 确定性；S28 事件计数 |
| 纯执行 before/after | **最终 after（含 P1-4）** N=5000：arithmetic 32.504→22.349 ms（**1.454×**）、array_scan 110.945→71.474 ms（**1.552×**）、dict_counts 176.090→58.847 ms（**2.992×**）；3/3 负载 ≥15%，无回归。P0 单独提交时的 after 为 1.463×/1.490×/2.790×（见 `reports/s44-performance/after/` 历史提交 `27a0a6b`），P1-4 在此基础上进一步降低。注：P0-3 + P0-4 + set-hoist 是**组合**收益，单项未独立分离测量（改动集中在同一递归热路径，独立测量需多次回滚重建基线；见下方说明） |
| 保留/回滚 | **保留**（3/3 超阈值，组合结构性收益明确） |

> **组合测量说明**：任务书要求"每项独立提交、独立前后测量"。P0-3（type 分派 + set hoist）与 P0-4（字面量预解码）都落在 `_evaluate`/`_execute_statement` 同一递归热路径，且 before 基线只有一份。为遵守"不把所有改动塞进一个提交后再找原因"，我在改动前做了**分派方式的合成微实验**（见上表）作为 P0-3 的独立决策依据；最终 A/B 测的是两项组合。这是偏离严格"逐项 A/B"的取舍，理由与数据已如实记录，不把组合倍率冒称单项收益。

### P0-4 整数字面量预解码（WP2，进行中）

| 项 | 内容 |
|---|---|
| 假设 | 解析期把 INT lexeme 预解码进 `LiteralExpression.value`，执行期不再每次 `parse_decimal_integer` |
| 改动 | 新增依赖无关 `lwt/_decimal.py`（从 runtime 原样搬出分块转换器）；parser `_atom` 对 INT 填解码值；runtime 字面量分支直接返回 `value`（保留对直接构造 AST 的 INT/None 防御性回退）；runtime re-export 两函数保持 API |
| 闸门 | 6000 位整数、前导零、负数、任意精度黑盒（`arbitrary-precision-integer`）通过 ✓；`parse_decimal_integer` 分块算法未变（绕开 CPython int 字符串长度限制） |
| 纯执行 before/after | 与 P0-3 组合测量：N=5000 三负载 1.463×/1.490×/2.790×（见上）；循环内字面量 `i * 17 + 3` 的 17/3/1009/97 每次求值省一次字符串分块解析，是 array_scan/dict_counts 收益的重要来源 |
| 保留/回滚 | **保留**（6000 位/前导零/负数/任意精度闸门全过，组合收益超阈值） |

## P1 候选（WP3，逐项独立测量）

### P1-2 `Environment.resolve` 一次 `dict.get` + 哨兵 —— **未保留（回滚）**

| 项 | 内容 |
|---|---|
| 假设 | 新增 `resolve_value` 一次 `dict.get` 同时返回 scope 与值，省掉调用方第二次 hash 查找 |
| 实测（基线=已提交 P0 后，2 预热+7 正式） | arithmetic N=5000 1.031×、array_scan 1.004×、dict_counts 1.003×；N=1000 有回归迹象（0.848×/0.943×/1.015×） |
| 判定 | **回滚**：3 负载中 2 个 <2%、无结构性收益，按规则不保留；`git diff lwt/runtime.py` 回到 HEAD，零残留 |
| 教训 | 变量读取的 `dict` 二次查找在 CPython 3.13 已高度优化，方法调用开销抵消了收益；合成微基准未预示这一点，凸显"逐项实测"的必要性 |

### P1-4 `format_decimal_integer` 小整数 C 快路径 —— **保留**

| 项 | 内容 |
|---|---|
| 假设 | 绝对值 < 10^9 的整数走 CPython C 层 `str(int)`，大整数仍走分块算法绕开 4300 位限制 |
| 语义验证 | 6000 位 roundtrip、快路径边界（±999999999/±10^9）、10^50 大值全部与分块算法一致；`arbitrary-precision-integer` 黑盒通过 |
| 实测（基线=P0 后，2 预热+7 正式） | arithmetic N=5000 **1.035×**、array_scan **1.068×**、dict_counts **1.164×（+16.4%）**；N=1000 在噪声范围（0.977–1.094×）。最终 after（P0+P1-4 同一次测量，相对最初 before N=5000）：arithmetic **1.454×**、array_scan **1.552×**、dict_counts **2.992×** |
| 判定 | **保留**：N=5000 三负载均 ≥3.5%，dict_counts 因循环内 `str(key)` 高频调用收益显著，结构性收益明确 |

### P1-1 / P1-3 —— 未做（记录理由）

- **P1-1（record 字段集合缓存）**：三个 S11-v2 基准负载（arithmetic/array_scan/dict_counts）都**不涉及 record**，无法在冻结 workload 上测出收益；任务书禁止改 workload 或为测量新增自定义负载。因此无测量依据，不做（避免"看起来优化了"的无证据改动）。record 负载的潜在收益列为未验证项。
- **P1-3（内置函数表驱动）**：需把 `_invoke_builtin` 的 13 个分支抽成 handler 表，改动面大、风险高；P0 已使三负载全部 ≥1.46× 超额达标，边际收益不足以正当化回归风险。列为未验证/后续。

### 单元测试契约适配（P0-4 引起）

P0-4 有意改变 `LiteralExpression.value` 对 INT 的语义（从 `None` 变为解析期预解码的 `int`），这是任务书 P0-4 的明确要求。`tests/test_parser.py` 的 `test_long_integer_is_retained_without_conversion`（断言 `value is None`，反映 S2「词法阶段不调用 int()」的历史约束）随之失效。该测试已改名 `test_long_integer_is_predecoded_with_full_precision` 并改为断言新契约：预解码值正确、6000 位精度保持、`lexeme` 原样保留。**这不改任何黑盒期望**（`tests/cases/**` 零改动），只适配随实现契约变更的单元测试；测试意图（长整数不丢精度）被保留并加强。

**执行原则**：P0 已使纯执行目标（3/3 ≥15%）超额达标；P1 逐项独立测量，<2% 无结构性收益即回滚（P1-2 已据此回滚）。不为凑阈值扩大范围、不改 workload。
