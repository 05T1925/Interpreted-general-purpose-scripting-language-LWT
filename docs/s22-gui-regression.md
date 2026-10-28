# S22：Tk 图形界面交互回归与交付前可靠性报告

状态：**实施完成，等待主窗口审查。** 本报告区分无头核心测试、真实 Tk 控件/事件集成、真实 LWT CLI 子进程、人工桌面操作和静态审阅。合成事件与控件调用不能代替真实桌面验收。

## 1. 基线与交付状态

- 阶段基线：本地已审查 `main` 的 `1919861652266edd75ce278736d71958eb90cd62`（规划提交 `1919861`）。开工时本地 `main` 与 `stage/s22-gui-regression` 均在该提交，工作区干净；S21 最终提交 `d7ca188168cd449027de546b61f78670c29e08ca` 是基线祖先。
- 阶段分支：`stage/s22-gui-regression`。开工时该分支已存在且与本地 `main` 一同指向指定基线，因此核验后续用，没有强制重建。按“GUI 测试/CI”与“阶段报告/状态文档”分层提交；最终 tip 和工作区状态以本报告提交后的执行交接为准。
- 已完成的分层提交：`790146aeec52e3551ae523eae18175379e468006`（UI 依赖接缝、真实控件测试和计数 runner）；`652ef58213c4ba2be988b3d51b70ab0392475e98`（Linux/Xvfb CI）。本报告与状态文档提交为阶段最终 tip；其 SHA 在执行交接中列出。
- 远端：只读运行 `git ls-remote origin refs/heads/main`，返回 `schannel: failed to receive handshake, SSL/TLS connection failed`（退出码 1）；因此远端当前 tip 未能核实。没有 fetch、pull、push、合并或改写历史。
- 环境：Windows，Python/Tk/Tcl 版本、桌面可用情况及每条测试命令的实际结果见第 5 节。
- 保护范围：没有计划改动 `lwt/`、正式语言规范、黑盒用例/矩阵、`app/log_report.lwt`、S10 的 25 项 CLI 契约、并发/性能 raw。最终按阶段基线核对后在此列出实际差异结果。

## 2. 架构与证据边界

S22 不新增应用功能。语义实验室和日志侦探仍把工作交给公开 LWT CLI；Snake 仍是独立 Python/Tkinter 附加演示。三个界面新增的仅是可选 runner/timer 注入点，默认路径保持现有真实 CLI 和 `root.after`/`after_cancel`；测试仍创建真实 Tk 根、真实应用控件和实际事件循环。

| 证据类别 | 本阶段证据 | 能说明什么 | 不能说明什么 |
|---|---|---|---|
| 无头 core/状态 | S22 GUI 集成套件外的现有 core 测试；工作台/实验室状态仍由原 core 管理 | 核心状态规则和请求失效逻辑 | Tk 控件绑定、实际窗口可用性 |
| Tk 控件/事件集成 | `tests/test_gui_integration.py` 中 10 项测试，使用真实 Tk/Ttk 控件、事件和事件循环 | 控件回调、状态显示、异步队列/定时器与 GUI 集成 | 物理输入、输入法、桌面合成器、视觉易读性/体验 |
| 真实 LWT CLI | 实验室三个主题、工作台默认/组合筛选/空结果/文件错误恢复、五题挑战均由 UI 触发 LWT 子进程 | 前端发起的 CLI 调用、stdout/stderr/退出码和报告呈现 | 真实用户桌面操作 |
| 人工桌面操作 | 本阶段未执行 | 无 | S21 的 A/B/C 项仍须 S12 现场预检 |
| 静态审阅 | 复核 UI 构造、Tk 线程边界、worker/队列、窗口关闭、Snake `after` 取消、CI 条件和保护路径 diff | 代码结构与声明的运行路径相符 | 不能单独证明运行时交互正确 |

## 3. 控件、事件和断言映射

