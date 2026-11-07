# LWT 运行时微基准与热点画像（S44 baseline (before)）

> 本文件是 S44 baseline (before) 的**独立画像证据**，不是 S11 正式性能报告的修订。计时口径、原始 run 身份与六组表格仍以 [S11 报告](../../performance.md) 为准；本工具不写入 `bench/results.json`，也不改写任何 S10/S11/S28/S29 固定证据。

## 环境与口径

- 采集时间（UTC）：2026-11-07T09:00:20.114291Z
- Git HEAD：`344c2559e4453c2d1ff0f63c0c28ce8dd108e238`
- Python：`3.13.14 (main, Jun 11 2026, 04:04:46) [MSC v.1944 64 bit (AMD64)]`；平台：`Windows-11-10.0.26200-SP0`
- 工具：`tools/micro_bench.py`（schema v1）
- 每负载每规模：预热 2 次、计时 7 次；同一进程、同一已解析 AST，输出逐次与独立 oracle 比对。
- `parse` = 读源文件 + 词法 + 语法 + 模块链接；`execute` = 纯 AST 树遍历执行（**不含**进程创建、Python 启动和包导入）。因此本表中的 `execute` 不能直接与 S11 端到端墙钟倍率相减或相除。

## 阶段耗时（中位数，ms）

| 负载 | N | parse | execute | parse/execute | 输出校验 |
|---|---:|---:|---:|---:|---|
| arithmetic | 100 | 0.610 | 0.870 | 0.701 | pass |
| arithmetic | 1000 | 0.719 | 7.066 | 0.102 | pass |
| arithmetic | 5000 | 0.751 | 32.504 | 0.023 | pass |
| array_scan | 100 | 1.057 | 2.947 | 0.359 | pass |
| array_scan | 1000 | 1.192 | 24.455 | 0.049 | pass |
| array_scan | 5000 | 1.194 | 110.945 | 0.011 | pass |
| dict_counts | 100 | 0.937 | 1.802 | 0.520 | pass |
| dict_counts | 1000 | 0.908 | 15.801 | 0.057 | pass |
| dict_counts | 5000 | 0.807 | 176.090 | 0.005 | pass |

## 热点事件分布（S28 ProfileCollector，单次采集）

| 负载 | N | 事件总数 | 事件类型占比 |
|---|---:|---:|---|
| arithmetic | 1000 | 3008 | statement=2005 (66.7%), decision=1001 (33.3%), program_end=1 (0.0%), program_start=1 (0.0%) |
| array_scan | 1000 | 10024 | statement=7020 (70.0%), decision=3002 (29.9%), program_end=1 (0.0%), program_start=1 (0.0%) |
| dict_counts | 1000 | 6008 | statement=4005 (66.7%), decision=2001 (33.3%), program_end=1 (0.0%), program_start=1 (0.0%) |

## S43 决策规则（本轮只测量，不优化）

S42 **不实现字节码 VM**。是否进入 S43 VM 评估，按以下门槛判断：

1. 若 `execute` 阶段在总耗时中占主导，且 S28 事件分布显示 **>60% 事件落在高频语句/decision 分派**，才有必要评估寄存器式 VM 以减少分派开销；否则优先树遍历热点优化（热循环局部变量化、整数 opcode + 跳转表替代 Enum/`isinstance`、`@dataclass(slots=True)`、超级指令/指令融合）。
2. 任何 VM 方案必须以**双后端交叉验证**为首要价值（用独立后端暴露树遍历漏掉的正确性缺陷），性能只是副产品；不得只以倍率作为立项理由。
3. VM 结论必须绑定具体 CPython 版本：PEP 659 特化解释器会改变相对倍率，不得把某一版本的微基准外推到其它版本或真实负载。
4. 本表数据仅代表本机本进程内重复执行；不含启动与导入，不得与 S11 端到端 2.7–5.0× 混为一谈，也不得在 PPT/答辩中作为 S11 性能提升。

## 已知限制

- 微基准在**单进程**内重复执行，规避了进程启动噪声，因此看不到 S11 所量的启动/导入成本；它用于定位**解释器内部**耗时结构，不用于评价端到端用户体验。
- S28 profile 观测本身带来额外开销，事件分布只用于结构占比，不用于计时。
- 未在本轮运行 Python 3.10 / Linux / 远端 CI；相关兼容结论仍为未验证。
