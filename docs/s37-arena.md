# S37 策略擂台执行报告

状态：**实施完成，等待主窗口审查**。日期 2026-11-02。S12 未开始，S37 未合并或推送。

## 基线与设计

开工 `git status -sb` 干净，本地/跟踪/实时远端 main、HEAD 与 merge-base 均为 `65994968732f017e84821bf82a4baf1184637b93`。最近提交含 S36 主窗口复核 `3bf7eff`，审查文档记载该精确功能分支 SHA 的远端 Actions 四格完成成功。由此建立 `feature/lwt-strategy-arena`。没有把 S36 CI 算作本阶段 CI。

先单独冻结[擂台契约](s37-arena-contract.md)：ID 仅 baseline/bfs、源码归一化摘要、8×5/三 seed 默认、1–100 TICK、1/2/4 workers、单请求 5s/整局 60s、新目录、固定 JSON schema/退出码与停止类别。`baseline` 在 LWT 中检验逆向、墙、身体与尾格，优先保持 DIR，否则 U/R/D/L 首个合法步；BFS 延用 S36。每局两个独立 LWT 进程、独立 recorder；Python 只管理协议/进程/排序/统计。相同 seed 固定初始 PRNG，不保证后续食物序列相同，结果不证明算法优越性。

六局固定样例在[结果 JSON](../reports/s37-demo/result.json)，回放在同目录 `replays/`；`-text` 属性保护提交到 Git 的原始字节摘要。原 `.gitattributes` 四条特殊 fixture 属性全部保留。没有第二套坐标真值；`--verify` 不信任结果文件的 `verified` 字段，核对策略与游戏源码摘要、回放原始字节摘要、设置、TICK 数、最终快照/分数，并在新游戏进程中逐笔比较。篡改回放响应后即便同时更新文件 SHA，仍在事务字段处失败。失败局的完整前缀可保存并验证，失败类别另计。

## 固定六局实测

命令（仓库根目录）：

```powershell
python -m app.lwt_snake.arena --seeds 4,7,11 --max-ticks 12 --workers 2 --output reports/s37-demo
python -m app.lwt_snake.arena --verify reports/s37-demo/result.json
```

两条均 exit 0；后者输出以下逐局结果并以 `Verified 6 matches.` 结束，stderr 空。各局 stop_reason 均为 `limit`，phase=RUNNING、ticks=12、verified=true；`limit` 不是游戏终局或胜利。

| 策略 | seed 4 | seed 7 | seed 11 | 完成局分数 median/min/max |
|---|---:|---:|---:|---|
| baseline | 10 | 0 | 0 | 0 / 0 / 10 |
| bfs | 40 | 30 | 20 | 30 / 20 / 40 |

另在测试的独立临时目录用 workers=1、2、4 各运行同配置并 `--verify` 六局；结果 JSON **字节相同**，无 PID 或时间字段，文件名不碰撞。局数小且 TICK 上限 12，适合作为离线演示，不外推到大棋盘或其他机器。运行耗时的精确观测以本轮测试命令为准，不属于 S11 性能比较。

## 失败与复核边界

`tests/test_lwt_snake_arena.py` 的真实 CLI 测试覆盖 baseline 正常/错误 LWA1、尾格、墙、身体、待执行 DIR、无合法方向与 EOF；真实并发六局、多进程回放；对 score、seed、策略摘要、游戏摘要、缺失回放和单笔响应的篡改均非零，指出局与字段或事务。首次 seed 篡改测试失败，因为旧诊断只报身份不符；细化为 `bfs/4: seed mismatch` 后复跑通过。受控策略坏帧、超时、stderr 洪流和非零退出均保留 INIT/START 两笔完整前缀并由新游戏进程验证，归类 failed 而非零分正常完成；游戏 INIT 阶段坏帧单独归 failed、无伪回放；预取消无伪回放；写盘错误抛出并由 CLI 归为输出错误。旧 S35/S36 回归、GUI 和黑盒结果在下面逐项列出。

所有自动 GUI 证据仅是原 23 项真实 Tk 控件/合成事件，无新增擂台 GUI；本阶段以 CLI 表格和可读 JSON 回放为离线展示。人工物理键鼠、视觉和输入法仍未验证。默认拒绝任何已存在输出目录，验证仅沿固定相对回放路径；无网络、账号或第三方依赖。