| 应用/测试 | 实际控件或事件 | 关键断言 |
|---|---|---|
| 语义实验室：`test_real_combobox_events_switch_all_topics_and_keep_source_read_only` | `Combobox.current()` + `<<ComboboxSelected>>`；真实 Text；Run、Radiobutton、提交按钮 | 六个主题同步源码/问题/规范章节；源码为 disabled 且不可编辑；未提交预测时 Run 禁用且不能启动任务 |
| 语义实验室：`test_real_buttons_run_success_stdin_and_expected_runtime_error_cli_cases` | 主题选择、真实预测 Radiobutton、提交和 Run `.invoke()` | UI 发起真实 CLI；成功 stdout 精确为 `120\n`；stdin 字节/输出正确；RuntimeError 为退出码 3、含稳定位置字段并显示 stderr；错误预测反馈与 CLI 结果分开 |
| 语义实验室：`test_busy_controls_are_locked_and_window_close_rejects_late_worker_result` | 真实控件、WM_DELETE_WINDOW 协议；Event 门控的 runner 仅替代边界依赖 | 忙时选择/重置/运行控件禁用；重复 invoke 无效；关闭后迟到 worker 不更新 UI、不访问销毁窗口 |
| 日志工作台：`test_default_and_combined_queries_use_real_lwt_cli_and_same_request_report` | 查询按钮、Level/Keyword/Top Entry、完整报告按钮/Toplevel | 默认摘要正确；WARN+retry+top=2 的 argv、摘要、排行、示例和同次 raw 报告一致；真实 CLI 子进程完成查询 |
| 日志工作台：`test_actual_file_picker_path_zero_match_failure_and_recovery` | 选择文件按钮（仅系统文件对话框边界被 autospec patch）、筛选 Entry、查询按钮 | 空格/Unicode 路径能传给 CLI；零匹配为空态；缺失文件错误可见；换回有效路径后恢复查询 |
| 日志工作台：`test_pending_query_busy_lock_invalidation_and_close_do_not_apply_stale_result` | 查询按钮、Entry 状态、`StringVar` trace、WM_DELETE_WINDOW；Event 门控 runner | 查询中拒绝重复触发；条件 revision 变化清空指标并丢弃旧结果；下一次查询成功；关闭时取消 UI poll，迟到结果不触碰已销毁窗口 |
| 五题挑战：`test_five_question_game_uses_real_widgets_enter_and_real_cli_queries` | Notebook、开始/提交/下一题/重开按钮、Entry 的 `<Return>` | 真实 CLI 查询驱动五题；交替正确/错误反馈、进度/得分、结束页和重开正确；Enter 走控件绑定 |
| Snake：`test_real_buttons_keys_and_manual_ticks_keep_controls_and_canvas_in_sync` | 开始/暂停按钮、按钮焦点下的 Up/Down/WASD/Space/R 合成键、真实 Canvas；可控 timer 仅替代时钟 | 蛇移动状态与 Canvas/按钮一致；接受合法方向、拒绝直接反向；暂停/继续/重置；一个活动 tick 不重复排队 |
| Snake：`test_focus_out_pause_terminal_collision_replay_and_close_cancel_ticks` | FocusOut/FocusIn、主按钮、R、真实 Canvas；timer 受控 | 失焦暂停并清 tick；FocusIn 不自动续跑；撞墙进入终态；“再来一局”恢复运行；关闭取消 tick |
| Snake：`test_narrow_and_large_geometry_keep_canvas_and_primary_controls_bounded` | 真实窗口几何、Canvas 项坐标和主控件尺寸 | 480×440 与 1100×820 的几何约束均有效；Canvas 非零尺寸，绘制项在边界内。此项是布局约束检查，不是视觉验收 |

测试只在难稳定控制的 runner/timer 边界注入依赖；不 mock Tk、主窗口、实际控件、应用状态机或主要 CLI 路径。文件选择器由原生系统对话框接口替换返回一个带空格和 Unicode 的确定路径，文件内容仍经真实 `app/log_report.lwt` 和公开 CLI 读取/统计。

自动断言中的关键结果：语义实验室 `functions` 示例 stdout 为 `120\n`、退出码 0；stdin 样例保留输入 `LWT 输入演示\n` 并输出 `Enter one line:\nLWT 输入演示\n`；预期除零诊断退出码 3 且包含 `:2:8: RuntimeError:`。工作台默认值为 Total/Valid/Malformed/Matched=`7/6/1/6`，级别 ERROR/INFO/WARN 各 2；组合筛选 `WARN + retry + top=2` 的匹配数为 1，级别 `WARN|1`、模块 `cache|1`，样例为 `2026-10-07T10:00:03Z|WARN|cache|retry scheduled`；缺失文件显示错误后恢复默认查询到 6 个匹配。五题挑战每题调用真实日志 CLI，测试使用交替正确/错误答案验证最终 `2/5` 并重新开始。Snake 受控 tick 后头部与期望格相同，按钮焦点下合成 Up/Down/WASD 和 Space/R 路径更新状态，碰墙后主按钮可重开。几何断言覆盖 480×440 和 1100×820。

