# LWT S13 全项目复检与风险审计

> **阶段结论：执行完成，等待主窗口审查。** 这不是 S13 已通过审查的标记。本报告记录 2026-10-07 在 Windows 本地阶段分支上的本次实测、对历史原始数据的独立复算、静态文档/代码审阅，以及仍未验证的事项。它不替代 S12 新克隆验收。

## 1. 范围与 Git 基线

本阶段只做全项目审计、验证和状态文档更新；未发现需要代码修复的确认缺陷，也没有修改解释器、测试、基准、应用、示例、PPT 或并发/性能历史原始数据。没有实施性能优化，理由见第 7 节。没有合并、推送、创建标签、制作 PPT 或执行最终新克隆验收。

| 检查项 | 实际结果 |
|---|---|
| 仓库 | `C:\Users\28641\Desktop\大三上\程序设计实践\大作业` |
| S11 审查后本地 `main` / 本次基线 | `86475757efa5492fa768edd77f25531311570832`；创建阶段分支时工作区干净 |
| 阶段分支 | `stage/s13-comprehensive-review`，从上述本地 `main` 创建；开始时不存在同名分支 |
| 当前分支/HEAD（编写报告前） | `stage/s13-comprehensive-review` / `86475757efa5492fa768edd77f25531311570832` |
| `origin/main` 跟踪引用 | `de608f7fbf50946715d370df014657169eb8f26d` |
| 实时远端查询 | `git ls-remote origin refs/heads/main` 返回同一 SHA；远端确实仍停在 S4 |
| 本地 `main` 相对远端 | 领先 31 个提交；没有把过期 `origin/main` 用作阶段基线 |
| 初始工作区 | 干净；未发现需要隔离的既有未提交更改 |

本报告中的“本次”表示本轮重新执行；“历史证据”表示复核既有文件和数据，但没有重新运行相应历史实验；“静态审阅”表示检查代码/文档或 Git 对象，没有声称运行通过。

## 2. 课程要求与交付证据追踪

作业要求来源是[`大作业内容.md`](../大作业内容.md)。表中的“本次证据”只写本轮实际观察；性能原始数据、盲测和并发试验等历史结果明确标为历史证据。

| 原始要求/评分项 | 仓库交付与可复核入口 | 本轮实测/可观察证据 | 状态、缺口及责任阶段 |
|---|---|---|---|
| 解释型通用脚本语言及解释器；整数、字符串、数组、结构、I/O、分支循环、函数（解释器 20 分） | `docs/language-spec.md`；`lwt/lexer.py`、`parser.py`、`ast_nodes.py`、`runtime.py`、`cli.py`；`examples/` | Python 3.13.7：194 项 CLI 黑盒全过；collections、control-flow、functions、text-tools 示例退出码均为 0，输出见第 5 节 | 已验证实现和冻结行为。语言“特色”由 `record`、`when/otherwise`、`each`、`emit` 的组合展示；项目不声称完成全球语言全集的形式化唯一性证明，S12 演示时说明设计取舍即可 |
| 覆盖语言功能的完整自动黑盒测试集，一个命令执行（测试 20 分） | `tests/cases/`、`tools/run_tests.py`、`docs/test-matrix.md`；命令 `python tools/run_tests.py` | 本次 Python 3.13.7 和 3.11.16 分别为 194/194；194 个唯一 JSON ID 与 194 个 `.lwt` 文件一一配对，其中 189 个执行 LWT 源程序、5 个检查 CLI argv | 已验证。63 条矩阵规则所引用的测试文件均存在；本次矩阵/文件静态检查通过 |
| LWT 与同功能 Python 脚本的性能比较（性能 10 分） | `bench/*.lwt`、`bench/*.py`、`tools/benchmark.py`、`bench/results.json`、`reports/performance.md` | 本轮没有重跑计时实验；只读脚本核验 3 个历史 run、每条输出 Base64/长度/hash、expected 输出、60 个 pair 关联和六组统计，全部与 raw/report 一致 | 历史证据完整并已复算；不是本轮性能实测。S12 可复核报告，不必为本审计覆盖旧 raw 数据 |
| 语言语法说明、人和 Agent 可用的开发指南（文档 20 分） | `docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md`、`docs/agent-blind-test.md` | 本次运行开发指南中的 collections、control-flow、functions、text-tools 命令；对指南、Skill、规范及入口作一致性审阅。S9 三项独立盲测为历史证据，本轮未重跑 | 文件、运行入口和当前 CLI 一致；独立 Agent 盲测保留历史证据，不把它说成本轮复测。自动 Skill 路由在当前平台不可观察 |
| Agent 辅助编写 ≥200 行完整应用，关注并发读取（应用 30 分） | `app/log_report.lwt`、`app/README.md`、`docs/agent-dev-log.md`、`tests/test_app.py`、`docs/app-concurrency.md`、`reports/app-concurrency.json` | 本次行数工具报告 246 行；应用公开 CLI 定向测试 25/25；默认和过滤命令退出码为 0。固定 fixture 的并发记录为历史证据，详见第 4 节 | 已验证行数和本轮 CLI/定向测试；并发试验不是本轮重跑，也不证明 LWT 线程或加速。权限拒绝情形未跨平台可移植地单测，列为低风险/S12 选做 |
| 使用 Git 版本管理并提交全部工作历史 | 本地 `git log`、阶段分支和提交历史；本报告及状态更新留在独立 S13 分支 | 本次核对 `main`、`origin/main`、HEAD、远端实时引用；初始状态干净。S13 不推送或合并 | 本地历史可审计；S5–S13 本地进度未推到远端。S12 应在审查/集成获准后处理最终远端同步 |
| 系统介绍 PPT、线下验收演示 | 当前未交付；按用户安排属于 S12 | 本轮没有制作 PPT、没有录制/模拟现场验收 | 待 S12；不得用本报告替代最终演示或把本地现有工作区称为新克隆通过 |