## 实际命令与结果

| 命令 | 本轮实际结果 |
|---|---|
| Git 开工检查：`git status -sb`、`git rev-parse HEAD main origin/main`、`git merge-base main HEAD`、`git log -6 --oneline --decorate`、`git ls-remote origin refs/heads/main` | exit 0，均核实基线 `6599496`、干净 main |
| `python -m unittest tests.test_lwt_snake_strategy -q` | S36 基线定向 8 项通过 |
| `python -m lwt --check app/lwt_snake/strategy_baseline.lwt`；同命令检查 `strategy.lwt` | 两者各 exit 0，1 source passed |
| 新 baseline 真实 CLI 运行 S36 的三条演示帧 | exit 0，SPACE、SPACE、TRAPPED，stderr 空 |
| `python -m unittest tests.test_lwt_snake_arena -v` | 初次 4 项中 seed 诊断断言失败；修复后 `-q` 4/4，exit 0，23.099s；随后扩充游戏坏帧故障注入并定向重跑 |
| `python tools/run_gui_integration.py --require-no-skips` | exit 0，Tk 8.6.15，discovered/run/pass=23/23/23，fail=0，skip=0，36.685s |
| `python -m app.lwt_snake.arena --verify reports/s37-demo/result.json` | exit 0，六局逐笔验证，`Verified 6 matches.` |
| `python -m unittest discover -s tests -q` | exit 0，497/497，175.421s；S36 基线 493 项，本阶段增 4 项 |
| `python -m unittest discover -s tests -p test_app.py -q` | exit 0，S10 原 25/25，6.510s |
| `python tools/check_project_integrity.py` | exit 0，287 cases、384 matrix_links、287 referenced_cases |
| `python -m compileall -q lwt tests tools bench app` | exit 0 |
| `python tools/count_lwt_lines.py` 分别对 `app/log_report.lwt`、`app/lwt_snake/game.lwt`、`strategy.lwt`、`strategy_baseline.lwt` | 各 exit 0；有效行分别 246、313、141、107 |
| `python -m app.lwt_snake.replay --verify` 对 S35 `demo-parent.json`、`demo-child.json` | 各 exit 0；分别 `Verified 10 transactions.`、`Verified 12 transactions.` |
| `python -m unittest tests.test_lwt_snake_strategy -q`；`python -m unittest tests.test_lwt_snake_replay tests.test_lwt_snake_clock -q` | 各 exit 0；8/8（10.770s）、9/9（10.339s） |
| `python tools/run_tests.py` | exit 0，287/287、failed 0、43.157s；九类 32/43/13/43/40/3/52/30/31 全通过 |
| 修改过的 7 份 Markdown 相对链接/代码围栏 Python 检查 | exit 0，错误列表为空 |

最终 `git diff --exit-code main --` 对保护路径 exit 0；修改过的 Markdown 相对链接/代码围栏检查、`git diff --check main...HEAD` 与工作区状态在收尾提交后复查。未运行的命令不能当作通过。

## 文件与交接

新增 `docs/s37-arena-contract.md`、`app/lwt_snake/strategy_baseline.lwt`、`app/lwt_snake/arena.py`、`tests/test_lwt_snake_arena.py`、`reports/s37-demo/result.json` 与六个 replay 文件、本报告；更新 `.gitattributes`（只增 S37 样例字节保护）、`README.md`、`app/README.md`、`project.md`、`阶段执行与审查路线图.md`、`docs/agent-dev-log.md`。完整分层 SHA 和最终工作区状态以 `git log --format="%H %s" main..HEAD` 与 `git status -sb` 实时核对，交接回复列出全部。保护检查应覆盖游戏、S36 BFS、S35 固定回放、日志应用、语言实现/规范/黑盒与 S10/S11/S28/S29/S34/S36 原始数据，不能把远端旧审查结果误认作 S37 精确 SHA 的 CI。

一次添加测试文件时误把目录字写成仓库旁的 `大作ҵ`。测试文件已移到正确仓库；只读检查确认旁边仅剩空 `tests` 文件夹。清理该空目录的 `Remove-Item` 命令被自动审批策略以 `blocked by policy` 拒绝，因此未继续删除或绕过限制。这不影响 Git 工作区或测试，需由用户按本机意愿清理。
