# S18 执行报告：LWT 驱动的交互分析工作台与应用证据强化

状态：**实施完成，等待主窗口审查**。本报告记录阶段执行窗口的实测；未合并或推送，S12 未开始。

## 一、基线、范围和提交

开工运行 `git status -sb`、`git rev-parse HEAD`、`git log -5 --oneline`。本地 `main` 干净，HEAD 为 `8be88474316238532294f6bb7e83b0cdb8ebfdb5`，与用户给定基线完全一致；`git status -sb` 显示本地比跟踪的 `origin/main` 领先 52 个提交。没有从落后的远端覆盖本地进度。从该 HEAD 新建 `stage/s18-lwt-analysis-workbench`。

| 顺序 | 提交 | 内容 |
|---:|---|---|
| 1 | `35f006837a6cd933b5793fffc84b0b40d9057aec` | 无 Tk 的严格 LWT 固定报告模型、真实 CLI 集成与损坏报告测试 |
| 2 | `2dcdba8603a012794382a0360171316289b20af3` | 工作台 Tk 视图、原挑战选项卡与异步请求状态 |
| 3 | `278af9a88855eff6d5e37ce940ba52522d4b75d1` | 补充示例文本看似固定字段时仍合法的解析回归 |
| 4 | `ac79b35320bd5c1614ac2a16f1aea6ba85e27c33` | 补四字段示例行的格式校验，拒绝内容损坏但条数正确的报告 |
| 5 | `dad8156851d9b9eefb88b8f97bb884b18942d33e` | 界面来源文案准确写明 Python 调用、校验与展示的职责 |
| 6 | `2b502a2dc6e206ce37cd6c29832dc29d7f8823d3` | 拒绝级别或模块计数行中的多余分隔符 |
| 7 | 文档与演示数据提交 | 本报告、展示说明、演示日志、README/计划/项目状态；最终 SHA 以阶段分支 `git log -1` 为准 |

本阶段没有修改 `app/log_report.lwt`、原有 25 项 `tests/test_app.py`、解释器/语言规范或 Snake 代码，也没有运行会覆盖 S10 并发 raw 或 S11 性能 raw 的生成命令。

## 二、修改文件及职责

| 文件 | 变更 |
|---|---|
| [`app/log_report_view.py`](../app/log_report_view.py) | 纯 Python 报告数据契约、查询参数模型、严格解析和请求版本状态；不打开日志文件或重算业务统计 |
| [`app/log_workbench_ui.py`](../app/log_workbench_ui.py) | Tk 过滤输入、摘要、Canvas 级别/模块条形图、匹配示例、来源/argv/原始报告入口 |
| [`app/log_detective_ui.py`](../app/log_detective_ui.py) | 工作台和五题挑战选项卡、后台查询队列接入、旧结果失效；挑战答题区紧跟题面 |
| [`tests/test_log_report_view.py`](../tests/test_log_report_view.py) | 13 项正常、边界、损坏格式、真实 CLI 和异步过期结果测试 |
| [`app/fixtures/showcase.log`](../app/fixtures/showcase.log) | 固定 UTF-8 丰富日志：12 行、11 有效、1 坏行，含 Unicode、多模块、多级别 |
| [`app/README.md`](../app/README.md)、[根 README](../README.md) | GUI 用法、CLI 演示、Python/LWT 职责与 Snake 身份 |
| [`docs/s18-app-showcase.md`](s18-app-showcase.md) | 教师评分对应表、三分钟顺序、无 GUI CLI 方案 |
| 本报告、[Agent 开发记录](agent-dev-log.md) | 决策、实际命令、桌面观察和限制 |
| [`project.md`](../project.md)、[优化规划](s18-optimization-plan.md)、[总体方案](../LWT大作业总体方案与复检.md)、[详细规划](../详细实施规划.md)、[路线图](../阶段执行与审查路线图.md) | 统一 S18“阶段分支实施完成，等待主窗口审查”和 S12 未开始 |

## 三、报告契约与设计权衡

工作台运行现有 `run_lwt_report`：当前 Python 解释器、argv 列表、`shell=False`、UTF-8、仓库根 `cwd`、20 秒超时；工作线程只等待子进程，Tk 更新由主线程消息队列执行。输入参数 Level/Keyword 可留空，Top 只接受非负 ASCII 十进制数字；路径经 `Path.resolve()` 后作为一个 argv 元素。页面同时显示筛选条件和实际 argv；当前报告按钮始终绑定这一次成功查询保存的原始 stdout。

解析器要求固定标题、四个唯一有序计数字段、三个唯一有序章节、非负十进制计数、末尾换行和示例行四字段格式。校验 `total=valid+malformed`、`matched≤valid`、级别合计等于匹配数、模块排行计数和不超过匹配数、Top 截断、前三条示例数量。级别按名称升序、模块按计数降序再按名称升序。空日志、零匹配、Top=0 和合法空字段可解析。模块排行可能被 Top 截断，所以**没有**要求其总和等于匹配数。缺字段、重复字段、错序、坏计数、矛盾数据和截断报告均抛出可读错误；界面清空旧图表并保留重试路径。