## 3. 正式规范、实现和测试矩阵

语言语义以[`docs/language-spec.md`](language-spec.md)为权威。本轮读取规范、实现、测试矩阵、指南、Skill 和代表性 CLI 行为；没有提出会改变既定语义的差异。

| 规范范围 | 主要实现 | 覆盖矩阵/本轮检查到的用例证据 |
|---|---|---|
| §2 源文件、词法与错误位置 | `lwt/lexer.py`、`lwt/errors.py`、`lwt/cli.py` | `lexer-parser` 42 项；包含 BOM/CR 行、ASCII 标识符、字符串转义、未知转义、原始换行、注释和错误列；`cli-errors` 13 项 |
| §3 完整语法、优先级、左值和绑定 | `lwt/parser.py`、`lwt/ast_nodes.py` | `lexer-parser` 42 项与 `values-operators` 31 项；含空程序/块、分号、尾随逗号、otherwise 绑定、非法左值、嵌套函数、返回位置、结合性和比较链 |
| §4 值、运算、数组/record、求值次序与显示 | `lwt/runtime.py`、`lwt/ast_nodes.py` | `values-operators` 31 项、`arrays-records-each` 32 项；含整数边界、负除法/取模、类型错误、短路、别名、身份相等、字段验证、each 快照和循环显示 |
| §5 作用域、函数、条件和循环 | `lwt/runtime.py`、`lwt/parser.py` | `control-functions` 30 项及集合用例；含遮蔽、块生命周期、前向/相互/递归调用、参数数量、return、严格条件和 each 每轮作用域 |
| §6 内置函数、输入输出与 CLI | `lwt/runtime.py`、`lwt/cli.py` | `builtins-text-io` 43 项、CLI/集成项；覆盖 EOF/换行、args 边界、read_text 编码/路径错误、Unicode len、split、trim、to_int、str、push、fail、stdout/stderr |
| §7 诊断、错误类别和退出码 | `lwt/errors.py`、`lwt/cli.py`、lexer/parser/runtime | `cli-errors` 13 项加各语义类别错误用例；本次 CLI 样例成功码为 0；历史矩阵包含语法 2、运行时 3、CLI/源文件 4 的精确 stderr/退出码断言 |
| §8 规范示例和设计决策 | 规范本身；相关 lexer/parser/runtime 模块 | 示例所依赖行为由 §2–§7 规则和用例覆盖；本次实际运行指南示例，但没有把规范片段逐段当作独立执行套件 |

