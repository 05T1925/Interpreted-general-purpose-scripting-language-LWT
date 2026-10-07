# S17：应用复检与图形界面打磨

日期：2026-10-07。状态：**实施完成，等待主窗口审查**。本阶段只改动应用 GUI、对应状态回归测试和阶段文档；没有开始 S12。

## 基线、分支与提交

- 仓库：`C:\Users\28641\Desktop\大三上\程序设计实践\大作业`
- 开工分支：`main`；开工时工作区干净，HEAD 为 `ffc276f941c591f804ad7b78d976c36ee87bf59a`，与 S17 规划基线一致。
- 本地分支状态：开工时 `main...origin/main [ahead 48]`。没有查询实时远端，也没有 fetch、push 或 merge；使用本地已审查的 `main` 创建阶段分支。
- 阶段分支：`stage/s17-app-polish`。
- 提交：

  | SHA | 内容 |
  |---|---|
| `7412e83e12124c2010fba93b5d325dfed5a03c88` | `Polish Tkinter application layouts and feedback`：共享主题、两个 GUI 的版式/反馈及 Snake 主操作状态转移。 |
| `8e5d26c6a6c7083cae662a46c9bf154718777a77` | `Cover Snake replay after terminal states`：分别覆盖 GAME_OVER 和 WON 后点击主操作的无头回归测试。 |
  | 文档提交 | 本报告和项目状态文档随文档单元提交；提交列表和阶段最终 tip 的完整 SHA 由阶段执行窗口最终报告中的 `git log` / `git rev-parse HEAD` 结果给出。提交对象不能在自身内容中写入自身 SHA，否则提交内容和 SHA 会改变。 |

最终分支 tip 是完成全部提交后的阶段 SHA；执行窗口会在最终报告中给出完整 40 位值。阶段工作应保持在 `stage/s17-app-polish`，工作区提交后干净。

## 桌面能力与启动尝试

环境为 Windows、CPython 3.13.7、Tk 8.6。`cua.getState()` 返回 `apps: []`；只列出了浏览器表面，且浏览器扩展状态读取报 `nodeRepl.fetch request failed`。本会话没有桌面截图、窗口选择、点击或键盘输入接口，因此不能进行可归因的鼠标/键盘操作，也不能目视检查窗口布局。Tk 可导入和窗口能启动不等同于 GUI 交互验收。

改动后分别用 PowerShell `Start-Process -FilePath python -ArgumentList 'app/log_detective.py'` 与 `Start-Process -FilePath python -ArgumentList 'app/snake_game.py'` 从仓库根目录启动。操作系统进程报告标题分别为 `LWT 日志侦探`、`LWT 贪吃蛇`，并返回非零窗口句柄；对各自 PID 发送 `WM_CLOSE` 后均正常退出，退出码均为 0。这证明窗口创建和关闭路径可启动，**没有证明窗口内容、控件状态或玩法通过人工验收**。

### 日志侦探人工验收

| 验收项目 | 状态 | 证据/限制 |
|---|---|---|
| 启动并创建主窗口、标题、关闭 | 启动/关闭通过；外观未验证 | Windows 主窗口标题为 `LWT 日志侦探`；WM_CLOSE 后进程退出码 0。没有截图或可操作控件。 |
| 窗口大小变化、最小尺寸、文字/长路径换行 | 未验证 | 代码已改为宽度驱动 `wraplength`；需在可控桌面手动缩放观察。 |
| 正确/错误答案反馈、分数与进度、重复提交 | 未验证 | 现有会话和 CLI 自动测试通过；没有人工点击/输入。 |
| 下一题、最后一题、最终结果和重新开始 | 未验证 | 无窗口输入能力。 |
| 完整 LWT 报告窗口打开/关闭 | 未验证 | 无窗口输入能力。 |
| 选择含空格与 Unicode 的文件、读取失败后恢复 | 未验证 | core 的真实公开 CLI 路径覆盖 Unicode/空格文件；图形文件选择和恢复未操作。 |
| Enter、Tab 顺序、焦点可见性 | 未验证 | `<Return>` 处理仍存在且返回 `break`；焦点外观需实际桌面检查。 |
| 查询忙闲、失败后的控件恢复 | 未验证 | 队列/CLI 状态由代码审查和无头 CLI 测试覆盖；未在 UI 中点击验证。 |
| 查询期间关闭窗口、后台任务/回调安全 | 未验证 | 关闭路径现在停止 `after` 轮询，worker 只向队列投递；需人工或桌面事件测试确认整体观感。 |

### 贪吃蛇人工验收

