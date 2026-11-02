# S36：LWT 策略助手、提示与自动驾驶实施报告

日期：2026-11-02。结论：**实施完成，等待主窗口审查**。未合并、未推送、未开始 S12。本报告的自动结果不表示主窗口审查、远端 CI 或人工桌面验收。

## 1. 基线、环境与提交

开工 `git status -sb` 为干净 `main...origin/main`；HEAD、本地 main、origin/main、`git merge-base main HEAD` 均为 `7bc0a13524b22eb26a0daaba67a9af3f409effb1`。`git log -6 --oneline --decorate` 确认其包含 S35 Linux FocusOut 修复 `33d5c04`、主窗口审查 `b800962` 及主线状态同步。只读 `git ls-remote origin refs/heads/main` 当场返回同一完整 SHA，不采用旧报告快照。新建并使用 `feature/lwt-snake-strategy`，没有重置、重写历史或覆盖用户修改；结尾再次查询远端 main 未变化、策略分支尚无远端引用。

本机 Windows 11 / `10.0.26200`，CPython 3.13.7，Tcl/Tk 8.6.15，可构造真实 Tk 控件。`py -0p` 列出 3.13、3.12、3.11，未安装 3.10。本阶段未运行 Linux、3.10 或精确阶段 SHA 的远端 Actions。现有 CI 文件和严格 GUI runner 不修改；现有 `test_lwt_snake*gui.py` 发现规则自动包含新测试。

| 分层提交 | 完整 SHA |
|---|---|
| 编码前独立冻结策略协议、算法和调度所有权 | `0142c3962711bf41075f3f16b1395e34393eb0b3` |
| LWT BFS 策略、长驻桥接/worker、首批真实 CLI 与故障/回放测试 | `05ee27798520917740e2754f9d64bab54e430d00` |
| Tk 提示、自动驾驶单串行链和真实控件回归 | `1895daedab671f82b81ad34bf126356cf4d14613` |
| 真实待执行 TURN 验证、独立时延工具和数据 | `2c6494c681eae5ffac135de70f41410f860d66da` |
| 固定 CLI 演示、UTF-8 边界澄清及静态清理 | `557f7f29bf4f103b122eed3a4a4cb3f7a050f4fc` |

上表为实现/验证冻结点；本文与状态文档的收尾提交完整 SHA 随执行交接回复给出。复核本 checkout 的最终提交、列表和工作区：`git rev-parse HEAD`、`git log --format="%H %s" main..HEAD`、`git status -sb`。最终保持策略功能分支干净，本地主线不前移。

## 2. 课程要求、边界和算法