矩阵文件记有 63 条规则行，覆盖 N/B/E（正常、边界、错误）用例和“不适用”说明。对 194 份 JSON 元数据的 `spec_refs` 盘点覆盖规范 §1、§2.1、§2.2、§3、§4.1–§4.3、§5、§6、§7；§8 是规范示例/取舍，测试归属仍指向其所说明的语义章节。静态检查得到 194 个唯一用例 ID、无重复、无孤立 `.lwt`/`.json`、矩阵链接引用的用例均存在。黑盒期望是 runner 外部 JSON 中的固定 stdout/stderr/退出码；不是运行时从被测解释器生成。

黑盒类别数与本次通过数一致：lexer/parser 42，values/operators 31，control/functions 30，arrays/records/each 32，builtins/text/I/O 43，CLI/errors 13，integrated 3；总计 194。运行器报告 189 项调用 LWT 源程序，5 项显式测试 CLI 参数契约。

## 4. S10 应用与并发证据

- `python tools/count_lwt_lines.py app/log_report.lwt` 本次退出码 0，报告 **246 effective LWT lines**，超过课程 200 行门槛。
- `python -m unittest discover -s tests -p "test_app.py" -q` 本次 25/25 通过。测试覆盖固定样例、过滤和 AND、大小写、Unicode keyword、Top=0/1/默认 5、并列排序、长十进制参数、空输入/终止 LF/末行无 LF/连续 LF、坏行、缺文件/目录/非法 UTF-8 和 usage 错误。
- 本次实际运行 `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` 和 `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2`，均退出 0；第一条产生 6 条有效记录/1 条坏行的报告，第二条匹配 1 条 `WARN|cache|retry scheduled` 记录，与应用说明吻合。
- 并发记录不是本轮运行。本轮只读核对 [`reports/app-concurrency.json`](../reports/app-concurrency.json)：原记录在 Windows 11 / Python 3.13.7，1、2、4 进程分别 5 个批次；计时子进程总计 35 个，另有一个共享 warm-up。各子进程返回码 0、未超时、stderr 为空，433 字节 stdout 哈希均为 `d4955d74db17340a8ac5629db89816f29a678514b7661d84998abf1efd258ac4`；所有 Base64、长度和 SHA-256 可相互复算，`errors` 为空。
- 并发记录绑定的应用源 SHA `39807dd117813578896bc68165f161c48c106a99603a22406c7e4e637aa8acc1` 与 Git 提交 `f7bde96` 中的 `app/log_report.lwt` blob 一致；输入 7846 bytes / SHA `512fa16f3d0ea7911709dbf4ee5a3ba13a05f926be01c071106973aa9909a118` 与记录提交 `4e01004` 中的 fixture blob 一致，试验后 SHA 相同且记录未被改动。
- 当前 Windows 工作树原始文件字节因 `core.autocrlf=true` 将 LF 检出为 CRLF（当前 fixture 7966 bytes），故不应把当前工作树 byte hash 误当历史试验的原始输入 hash；对照对应 Git blob 后历史哈希吻合。应用说明将结论限定为固定只读输入下独立进程的输出一致性/墙钟记录，没有声称 LWT 线程支持或并发加速。

## 5. S11 性能报告与原始数据独立复算

本轮没有重新计时，也没有更改 [`bench/results.json`](../bench/results.json)。用独立只读脚本解析 JSON（未调用 benchmark 的统计函数）完成以下复核：对每个 warm-up/trial 的 stdout、stderr、expected stdout 分别 Base64 解码，核对长度及 SHA-256；重算 expected-output 标记；按 pair ID 关联 LWT/Python attempts，验证输出相同、独立期望相符、`valid` 标记与两个 attempts 一致；最后以 pair-linked elapsed ns 重新计算六组 median/min/max/range/ratio。另用不同算法复算独立预期值：arithmetic 使用求和闭式，array_scan 使用列表生成后以 `sum`/谓词计数，并将六个规模/负载组合与全部 120 条 formal `expected_stdout` 和实际 stdout 比较。全部校验通过。

