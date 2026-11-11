# S52 补充性能测量：时间分位数与空间峰值

> **这是 S52 的补充测量，不是 S11 正式结果的替代。** S11 的 `bench/results.json` 与 `reports/performance.md`、S44 的 `reports/s44-performance/` 均未修改（见 §5 冻结输入）。

## 1. 目标、基线与停手判据（第 7 章 7.1/7.2）

- **目标**：在 N=100/1000/5000 的三个既有负载上给出可复现的 p50/p95/p99 与峰值内存；不追求比 CPython 快，目标是第 7 章要求的测量方法与空间维度。
- **基线**：S11 正式中位数（reports/performance.md）与 S44 分层加速（reports/s44-performance/）为基线；本文件只做补充测量，不替代、不修改它们。
- **停手**：若 S44 compare_perf 门槛仍满足、且 S52 复测 p95 相对本文件波动 <15%，停止优化；若某优化使峰值内存单调上升或无时间收益，按第 7 章“无收益即回滚”。
- **环境**：Windows-11-10.0.26200-SP0；Python 3.13.14；裸解释器启动地板 p50 = **320.68 ms**（CLI 墙钟包含它，故同时给净时间）。

## 2. 方法

| 维度 | 做法 | 说明 |
|---|---|---|
| 时间 | 子进程跑 `python -m lwt bench/<w>.lwt -- N`，2 次预热 + 9 次正式，nearest-rank 分位数 | 不用平均值掩盖尾部；`net_*` = 墙钟 − 启动地板 |
| 空间（进程内） | `tracemalloc.get_traced_memory()` 的单次 CLI 调用峰值 | 跨平台；只覆盖 Python 堆分配 |
| 空间（子进程） | Windows `psapi.GetProcessMemoryInfo` 每 20 ms 采样 WorkingSetSize | 非 Windows 为 `null`；RSS 含解释器基线，不宜当精确增量 |
| 压力 | `array_scan` 在 N=1000/5000/20000 的规模扫描 | **有界**，不是 soak，不证明 7×24 稳定 |

## 3. 时间分位数与内存峰值

| 负载 | N | p50 ms | p95 ms | p99 ms | 净 p50 ms | peak_bytes | 子进程 RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|
| arithmetic | 100 | 489.22 | 508.51 | 508.51 | 168.54 | 21468 | 28.2 |
| arithmetic | 1000 | 493.83 | 543.36 | 543.36 | 173.15 | 21421 | 27.1 |
| arithmetic | 5000 | 512.68 | 531.32 | 531.32 | 192.00 | 21525 | 30.0 |
| array_scan | 100 | 484.32 | 505.29 | 505.29 | 163.64 | 51103 | 26.8 |
| array_scan | 1000 | 503.44 | 540.13 | 540.13 | 182.76 | 67020 | 30.4 |
| array_scan | 5000 | 569.08 | 591.75 | 591.75 | 248.40 | 208516 | 26.5 |
| dict_counts | 100 | 484.02 | 507.79 | 507.79 | 163.34 | 45473 | 28.3 |
| dict_counts | 1000 | 503.71 | 535.97 | 535.97 | 183.03 | 107504 | 26.6 |
| dict_counts | 5000 | 546.25 | 593.14 | 593.14 | 225.57 | 107973 | 30.6 |

**读法**：p95/p99 与 p50 的差距反映尾部抖动；`peak_bytes` 随 N 增长的是数据结构本身（array_scan 51 KB→208 KB、dict_counts 45 KB→108 KB），arithmetic 近似常数（O(1) 工作集）。子进程 RSS 在 28–33 MB 间波动，主要是解释器基线，不能用它推断小规模泄漏。

## 4. 有界压力扫描（array_scan）

| N | p50 ms | peak_bytes | 子进程 RSS (MB) |
|---:|---:|---:|---:|
| 1000 | 488.30 | 72508 | 29.6 |
| 5000 | 535.63 | 200564 | 30.6 |
| 20000 | 791.96 | 689734 | 26.9 |

`peak_bytes_monotonic = True`。时间从约 0.49 s 升到 0.79 s，峰值从 72 KB 升到 690 KB，说明规模上升时工作集与耗时同步增长；**没有**观察到峰值在固定 N 下持续上升的泄漏信号，但本实验**不证明**长时间运行无泄漏（这是有界规模扫描，不是长时间 soak；不证明 7×24 稳定，也不证明无泄漏。）。

## 5. 冻结输入与平台边界

| 文件 | 状态 |
|---|---|
| `bench/results.json`（S11） | 只读，未改 |
| `reports/performance.md`（S11） | 只读，未改 |
| `reports/s44-performance/`（S44） | 只读，未改 |
| `platforms.ubuntu.maximum_resident_set_kb` | `null`：未在 CI 采集 `/usr/bin/time -v` 或 `resource.getrusage`（Unix-only），**未验证** |

## 6. 观察 → 假设 → 验证（第 7 章三段式）

1. **观察**：S11 只有中位数，无法回答尾部与空间；S52 复测 p95/p99 与峰值。
2. **假设**：若规模增长导致工作集线性增长，`peak_bytes` 应随 N 单调上升；若时间被启动地板主导，净 p50 在小 N 上应接近常数。
3. **验证**：array_scan 的 peak 单调上升（72→200→690 KB），净 p50 随 N 增长；arithmetic 的 peak 近似常数，符合 O(1) 工作集。结论只覆盖本机、本负载、本规模。

## 7. 复现

```bash
python tools/measure_memory_profile.py
```

> 输出同时写入 `reports/s52-course-align/performance-space.json`（机器可读）与本文件（人读）。
