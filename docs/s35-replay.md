# S35 稳定时钟、可验证回放与前缀接管

状态：实施完成，等待主窗口审查。日期：2026-11-01。S12 未开始；未合入 main、未推送。

## 基线、历史与提交

开工工作区干净，当前功能分支 `feature/lwt-snake-game`，HEAD 为用户指定审查/规划提交 `89ed4b7db6a6c24a43972626a0769081224d0ed6`，包含 S34 产品 `f87e8b8abed1b25326428443483adbc9e2c05866`。本地 main 和 merge-base 为 `9d562b717ba82fc322ff152e6e1b7d5ff4b5c36c`。继续原功能分支，保留审查历史，没有用 main 覆盖它。

开工实时 `git ls-remote` 遇 Schannel TLS 失败；收尾期间成功只读查询到远端 main 仍为 `9d562b717ba82fc322ff152e6e1b7d5ff4b5c36c`，未列出远端游戏分支。没有 fetch/pull/push、历史重写或禁用 TLS。精确 S35 SHA 的远端 Actions 没有运行，不能从旧 CI 快照推断通过。

| 提交 | 完整 SHA |
|---|---|
| 先修复 S34 时钟与焦点测试门槛 | `7506f4524d7f3454534a4f6e5df14a6944cf949a` |
| 编码前冻结回放契约 | `504dd6a061edb5186644f42ef631a2ab20a5c584` |
| 真实事务录制/严格文件/新 LWT 验证 | `f2c0bf5bb42a1a2f9d61a245366016f454d864a9` |
| GUI 复盘/接管与严格 GUI runner | `b61ad203956781d62690cdb28428e95a7a88421d` |
| 固定父局/子局/分歧示例 | `8c5c543b65b38e29f40a91b4581b8805a855d70b` |
| 取消/总截止时间与 Tk 所属线程清理 | `98fb55f07a3a2b427fc6d9ec583ca73c747de970` |
| 中断后完整前缀仍可导出验证 | `57dd7331b77a922e654780b2af2ad41db023dbb7` |
| 等待截止时间监视线程完成回收 | `edb8b87d6647eaf2b3a300c1cad39d7164615eaf` |
| 使用说明、阶段状态及历史修正索引 | `bb4d77e697b250b00708e9d30e13b84cfcb7a2c8` |

报告自身最终 SHA、工作区干净状态和最后差异检查在最终交接列明，避免报告自引用 SHA。

## S34 修复门槛与实际失败

**R34-01：** 新增旧实现回归首次失败（exit 1）：START 后持续 TURN，蛇头断言显示 `(12, 9) == (12, 9)`。修复为独立单调截止时间：TURN/拒绝响应不会重设 deadline；到期 busy 时保留一个过期意图，响应后优先发一个 TICK。慢 TICK 完成后从当前时间建立下一截止时间，不补发累计过期格数。PAUSE/RESET/终态/错误/关闭停止旧时钟，START/RESUME 建立新时钟；旧 request/generation 回复不参与调度。

独立 fix 提交前实跑 S34 系列 15 项全部通过；之后再强化为真实 Canvas KeyPress 的连续 Right 与连续拒绝 Left，两种场景都确认收到超过 5 笔真实 TURN，且 1.15 秒窗口内蛇头推进。另用受控完成 Event 让真实 TURN 响应延迟到超过截止时间，busy 期间无 TICK 积压，释放后仅推进一次，再暂停取消时钟。确定性时钟模型另验证重复 start、到期 busy、长延迟、停止/重启，不以精确 FPS 当断言。

**R34-02：** 主窗口已有“整组失败、单跑通过”不能忽略。诊断实测新 Toplevel `ismapped=0` 时焦点为根窗 `.`，立即 focus_force 后仍为 `.`；执行映射事件后 `ismapped=1`，焦点才到 `.!toplevel`。旧测试没有确认这项前置条件。现在先等待映射，再请求焦点并确认实际顶层归属，然后仍断言 LWT PAUSED；没有延长超时、无限重试或删除暂停断言。fix 门槛整组 15/15 与单独该方法 1/1 均通过。可控同窗/外窗/无焦点判定另作独立无头测试；真实焦点用例通过事件循环确认映射/归属，不能由无头判定替代。