| Run | 类型/状态 | warm-up | 计时 attempts | 配对 | failures / invalid pairs / errors | 纳入正式统计 |
|---|---|---:|---:|---:|---:|---|
| `354fccce-bba0-4690-ad33-6a7811562a1a` | calibration / invalid | 12 | 0 | 0 | 6 次失败尝试；历史 schema 未记录 invalid_pair_count；0 errors | 否；Windows Python 文本 stdout CRLF 与 LWT LF 不同的失败校准保留 |
| `a3c713d5-93d1-4479-8653-91af2eb3dc12` | calibration / valid | 12 | 12 | 6 | 0 / 0 / 0 | 否；只用于选定可行规模 |
| `291bd4e2-8a3e-4de6-be86-46b62980e656` | formal / valid | 12 | 120 | 60 | 0 / 0 / 0 | 是；6 个 workload-size 组合每组 10 对 |

正式记录的 4 个 workload 源文件 SHA-256 与采集提交 `c6f38a0e9ee796c9ac82498599d91da542ae325a` 中的 Git blob 全部一致。120 个 attempts 全部成功退出、无 timeout、stderr 为空，stdout 与本次运行内保存的独立 expected bytes 匹配；60 个 pair ID 关联完整，输出相等、expected 匹配且有效。未把失败 calibration 混入正式统计，也未再生成 132 个样本。

从 raw JSON 重算的正式统计（时间为 ms，三位小数；比值为 LWT median/Python median）：

| workload | N | pairs | LWT median / min / max / range | Python median / min / max / range | median ratio |
|---|---:|---:|---:|---:|---:|
| arithmetic | 100 | 10 | 108.117 / 103.070 / 122.555 / 19.485 | 39.187 / 33.344 / 52.261 / 18.917 | 2.759 |
| arithmetic | 1000 | 10 | 107.483 / 102.548 / 134.646 / 32.098 | 37.394 / 33.462 / 51.255 / 17.793 | 2.874 |
| arithmetic | 5000 | 10 | 129.590 / 124.769 / 143.968 / 19.199 | 38.389 / 34.185 / 48.240 / 14.055 | 3.376 |
| array_scan | 100 | 10 | 111.168 / 100.657 / 130.652 / 29.995 | 40.837 / 36.609 / 58.113 / 21.505 | 2.722 |
| array_scan | 1000 | 10 | 129.359 / 111.726 / 160.946 / 49.221 | 38.826 / 34.848 / 48.945 / 14.097 | 3.332 |
| array_scan | 5000 | 10 | 182.926 / 177.544 / 223.719 / 46.175 | 36.707 / 35.412 / 44.847 / 9.435 | 4.983 |

原报告将计时描述为新进程端到端墙钟时间，包含启动、导入、词法/语法分析、执行、输出及等待退出；runner 的 expected 计算/比较、统计和 JSON 写入处在计时之外。工作负载算法、N 和字节输出契约匹配，runner 对每侧输出分别核对独立期望值。历史 raw 正式提交为 `c6f38a0`，当前仓库 S11 审查补丁 `2d2585c` 将失败尝试与无效配对拆开计数；修复由 `test_benchmark.py` 的回归用例保护，本次 12 项 benchmark 单测通过。正式 run 全部成功，且采集早于计数补丁，因此其旧 schema 不含 `invalid_pair_count` 是历史格式，不造成统计差异。

## 6. CI、运行环境、依赖和文档/Git 检查

### 环境与 CI

| 环境/入口 | 本次观察 |
|---|---|
| 默认 `python` | Windows 11 build 26200 / CPython 3.13.7 AMD64；完整测试与示例运行成功 |
| 可直接调用的 CPython 3.11 | `C:\Users\28641\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none\python.exe`，版本 3.11.16；黑盒、全量 unittest、compileall 均成功 |
| Python 3.10 | 本机无可用解释器（`py -3.10 --version`：No suitable Python runtime）；未下载/安装 |
| Linux/WSL | Ubuntu 20.04 WSL 可调用，但只有 Python 3.8.10，低于项目最低支持版本。实际执行 `python3 -m lwt examples/collections.lwt` 以 `TypeError: dataclass() got an unexpected keyword argument 'slots'` 退出 1；这不是支持范围内的 Linux 测试，也不能替代 CI Python 3.10 |
| 远端 GitHub Actions | 本轮没有触发，也没有可观察的远端 workflow run；不能称 CI 已通过 |