图表长度按 LWT 报告中的已给计数除以该图自身最大计数缩放；Python 不读取原日志，也不聚合或重排记录。点击级别只把名字填进过滤框，用户再点查询才调用 LWT。模块排行没有不存在的“模块过滤”操作。更改条件、选择新日志或查询中切走工作台会递增请求版本、清空旧图和原始报告入口；旧线程结束也不能覆盖新条件。查询期间禁用重复触发与条件输入；关闭窗口后停止队列轮询。

五题挑战保留 Enter 提交、反馈、计分、重开和未过滤完整报告。S17 遗留的大窗口题面与答题行距离过大，源于反馈行 `row=2` 被赋予扩展权重；本阶段将扩展行移到答题行下方，没有改变游戏状态规则。独立 Snake 没有代码改动；文档明确它是 Python/Tkinter 附加演示，并非第二个 LWT 应用。

## 四、公开 CLI 精确结果与边界

以下命令均从仓库根运行。成功命令原生退出码 0、stderr 空。

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log
```

```text
LWT log report
Total lines: 7
Valid records: 6
Malformed lines: 1
Matched records: 6
Level counts:
ERROR|2
INFO|2
WARN|2
Top modules:
cache|2
api|1
auth|1
db|1
web|1
Matching examples (first 3):
2026-10-07T10:00:00Z|INFO|auth|login accepted
2026-10-07T10:00:01Z|WARN|cache|eviction started
2026-10-07T10:00:02Z|ERROR|db|connection lost
```

```powershell
python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2
```

```text
LWT log report
Total lines: 7
Valid records: 6
Malformed lines: 1
Matched records: 1
Level counts:
WARN|1
Top modules:
cache|1
Matching examples (first 3):
2026-10-07T10:00:03Z|WARN|cache|retry scheduled
```

新增演示日志默认命令 `python -m lwt app/log_report.lwt -- app/fixtures/showcase.log` 的完整 stdout：

```text
LWT log report
Total lines: 12
Valid records: 11
Malformed lines: 1
Matched records: 11
Level counts:
DEBUG|1
ERROR|3
INFO|4
WARN|3
Top modules:
api|3
auth|2
cache|2
db|2
worker|2
Matching examples (first 3):
2026-10-07T11:00:00Z|INFO|auth|用户 登录成功
2026-10-07T11:00:01Z|WARN|cache|retry 缓存刷新
2026-10-07T11:00:02Z|ERROR|db|连接失败
```

`python -m lwt app/log_report.lwt -- app/fixtures/showcase.log --level WARN --keyword retry --top 2` 得到 `Total lines: 12`、`Valid records: 11`、`Malformed lines: 1`、`Matched records: 2`、`WARN|2`、`cache|2`；示例是 `2026-10-07T11:00:01Z|WARN|cache|retry 缓存刷新` 和 `2026-10-07T11:00:04Z|WARN|cache|retry 延迟队列`。

边界实测：`--level TRACE --top 0` 得到总/有效/坏行 7/6/1、匹配 0，三个章节标题存在且无条目；仅 `--top 0` 匹配仍为 6，级别和前三示例保留，模块排行为空。`--top nope` 的原生退出码 3、stderr 单行 usage 诊断、stdout 空；缺失输入文件的原生退出码 3、stderr 为 `RuntimeError: could not read text file`、stdout 空。PowerShell 宿主在 native 非零时自身退出码显示 1；用 `$LASTEXITCODE` 复核了子进程真实码 3。空日志和 Unicode/空格路径经新增真实 CLI 测试通过；损坏报告经纯解析测试拒绝，未在 GUI 注入伪 CLI 输出。

## 五、实际自动检查

开工基线：语言黑盒 194/194、全量 unittest 243 项、S10 定向 25 项、完整性 194/287/194、LWT 有效行数 246，均为本轮实际运行；不是转抄旧报告。

| 实际命令 | 退出码与关键结果 |
|---|---|
| `python tools/check_project_integrity.py` | 0；194 cases、287 matrix links、194 referenced cases |
| `python tools/run_tests.py` | 0；黑盒 194/194，0 失败 |
| `python -m unittest discover -s tests -q` | 0；256 项通过（基线 243 + 新增 13） |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 0；S10 原 25 项通过 |
| `python -m unittest discover -s tests -p "test_log_detective.py" -v` | 0；原 11 项通过 |
| `python -m unittest discover -s tests -p "test_snake_game.py" -v` | 0；原 13 项通过 |
| `python -m unittest discover -s tests -p "test_log_report_view.py" -q` | 0；新增 13 项通过 |
| `python -m compileall -q lwt tests tools bench app` | 0；无输出 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0；Effective LWT lines: 246 |
| `git diff --exit-code 8be88474316238532294f6bb7e83b0cdb8ebfdb5 -- app/log_report.lwt tests/test_app.py reports/app-concurrency.json docs/app-concurrency.md bench/results.json reports/performance.md` | 0；S10/S11 六个保护文件相对基线无差异 |
| `git diff --check main...HEAD` | 0；阶段提交无空白错误 |
| Python Markdown 检查（读取本轮 10 份关联文档、URL 解码后核验本地链接与三反引号代码围栏） | 0；165 个相对链接存在、代码围栏平衡 |
| 两条 `python -c` Tk 几何检查，在 640×500 创建工作台和挑战页并读取控件矩形 | 0；工作台查询按钮 (33,308,123,43)、Top (535,225,58,31)、原始报告 (164,309,132,41)、选文件 (489,112,117,41)；挑战页答案 (140,369,142,31)、提交 (292,363,122,43)、开始 (33,428,122,43)、下一题 (163,429,116,41)、报告 (287,429,141,41)，均在窗口内 |

测试数增加证明报告契约和状态边界有回归保护，不单独证明 GUI 全流程或课程功能完整。没有重跑正式性能基准、并发原始数据生成、Python 3.10/远端 Actions、新克隆验收。

## 六、桌面逐项验收与限制

本轮在 Windows CPython 3.13.7/Tk 8.6 环境启动 `python app/log_detective.py`，Computer Use 枚举到标题 `LWT 日志侦探`，实际点击最大化与“运行 LWT 查询”。截图观察默认样例的 7/6/1/6、ERROR/INFO/WARN 三条等长计数 2、实际 CLI argv 和“数据由 LWT 程序计算”来源文字。后续通过桌面工具输入组合条件时，工具报告“user input was detected in this window”并中断；窗口随后被用户其他应用覆盖。为避免把他人操作归因于本执行窗口，以下未完成项如实保留。

| 项目 | 本轮状态 | 证据或限制 |
|---|---|---|
| 工作台打开、默认日志查询、摘要、级别图、来源和 argv | **实际点击/观察** | 运行按钮后截图显示 7/6/1/6，各级别为 2 |
| 工作台组合过滤、Top 0、零匹配、错误重试、原始报告按钮 | **仅无头/CLI 测试** | 解析与真实 CLI 结果通过；桌面连续输入被其他用户输入打断 |
| 文件选择、Unicode 路径、缺失文件后的 GUI 恢复 | **仅无头/CLI 测试；GUI 未验证** | 路径作为单独 argv、缺失文件和 Unicode 空格路径测试通过 |
| 查询忙碌、切换视图时过期结果、关闭窗口 | **仅状态测试/代码复核；GUI 未验证** | 请求版本测试覆盖过期结果，队列/关闭处理未做可归因点击 |
| 五题挑战第五题结束页、Enter、计分、重开、报告窗 | **S17 主窗口曾测主路径；本轮第五题未验证** | 本轮原有 11 项无头测试通过，不冒充实际点击 |
| 最小窗口缩放、题面与答题区间距 | **Tk 几何检查通过；实际拖拽未验证** | 640×500 下测得工作台查询/原始报告/Top/选文件控件，以及挑战答题/提交/开始/下一题/报告控件均在窗口边界内；扩展权重已移至答题区下方 |
| Snake 方向键、缩放、焦点、中文输入法下 R | **本轮未验证** | 原 13 项无头测试通过；中文输入法拦截 R 的 S17 观察仍成立，按钮路径需主窗口实际复核 |

没有因无法复现的 GUI 猜测修改 Snake。中文输入法问题未声称跨环境解决；用户可使用界面上的“重新开始”按钮。主窗口可在无其他桌面输入干扰时补做上述可归因点击。

## 七、保护、差异与后续审查

本轮无 LWT 语义、解释器、S10 CLI 报告格式变更，也未触碰 S11 性能记录。相比 S18 规划，工作台按原方案使用标准库 Tk/Canvas，新增的请求版本状态只为防止旧查询覆盖新条件；没有联网、账号、图表依赖、音效或新语言语法。S18 的公开 CLI 与原有挑战各用同一 LWT 应用，Snake 明确是 Python 附加演示。

主窗口仍需重点审查：① 在稳定桌面环境实际走完工作台组合过滤/原始报告/空态/错误恢复及第五题；② 检查 640×500 最小窗口与 Snake 的方向/焦点/输入法按钮路径；③ 审阅严格解析器对固定报告契约的取舍。审查通过前不得把 S18 记作已合入。S12 的新克隆、远端同步/Actions、Python 3.10 最终矩阵、PPT、标签和发布均未开始。
