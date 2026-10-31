# S34：LWT 驱动贪吃蛇实施报告

状态：**实施完成，等待主窗口审查**。日期：2026-10-31。分支 `feature/lwt-snake-game`；没有合并、推送或开始 S12。

## 基线与提交

开工实测工作区干净，当前分支为 main，HEAD、本地 main、origin/main 和实时 `git ls-remote` 的 main 均为 `9d562b717ba82fc322ff152e6e1b7d5ff4b5c36c`。随后从该 main 建立功能分支。收尾两次实时查询均因 Schannel TLS 握手失败，无法据此断言远端收尾位置；没有 fetch/pull/push 或禁用 TLS。

| 层次 | 完整提交 SHA |
|---|---|
| 先冻结协议/游戏规则 | `c926a75543946b41340bcb3b093f1ae44655c28f` |
| LWT 规则与获胜重放 | `4a13c15db948327f8d14eb127981fd422c2d5fba` |
| Python bridge/worker/Tk | `f920f363f606aafc3d1afd1f0b12c7e312c13de8` |
| 规则、故障、Tk 测试与活动时延记录 | `5d759d18b1d462a8be19cf6f961f21318dfa9374` |
| 完整固定规则重放 | `f5df72e46e5d251701422caee0562d375ab73910` |
| 使用说明与阶段状态 | `de9611f74d00029abf1751d6c8c1a02138d12eb5` |
| 故障子进程保持存活后验证拒绝 | `51275d01ea5fc4f253651d7298d12456b537a93b` |

后续状态文档与本报告按独立提交交接；最终 SHA/干净工作区由最终回复给出，避免报告自引用 SHA。

## 应用与课程证据

课程要求的数组、结构、输入输出、分支循环和函数在 `app/lwt_snake/game.lwt` 中直接用于完整游戏规则。有效 LWT **313 行**，没有靠注释、空白或无意义重复凑数。采用一个可独立运行的源码文件。已有日志应用继续为 **246 行有效 LWT**。

| 责任 | 源码与证据 |
|---|---|
| 蛇身、方向、转向队列、食物、Park–Miller 随机、计分、碰撞、胜利、暂停和复位 | `app/lwt_snake/game.lwt`；全部由 LWT 计算 |
| 长期公开 CLI 子进程、帧/序号/范围校验、超时和退出 | `app/lwt_snake/bridge.py`、`protocol.py` |
| 有界串行请求、响应交接、关闭回收 | `app/lwt_snake/session.py` |
| 控件事件、定时 TICK、显示/绘图 | `app/lwt_snake/ui.py`；不导入 Python SnakeGame |
| 原 Python Snake | 原入口、core、UI 和测试均未修改；仅新测试中的独立 oracle 引用它 |
| Agent 辅助开发记录 | [Agent 记录](agent-dev-log.md) S34：用户需求、生成内容、代码复核、故障复现与修复 |

Python bridge/UI 是应用前端；第二款 LWT 应用的规则源码是 game.lwt。没有改变解释器、正式规范、黑盒用例或日志应用的职责。

## 协议、进程与设计取舍

完整规则在编码前提交的[冻结协议](../app/lwt_snake/protocol.md)。请求固定 6 字段，版本 LWS1、六位递增序号、最多 128 ASCII 字节；正常响应固定 10 字段、最多 4096 字节，包含状态/分数/下一移动方向/食物/头到尾蛇身。错误响应固定 4 字段。宽度 4–24、高度 1–18、最多 432 格；GUI 默认为 24×18、种子 1。小棋盘只是相同规则的测试配置，可在 4×1 场景直接观察填满获胜。

每个 bridge 使用 `[sys.executable, '-u', '-m', 'lwt', source]` 和仓库 cwd、`shell=False`，生命周期内保留同一个 PID。stdout 和 stderr 独立 reader 线程并行排空；stdout 队列最多 4 项、stderr 仅保存最近 8192 字节，响应超时默认 2 秒。stdout 读取本身有 4098 字节上限，避免等待 LF 时无限累积。非 ASCII/非法 UTF-8、字段错误、重复或错误序号、坐标越界/重复/不连续、食物重叠和多余帧均拒绝；多余帧若稍后到达，会在下一请求前/应答时或 QUIT 退出检查中拒绝。

worker 命令队列最多 1 个等待请求，Tk 结果队列最多 16 项；UI 只有收到响应后才安排下个 tick。普通按键在 busy 时忽略，复位/失焦暂停可替换唯一待办命令。请求 ID 和 worker generation 丢弃旧响应。所有 Tk 更新只在主线程 poll 进行；关闭取消 after/焦点回调，worker 完成本次有界等待后 QUIT、关闭管道、join reader 并回收进程。故障时终止进程，Windows 对进程树 taskkill 后再做 terminate/kill 等待兜底；重试创建新 worker 与新进程。

