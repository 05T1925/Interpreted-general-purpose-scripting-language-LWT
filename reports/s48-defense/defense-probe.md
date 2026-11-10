# S48 现场可质询证据探针结果

> 生成：2026-11-10T07:29:55Z；运行 24 条；**PASS 24 / FAIL 0**。每条都是真实子进程与真实退出码。

| id | 断言 | 命令 | 退出码 | 结果 | 用时(s) |
|---|---|---|---:|---|---:|
| blackbox | 400/400 黑盒通过 | `python tools/run_tests.py` | 0 | **PASS** | 248.722 |
| blind | T 组 30/30、C 组 29/30 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;d=json...` | 0 | **PASS** | 0.301 |
| blind-ci | T−C 的 95% 区间已计算且含 0 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;d=json...` | 0 | **PASS** | 0.24 |
| bundle-index | 包索引与 bundle 截止 SHA 一致且 lag 通过 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;d=json...` | 0 | **PASS** | 0.278 |
| check | --check 对模块示例退出 0 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m lwt --check exampl...` | 0 | **PASS** | 1.205 |
| compare-perf | 性能门槛 all_pass=true | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe tools/compare_perf.py...` | 0 | **PASS** | 0.291 |
| dap | DAP spawn 拒绝：exit 4、无 stopped、无 stdout 泄漏 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m unittest tests.tes...` | 0 | **PASS** | 1.631 |
| determinism | 46 项并发 ×10 次逐字节稳定 | `python tools/run_concurrency_determinism.py --repeat 10 --out C:\Users\28641\AppData\Lo...` | 0 | **PASS** | 283.37 |
| diff-eq | 并发日志应用与串行版逐字节等价（去块头） | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import subprocess,...` | 0 | **PASS** | 1.655 |
| doc-consistency | 当前状态文档与 manifest 一致（15 项） | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m unittest tests.tes...` | 0 | **PASS** | 0.552 |
| fresh-clone | 新克隆 400/400 且 6 条命令退出 0 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;d=json...` | 0 | **PASS** | 0.27 |
| hello | 最小程序 hello 输出 Hello, LWT! | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m lwt examples/guide...` | 0 | **PASS** | 1.147 |
| help | python -m lwt --help 退出 0 且列出入口 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m lwt --help` | 0 | **PASS** | 0.978 |
| integrity | 覆盖闭环 400/400 unreferenced=0 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe tools/check_project_i...` | 0 | **PASS** | 2.42 |
| no-concurrency | 非 spawn 程序不加载 lwt.concurrency | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import sys,lwt.cli...` | 0 | **PASS** | 0.375 |
| ppt | 21 页且第 10 页原生图表 12 数值点 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import zipfile,re
...` | 0 | **PASS** | 0.283 |
| replay | 调度记录→重放 round-trip 逐字节一致（当前工作树字节；历史 trace 因 CRLF 入库仅作绑定校验素材） | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import subprocess,...` | 0 | **PASS** | 1.288 |
| s11 | S11 报告记录 2.759× 端到端中位倍率 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c t=open('reports/pe...` | 0 | **PASS** | 0.369 |
| s44-exec | 纯执行 N=5000 三负载 ≥1.45× | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;b={(m[...` | 0 | **PASS** | 0.292 |
| s44-startup | 启动 --help 1.256×、hello 1.224× | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;b=json...` | 0 | **PASS** | 0.345 |
| s46-clean | clean corpus 8 程序 / 0 violation | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;d=json...` | 0 | **PASS** | 0.272 |
| s46-mutant | mutant 4 violation、最小前缀 []、重放匹配 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -c import json;d=json...` | 0 | **PASS** | 0.321 |
| unittest | 全量 unittest 677+ 通过 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m unittest discover ...` | 0 | **PASS** | 949.794 |
| version | CLI 版本为 lwt 0.3.0 | `C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe -m lwt --version` | 0 | **PASS** | 0.992 |

## 失败明细

无。
## 口径

- `PASS` = 退出码匹配且 stdout 含预期片段；`FAIL` 如实记录，不写“基本通过”。
- heavy 行（全量黑盒/全量 unittest/46×10 确定性）现场可用 `--claim` 抽一条，或 `--all --skip-heavy`。
- 只读旧证据，不覆盖任何报告；结果写入 `reports/s48-defense/defense-probe.{json,md}`。