| 验收项目 | 状态 | 证据/限制 |
|---|---|---|
| 启动并创建主窗口、标题、关闭 | 启动/关闭通过；外观未验证 | Windows 主窗口标题为 `LWT 贪吃蛇`；WM_CLOSE 后进程退出码 0。没有截图或可操作控件。 |
| 棋盘、HUD、提示文字和窗口缩放 | 未验证 | 已实现居中等比网格、动态提示换行、窄棋盘提示换行及小格隐藏网格线；未现场缩放查看。 |
| 开始、方向键/WASD、防反向、按钮焦点下按键 | 未验证 | 核心规则测试通过；没有人工按键能力。帮助文字现在明确方向键在按钮聚焦时仍生效。 |
| Space 暂停/继续、R 重置、失焦自动暂停/重新聚焦 | 未验证 | 状态核心已有无头测试；焦点事件未现场操作。 |
| 撞墙、自碰撞、胜利及对应状态提示 | 未验证 | 核心测试覆盖输/赢；游戏窗口内的文字与遮罩未人工查看。 |
| 结束态“再来一局”按钮和计时器 | 按钮逻辑回归通过；GUI 点击/定时器仍未验证 | 无头测试证明两个结束状态下同一主操作转为 RUNNING；实际控件点击和连续 tick 需桌面验收。 |

## 复检发现与处理

### S10 / 日志侦探边界

- `app/log_report.lwt` 仍是唯一日志解析、筛选和统计实现。日志侦探通过 `sys.executable -m lwt` 和 argv 列表调用公开 CLI，设置仓库根 `cwd`、`shell=False`、UTF-8、捕获输出和有限 timeout；Python GUI 未复制日志逻辑。
- 耗时查询继续在线程中等待 CLI，结果通过 `queue.Queue` 返回，控件更新只在 Tk 主线程轮询回调中发生。查询期间主操作、文件选择和报告按钮禁用；错误保留可重试路径。
- 原关闭路径依赖 Tk 销毁时清除定时器。S17 明确保存轮询 ID，并在关闭时置 `_closing`、取消轮询、销毁根窗口；worker 完成后只投递队列，不直接访问控件。worker 本身不因关闭主动取消，至多继续等待已有 CLI timeout；这项仍需桌面/进程级审查。
- 固定几何窗口和常量换行宽度会降低窄窗口的文本可读性；这属于布局观察，不是声称已现场复现的视觉缺陷。S17 将最小宽度调整为 640，路径、说明、问题和反馈宽度随根窗口尺寸变化，并使用卡片分组与清晰状态文字。

### Snake 状态转移

- 复现的代码路径：让 `SnakeGame` 进入 `GAME_OVER`，旧 `_start_or_resume()` 的结束态分支只调用 `restart()`；`restart()` 结果为 `READY`。旧 UI 接下来只在 `RUNNING` 时安排 tick，故状态回到 READY 且没有下一步，主按钮文案也从“再来一局”变回“开始游戏”。
- 当前分支执行的无头确认输出为：`old terminal-button path: ready tick_scheduled=False`；修复后同一终态下调用 `activate_primary_action()` 输出 `fixed primary action: running tick_scheduled=True`。这不是现场点击或图形界面验收。
- 修复：`SnakeGame.activate_primary_action()` 统一 READY 开始、PAUSED 继续、GAME_OVER/WON 重置并立即开始；`SnakeGameApp` 的主按钮调用该状态方法。`R` 与“重新开始”保留为重置到 READY。
- 新增 2 项确定性测试：先真实走到墙碰撞后的 GAME_OVER 和满盘后的 WON，再调用 UI 使用的主操作状态方法，断言 RUNNING、分数重置和蛇身重置。
- 原 UI 用单个 `after` ID 管理 tick，只有 RUNNING 且无挂起 ID 才安排下一 tick；暂停、失焦、重开会取消回调。该规则由代码审查与核心测试支持，GUI 定时器未人工验收。

## 已实施的设计改进

- 新增 `app/ui_theme.py` 集中颜色和 ttk 样式；字体从 Tk 的 `TkDefaultFont` 获取活动系统字体族，不要求 Microsoft YaHei UI 或 Consolas。仍使用标准库 Tkinter/ttk/Canvas，没有新增依赖、图片、网络资源或音效。
- 日志侦探：浅色页面与白色内容卡片区分标题、路径、题目、反馈和操作；正确/错误反馈与状态文字同时传达结果；题目、说明和长文件路径按宽度重新换行；Enter 提交返回 `break`；报告窗口可缩到 460×300；窗口关闭会清除队列轮询。
- 贪吃蛇：标题/规则提示、得分、状态、主操作和辅助操作层次分开；状态显示输/赢文案并带文字色调；棋盘使用居中比例单元格，窗口窄到格子低于 12 px 时隐藏密集网格线；结束/暂停遮罩按文字 bbox 和棋盘宽度计算，不再固定 360 px；帮助文本随窗口宽度换行。
- 这些是基于源代码审阅确定的易读性/适配目标，不宣称截图对比或人工可用性结果。

## 变更文件

