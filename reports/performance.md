# LWT/Python 成对性能实验报告

> 本报告呈现新进程端到端墙钟时间，不是纯 AST 执行速度、CPU 时间或磁盘吞吐率。统计数字由 `bench/results.json` 的有效正式运行逐项复算。

## 目的与工作负载

本实验响应课程“使用 LWT 脚本进行性能测试，并与相同功能 Python 脚本比较”的要求。`arithmetic` 逐项累加 1 到 N；`array_scan` 用第一遍循环构造 `(i*17+3)%1009` 数组，再用第二遍循环计算元素总和及 `%97==0` 的数量。两侧使用相同正整数 N、显式循环和一行十进制输出：前者为 `N|sum\n`，后者为 `N|sum|hits\n`。Python 被测脚本没有用 `sum`、推导式或生成器替代循环。runner 在计时外另行计算预期值，并要求 LWT、Python 输出字节分别匹配预期且彼此相同。

按规模 N 传参的命令形式为 `python -m lwt bench/arithmetic.lwt -- N` / `python bench/arithmetic.py N`，以及 `python -m lwt bench/array_scan.lwt -- N` / `python bench/array_scan.py N`。raw JSON 为每个实际子进程保存含当前 `sys.executable` 的完整 argv 和固定仓库根目录 cwd。

## 协议

- 命令从仓库根目录启动，使用 `sys.executable`、argv 数组、`shell=False`、stdin=`DEVNULL`、stdout/stderr 字节捕获及有限 timeout。每次 warm-up 和正式试次都是独立的新进程；先逐一校验 warm-up，再进行正式试次。
- 正式样本按固定 seed 随机排列配对块，并在每对内随机 LWT/Python 先后顺序；同一时刻仅运行一个被测子进程。
- `perf_counter_ns()` 紧贴一次 `subprocess.run()` 前后调用。端到端时间包括子进程创建、Python 启动、LWT 包导入与源码词法/语法分析、工作负载、输出生成及等待进程退出；不包括 runner 的输出解码、验证、统计、哈希和 JSON 写入。
- 原始纳秒整数保存于 JSON。表格统一将 ns 除以 1,000,000 换为 ms，固定显示三位小数；range=max−min；比值=LWT median/Python median。比值大于 1 表示该组 LWT 中位时间较长。
- calibration 运行用于确认规模是否可在目标环境完成，不进入正式统计。全部失败/无效尝试仍保存在 JSON；无效 run 不生成有效性能表格。

