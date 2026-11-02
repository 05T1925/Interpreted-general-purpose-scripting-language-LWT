# S38 策略决策链验真与可解释回放执行报告

状态：**实施完成，等待 S37/S38 主窗口联合复审**。日期 2026-11-02。功能分支未合并、未推送；S12 未开始。

## 基线、审查反例与决策

开工分支 `feature/lwt-strategy-arena` 干净，HEAD `b8a5bdf2e0295a2f6ef49581b5042d206ff8beee`（主窗口在 S37 tip `3ed956d977f504a8854dac9feb34231fa862dad8` 后追加审查/派发文档）。`main`、`origin/main` 与实时 `git ls-remote origin refs/heads/main` 均为 `65994968732f017e84821bf82a4baf1184637b93`；merge-base 同此。未从旧 main 另建分支，未覆盖用户改动。

分层提交 SHA（最终文档收尾提交另在交接回复列出）：失败回归 `75963353871424719fc4a425a22c21cbcaeb25df`；v2 契约 `ab9074e3a348c51fe5492f0588a8f210063e87a8`；决策链实现 `046138ccf15ef8e13cb4c78d26e9bd612b9d2a43`；固定六局 `120ce1d5b102100d6e6850116e2673eca894349b`；证据断言 `7b6d0e3324c8aecfc40369a4519fa0e95b401786`；有限 median 与失败前缀 `adbaab4362383f932e7d983c74ffaa61c33be69c`；文档交接 `0d0a65483f75a4aa7644a964587895db5c76b8ba`；真实终局反例 `688835b6953168e4e3c9fcf49c4f5422d0bbd730`；伪造 TRAPPED 反例 `e0da694fa386eeeb7cbfb1ec560c193ff5777995`。

先增失败回归：仓库外临时目录复制真实 `baseline/4` 12 TICK 游戏回放（10 分），改标 BFS 与白名单路径/摘要并更新普通 summary，旧 `--verify` 返回 0，输出含 `bfs 4 10 12 limit true`、`Verified 1 matches.`；空策略/种子/cases/summary 的 v1 文件旧版也返回 0。两条测试在原实现分别 exit 1，失败文本为 `relabelled baseline replay passed as BFS` 与 `empty inventory passed verification`。原六局未被指控造假；旧验证器只能证明 LWS1 游戏命令回放。

先单独提交 [v2 契约](s38-policy-proof-contract.md)，然后实现两种证明：`game_verified` 是新 `game.lwt` 进程逐事务重放；`policy_verified` 是新长驻 LWT 策略进程从真实查询前状态重新回答，并核对方向/原因与 TURN/TICK 链。每个完整问答保留序号、咨询前游戏事务索引、规范 LWA1 请求及精确响应，写入 `decisions/<ID>-<seed>.json`，结果绑定其 SHA-256 与 S35 回放摘要。Python 不重算方向、路径、碰撞、食物或得分。`--explain` 先执行双层验真，才展示证据；SHA-256 是字节完整性和当前源码确定性一致性的标识，不是历史执行者的密码学签名。

历史 `reports/s37-demo/` 原样保留。普通 `--verify` 对 v1 exit 3，诊断 `v1 game replay only; strategy decisions unverified; use --game-only --verify`；显式 `--game-only --verify` 对严格 inventory 和游戏事务复核后 exit 0，并打印 `game replay only; strategy decisions unverified`。v1 的 `verified=true` 从未提升为策略证明。v2 拒绝空 inventory、缺失/额外/重复键、布尔冒充整数、越界参数、重复/非连续案例、NaN、过长整数、文件/路径越界及超大 JSON；S35 回放解析器未放宽。

## 固定样例与解释

新 [v2 结果](../reports/s38-demo/result.json)与同目录六份 `replays/`、六份 `decisions/` 在新路径保留，`.gitattributes` 的 `-text` 使原始 SHA 在跨平台检出时稳定。运行身份：8×5，seed 4/7/11，每局上限 12 TICK，workers 2；策略 SHA-256：baseline `01482253e3c9887c121f1a4d52a528e472c7fc3b5fd6779d3412cc3504747327`，BFS `a5aae877f2b4da5d238e7387b87d439c2509d7c3677d61a116a7d6dc1616d9ec`，游戏 `99083722c6fbb4e0f77afc51378381a53af0444c0ae4a4e45aa9d7f8fccd506d`。六局均为 `limit`、ticks 12、两级证明 true：baseline seed 4/7/11 分数 10/0/0；BFS 40/30/20。median/min/max 分别 0/0/10、30/20/40；不是胜率或策略优越性证明。workers 1/2/4 的六局结果 JSON 字节一致、文件名不冲突；每局使用独立游戏、策略进程及 recorder。

```powershell
python -m app.lwt_snake.arena --seeds 4,7,11 --max-ticks 12 --workers 2 --output reports/s38-demo
python -m app.lwt_snake.arena --verify reports/s38-demo/result.json
python -m app.lwt_snake.arena --explain reports/s38-demo/result.json --case bfs/4 --step 3
python -m app.lwt_snake.arena --game-only --verify reports/s37-demo/result.json
```

上述生成命令在全新目录执行一次，exit 0；本报告中的路径是已提交的固定结果，不要再次原地覆盖。新样例 `--verify` exit 0，末行 `Verified 6 matches: game and policy decisions.`；旧样例降级命令 exit 0，末行 `game replay only; strategy decisions unverified`。解释命令 exit 0，核心逐字输出：

