# S11-v2 分层性能基准（S44 优化验证附录）

> 本文件是 S44 的**独立优化验证附录**，不是 S11 正式性能报告的修订。`bench/results.json` 与 `reports/performance.md` 未被读取或改写。
> 端到端为新进程墙钟（启动+导入+解析+执行）；纯 parse/execute 来自同协议的 micro_bench A/B。**端到端倍率不含分层拆解时不称为纯执行倍率。**

## 环境与协议

- 采集时间（UTC）：2026-11-07T09:36:44.106653+00:00
- Git HEAD：`639d0e3cd6e0b5eb8fa1b0cacca4be7742d69edd`（分支 `feature/engine-performance`）
- Python：`3.13.14 (main, Jun 11 2026, 04:04:46) [MSC v.1944 64 bit (AMD64)]`；可执行：`C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- 平台：`Windows-11-10.0.26200-SP0`；CPU：`13th Gen Intel(R) Core(TM) i9-13980HX`；逻辑核 32；电源 `电源方案 GUID: 64a64f24-65b9-4b56-befd-5ec1eaced9b3 (Silent)`
- 协议：2 预热 + 7 正式，seed 20261107 交错配对；每次逐字节 oracle 校验（126 次正式全部通过）。

## A. 端到端（新进程墙钟，中位数 ms）

| 负载 | N | LWT | Python | LWT/Python |
|---|---:|---:|---:|---:|
| arithmetic | 100 | 459.796 | 305.383 | 1.506× |
| arithmetic | 1000 | 450.926 | 303.524 | 1.486× |
| arithmetic | 5000 | 497.284 | 325.232 | 1.529× |
| array_scan | 100 | 451.157 | 300.918 | 1.499× |
| array_scan | 1000 | 483.705 | 297.112 | 1.628× |
| array_scan | 5000 | 530.853 | 296.133 | 1.793× |
| dict_counts | 100 | 450.998 | 304.295 | 1.482× |
| dict_counts | 1000 | 464.160 | 313.899 | 1.479× |
| dict_counts | 5000 | 520.176 | 317.000 | 1.641× |

## B. 分层：纯执行 execute（micro_bench A/B，中位数 ms）

同机 before/after 均 2 预热 + 7 正式、单进程内同一 AST、逐次 oracle 校验。此段不含进程启动与包导入；不与上段端到端倍率相减或相除。

| 负载 | N | before | after | 提升 |
|---|---:|---:|---:|---:|
| arithmetic | 100 | 0.870 | 0.524 | 1.661× |
| arithmetic | 1000 | 7.066 | 4.733 | 1.493× |
| arithmetic | 5000 | 32.504 | 22.349 | 1.454× |
| array_scan | 100 | 2.947 | 1.877 | 1.570× |
| array_scan | 1000 | 24.455 | 15.834 | 1.544× |
| array_scan | 5000 | 110.945 | 71.474 | 1.552× |
| dict_counts | 100 | 1.802 | 1.305 | 1.380× |
| dict_counts | 1000 | 15.801 | 10.528 | 1.501× |
| dict_counts | 5000 | 176.090 | 58.847 | 2.992× |

## C. 四段口径与限制

- **启动/导入**：`python -c pass` vs `python -m lwt --help` 的中位数差（`reports/s44-performance/{before,after}/startup.json`）。
- **解析 parse**、**纯执行 execute**：micro_bench 同进程分层（本报告 B 段）。
- **端到端**：本报告 A 段，含启动+导入+解析+执行+输出。
- LWT/Python 端到端仍慢，主要来自解释器的分派/对象分配与包导入；S44 优化的是分层中的启动与纯执行，不把端到端倍率说成纯执行倍率。
- 只在本机本次运行有效；未在本机 Python 3.10 / Linux / 远端 CI 复验；背景负载、电源、page cache 影响绝对值，同机 A/B 差值与中位数为准。