- `app/ui_theme.py`：新增两个 GUI 共用的颜色、字体回退与 ttk 主题。
- `app/log_detective_ui.py`：响应式路径/题目/反馈排版、状态呈现、Enter 事件收尾及关闭轮询清理。
- `app/snake_game_core.py`、`app/snake_game_ui.py`：统一主按钮状态动作、输赢颜色状态、提示和棋盘缩放排版。
- `tests/test_snake_game.py`：新增 GAME_OVER 与 WON 主操作回归测试；S8 的 LWT 黑盒集仍为 194 项。
- `app/README.md`、`README.md`、`project.md`、`LWT大作业总体方案与复检.md`、`详细实施规划.md`、`阶段执行与审查路线图.md`、`docs/agent-dev-log.md`：同步启动方式、真实状态、验证和审查限制。
- 本文件：阶段发现、改动、验证矩阵和限制记录。

## 自动验证

环境：Windows；Python 3.13.7；Tk 8.6。下表为实际命令及结果；这些自动检查不替代上方未验证的 GUI 人工操作。

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p "test_snake_game.py" -v` | 退出码 0；13 项通过（含 2 项新增终态重开测试）。 |
| `python -m unittest discover -s tests -p "test_log_detective.py" -v` | 退出码 0；11 项通过。 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 退出码 0；既有 S10 CLI 契约测试 25 项通过。 |
| `python -m unittest discover -s tests -q` | 退出码 0；243 项通过。 |
| `python tools/run_tests.py` | 退出码 0；194/194 黑盒用例通过；分类：数组/record/each 32、文本/I/O 内置函数 43、CLI 错误 13、控制/函数 30、综合 3、词法/语法 42、值/运算符 31。 |
| `python tools/check_project_integrity.py` | 退出码 0；194 cases、287 matrix links、194 referenced cases。 |
| `python -m compileall -q lwt tests tools bench app` | 退出码 0。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 退出码 0；246 行有效 LWT。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 退出码 0；输出为默认固定报告，6 条有效、1 条坏记录。 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2` | 退出码 0；`Matched records: 1`，模块 `cache|1`，示例为 `retry scheduled`。 |
| 两款 GUI 的进程启动/关闭尝试 | 两个窗口句柄非零，系统标题正确；发送 WM_CLOSE 后各退出码 0。未做内容截图或输入操作。 |
| `git diff --check` | 退出码 0；未发现空白错误。 |
| Markdown 相对链接与代码围栏检查 | 退出码 0；检查 21 份 Markdown、481 个相对链接；百分号编码路径解码后无断链或未闭合代码围栏。 |

没有运行 `python tools/run_app_concurrency.py` 或 `python tools/benchmark.py`。

## 保护文件核验

以下 Git blob 对象 ID 与 S17 基线 `ffc276f...` 的 blob 完全相同，等价于基线内容未改动：

| 保护文件 | 基线 blob | 工作区 blob | 结论 |
|---|---|---|---|
| `app/log_report.lwt` | `c86d18ae2fe6b4eff101c30fca5e6ac7b2522904` | `c86d18ae2fe6b4eff101c30fca5e6ac7b2522904` | 未改 |
| `tests/test_app.py` | `64a1041fdf18476cc34e1149d03c6d23e4aac24b` | `64a1041fdf18476cc34e1149d03c6d23e4aac24b` | 未改；25 项契约保留 |
| `reports/app-concurrency.json` | `a619327b3013677a506ec6e9d2e058b0fd9c6be4` | `a619327b3013677a506ec6e9d2e058b0fd9c6be4` | 未改 |
| `docs/app-concurrency.md` | `a1307f5becc3537ff39e828505a2a0f147d04cc4` | `a1307f5becc3537ff39e828505a2a0f147d04cc4` | 未改 |
| `bench/results.json` | `fe4fc43e4bd5930c0d45d27213fd592f68e87d03` | `fe4fc43e4bd5930c0d45d27213fd592f68e87d03` | 未改 |
| `reports/performance.md` | `5bd1bb56faf46137298a02d430fe00e040b99071` | `5bd1bb56faf46137298a02d430fe00e040b99071` | 未改 |

没有改动 `lwt/`、语言规范、黑盒用例或矩阵。并发 raw 生成器和性能基准均未运行，以避免覆盖保护数据。

## 未验证与待审查事项

- 日志侦探的答案反馈、进度/计分、报告窗口、重新开始、图形文件选择/错误恢复、Enter/Tab、忙闲控件和关闭期间的可视反馈仍需有桌面输入能力的主窗口或人工审查者逐项确认。
- Snake 的方向键/WASD、Space、R、结束态主按钮点击、碰撞/满盘表现、失焦暂停/恢复、窗口缩放和焦点行为也未进行人工操作；当前无头测试只证明规则状态与主按钮状态方法。
- Tk 8.6/Python 3.13.7 上成功启动不代表 Python 3.10、其他主题或高 DPI 环境的布局兼容性。Python 3.10、Linux GUI、远端 Actions、新克隆、PPT 与最终演示仍属 S12。
- S17 阶段状态：**实施完成，等待主窗口审查**。S12 尚未开始；没有合并、推送、改写历史或发布。