两项内部修复门槛满足后才开发回放；未把内部通过写成主窗口审查通过。S34 原报告保持历史结果，仅追加本报告索引。

后续开发还记录了三次失败：

1. CLI 成功字节断言首次失败：Windows print 产生 CRLF。改用 ASCII buffer 写固定 LF；重跑 CLI 成功/分歧/文件错误均符合契约。
2. 录制中断提示一度覆盖旧 GUI 测试要求的“引擎错误”前缀，定向组 10 项出现 1 失败。修复提示优先级，保留原错误断言，之后通过。
3. 首轮全量 unittest 进程 exit 1，出现 `Variable.__del__: main thread is not in main loop`，最后 `Tcl_AsyncDelete`，没有可用的最终 testsRun 汇总。Tk 对象析构发生在非所属线程；静态复核同时找到局部递归键盘标签安装函数会形成捕获 app 的引用环。测试现在在所属主线程释放 app/root 并显式回收退休 Tk 引用环，安装函数移至模块级避免该闭包。主线程清理后全量 481 项通过；最终清理版本又运行严格 GUI 与全量复核，结果见下表。没有禁用全局 GC、吞掉析构异常或将失败算通过。

## 记录、兼容与执行边界

格式详见 [snake-replay-format.md](snake-replay-format.md)，在编码前冻结并写出真实有效/无效文件。唯一事实为规范 ASCII request/response 帧；不保存第二份可能冲突的坐标真值。版本 `schema_version=1`、`protocol_version=LWS1`。源码身份使用严格 UTF-8、仅首个 BOM 去除、CRLF/CR→LF 后 UTF-8 SHA-256，算法名固定；不依赖 Git SHA。文件不含可执行 source_path 或自定义 argv，重建只执行仓库固定可信 game.lwt。

Recorder 钩子在 bridge 完整验证事务后、抛出 CommandRejected/交给 UI 之前执行，含 INIT、ERR、RESET，QUIT 单独作清理而不入记录。测试用完成 Event 阻住 TURN 的 UI 交接，再排入 RESET，证明即使旧 request_id 不再显示，实际 INIT/START/TURN/RESET 仍全部保存。半帧/超时不伪造事务，保存此前完整前缀和中断原因。

常量集中于 replay.py：最多 5000 笔、16 MiB 文件、10 位 JSON 整数字面量、默认总执行截止时间 30 秒，每请求沿用 bridge 2 秒。bool 不作整数；重复键、非有限数、未知字段、非法 UTF-8、超大整数/文件、乱序/缺事务、坏帧/版本/源码摘要均拒绝。达到录制上限停止追加并明确“仅保存到第 N 条”。总截止时间包含重建结构验证，watchdog 可在取消/截止时终止当前子进程；KeyboardInterrupt 也走清理，取消不能返回通过。

SAVE 是 worker 串行边界上的不可变完整前缀，不是只取 UI 最后一帧。保存对话框触发的 PAUSE 若真实执行也进入 recorder；取消对话框不保存。原子保存使用同目录唯一临时文件后 os.replace，失败清理本次临时文件并保留原目标；不承诺任意断电持久性。用户文件仅按明确选择位置保存，不自动加入 Git 或上传；仓库 replays 目录中的文件是本阶段主动生成的固定演示/测试样本。

## 真正的验证、复盘和接管

验证开启新的公开 `sys.executable -u -m lwt game.lwt` 进程，按记录顺序发命令，逐笔比较完整 STATE/ERR 响应；结束发送 QUIT、检查退出并回收。首个分歧报告事务索引/序号/命令/字段及有界预期/实际值。文件验证不是只验哈希；改分数、seed 或规范命令仍需经真实引擎比较，不能用文件自述绕过。

只有通过该服务生成的状态才进入复盘缓存。上一条/下一条/有限速度播放按事务计位置，TURN/PAUSE/RESET/ERR 也占位置；视觉暂停不向 LWT 发 PAUSE。接管另开新进程重新执行 INIT 到选定前缀，故随机状态和 pending_direction/has_pending 被真正重建，而非从坐标推测。READY 等待开始，PAUSED 等待继续，RUNNING 仅在用户明确接管后启用时钟；终态拒绝直接接管。子局包含完整已执行前缀和新事务、连续协议序号，来源摘要/前缀数只作说明。