游戏允许一个 TICK 前多次合法转向，最后一个合法值生效，反向判断相对最近接受值。它与原 Python core“立即变更方向”的规则存在输入时机差异；独立 oracle 对照限定每 tick 至多一个 TURN，并明确适配后逐状态比较，未宣称任意输入序列全量等价。多转向、自碰撞和尾格另外有明确 CLI 预期。

内部不变量失败调用 LWT fail，未用 recover 吞掉内部异常。协议命令被拒绝可保留进程继续请求；启动失败、超时、EOF 或坏输出则终止本局并显示可读诊断、保留重试。

## 可复现 CLI 输出

从仓库根运行 GUI：`python -m app.lwt_snake`。公开 CLI 后退：

```powershell
python -c "import subprocess,sys,pathlib; p=subprocess.run([sys.executable,'-u','-m','lwt','app/lwt_snake/game.lwt'],input=pathlib.Path('app/lwt_snake/demo.commands').read_bytes()); sys.exit(p.returncode)"
```

退出码 0，stderr 空；stdout 恰为：

```text
LWS1|000001|STATE|READY|0|R|3|0|3|2,0;1,0;0,0
LWS1|000002|STATE|RUNNING|0|R|3|0|3|2,0;1,0;0,0
LWS1|000003|STATE|WON|10|R|-|-|4|3,0;2,0;1,0;0,0
LWS1|000004|STATE|WON|10|R|-|-|4|3,0;2,0;1,0;0,0
```

同一命令把 demo.commands 换成 rules.commands，可重放 24 个请求；[完整期望](../app/lwt_snake/rules.expected)已逐行冻结。关键检查：序号 3 得分 10/长度 4；序号 9 新头 `(2,1)` 进入前一帧将离开的尾格、仍 RUNNING；10/11 PAUSED 蛇身不变；13 RESET 回初始；15 BAD_TURN；16/17 连续 U/L 转向后 18 撞身 GAME_OVER；21 吃食物后 22 撞墙；23 BAD_COMMAND；24 返回终局快照并正常退出。畸形字段/版本/序号、空 stdin EOF 及重放另外由公开 CLI 测试验证。

## 实际验证与环境

本机 Windows 11，CPython 3.13.7，Tk/Tcl 8.6.15。用真实临时 UTF-8 LWT echo 文件分别在 **3.13.7 和 3.11.16** 以 `-u -m lwt` 启动，写 `ping 雪\n` 并 flush，在 3 秒上限内读到相同 UTF-8 行；关闭 stdin 后均 exit 0、stderr 空。`py -0p` 列出 3.13、3.12、3.11，没有 Python 3.10，因此 3.10 实测仍未验证，未由文档兼容性推断通过。

| 实际命令 | 退出码与结果 |
|---|---|
| `python tools/run_tests.py` | 0；287/287，9 类保持不变，50.519s |
| `python tools/check_project_integrity.py` | 0；287 cases / 384 matrix links / 287 referenced cases |
| `python -m unittest discover -s tests -q` | 0；最终 467 项通过，106.057s；新增完整重放后又定向复验 |
| `python -m unittest discover -s tests -p "test_lwt_snake*.py" -v` | 0；13 项（规则/CLI/bridge 9，真实 Tk 4），0 skip；最终重放补充后定向复跑 |
| `python -m unittest tests.test_lwt_snake.BridgeFaultTests -v` | 0；3 项；最后增强故障夹具为先读 INIT、输出错误后保持子进程存活，避免仅靠提前退出令测试通过 |
| `python -m unittest discover -s tests -p "test_app.py" -v` | 0；原 S10 25 项通过 |
| `python -m unittest discover -s tests -p "test_snake_game.py" -v` | 0；原 Python Snake 13 项通过（开工与收尾均跑） |
| `python -m compileall -q lwt tests tools bench app` | 0 |
| `python -m lwt --check app/lwt_snake/game.lwt` | 0；1 source file |
| `python tools/count_lwt_lines.py app/lwt_snake/game.lwt` | 0；313 行 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0；246 行 |
| 文档相对链接、围栏、`git diff --check` | 0；8 份相关 Markdown 检查通过；最终 `main...HEAD` 提交后再检查并在交接列明 |

