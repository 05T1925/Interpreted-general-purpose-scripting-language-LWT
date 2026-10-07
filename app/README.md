# LWT 日志分析器

`log_report.lwt` 是一个只读的日志统计 CLI 程序。它从一个 UTF-8 文本文件读取记录，在 stdout 输出固定格式的报告，不修改输入文件，也不写其他应用输出文件。

## 运行

从仓库根目录执行：

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log
```

参数形式如下；三个选项可以按任意顺序出现，每种最多一次：

```text
python -m lwt app/log_report.lwt -- INPUT_PATH [--level LEVEL] [--keyword TEXT] [--top N]
```

- `INPUT_PATH` 必须是第一个应用参数，且不能为空。相对路径按**进程当前工作目录**解析；示例命令均从仓库根目录运行。
- `--level LEVEL` 对第二字段作区分大小写的精确匹配。
- `--keyword TEXT` 对第四字段 message 作区分大小写的子串匹配；不检查时间、级别或模块，不能为空。
- 同时给出 `--level` 和 `--keyword` 时使用 AND 条件。
- `--top N` 限制模块排行项数，默认 `5`；只接受 ASCII 数字组成的非负十进制整数。`0` 保留排行标题但不输出排行条目。
- 未知、重复、缺值的选项，额外位置参数、缺少路径、空 keyword 和不合法 top 都通过 LWT `fail()` 给出单行 usage 诊断；stdout 为空、进程非零退出，不产生 Python traceback。

所有参数错误都在打开文件和打印报告前检查。文件不存在、不可读取或不是有效 UTF-8 时由 `read_text()` 报运行时错误，退出码为 3；这类错误同样不会打印应用报告或 Python traceback。

## 输入记录与坏行

每个逻辑行使用四字段格式：

```text
timestamp|level|module|message
```

时间戳是原样保留的不透明文本，不解析日期；字段不作裁剪。字段数恰好为 4 就是有效记录，空字段允许。字段数少于或多于 4 的行（包括空行，以及 message 含额外 `|` 的行）计为坏行；应用继续分析后续行。其他字段内容不作额外校验。UTF-8 BOM 与 CRLF/CR 按 LWT `read_text()` 规范处理。

空文件有 0 条逻辑行。文本按 LF 切分后，如果最后一个切分元素为空，只去掉这一个元素作为行结束结果。因此一个终止 LF 不增加行数；多个连续终止 LF 中，除最后一个外，之前产生的空逻辑行仍会作为坏行计入。无终止 LF 的最后一行仍参与处理。

默认示例 [`fixtures/sample.log`](fixtures/sample.log) 含 6 条有效记录和 1 条坏记录；完整期望输出在 [`fixtures/sample.expected.txt`](fixtures/sample.expected.txt)。异常样本 [`fixtures/malformed.log`](fixtures/malformed.log) 展示空行、短行和多字段行如何计数。

## 过滤、统计与输出

先统计逻辑行、有效记录和坏行；再对有效记录应用过滤条件。`Matched records`、级别统计、模块排行和匹配示例都只针对匹配记录。级别统计按 level 字符串升序排列；模块先按出现次数降序，次数相同时按模块名升序。匹配示例是原文件顺序中的前三条匹配记录。`--top` 只裁剪模块排行，不影响级别统计和匹配示例。

报告固定包含以下 section，顺序不变；空 section 保留标题且不增加空行：

1. 固定标题 `LWT log report`
2. `Total lines`、`Valid records`、`Malformed lines`、`Matched records`
3. `Level counts:` 及各 `LEVEL|COUNT` 项
4. `Top modules:` 及各 `MODULE|COUNT` 项
5. `Matching examples (first 3):` 及原始记录行

过滤示例：

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2
```

该命令匹配一条记录：级别为 `WARN|1`，模块为 `cache|1`，示例行为 `2026-10-07T10:00:03Z|WARN|cache|retry scheduled`。正常报告不包含输入路径、当前时间或耗时，因此对同一输入和参数重复运行会产生相同输出。

## 实现限制与复杂度

应用一次性用 `read_text()` 读取整个文件，并在内存中保存逻辑行和解析出的匹配 record；它不适合超大日志流式处理。没有字典数据类型，级别与模块通过数组线性查找聚合。若 `R` 条有效记录都匹配、`M` 是不同模块数、`L` 是不同级别数，聚合最坏约为 `O(R × (M + L))`；关键字拆分另随 message 长度增长。级别排序约 `O(L²)`；模块排行每选出一项扫描候选数组，输出 `K = min(M, top)` 项时约 `O(M × K)`。空间复杂度包含整个输入、行数组、记录数组和 `O(M + L)` 聚合项。

## 独立进程读取验证

可运行：

```powershell
python tools/run_app_concurrency.py
```

工具用同一个 [`fixtures/concurrency.log`](fixtures/concurrency.log)、同一命令和当前应用文件，分别并发启动 1、2、4 个独立 `python -m lwt` 操作系统进程；每组先做 warm-up，再进行 5 个计时试次，逐字节核对 stdout、空 stderr 和退出码。Python 线程池只负责同时调度子进程，**这不是 LWT 线程、语言级并发或并行加速结论**。原始数据和解释见 [`../docs/app-concurrency.md`](../docs/app-concurrency.md) 与 [`../reports/app-concurrency.json`](../reports/app-concurrency.json)。

固定 fixture 的完整行为通过 `tests/test_app.py` 经公开 CLI 测试；该应用测试不加入 S8 的 194 项语言黑盒覆盖矩阵。