```text
case=bfs/4 step=3 strategy_sha256=a5aae877f2b4da5d238e7387b87d439c2509d7c3677d61a116a7d6dc1616d9ec
before_tx=5 phase=RUNNING score=10 direction=D head=(5, 3) food=(4, 3)
LWT_advice=LWA1|000003|MOVE|L|FOOD commands=TURN,TICK
after_tx=7 phase=RUNNING score=20 delta=10 head=(4, 3)
```

CLI 无 Tk、断网可用。正常一步和转向吃食物一步均由定向测试核对；损坏证据或不适用的 v1 不会显示为真实策略决策。

## 回归与故障证据

环境：Windows，Python 3.13.7，Tk 8.6.15。本阶段没有 Linux/Python 3.10 的本地运行或精确提交 SHA 的远端 Actions；不得据 Windows 结果推断它们通过。以下仅列本轮实际执行：

| 命令 | 退出码与结果 |
|---|---|
| `python -m unittest tests.test_lwt_snake_arena -q` | 最终 exit 0，10/10，66.901s。针对旧实现两条审查反例各 exit 1，修复后同测试通过 |
| `python -m unittest discover -s tests -q` | 最终 exit 0，503/503，208.015s；S37 报告 497，本阶段增 6 项 |
| `python tools/run_tests.py` | 0，语言黑盒 287/287，九类均通过，52.599s |
| `python tools/check_project_integrity.py` | 0，287 cases、384 matrix links、287 referenced cases |
| `python tools/run_gui_integration.py --require-no-skips` | 0，真实 Tk 控件/合成事件 23/23，fail 0、skip 0，35.772s |
| `python -m unittest tests.test_lwt_snake_strategy tests.test_lwt_snake_replay tests.test_lwt_snake_clock -q` | 0，S35/S36 定向 17/17 |
| `python -m unittest discover -s tests -p test_app.py -q` | 0，S10 日志应用 25/25 |
| `python -m lwt --check app/lwt_snake/strategy.lwt`；同命令检查 `strategy_baseline.lwt` | 各 0，1 source passed；原 LWT 策略未修改 |
| `python -m compileall -q lwt tests tools bench app` | 0 |
| `python tools/count_lwt_lines.py` 对日志应用、游戏、BFS、baseline | 各 0，有效行依次 246、313、141、107 |

定向攻击测试把决策方向、`FOOD/SPACE` 原因、响应序号、咨询计数、咨询前事务索引、查询快照或策略 ID 改坏并重算可控的普通 SHA，`--verify` 均非零，错误定位到 `strategy/seed` 和决策/事务字段。旧 S37 的 replay score、seed、源码摘要、缺失文件及事务篡改回归继续通过。策略坏帧、超时、stderr 洪流、非零退出、游戏启动坏帧、预取消与写盘失败均在测试中有受控注入；失败前缀不记成正常零分。严格 GUI runner 仍是自动控件证据，不等同物理键鼠或视觉人工验收。

补充 workers 一致性时把每个输出目录下的结果、回放、决策 JSON **全部按字节比较**，而非只比顶层结果。又发现两个完成局的合法 median `5.0` 曾被过严的 JSON 小数解析拒绝；修改为接受有限小数，仍用 summary 重算拒绝伪造数值，新增两种子真实 LWT 回归。首次放置该测试时误把畸形 JSON 断言缩进到新测试，定向运行出现 `NameError`；调整归属后两项定向测试 exit 0，最终全量在修正后的文件上重跑。此处不将中间失败写成绿灯。

终局边界另用真实 4×2 棋盘、baseline/4 运行到 `won` 并双层验真；随后追加第 11 次虚构咨询并同步更新决策文件 SHA，`--verify` exit 3、指出 `baseline/4: decision`。达到上限的真实 baseline/4 结果也被伪加最后一条 `NONE|-|TRAPPED` 并改写 summary/普通 SHA；全新 LWT 策略仍返回 MOVE，验真 exit 3。该测试只接受真实获胜局为正例，不以手写游戏状态代替 LWT 引擎。

## 修改文件、保护与交接

新增 [v2 契约](s38-policy-proof-contract.md)、本报告和 `reports/s38-demo/` 下的 13 个结果/回放/决策文件；修改 `app/lwt_snake/arena.py`、`tests/test_lwt_snake_arena.py`、`.gitattributes`、根/应用 README、`project.md`、`阶段执行与审查路线图.md`、`docs/agent-dev-log.md`。按审查反例、契约、实现、固定结果、测试修正、文档分层提交；完整 SHA 在本报告收尾提交及交接回复中以实时 Git 记录核对。

`git diff --exit-code b8a5bdf --` 对 `game.lwt`、原 BFS `strategy.lwt`、`reports/s37-demo/`、`app/log_report.lwt`、`lwt/`、正式规范/矩阵/黑盒、S10 测试与原始并发、S11 性能等保护路径 exit 0。原始 S35/S36 证据没有改写。本阶段没有跑 S10/S11/S28/S29 证据生成器。尚待主窗口复审 v2 协议、失败前缀口径、Linux/Python 3.10 精确 CI、人工 GUI 与 S12 新克隆/PPT/最终交付。

全量测试仍在运行时曾读到 2 个 LWT Snake 子进程，属于测试中的实际会话；定向测试全部结束后按进程命令行只读复查为 0。修改的 7 份 Markdown 相对链接和代码围栏检查 exit 0、错误列表空；compileall exit 0；最终 `git diff --check main...HEAD` 在文档提交后再核对。
