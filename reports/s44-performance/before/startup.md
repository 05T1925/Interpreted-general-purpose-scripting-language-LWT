# LWT 启动成本测量（S44 baseline (before)）

> 独立证据；新进程端到端墙钟，含 Python 启动 + 包导入 + CLI 解析；不是纯 AST 执行速度。复算见 `tools/measure_startup.py`，原始逐次样本见同名 JSON。

> 说明：python -m lwt --help currently exits 4 (FileError: cannot read source file); the measurement still captures the full package-import + CLI-parse path. Exit codes are recorded per command and held stable across warm-ups and formal runs.

## 环境与协议

- 采集时间（UTC）：2026-11-07T09:00:07.549707+00:00
- Git HEAD：`344c2559e4453c2d1ff0f63c0c28ce8dd108e238`（分支 `feature/engine-performance`）
- Python：`3.13.14 (main, Jun 11 2026, 04:04:46) [MSC v.1944 64 bit (AMD64)]`；可执行：`C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- 平台：`Windows-11-10.0.26200-SP0`；CPU：`13th Gen Intel(R) Core(TM) i9-13980HX`；逻辑核 32
- 电源方案：`电源方案 GUID: 64a64f24-65b9-4b56-befd-5ec1eaced9b3 (Silent)`
- 协议：2 预热 + 10 正式，interleaved round-robin blocks，perf_counter_ns 紧贴 subprocess.run。

## 结果（中位数 / min / max / range，ms）

| 命令 | 中位数 | min | max | range | 退出码 |
|---|---:|---:|---:|---:|---:|
| `python -c pass` | 365.370 | 338.169 | 420.912 | 82.743 | 0 |
| `python -m lwt --help` | 624.170 | 592.646 | 673.184 | 80.538 | 4 |
| `python -m lwt examples/guide/hello.lwt` | 611.217 | 589.426 | 705.466 | 116.040 | 0 |

## 派生量

- `--help − pass` 中位数差：258.800 ms（LWT 包导入 + CLI 解析的近似上界）
- `hello − pass` 中位数差：245.847 ms（上项 + 词法/语法 + 极小程序执行）
- `--help / pass`：1.708；`hello / pass`：1.673

## 限制

- 只在本机本次运行有效；未在 Python 3.10 / Linux / 远端 CI 复验。
- 背景负载、电源模式、page cache 与 CPU 调度会影响绝对数值；以同机 A/B 差值与中位数为准。
- 这些数值是端到端墙钟，不能与 `micro_bench.py` 的纯 `execute` 阶段相减或相除。