## 4. 缺陷与代码变化

本阶段没有复现可稳定复现的产品 GUI 缺陷，因此**没有新增产品逻辑修复**。为让真实控件回归能确定性控制耗时边界，增加了三个可选测试接缝：语义实验室 `example_runner`、日志工作台 `workbench_runner`、Snake `after`/`after_cancel`；生产默认值仍分别指向原 CLI 函数和 Tk timer。没有改变用户可见行为。

回归测试开发中出现过测试预期文案不匹配、隐藏 Notebook tab 不接受合成 Return、测试 runner 未将仓库根加入导入路径等测试夹具问题；逐一按真实控件状态/焦点和标准导入路径修正，不作为应用缺陷，也没有降低产品断言。

## 5. 环境和实际验证

运行环境：Windows 11 家庭中文版 build 26200，Python 3.13.7，Tk 8.6/Tcl 8.6；真实 Tk root 与本机显示可用。GUI 定向测试在隔离 Tk root 中运行；没有向其他应用发送物理鼠标或键盘事件。此处不把 root 创建当作人工 GUI 操作证据。

新增测试定向命令：

```powershell
python -m unittest discover -s tests -p "test_gui_integration.py" -v
python tools/run_gui_integration.py --require-no-skips
```

CI 在 Linux job 中运行时检查 `xvfb-run`；存在则直接使用，不存在才安装 `xvfb`/`xauth`，然后探测真实 Tk display 并运行带 `--require-no-skips` 的 GUI runner。该 runner 显示 discovered/run/pass/fail/skip 和每条 skip 原因；GUI 用例随后也在 Xvfb 下包含于完整 unittest。Ubuntu/Windows × Python 3.10/3.13 矩阵没有改变。本执行窗口未推送阶段分支，因此没有可归因的远端 Actions run；workflow 实际安装与四格结果留待 S12/合并后的 Actions 核验。

实际验证命令和结果（逐条记录，不用汇总句替代）：

| 命令 | 退出码/结果 |
|---|---|
| `python -m unittest discover -s tests -p "test_gui_integration.py" -v` | 退出码 0；Ran 10 tests，OK；10/10 通过、无 skip |
| `python tools/run_gui_integration.py --require-no-skips` | 退出码 0；Tk display available (Tk 8.6.15)；discovered=10 run=10 pass=10 fail=0 skip=0 |
| `python -m unittest discover -s tests -q` | 退出码 0；Ran 286 tests，OK（较基线 276 项增加 10 项） |
| `python tools/run_tests.py` | 退出码 0；passed=194 failed=0 total=194；分类：数组/record/each 32、内置/文本/I/O 43、CLI 错误 13、控制/函数 30、集成 3、词法/语法 42、值/运算符 31，全部满额 |
| `python tools/check_project_integrity.py` | 退出码 0；OK；194 cases、287 matrix links、194 referenced cases |
| `python -m compileall -q lwt tests tools bench app` | 退出码 0；无诊断 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 退出码 0；Effective LWT lines: 246 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 退出码 0；25 项通过（S10 CLI 契约数量保持不变） |
| PyYAML 读取 `.github/workflows/tests.yml` 并打印 job/matrix/steps | 退出码 0；语法可解析，仍为 Ubuntu/Windows × Python 3.10/3.13 四格；含 Linux GUI/Xvfb 定向与完整套件步骤 |
| 相对链接/Markdown fence 检查（10 份本阶段改动的 Markdown） | 退出码 0；本地相对目标存在，fence 数成对 |
| `git diff --check` | 退出码 0；无 whitespace error（Git 对两份 Windows 文档的 LF→CRLF 转换曾给提示，工作副本随后统一换行再复查） |
| 阶段基线 S10/S11 保护路径与语言/黑盒保护路径 `git diff --quiet 1919861652266edd75ce278736d71958eb90cd62 -- ...` | 两组命令退出码均 0；S10/S11 六个保护文件、`lwt/`、正式规范、黑盒矩阵/用例无差异 |

