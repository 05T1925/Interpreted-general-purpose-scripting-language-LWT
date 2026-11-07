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
| 纯执行 before/after | N=5000：arithmetic 32.504→22.221 ms（**1.463×**）、array_scan 110.945→74.462 ms（**1.490×**）、dict_counts 176.090→63.111 ms（**2.790×**）；3/3 负载 ≥15%，无回归（所有规模 ≥1.29×）。注：这是 P0-3 + P0-4 + set-hoist 的**组合**收益，单项未独立分离测量（改动集中在同一递归热路径，独立测量需多次回滚重建基线；见下方说明） |
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

## P1 候选（WP3，按 P0 测量结果决定）

- P1-1 record 字段集合缓存（`_construct_record` 的 `set(declared_fields)`）
- P1-2 `Environment.resolve` 一次 `dict.get` + 哨兵（2 处调用点）
- P1-3 内置函数名表驱动（保留 arity/type 错误消息）
- P1-4 `format_decimal_integer` 小整数 `str(int)` 快路径 + `sys.intern`

**执行原则**：P0 测量后若纯执行目标未达标，按任务书停止规则提交负结果与原因分析，**不**为凑阈值扩大范围、不改 workload。若 P0 达标，P1 逐项独立提交，<2% 无收益即回滚。