| 课程要求 | S36 证据 | 边界 |
|---|---|---|
| Agent 使用 LWT 编写完整应用 | [strategy.lwt](../app/lwt_snake/strategy.lwt) 实质编写解析、一步预测、BFS 与选择；[Agent 记录](agent-dev-log.md) | 策略 141 行有效 LWT；不凑 200 行，已有规则引擎 313、日志应用 246 行继续满足应用规模依据 |
| 使用已支持的语言能力 | record、数组、函数、while/each、continue、字符串与 stdin/stdout | 不修改解释器、语法或正式语义 |
| 可自动核验与 Git 历史 | CLI、协议故障、Tk 和真实回放/接管测试；分层提交 | 不把新增测试数量当作完备性证明 |
| 答辩演示、开发过程 | [应用说明](../app/README.md#s36-lwt-策略提示与自动驾驶)、[冻结协议](snake-strategy-protocol.md)与本报告 | 未制作 PPT，未开始 S12 |

游戏状态仍唯一来自 `game.lwt`。独立策略长驻公开 CLI 只计算建议，Python 不复制 BFS、碰撞、食物或计分规则。策略按 U/R/D/L 排序，排除逆向、墙和身体（非增长步允许离开的尾格）；对每步后的静态占用做有限数组队列 BFS。可达食物且可达数至少当前蛇长，或直接吃到食物时，选最短距离；否则选最大空间；平局保持固定方向序；无合法步返回 NONE/TRAPPED。这不是未来存活或最优路径证明。

DIR 是**已验证快照的下一次方向，含待消费 TURN**。真实测试先向游戏发送 TURN U，策略对该快照选择 R，再由游戏接受 TURN R/TICK 并产生 score=10、长=4，避免把旧身体朝向误当作当前约束。食物在尾格不可能是合法快照；增长时尾格保留的判定在 LWT 候选逻辑中，食物与尾格重叠的畸形输入必须拒绝。

## 3. 协议、线程与交互

完整唯一契约在[策略协议](snake-strategy-protocol.md)。请求九字段 LWA1/六位序号/宽/高/DIR/食物 x/食物 y/蛇长/头到尾身体；请求至多 4096 字节，响应至多 128，ASCII+LF。响应 MOVE/方向/FOOD或SPACE、NONE/-/TRAPPED，或四字段 ERR。序号严格递增，错误不消费。合法 UTF-8 的非 ASCII 文本为 BAD_FRAME；非法 UTF-8 在正式 input 层产生 RuntimeError/exit 3。EOF 安静退出。

`StrategyBridge` 复用原桥接的有界管道读取与回收设施，独立 PID、序号、超时（默认 5s）、stdin EOF 清理。并行排空 stdout/stderr，stderr 尾部 8192 字节；错字段、错序、超长、非 ASCII、半帧、额外帧、早退、超时、取消均拒绝并回收。不吞内部 LWT 异常伪造 MOVE。Python 仅作结构校验及直接逆向防御，不选替代方向。

worker 不触碰 Tk。UI 只保留一个策略 owner、一个在途请求和有界队列，代号和完整不可变快照共同过滤旧响应；旧 owner finished 后才创建下一 owner。取消只发事件，进程回收在后台完成。提示不发游戏命令，计算时临时停止手动时钟，结果以棋盘外文字箭头/理由显示，恢复时钟后下一快照清除旧建议。PAUSED 需先继续再查询，符合“仅 RUNNING 查询”的冻结范围。

自动模式停用手动 GameClock，严格“策略 → 必要 TURN → TICK → 新快照”，链间至少 140ms、无补帧积压；不等同于硬实时控制。真实游戏请求仍走 EngineWorker/bridge/recorder。手动方向键退出自动并接管；暂停、重置、终态、失焦、保存/载入对话框、复盘、接管、关闭取消旧策略；恢复焦点不会自行恢复自动。保存先请求 PAUSE，再在原事务边界保存，即使取消文件选择也不自动恢复。策略故障停止所有定时推进，保留最后确认快照和事务前缀，可手动接管/重试，无 Python 策略回退。

## 4. 实际回放闭环与故障恢复

固定宽 8、高 5、seed=4，经真实 LWT 策略和真实游戏执行 18 个 TICK（只在建议不同于有效 DIR 时 TURN），共 28 笔完整事务；不是坐标动画。旧策略和游戏都 exit 0 后，在临时目录保存，再调用全新的公开验证 CLI。实际输出：

```text
parent 28 40 RUNNING
LWS1|000028|STATE|RUNNING|40|L|2|3|7|3,3;4,3;5,3;6,3;7,3;7,2;7,1
old processes exit 0 0
parent verify: exit 0, stdout b'Verified 28 transactions.\n', stderr b''
child verify: exit 0, stdout b'Verified 4 transactions.\n', stderr b''
LWS1|000004|STATE|RUNNING|0|D|5|2|3|4,3;4,2;3,2
```

子局在新进程重执行父前两笔 INIT/START 后显式手动 TURN D/TICK，前缀完全一致、后续与原自动局不同，父/子分别验证成功。随机与待转向状态从真实前缀恢复，不从坐标推断。可复现自动验证命令：`python -m unittest tests.test_lwt_snake_strategy.StrategyBridgeTests.test_auto_record_fresh_cli_verification_and_prefix_branch -v`；本轮通过全量及联合定向运行该方法，另用同轨迹临时脚本打印以上精确值。临时文件未加入 Git。

故障恢复：真实 Tk 自动按钮启动不存在的 Python（仅此边界注入），UI 显示策略停止，TICK 数仍 0、GameClock 不再推进；旧 worker 回收后再次点击自动按钮启动真实 LWT，完成至少四步、保存、载入新进程验证成功。另将一个真实已计算提示用 Event 暂缓交接，期间真实 RESET 控件仍完成，释放后的旧结果不能覆盖 READY。所有这些为自动控件证据，不是人工体验。

## 5. 用例和证据分层

| 层次/文件 | 实际覆盖与断言 |
|---|---|
| 真实 LWT CLI：`tests/test_lwt_snake_strategy.py` 的 4 个 CLI 方法 | 4×1、直达食物、墙边唯一转向、尾格合法、身体隔断、食物不可达、FOOD 与 SPACE 平局、待执行方向、无路、24×18 空旷与 431 节身体；重复请求方向/理由一致且序号递增；坏版本/序号/字段数/长度/Unicode/坐标/食物/蛇长拒绝，EOF 及坏 UTF-8 |
| Bridge/真实进程：同文件的 4 个 bridge 方法 | 错字段/错序/非法编码/超长/半帧/额外输出/直接反向、超时、stderr 洪流、早退 exit 7、取消、启动失败、重启、空格 Unicode 源路径；进程退出、读线程结束、stderr 上限；真实待 TURN、自动父/子局全新 CLI 验证 |
| 真实 Tk：`tests/test_lwt_snake_strategy_gui.py` 的 4 个方法 | hint_button 不变事务数；auto_button 真实多步、策略 PID 稳定、无手动 tick_id/deadline、TURN 后 TICK、队列至多一；按钮焦点合成 Up 手动接管；暂停/重置/外部 Toplevel 失焦/复盘/接管/关闭取消；保存一致前缀、启动失败恢复、旧代拒绝、已计算未显示提示 RESET、自动/手动三轮切换无双 TICK |
| S35 定向/core | 原时钟、录制、文件错误、随机/待 TURN 前缀、取消/清理和原 Tk 回归全部保留，联合 30 项通过 |
| 静态审阅 | 仅 LWT 文件存在路径选择算法；Python 没有规则后备；原保护文件无差异 |
| 人工桌面 | **未执行**物理鼠标键盘、中文输入法、视觉可读性、真实缩放体验；合成事件和控件 invoke 不能替代这些验收，交 S12 现场预检 |

## 6. 实际命令与结果

以下全部是在本阶段实际运行的命令；无头跳过不计 GUI 通过。环境探测使用 `python -c` 构造并销毁 Tk，打印 platform、sys.version、Tcl/Tk patchlevel，以及 `py -0p`，均 exit 0。

| 命令 | 退出码、实际关键结果 |
|---|---|
| 开工 `git status -sb`、`git branch --show-current`、`git rev-parse HEAD`、`git log -6 --oneline --decorate`、`git remote -v`、`git rev-parse main origin/main`、`git merge-base main HEAD`、`git ls-remote origin refs/heads/main` | 0；干净 main、实时 main=7bc0a13，拓扑一致；未 fetch/pull/push |
| `git switch -c feature/lwt-snake-strategy` | 0；从最新已审查本地主线创建 |
| 基线 `python -m unittest tests.test_lwt_snake_clock tests.test_lwt_snake_replay -q` | 0；9/9，10.020s |
| `python -m lwt --check app/lwt_snake/strategy.lwt` | 0；1 source passed，编码后和最终静态阶段均执行 |
| `python -m unittest tests.test_lwt_snake_strategy -v` | 初次缺源码 exit 1（子进程 FileError/4）；编码后尾格理由误期望 exit 1；更正为 SPACE 后先 2/2，补充后 8/8，最后独立运行 12.607s |
| `python -m unittest tests.test_lwt_snake_gui tests.test_lwt_snake_replay_gui -q` | 接入初版 exit 1：连续 TURN 时钟失败，9 项中 1 fail；保留断言修复，后续联合全过 |
| `python -m unittest tests.test_lwt_snake_strategy_gui tests.test_lwt_snake_gui -v` | 初版 9 项中旧逆向 TURN 时钟 1 fail；补充仅对活跃策略切换后通过。另一次新增方法误放保存断言，修正测试方法归属，未放宽断言 |
| `python -m unittest tests.test_lwt_snake_strategy_gui tests.test_lwt_snake_gui tests.test_lwt_snake_replay_gui -v` | 0；13/13，31.480s |
| `python tools/run_gui_integration.py --require-no-skips` | 0；Tk 8.6.15，discovered=23 run=23 pass=23 fail=0 skip=0，32.059s |
| `python -m unittest discover -s tests -q` | 0；493/493，143.456s；较 S35 481 项增加 12（8 CLI/bridge、4 Tk） |
| `python tools/run_tests.py` | 0；287/287，43.101s；各类别 32/43/13/43/40/3/52/30/31 项全过 |
| `python tools/check_project_integrity.py` | 0；287 cases、384 matrix_links、287 referenced_cases，执行两次结果一致 |
| `python -m unittest tests.test_lwt_snake_clock tests.test_lwt_snake_replay tests.test_lwt_snake_gui tests.test_lwt_snake_replay_gui tests.test_lwt_snake_strategy tests.test_lwt_snake_strategy_gui -v` | 0；30/30，46.005s |
| `python -m unittest discover -s tests -p test_app.py -v` | 0；原 25/25，6.768s |
| `python -m unittest discover -s tests -p test_snake_game.py -v` | 0；13/13，0.077s |
| `python -m compileall -q lwt tests tools bench app` | 0；无编译错误，独立重跑也 exit 0 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0；246 |
| `python tools/count_lwt_lines.py app/lwt_snake/game.lwt` | 0；313 |
| `python tools/count_lwt_lines.py app/lwt_snake/strategy.lwt` | 0；141 |
| `python tools/measure_snake_strategy.py`，随后 `python tools/measure_snake_strategy.py --output reports/s36-strategy-latency.json` | 均 0；每次 8×5/24×18 各九请求、24 步串行自动局；正式 S36 样本用第二条保存，未混入 S11 |
| [应用说明](../app/README.md#s36-lwt-策略提示与自动驾驶)的 `python -c` 公开 CLI 演示，附 capture_output 与 `.expected` 字节比较 | 0；stdout 为下列三行，stderr b''，LF/CRLF 规范化后与新 expected 完全相等 |
| 同 18 步轨迹临时验证脚本（第 4 节） | 0；旧进程退出、新验证父 28/子 4，stderr 空；固定 S35 样例未写入 |
| `git diff --check`、`git diff --check main`、`git diff --check main...HEAD` | 初次已提交测试文件多余 EOF 空行导致 1；去除后重验 0，无产品逻辑改动 |

演示三行精确逻辑输出：

```text
LWA1|000001|MOVE|R|FOOD
LWA1|000002|MOVE|L|SPACE
LWA1|000003|NONE|-|TRAPPED
```

新增测试不修改语言黑盒矩阵/库存。完整 unittest 后只修改了类型注解、演示文件、文档和空行；未再改策略或调度行为。最终 `compileall` 再次 exit 0；本阶段 7 份 Markdown 的相对文件链接（URL 解码后）和成对代码围栏检查 exit 0；保护 diff、最终 diff 检查和干净工作区在收尾时核对。

## 7. S36 时延与停止条件

[独立原始样本](../reports/s36-strategy-latency.json)由[测量工具](../tools/measure_snake_strategy.py)本轮实际生成。每种棋盘九次同快照请求（包含首轮解释器启动/加载成本），策略 PID 各自稳定：

| 棋盘 | median | max | 策略 PID |
|---|---:|---:|---:|
| 8×5 | 14.022ms | 168.132ms | 47600 |
| 24×18 | 142.124ms | 292.867ms | 50068 |

另一组 seed=4、8×5 串行自动链 24 TICK、36 笔事务、score=60、RUNNING；首链 175.644ms，后续约 4.943–16.003ms，采样点待处理响应数最大 0。实际 Tk 自动请求队列另由控件测试断言至多一，手动 tick_id/deadline 为 None。没有硬实时、稳赢、跨硬件或解释器性能结论；这些时延不进入 S11。初探三次最大棋盘请求约 0.2812/0.1346/0.1358s，也只作可实施性门槛参考。

本机未触发“明显无法交互则停止扩展”条件；最大棋盘暖查询约 0.14s，加链间至少 140ms，自动驾驶比手动节拍慢且不补帧。其他硬件需要重测，有界超时失败时停止策略，不降安全校验。S35 最多 5000 笔录制的限制继续有效，不另称无限保存。

## 8. 修改文件与保护核对

| 文件 | 内容 |
|---|---|
| `docs/snake-strategy-protocol.md` | 编码前独立冻结九字段帧、有限算法、取消规则；补充 UTF-8 input 边界 |
| `app/lwt_snake/strategy.lwt` | 独立解析/合法候选/预测占用/BFS/确定性选择长驻服务 |
| `app/lwt_snake/strategy.py` | 有界策略 bridge/worker、响应与快照结构校验、代号消息 |
| `app/lwt_snake/ui.py` | 提示/自动控件、串行链、取消/手动接管/失败保持状态 |
| `tests/test_lwt_snake_strategy.py` | 8 项真实 CLI、故障、生命周期与回放/分支测试 |
| `tests/test_lwt_snake_strategy_gui.py` | 4 项真实 Tk/事件/真实子进程测试 |
| `app/lwt_snake/strategy-demo.commands`、`strategy-demo.expected` | 可独立执行的 FOOD/SPACE/TRAPPED 三场景 |
| `tools/measure_snake_strategy.py`、`reports/s36-strategy-latency.json` | 隔离的本机策略时延与串行链样本 |
| `README.md`、`app/README.md` | 当前能力、命令、交互/失败边界和两分钟演示 |
| `project.md`、`阶段执行与审查路线图.md` | S36 等待审查；S12 未开始 |
| `docs/agent-dev-log.md`、本报告 | 实际需求、生成/复核修正、证据与交接 |

相对开工 SHA，`git diff --exit-code 7bc0a13524b22eb26a0daaba67a9af3f409effb1 -- ...` 逐项保护核对无差异（exit 0）：`game.lwt`、S34 demo/rules 命令与 expected、S35 `replays/`、`app/log_report.lwt`、原 Python Snake 实现/测试、`tests/test_app.py`、`lwt/`、正式语言规范、测试矩阵、`tests/cases/`、S10 并发 JSON/文档、S11 bench/results.json 与 performance.md、S28 app-lwt-profile JSON/HTML、S29 lsp-smoke、S34 lwt-snake-roundtrip。未运行任何这些历史证据的生成器。S36 新时延文件单列。

## 9. 主窗口与 S12 交接

请重点复核有效 DIR/待 TURN、预测占用与静态 BFS 的界限、策略/游戏两个 owner、关闭/取消代号、自动链没有手动双 TICK、所有真实事务仍在原 recorder。故障模拟与真实 LWT 路径、Tk 合成事件与人工键鼠均已分开记录。严格 GUI 23/23、全量 493/493 是本机自动证据，不能推断未推送阶段的远端 Actions。

人工物理键鼠、中文输入法、窗口缩放/视觉可读性及不同硬件时延留给 S12 现场预检；本阶段未验证 Linux/Python 3.10、新克隆或最终交付。S36 是最后可选应用阶段；审查与集成由主窗口负责，之后优先 S12，不自行追加功能、合并、推送、打标签或发布。
