# S43 并发 I/O 重叠性能实验（诚实口径）

> 本文件是 S43 新增的**独立性能证据**，不是 S11 正式性能报告的修订。原始 JSON 见 `concurrency-performance.json`（含每次规模、fixture SHA、run 身份）。S11 的 `bench/results.json` 与 `reports/performance.md` 未被读取或改写。所有数字只描述本机本次运行，未在 Linux / Python 3.10 / 远端 CI 实测。

## 1. 实验设计

- **fixture**：运行时在临时目录生成 8 个各 2 MB 的纯文本日志（共 16 MB，LF 边界），运行后删除，不入库；每个文件的 SHA-256 记录在 JSON 中（`fixtures.sha256_by_file`）。
- **四组**：
  1. `lwt_serial`：8 个独立 `python -m lwt app/log_report.lwt -- FILE_i` 进程的墙钟之和（S11 风格端到端：含启动、导入、解析、执行）。
  2. `lwt_concurrent`：1 个 `python -m lwt app/concurrent_log_report.lwt -- FILE_1 … FILE_8` 进程的墙钟（8 个任务、`read_text` I/O 重叠）。
  3. `py_serial`：单 Python 进程顺序读 8 文件并按 `|` 分栏计数。
  4. `py_threads`：单 Python 进程用 `ThreadPoolExecutor` 并发读同样 8 文件。
- **协议**：2 次预热 + 7 次正式，报中位数与 min/max；page cache 为热（同一批文件重复读）。Python 版本与平台、git HEAD 记录在 JSON。

## 2. 实测结果（本机 Windows / CPython 3.13.x，git HEAD `e9bd715`）

| 组 | 中位数 (ms) | min | max | 范围 |
|---|---:|---:|---:|---:|
| LWT 串行（8 独立进程之和） | 28635.862 | 27362.972 | 28919.893 | 1556.921 |
| LWT 并发（1 进程，8 任务） | 22119.246 | 20677.437 | 24248.744 | 3571.307 |
| Python 串行（1 进程） | 44.535 | 40.552 | 47.145 | 6.593 |
| Python 线程（1 进程线程池） | 53.815 | 51.060 | 58.875 | 7.815 |

派生比值：`lwt_serial / lwt_concurrent = 1.295`；`py_serial / py_threads = 0.828`。

启动基线（5 次中位数）：`python -c pass` = 300.039 ms；`python -m lwt --help` = 571.218 ms。

## 3. 诚实解读（关键）

**1.295× 不能全部归功于 I/O 重叠。** `lwt_serial` 是 8 次独立进程启动，`lwt_concurrent` 只有 1 次；每次 `python -m lwt` 启动+导入约 571 ms，7 次额外启动约 3997 ms，占串行-并发差值（28636 − 22119 = 6517 ms）的约 61%。因此该比值主要反映「少启动 7 次进程」+「I/O 等待重叠」+「并发调度开销」的**合成效果**，不能作为纯解释器加速比，更不能与 S11 的 2.7–5.0× 端到端倍率混用。

**Python 线程版反而更慢（0.828×）。** 在热 page cache 下，2 MB 文件读取是内存拷贝，真正阻塞的 I/O 等待占比很小；线程切换与 `ThreadPoolExecutor` 开销超过重叠收益。这与规范 §11.1/§11.8 的诚实结论一致：**LWT 并发的价值不在 CPU 加速，而在「等待型 I/O 重叠」与「交错可复现」**；当等待占比很小时，重叠收益可被开销抵消。

**Amdahl 上限。** 设可重叠的 I/O 等待占比为 `p`，单令牌模型下理论最好加速为 `1/(1-p)`。本实验未直接测得 `p`（需要额外的单进程内「纯顺序读」对照实验，见"未验证项"），因此**不给出具体加速上界数字**，只说明结构：CPU 部分（解析、分栏、计数）在单令牌下串行，不受 `spawn` 加速；重叠只作用于文件读取等待。

**与 S11 的关系。** S11 测的是新进程端到端（启动+导入+解析+执行）的 LWT/Python 倍率，是正式性能结论；本实验是 S43 新增的独立画像，服务于"并发是否带来可测的 I/O 重叠"这一问题，两者口径不同、互不替代。答辩时应分别引用，不把 1.295× 说成 S11 性能提升。

## 4. 未验证项

- **纯 I/O 重叠的隔离测量**：未在单进程内做「顺序读 8 文件 vs 并发读 8 文件」的严格对照（那需要额外基准程序），因此无法把 1.295× 精确拆成"启动节省"与"重叠收益"两部分；本文用启动基线做了近似归属，标明为推算而非实测分解。
- **冷 page cache**：本实验是热缓存重复读；冷缓存（首次读、OS 缓存未命中）下 I/O 等待占比更高，重叠收益可能不同，未实测。
- **Linux / Python 3.10 / 远端 CI**：未在这些环境运行；`random:SEED` 跨版本一致性由 splitmix64 算法保证（规范 §11.4），但实测只在本机 Windows CPython 3.13.x。
- **大规模文件**：8×2 MB 是任务书建议规模；更大文件或网络挂载（规范明确不在契约内）未测。

## 5. 复算命令

```bash
python tools/run_concurrency_benchmark.py --files 8 --size-mb 2 --repeats 7
```

该命令会重新生成临时 fixture、跑四组、覆盖 `reports/concurrency-performance.json`；本报告的数字对应该 JSON 的 git HEAD `e9bd715` 那次运行。保护数据（`bench/results.json`、`reports/performance.md` 等）不受影响。