`.github/workflows/tests.yml` 声明 `ubuntu-latest`、`windows-latest` × Python `3.10`、`3.13`，执行黑盒套件、unittest 和 compileall。对 `lwt/`、`tests/`、`tools/`、`bench/` Python 文件的 AST 3.10 grammar parse 静态检查通过；import AST 检查只见 Python 标准库和项目内 `lwt`/`tools` 模块，未发现第三方依赖。仓库没有 `requirements*.txt`、`pyproject.toml`、`setup.py`、`Pipfile` 或 lockfile。静态语法/依赖检查不能替代 Python 3.10 运行时测试。

### 文档及命令静态检查

- 扫描仓库 17 份 Markdown：401 个相对本地链接均存在，没有奇数个三反引号围栏。
- `docs/test-matrix.md` 有 63 条规则行；矩阵引用的 `.lwt` 用例均存在。测试目录 194 对 `.lwt`/`.json` 无孤立文件，JSON ID 均唯一。
- 本轮运行四个指南/功能示例及两个应用 CLI 命令，成功输出与 README/开发指南/应用说明中声明的结果相符。
- 已执行远端只读查询；没有 fetch、push、merge、reset、rebase 或清理操作。`origin/main` 的实时 SHA 与本地跟踪引用相同。
- `git diff --check` 与报告/状态文档修改后的链接及代码围栏复核列于第 8 节；最终阶段提交后的 `git status -sb` 应为干净。

本次没有另行访问外部官方网页或课件；因此不新增资料链接或访问日期。项目内已有一手课程原文及性能报告引用的 Python/GitHub 官方文档仍可供 S12 演示准备参考。

## 7. 问题、风险与优化结论

### 问题等级汇总

| 等级 | 本次结论 |
|---|---|
| Blocker | 未发现 |
| High | 未发现 |
| Medium | 2 项需随 S12/最终集成交接处理，见 R-01、R-02 |
| Low | 2 项限制/边界说明，见 R-03、R-04 |
| 已修复 | 本阶段没有新增代码或测试修复；仅将过时 S13“尚未开始”状态更新为“执行完成，等待主窗口审查” |

| ID/等级 | 证据、影响 | 处理/责任阶段 |
|---|---|---|
| R-01 / Medium：支持矩阵未在最低版本/目标 Linux 实际验证 | CI 声明 Python 3.10/3.13 × Ubuntu/Windows；本机 Python 3.10 和远端 workflow 不可用。WSL 只有 3.8.10，低于支持边界，实际 CLI 失败于 3.10 才提供的 `dataclass(slots=...)` | S12：在 GitHub Actions 或现成 Python 3.10 环境复核至少 Ubuntu/Windows 的目标格；不得把本次 Python 3.8 结果当支持矩阵失败或通过 |
| R-02 / Medium：远端仍旧，阶段提交尚未推送 | `origin/main` 实时为 `de608f7`（S4）；本地经审查 S11 的 `main` 为 `8647575`、领先 31 个提交；S13 阶段分支也按指令不推送 | S13 按边界保留；S12 在 S13 审查/合入安排完成后核对最终提交，执行获准的远端同步 |
| R-03 / Low：Windows 权限拒绝文件场景未跨平台构造 | `docs/test-matrix.md` 明确记录 ACL/执行账号差异；缺失路径、目录、非法 UTF-8 有现存用例并通过，权限拒绝没有可移植的黑盒用例 | S12 如演示环境允许可验证；否则在限制说明中保留，不降低现有断言 |
| R-04 / Low：课程的“特色”要求不是全球唯一性证明 | 规范展示 `record`、`when/otherwise`、`each`、`emit` 的特征组合，并明确不声称穷尽比较全球现存语言 | 无需扩大语言范围；S12 演示组合设计与语义，不作无证据的全球唯一性断言 |

没有实施性能优化。S11 六组数据测量的是进程启动、导入、词法/解析、执行和退出等待的总和；本轮没有 profiler 或纯解释执行微基准来定位热点。只按端到端 ratio 优化会超出证据，故保留实现与历史性能定义不变。这符合“不为完成优化而优化”的阶段约束。

## 8. 本轮验证命令和结果