测试证据分层：CLI golden 比较逐行真实字节、stderr 与退出码；真实 LWT bridge 测试多次往返/同 PID、Unicode 空格源路径、规则状态；模拟故障使用真实 Python 子进程向 bridge 注入非法字节、超长/截断/重复/错序输出、提前退出、stderr 洪流和超时，明确不把这些模拟器称作 LWT 游戏。故障测试确认进程退出、reader 线程停止。真实 Tk 通过控件 invoke、合成键盘/焦点事件和 Tk 事件循环连接真实 LWT worker，不 mock 控件。

## 修复过程与桌面边界

首个测量脚本在游戏撞墙后再发 PAUSE，得到约定 BAD_STATE；这是驱动脚本错误，改成保持活动的固定矩形轨迹，没有放宽 LWT 状态规则。代码复核移除了未使用的辅助函数，内部不可达分支改为 fail，避免内部错误伪装正常终局。

初版真实 Tk 控件测试失败：给运行中的按钮 focus_force 后游戏意外 PAUSED。诊断确认根窗口 FocusOut 在同窗子控件接管焦点时也会出现。修复为 after_idle 后检查 focus_displayof 的顶层归属，只在离开本窗口时暂停；键盘独立 bindtag 优先于 ttk 类绑定。保留失败→通过证据：原测试超时，修复后四个 Tk 用例全部通过。

| GUI 项 | 实际证据 |
|---|---|
| 开始、按钮焦点方向键、暂停/继续、WASD/Space/R | 真实控件/合成事件，真实 LWT 响应，自动通过 |
| 同窗焦点不误暂停、其它顶层焦点暂停 | Tk focus_force 与合成事件，自动通过 |
| TICK 定时、复位旧响应丢弃、队列上限 | Tk 事件循环与真实 worker，自动通过 |
| 引擎 RuntimeError 后重试恢复、Unicode 路径 | 真实失败源文件→恢复源文件→控件重试，自动通过 |
| 请求中关闭、timer/poll 清理、worker/进程退出 | 自动通过 |
| 物理键鼠、中文输入法、外部窗口管理器、视觉可读性与截图 | **未人工验证**，交 S12 现场预检 |

## 活动 TICK 往返记录

新证据文件 [lwt-snake-roundtrip.json](../reports/lwt-snake-roundtrip.json) 包含全部 100 个样本。默认 24×18、seed 1，同一 PID；从 START 后沿右到 x=22、下到 y=16、左到 x=1、上到 y=1 的矩形路线转向，连续发 100 次 TICK，逐次断言 RUNNING。测量包住 `bridge.request('TICK')`，TURN 请求不计入样本；每次等待本次应答后再发下一次，所以没有积压请求。

本机 min **0.463 ms**、median **0.565 ms**、mean **0.571 ms**、max **0.764 ms**；100 次结束仍 RUNNING、同 PID、积压 0，QUIT 后 exit 0。该数仅支持当前机器/棋盘/轨迹可在 140ms tick 间隔内响应；没有写入 S11 性能数据，也不据此推断其它硬件或满盘最坏性能。

## 文件、保护范围与交接

新增：`app/lwt_snake/{protocol.md,game.lwt,protocol.py,bridge.py,session.py,ui.py,__init__.py,__main__.py,demo.commands,demo.expected,rules.commands,rules.expected}`；`tests/test_lwt_snake.py`、`tests/test_lwt_snake_gui.py`；`reports/lwt-snake-roundtrip.json`；本报告。

更新：根 README、app/README、project.md、阶段路线图、docs/agent-dev-log.md、docs/s34-lwt-snake-plan.md。原 Python Snake 的入口/core/UI/测试、app/log_report.lwt、tests/test_app.py、lwt/、正式规范、287 组黑盒/metadata/矩阵、S10 并发/S11 性能/S28 profile/S29 smoke 均以 Git diff 对照起始 main，保护内容无差异；未运行保护数据生成器。

三分钟演示：启动新入口并说明 LWT/Python 边界（30秒）；开始、转向、吃食物、暂停/恢复与复位（60秒）；展示 game.lwt 和冻结协议、一次进程 PID（30秒）；用 demo.commands 在公开 CLI 展示 WON 固定输出，rules.commands 展示尾格/错误（40秒）；说明自动测试与人工/3.10/远端 CI 未验证边界（20秒）。GUI 不可用时直接用上述 CLI 后退命令。

待主窗口审查：协议 v1 与多 TURN 行为、bridge 生命周期/错误校验、LWT 规则与独立 oracle 适配、真实 Tk 合成事件证据。远端 Actions 没有本阶段精确 SHA run（未推送），不可写通过；Python 3.10、人工桌面及现场答辩属于 S12 遗留。S12 未开始。
