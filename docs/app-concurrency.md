# LWT 日志分析器并发读取验证

- 生成时间（UTC）：`2026-10-07T06:40:09.617072+00:00`
- OS：`Windows-11-10.0.26200-SP0`
- Python：`3.13.7 (tags/v3.13.7:bcee1c3, Aug 14 2025, 14:15:11) [MSC v.1944 64 bit (AMD64)]`
- 阶段分支提交：`4e010043cde9239128ec13d61ec15e0ca2a44117`
- 应用文件提交：`f7bde96f95861c6090d343b0a181061b93b3d601`
- 应用源 SHA-256：`39807dd117813578896bc68165f161c48c106a99603a22406c7e4e637aa8acc1`
- 固定输入：`app/fixtures/concurrency.log` (7846 bytes)
- 输入 SHA-256：`512fa16f3d0ea7911709dbf4ee5a3ba13a05f926be01c071106973aa9909a118`
- 试验后输入 SHA-256：`512fa16f3d0ea7911709dbf4ee5a3ba13a05f926be01c071106973aa9909a118`（期间未改变：`True`）
- 命令：`C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m lwt app/log_report.lwt -- app/fixtures/concurrency.log`
- 单进程 warm-up：return code `0`，stderr bytes `0`，作为逐字比较基准。

每个计时试次通过 Python 线程池和 barrier 同时启动指定数量的独立 `python -m lwt` 子进程；计时使用 `perf_counter_ns()`，包含进程启动、解释器导入、解析、应用执行、输出和读取所需时间。每个子进程 timeout 为 30 秒。输出按字节与 warm-up stdout 比较，stderr 必须为空、return code 必须为 0。Python 线程仅用于协调外部进程，不是 LWT 线程或运行时并发。

| 进程数 | 试次数 | 每次批次墙钟时间（ms） | 每个进程输出一致 | return code / stderr |
|---:|---:|---|---|---|
| 1 | 5 | 114.724, 117.517, 119.408, 116.536, 119.902 | True | True / True |
| 2 | 5 | 128.779, 133.330, 131.858, 133.494, 132.105 | True | True / True |
| 4 | 5 | 141.669, 141.270, 139.623, 142.419, 139.272 | True | True / True |

全部逐试次原始记录（进程返回码、stdout/stderr 长度、SHA-256 和 Base64 原始字节）保存在 [`reports/app-concurrency.json`](../reports/app-concurrency.json)。

## 解释与限制

本次结果只证明固定输入在 1、2、4 个独立进程同时读取时输出一致，且保存了批次墙钟记录；不据此推断进程数增加会更快。样本规模、OS 文件缓存、进程启动与解释器解析成本、背景负载均会影响时间。输入文件在试验期间保持不变；不测试其他进程并发改写文件时的快照一致性。该实验不是 S11 的 LWT/Python 成对性能基准，也不是纯磁盘吞吐测试。