切换时先停止时钟/播放并提升 generation，等待旧 owner.finished 后才开新引擎。验证进度通过有界队列返回；取消、第二次载入、异常和窗口关闭会回收旧进程，旧回复不恢复计时器或冒充新验证成功。严格 GUI runner 新发现两类 LWT Snake GUI 测试，既有 Linux Xvfb CI 步骤会调用它；矩阵和 workflow 未改，远端实际结果仍未验证。

## 完整闭环与 CLI 实测

固定父局 `demo-parent.json` 10 笔：4×2 seed 4，从 START 吃到两次食物（score 20），末笔 TURN D 尚未消费。原引擎关闭后，以新进程验证并重建这 10 笔；接管后发 TICK、PAUSE，保存 `demo-child.json` 12 笔，子局可独立验证，不依赖父文件路径。测试同时让原引擎与新重建引擎运行同一后续 TICK/PAUSE/RESUME，完整状态/响应逐步相等；另一分支用不同后续 TURN/TICK，原父前缀不变，分支独立验证通过。另验证 ERR 前缀接管的下一协议序号、PAUSE 清除待转向、RESET、增长/尾格/撞身/撞墙及 4×1 WON。

GUI 闭环以真实按钮和真实进程完成：开始→TURN→暂停→保存；关闭旧进程→载入/验证→上一条/下一条/播放暂停→选 TURN 位置→接管→PAUSE 形成新后续→另存子局→再次真实验证→返回实时新局。文件对话框仅注入选定路径，控件/worker/LWT 未 mock。另测保存取消、不可替换目录目标后恢复、坏文件后恢复、验证中取消、第二次载入、验证中关闭；确认旧 worker/进程结束且新记录未被旧回复覆盖。

从仓库根执行以下真实命令：

| 命令 `python -m app.lwt_snake.replay --verify ...` 的路径 | 实际结果 |
|---|---|
| `app/lwt_snake/replays/minimal.json` | exit 0，stdout `Verified 1 transactions.\n`，stderr 空 |
| `app/lwt_snake/replays/demo-parent.json` | exit 0，stdout `Verified 10 transactions.\n`，stderr 空 |
| `app/lwt_snake/replays/demo-child.json` | exit 0，stdout `Verified 12 transactions.\n`，stderr 空 |
| `app/lwt_snake/replays/demo-divergent.json` | exit 3，stdout 空；第 3 笔、000003、TICK、field 4 分歧，预期 score 20，实际 10 |
| `app/lwt_snake/replays/invalid-version.json` | exit 2，stdout 空，stderr `cannot load replay: unsupported replay/protocol version` |

这些是应用工具退出码，不改变正式 LWT CLI。源码摘要标识兼容性，不是防作弊签名。

## 命令结果与证据层

本机重新查询环境：Windows 11 10.0.26200、CPython 3.13.7、Tcl/Tk 8.6.15。py launcher 列有 3.13/3.12/3.11，没有 3.10；本轮不把旧阶段平台结果复制成新实测。

| 实际命令 | 结果 |
|---|---|
| 旧实现 `python -m unittest tests.test_lwt_snake_gui.LwtSnakeTkTests.test_continuous_turn_responses_cannot_starve_real_lwt_ticks -v` | exit 1，旧实现不移动；不是通过 |
| 修复门槛 `python -m unittest discover -s tests -p "test_lwt_snake*.py" -v` | 当时 15/15，exit 0；焦点方法另单跑 1/1 |
| `python -m unittest tests.test_lwt_snake_clock tests.test_lwt_snake_gui tests.test_lwt_snake_replay tests.test_lwt_snake_replay_gui -v` | 18/18，exit 0；包含后续强化的真实忙碌和文件/接管场景 |
| `python -m unittest tests.test_lwt_snake_replay -v` | 7/7，exit 0；随后又纳入最终全量 |
| `python -m unittest tests.test_lwt_snake_replay.ReplayTests.test_worker_records_completed_reply_even_when_display_is_superseded -v` | 1/1，exit 0；最后增加中断后前缀导出/真实验证断言 |
| `python -m unittest tests.test_lwt_snake_replay.ReplayTests.test_cancel_total_deadline_and_recording_limit -v` | 1/1，exit 0；收尾等待监视线程回收预算强化后，确认无新增存活 deadline 线程 |
| `python tools/run_gui_integration.py --require-no-skips` | exit 0；discovered/run/pass=19/19/19，fail=0，skip=0；真实 Tk 与合成事件 |
| `python -m unittest discover -s tests -q` | 首轮进程失败见上；主线程清理后 481/481、exit 0、137.591s；最终清理版本再次 481/481、exit 0、139.514s，无析构警告 |
| `python tools/run_tests.py` | exit 0；287/287，9 类全通过，59.190s |
| `python tools/check_project_integrity.py` | exit 0；287 cases / 384 matrix links / 287 referenced cases |
| `python -m unittest discover -s tests -p "test_app.py" -v` | exit 0；原 S10 25/25 |
| `python -m unittest discover -s tests -p "test_snake_game.py" -v` | exit 0；原 Python Snake 13/13 |
| `python -m compileall -q lwt tests tools bench app` | exit 0 |
| `python -m lwt --check app/lwt_snake/game.lwt` | exit 0，1 source |
| 两个 `python tools/count_lwt_lines.py ...` | exit 0；game.lwt 313、log_report.lwt 246 |
| `git diff --check`、文档链接/围栏、保护路径差异 | exit 0；9 份 Markdown 链接存在/围栏平衡，保护内容无差异；最终提交范围另复验 |