计时依据：[Python 3.10 `perf_counter_ns`](https://docs.python.org/3.10/library/time.html#time.perf_counter_ns)、[Python 3.10 `subprocess.run`](https://docs.python.org/3.10/library/subprocess.html)、[`timeit` 重复测量说明](https://docs.python.org/3.10/library/timeit.html)。官方文档指出 `perf_counter` 适于测短时差值并包含等待时间；`timeit` 说明重复样本会受其他进程干扰，因此本报告保留中位数及完整离散范围，不只选择最快值。

## 校准记录（不计入正式结果）

### 354fccce-bba0-4690-ad33-6a7811562a1a（`invalid`）

- Git SHA：`b69fe8a76217212497d89b76274b7a7d6c1d9c0a`；开始时工作区干净：`True`；warm-up `12` 条，校准计时 `0` 条。
- 该校准因 6 条 warm-up 未通过而停止；按协议未启动计时校准。失败详情和原始字节见 raw JSON。本次观察到的 Windows Python 文本 stdout 使用 CRLF，而 LWT 契约输出 LF；修复后的 Python workload 改用 ASCII 字节写出。该失败运行保留，不纳入任何性能数字。

### a3c713d5-93d1-4479-8653-91af2eb3dc12（`valid`）

- Git SHA：`6ef01ce9e3fcb168b073e6ea434496db5e4eaca7`；开始时工作区干净：`True`；warm-up `12` 条，校准计时 `12` 条。
- 校准持续时间只用于确认三种规模可完成；规模 N=100、1000、5000 在校准后保持不变。选择规模依据是它们代表小/中/大循环工作量，最大规模在此次环境内可完成；未根据 LWT/Python 结果优劣挑选。校准数据不属于正式试次。

| benchmark | N | LWT calibration (ms) | Python calibration (ms) |
|---|---:|---:|---:|
| arithmetic | 100 | 106.721 | 40.933 |
| arithmetic | 1000 | 110.322 | 37.942 |
| arithmetic | 5000 | 125.627 | 39.552 |
| array_scan | 100 | 110.795 | 38.274 |
| array_scan | 1000 | 131.542 | 39.826 |
| array_scan | 5000 | 194.085 | 40.732 |

## 正式结果

| benchmark | N | 配对数 | LWT median (ms) | LWT min (ms) | LWT max (ms) | LWT range (ms) | Python median (ms) | Python min (ms) | Python max (ms) | Python range (ms) | median ratio LWT/Python |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| arithmetic | 100 | 10 | 108.117 | 103.070 | 122.555 | 19.485 | 39.187 | 33.344 | 52.261 | 18.917 | 2.759 |
| arithmetic | 1000 | 10 | 107.483 | 102.548 | 134.646 | 32.098 | 37.394 | 33.462 | 51.255 | 17.793 | 2.874 |
| arithmetic | 5000 | 10 | 129.590 | 124.769 | 143.968 | 19.199 | 38.389 | 34.185 | 48.240 | 14.055 | 3.376 |
| array_scan | 100 | 10 | 111.168 | 100.657 | 130.652 | 29.995 | 40.837 | 36.609 | 58.113 | 21.505 | 2.722 |
| array_scan | 1000 | 10 | 129.359 | 111.726 | 160.946 | 49.221 | 38.826 | 34.848 | 48.945 | 14.097 | 3.332 |
| array_scan | 5000 | 10 | 182.926 | 177.544 | 223.719 | 46.175 | 36.707 | 35.412 | 44.847 | 9.435 | 4.983 |
在 run `291bd4e2-8a3e-4de6-be86-46b62980e656` 的 arithmetic 样本中，N 从 100 增至 5000 时，LWT median 为 108.117→129.590 ms，Python median 为 39.187→38.389 ms，中位数比值为 2.759→3.376。这只描述本机的端到端样本；进程启动和导入/解析成本占比可能遮蔽循环本身的变化，不能据此推断纯运行时倍率。
在 run `291bd4e2-8a3e-4de6-be86-46b62980e656` 的 array_scan 样本中，N 从 100 增至 5000 时，LWT median 为 111.168→182.926 ms，Python median 为 40.837→36.707 ms，中位数比值为 2.722→4.983。这只描述本机的端到端样本；进程启动和导入/解析成本占比可能遮蔽循环本身的变化，不能据此推断纯运行时倍率。

## 运行身份与原始数据

### 291bd4e2-8a3e-4de6-be86-46b62980e656

- 状态：`valid`；模式：`formal`；UTC 开始：`2026-10-07T07:27:09.631236Z`。
- 采集代码 Git SHA：`c6f38a0e9ee796c9ac82498599d91da542ae325a`；开始时工作区干净：`True`。
- 环境：Windows-11-10.0.26200-SP0；架构 `AMD64`；Python `3.13.7 (tags/v3.13.7:bcee1c3, Aug 14 2025, 14:15:11) [MSC v.1944 64 bit (AMD64)]`；可执行文件 `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe`。处理器：`Intel64 Family 6 Model 183 Stepping 1, GenuineIntel`。
- 固定 seed：`20261007`；规模：`100, 1000, 5000`；正式重复数：`10`；timeout：`60 s`；正式样本 `120` 条、配对 `60` 组、warm-up `12` 条。
- 源文件 SHA-256：`bench/arithmetic.lwt` `54eb47c9266cba9f068670e09092a92b26d6b995888690e336d3f9e5032b1287`；`bench/arithmetic.py` `332a55ee3a30f06205a358d485b9819ac4fbb56bbe0ff3bf167c69d893b0d6ea`；`bench/array_scan.lwt` `2b656dec876de3cae8f78cdb0e8fae16904ce4391a348c49a842e6c419377b21`；`bench/array_scan.py` `2e6f9aec306b2db117396d58dbe4ddbbf9f064a5ccc07e8e120fcfc6fa33b3bd`。
- 原始记录：[bench/results.json](../bench/results.json) 中 run_id `291bd4e2-8a3e-4de6-be86-46b62980e656` 的完整对象，含每次 argv、执行顺序、elapsed_ns、返回码、timeout、stdout/stderr Base64/长度/hash、预期输出校验及配对状态。

## 结果解释与限制

小规模中固定的子进程创建、Python 启动及 LWT 导入/解析成本可能占较大比例；规模增加后循环工作相对增加，但具体趋势仅适用于本报告所列运行。中位数降低偶发调度尖峰的影响，min/max/range 保留了各样本波动；背景进程、CPU 调度、缓存和电源状态仍会影响结果。

本次测量只代表记录的 Windows 主机、CPU、Python 版本、提交和规模。没有在 Linux、macOS、Python 3.10 或其他硬件上复验；不推及其他机器或平台。计时包含启动、加载和解析，不能解释为纯 LWT 语言运行时倍率；样本规模有限，且未控制操作系统背景负载。S11 未实施解释器性能优化，也没有用 S10 并发读取时间作对照。