## 6. 桌面验收和未验证项

| 项目 | 本阶段状态 | 证据/交接 |
|---|---|---|
| S21 A：语义实验室现场点击、焦点、输入法、视觉 | 未执行/未验证 | S22 合成事件只验证控件绑定；交由 S12 安全现场预检 |
| S21 B：工作台/挑战的真实桌面点击、缩放、焦点 | 未执行/未验证 | S22 控件/CLI 回归不代表用户桌面体验；交由 S12 |
| S21 C：Snake 真实方向键、焦点、失焦与缩放观察 | 未执行/未验证 | 事件测试和几何约束不能替代物理设备、窗口管理器与视觉观察；交由 S12 |
| 远端 Git/Actions | 未验证 | `git ls-remote` 因 TLS 握手失败；无推送，未产生本阶段远端 workflow run |
| Python 3.10 / 四格 CI | 未验证 | S12 按最终候选提交执行 |

人工 GUI 检查矩阵不以截图、标题、句柄、Tk root 创建、无头状态测试或静态审阅标“通过”。S12 应继续执行 `docs/s12-final-delivery-plan.md` 中的语义实验室、日志工作台/挑战和 Snake 现场预检；桌面被遮挡、输入归属不清或非本任务输入出现时停止操作。

## 7. 保护文件和 S12 交接

阶段最终核对比较了 `app/log_report.lwt`、`tests/test_app.py`、S10 并发 JSON/报告、S11 性能 JSON/报告、`lwt/`、正式规范和黑盒矩阵/用例相对基线 `1919861652266edd75ce278736d71958eb90cd62` 的差异；两组 `git diff --quiet` 均退出 0。行数工具报告 246，S10 定向测试仍为 25 项。

S22 只补自动控件级回归，不开始 S12、不做 PPT、不执行新克隆/最终交付、不推送、不合并、不打标签。主窗口审查通过后 S12 是最后阶段；现场 GUI 证据、Python/远端 Actions 和新克隆检查仍在其范围内。

## 8. 修改文件

| 文件 | 内容 |
|---|---|
| `.github/workflows/tests.yml` | Linux 下探测/按需安装 Xvfb，单独运行 GUI 控件套件并在虚拟显示中运行完整 unittest；保留原 OS/Python 矩阵 |
| `app/language_lab_ui.py` | 添加默认仍指向真实 CLI 函数的可选 runner 注入点 |
| `app/log_detective_ui.py` | 添加默认仍指向真实分析器/CLI 的工作台 runner 注入点 |
| `app/snake_game_ui.py` | 添加默认仍使用 Tk `after`/`after_cancel` 的 timer 注入点 |
| `tests/test_gui_integration.py` | 新增 10 项真实 Tk/Ttk 控件、事件循环、异步生命周期和真实 CLI 集成测试 |
| `tools/run_gui_integration.py` | 新增显示探测和 GUI 测试 discovered/run/pass/fail/skip 汇总；可在 CI 强制零 skip |
| `app/README.md` | 添加控件级测试命令、Linux Xvfb CI 说明和证据边界 |
| `README.md` | 同步 S22 实施状态、报告入口和 S12 顺序 |
| `docs/agent-dev-log.md` | 记录 S22 提示目标、实现内容、人工复核、测试与责任边界 |
| `docs/s12-final-delivery-plan.md` | 保留人工桌面预检，把基线要求推进至含 S22 的已审查 main |
| `docs/s22-gui-regression-plan.md` | 更新阶段状态并链接实施报告 |
| `docs/s22-gui-regression.md` | 新增本阶段完整证据、风险、命令和修改文件报告 |
| `project.md` | 更新 S22 当前状态和 S12 下一步 |
| `阶段执行与审查路线图.md` | 记录 S22 执行结果、分支交接与最终顺序 |
| `LWT大作业总体方案与复检.md` | 同步 S22 控件回归和仍待现场复测的 A/B/C 边界 |
| `详细实施规划.md` | 更新 S22 状态、阶段映射及最终交付交接 |