无头时钟/codec/录制测试、真实 LWT 子进程、新进程重建等价性、真实 Tk 合成事件、静态复核是不同证据。**没有本轮物理键鼠/输入法/视觉人工验收，没有 Python 3.10/Linux 本机实测，也没有本阶段远端 CI。** 不因自动控件通过宣称桌面体验已审查；未改编辑器，因此未重复 npm/VSIX 测试。

## 文件、保护范围与剩余审查

产品新增 clock.py、replay.py 与五份固定 replay JSON；修改 bridge.py/session.py/ui.py。测试新增 clock/replay/replay GUI 文件，修改原 LWT Snake GUI 测试；严格 GUI runner 扩大发现范围并修正 run 后发现数被 suite 清空的问题。文档新增格式/本报告，更新 README、app/README、project、路线图、Agent 开发记录、S35 派发状态；历史 S34 执行报告只追加修正索引。

具体变更共 24 文件：

- `app/lwt_snake/bridge.py`、`clock.py`、`replay.py`、`session.py`、`ui.py`。
- `app/lwt_snake/replays/minimal.json`、`invalid-version.json`、`demo-parent.json`、`demo-child.json`、`demo-divergent.json`。
- `tests/test_lwt_snake_clock.py`、`test_lwt_snake_gui.py`、`test_lwt_snake_replay.py`、`test_lwt_snake_replay_gui.py`；`tools/run_gui_integration.py`。
- `README.md`、`app/README.md`、`project.md`、`阶段执行与审查路线图.md`、`docs/agent-dev-log.md`、`docs/s34-lwt-snake.md`、`docs/s35-replay-handoff.md`、`docs/snake-replay-format.md`、`docs/s35-replay.md`。

相对起始 `89ed4b7...` 检查：game.lwt、原 Python Snake 入口/core/UI/测试、日志应用与 S10 原测试、287 黑盒源码/metadata/矩阵、lwt/、正式规范、S10 并发/S11 性能/S28 profile/S29 smoke、S34 roundtrip JSON 与 demo/rules commands/expected 均无变化。未运行任何保护数据生成器，没有把回放吞吐当作解释器性能。

2–3 分钟演示：启动实时游戏，方向键确认持续输入仍移动，暂停并保存（40 秒）；载入验证、单步查看 TURN/PAUSE 与播放暂停（40 秒）；选 RUNNING TURN 前缀接管，改变后续、暂停并另存，再载入子局验证（45 秒）；CLI 验证父/子成功，再跑故意分歧文件显示第 3 笔拒绝（30 秒）。GUI 不可用时直接运行上述三个 demo CLI 命令，源码与测试给出前缀重建接口。

待主窗口审查：S34 两项处置证据、截止时间/慢响应策略、严格文件兼容/上限与事务完整性、取消/所有权清理、父子局重建与 UI 状态。人工现场、Python 3.10/Linux 和精确 SHA 远端 CI 留给后续审查/S12；S12 仍未开始。本次完成后优先收口最终验收，不新增应用功能阶段。
