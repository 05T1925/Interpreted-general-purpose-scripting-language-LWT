# S48 现场可质询证据探针结果

> 生成：2026-11-10T16:31:11Z；运行 24 条；**PASS 24 / FAIL 0**。每条都是真实子进程与真实退出码。

| id | 断言 | 命令 | 退出码 | 结果 | 用时(s) |
|---|---|---|---:|---|---:|
| blackbox | 400/400 黑盒通过 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe tools/run_tests.py` | 0 | **PASS** | 365.79 |
| blind | T 组 30/30、C 组 29/30 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;d=...` | 0 | **PASS** | 0.532 |
| blind-ci | T−C 的 95% 区间已计算且含 0 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;d=...` | 0 | **PASS** | 0.555 |
| bundle-index | 包索引与 bundle 截止 SHA 一致且 lag 通过 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;d=...` | 0 | **PASS** | 0.554 |
| check | --check 对模块示例退出 0 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -m lwt --check ex...` | 0 | **PASS** | 0.96 |
| compare-perf | 性能门槛 all_pass=true | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe tools/compare_per...` | 0 | **PASS** | 0.595 |
| dap | DAP spawn 拒绝：exit 4、无 stopped、无 stdout 泄漏 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -m unittest tests...` | 0 | **PASS** | 2.585 |
| determinism | 46 项并发 ×10 次逐字节稳定 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe tools/run_concurr...` | 0 | **PASS** | 282.647 |
| diff-eq | 并发日志应用与串行版逐字节等价（去块头） | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import subproc...` | 0 | **PASS** | 2.095 |
| doc-consistency | 当前状态文档与 manifest 一致（27 项，全部通过） | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -m unittest tests...` | 0 | **PASS** | 2.168 |
| fresh-clone | 新克隆 400/400 且 6 条命令退出 0 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;d=...` | 0 | **PASS** | 0.518 |
| hello | 最小程序 hello 输出 Hello, LWT! | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -m lwt examples/g...` | 0 | **PASS** | 0.851 |
| help | python -m lwt --help 退出 0 且列出入口 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -m lwt --help` | 0 | **PASS** | 0.762 |
| integrity | 覆盖闭环 400/400 unreferenced=0 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe tools/check_proje...` | 0 | **PASS** | 1.807 |
| no-concurrency | 非 spawn 程序不加载 lwt.concurrency | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import sys,lwt...` | 0 | **PASS** | 0.738 |
| ppt | 21 页且第 10 页原生图表 12 数值点 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import zipfile...` | 0 | **PASS** | 0.578 |
| replay | 调度记录→重放 round-trip 逐字节一致（当前工作树字节；历史 trace 因 CRLF 入库仅作绑定校验素材） | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import subproc...` | 0 | **PASS** | 2.367 |
| s11 | S11 报告记录 2.759× 端到端中位倍率 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c t=open('report...` | 0 | **PASS** | 0.545 |
| s44-exec | 纯执行 N=5000 三负载 ≥1.45× | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;b=...` | 0 | **PASS** | 0.608 |
| s44-startup | 启动 --help 1.256×、hello 1.224× | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;b=...` | 0 | **PASS** | 0.652 |
| s46-clean | clean corpus 8 程序 / 0 violation | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;d=...` | 0 | **PASS** | 0.54 |
| s46-mutant | mutant 4 violation、最小前缀 []、重放匹配 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -c import json;d=...` | 0 | **PASS** | 0.516 |
| unittest | 全量 unittest 一次跑完并通过（需带 tkinter 的解释器；实际解释器、Python 版本、TkVersion 与项数记录在证据文件里） | `py -3.13 tools/run_unittest_single.py` | 0 | **PASS** | 717.826 |
| version | CLI 版本为 lwt 0.3.0 | `C:\Users\28641\.workbuddy\binaries\python\versions\3.13.12\python.exe -m lwt --version` | 0 | **PASS** | 0.771 |

## 失败明细

无。
## 口径

- `PASS` = 退出码匹配且 stdout 含预期片段；`FAIL` 如实记录，不写“基本通过”。
- heavy 行（全量黑盒/全量 unittest/46×10 确定性）现场可用 `--claim` 抽一条，或 `--all --skip-heavy`。
- 只读旧证据，不覆盖任何报告；结果写入 `reports/s48-defense/defense-probe.{json,md}`。