除注明 3.11/WSL/历史外，下表的 `python` 是本机 CPython 3.13.7。黑盒及 unittest 是**本轮实测**；并发数据和 S11 正式性能数字是**历史 raw 的本轮只读复算**。

| 命令 | 结果 |
|---|---|
| `python tools/run_tests.py` | exit 0；黑盒 194/194；七类计数：32 + 43 + 13 + 30 + 3 + 42 + 31 |
| `python -m unittest discover -s tests -q` | exit 0；211 tests，OK |
| `python -m unittest discover -s tests -p "test_app.py" -q` | exit 0；25 tests，OK |
| `python -m unittest discover -s tests -p "test_benchmark.py" -q` | exit 0；12 tests，OK |
| `python -m compileall -q lwt tests tools bench` | exit 0 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | exit 0；246 effective LWT lines |
| `python -m lwt examples/collections.lwt` | exit 0；展示 each 浅快照和 record/数组输出 |
| `python -m lwt examples/control_flow.lwt` | exit 0；stdout `0`, `-1`, `2`, `-3` 各一行 |
| `python -m lwt examples/functions.lwt` | exit 0；stdout `120` |
| `python -m lwt examples/text_tools.lwt -- examples/fixtures/text_tools.txt preview` | exit 0；stdout 为开发指南记录的 3 行 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | exit 0；6 条有效记录、1 条坏记录 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | exit 0；1 条匹配记录，level/module/示例与应用说明一致 |
| 上述 `python tools/run_tests.py`、全量 unittest、compileall，以显式 CPython 3.11.16 可执行文件运行 | 三项均 exit 0；194/194、211 tests OK、compileall 成功 |
| 独立只读 Python 脚本审计 `bench/results.json` | exit 0；3 个 run 的所有输出 hash/长度、expected、pair 标记与 formal 六组统计校验通过；没有写 JSON/报告 |
| Markdown/link/fence/case inventory 检查脚本 | exit 0；17 文件、401 个有效本地链接、63 规则、194 唯一 ID/文件对，0 断链、孤立用例或奇数代码围栏 |
| WSL `python3 -m lwt examples/collections.lwt` | exit 1；环境是 Python 3.8.10，低于项目 3.10 下限；启动于 `dataclass(slots=...)`，只记录为环境限制，不计支持矩阵验证 |
| `git ls-remote origin refs/heads/main` | 成功只读返回 `de608f7fbf50946715d370df014657169eb8f26d` |

提交前后均运行 `git diff --check`；最终文件状态和 SHA 由执行窗口交接报告给出。没有重跑正式性能 132 样本或并发读取计时，也没有改动历史数据。

## 9. 给 S12 的交接顺序

只有本报告经主窗口审查通过后才进入 S12。建议依次：

1. 在经审查集成后的目标提交上做真正的全新克隆验收；不得把当前工作树或本次阶段分支直接称作新克隆。
2. 按仓库声明的 Python 3.10+ 环境运行 `python tools/run_tests.py`、完整 unittest、示例、应用 CLI、246 行统计和编译检查；通过可用 GitHub Actions 复核 Ubuntu/Windows × Python 3.10/3.13。
3. 从仓库根目录演示 `examples/collections.lwt`、控制流/函数、文本工具、应用默认与过滤命令；从 stdin 演示时给出明确输入。解释并发证据只涉及固定只读 fixture 和独立进程。
4. PPT 数字从审查后文件现取：黑盒 194、全量 unittest 211、应用定向测试 25、应用 246 行、S11 正式 120 attempts/60 pairs/12 warm-ups。性能表必须继续称为端到端耗时，不说纯解释器速度。
5. 说明未覆盖的最低版本/Linux/远端 CI 格、Skill 自动路由不可观察、权限拒绝场景和 LWT 特色边界；决定是否在目标账户/演示机完成权限场景检查。
6. 核对阶段提交、远端同步、最终标签及全部课程交付物；只有获准后执行 push/tag/release 等交付操作。本阶段没有触碰这些动作。

本阶段没有完成 S12 新克隆验收、PPT、现场演示或最终发布。后续窗口应先复核本报告、阶段差异和 Git 状态，再决定放行或要求 S13 修订。
