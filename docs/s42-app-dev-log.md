# S43 并发应用 Agent 开发记录：concurrent_log_report.lwt

> 记录格式沿用 S10 日志分析器：提示、产出、人工修正、验证命令。本应用由执行窗口内的 Agent 编写，全部逻辑在 LWT 中；Python 只负责进程/参数/校验（本阶段未新增 Python 应用驱动，直接用 `python -m lwt` 公共入口）。

## 1. 提示与目标

按任务书 WP6：写一个 ≥200 行有效 LWT 的并发应用 `app/concurrent_log_report.lwt`，接受多个日志路径，每个文件 `spawn` 一个任务读取并解析，结果经通道送回，主任务**按输入顺序**归并（不排序、不依赖完成顺序），输出固定格式摘要；至少演示一次 `attempt/recover`（坏文件不拖垮全局）与一次死锁边界注释；与 `app/log_report.lwt` 对同一组输入差分等价。

## 2. 产出

- `app/concurrent_log_report.lwt`：**233 行有效 LWT**（`python tools/count_lwt_lines.py` 实测）。
- 结构：复用串行应用的 `LogRecord`/`Count`/`Slice` record、`logical_lines`/`parse_log_line`/`add_count`/`count_array`/`emit_level_counts`/`emit_top_modules`/`emit_examples` 逻辑；新增 `Slice` 统计载体、`failed_slice` 容错、`worker(path, ch)` 并发体、`main()` 的按输入顺序收集与 `join`。
- 并发模型：`validate_paths` 校验参数 → 为每个文件创建**专属通道** → `spawn worker(path, ch)` → 主任务按输入顺序 `receive(ch)` 并 `emit_slice` → 末尾 `join` 所有任务（I7 无泄漏、§11.7 收尾）。专属通道保证输出顺序 = 输入顺序，与哪个 worker 先完成无关。
- 容错：`worker` 内 `attempt { read_text … } recover (problem) { send(ch, failed_slice(path)); }`——单个坏文件不会中断其它文件的报告（实测 1 坏 + 1 好 → 2 个块，坏块标记 unavailable、好块正常）。
- 死锁边界注释：`main` 中 `receive` 循环上方明确写"若 worker 从未 send，调度器报 `deadlock detected` 而非挂死（§11.6）"。

## 3. 差分等价契约

任务书要求并发版与串行版对同一组输入逐字节一致；多文件摘要无法与单文件串行调用逐字节相同，故冻结**逐字段映射**：

| 并发应用（单文件） | 串行 `app/log_report.lwt -- FILE` | 映射 |
|---|---|---|
| 第 1 行 `=== FILE ===` | 无 | 新增的源文件标识块头，核对时剥离 |
| 第 2 行起 `LWT log report` … | 第 1 行起 `LWT log report` … | 报告正文逐字节相同 |

多文件时，每个输入文件按顺序产生一个上述块；块 `i` 的正文与 `app/log_report.lwt -- FILE_i` 的输出逐字节相同。测试逐块比对正文（剥离块头）与串行输出，并核对退出码与 stderr。差分等价验证工具/结果见 WP8 阶段报告与 `reports/` 下证据。

## 4. 人工修正与验证

- 初版 `worker` 直接 `send(ch, slice)`，未捕获 `read_text` 失败；人工加入 `attempt/recover` 与 `failed_slice`，使坏文件不拖垮全局。
- 初版考虑用共享数组按索引写入，但数组下标赋值遇到未扩展长度会报错；改用**每文件专属通道**方案，更符合"each 浅快照不变"与确定性归并。
- 静态检查 `python -m lwt --check app/concurrent_log_report.lwt` 通过（0）。
- 实测命令与结果：
  - `python tools/count_lwt_lines.py app/concurrent_log_report.lwt` → `233`。
  - `python -m lwt app/concurrent_log_report.lwt -- app/fixtures/sample.log app/fixtures/showcase.log` → 退出 0，2 个按输入顺序的块。
  - 差分等价（4 个 fixture 文件逐一）：串行输出 == 并发单文件输出剥离块头，退出码与 stderr 均相同，**4/4 PASS**。
  - 坏文件容错：`-- does-not-exist.log app/fixtures/sample.log` → 2 个块，坏块 `LWT log report (unavailable)`、好块正常，退出 0。
  - 确定性：多文件运行 10 次输出 sha256 全部相同（1 个唯一哈希）。

## 5. 限制

- 并发只在 `read_text` 的等待期重叠；CPU 解析/计数仍在单令牌下串行执行，不加速（GIL + 单令牌，见规范 §11.1/§11.8）。性能实验见 WP6 `reports/concurrency-performance.*`。
- 差分等价按"每文件报告块正文"核对；多文件聚合输出是逐块拼接，不与任何单次串行调用逐字节相同（这是任务书允许的"多文件摘要格式"差异，已在上表冻结映射）。
- I/O 调度点只保证**普通文件**的重叠；FIFO、设备文件、网络挂载的终止性不在契约内（规范 §11.8），测试只用普通文件。
