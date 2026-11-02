# S41 Agent 策略差异自动发现与可复现反馈：执行报告

状态：**实施完成，等待主窗口审查**。日期 2026-11-02。执行环境 Windows / Python 3.13.7。未合并、未推送，S12 未开始。

## 基线与分层提交

开工 `git status -sb` 为干净 `main...origin/main`；HEAD、本地 main、origin/main、实时 `git ls-remote origin refs/heads/main`、merge-base 均为 `2e755914400d094694dc29bb81a863f94b1f28f5`。S40 已通过[主窗口复核](s40-main-review.md)，其精确功能分支的远端 CI 四格成功。本阶段分支 `feature/lwt-witness-discovery`。分层提交：冻结契约 `7261ea940d88692e206f108094574594bf5297e4`；搜索器/Tk 与测试 `91f1bba8f18a37bc64bbdeed4376c72802d80b50`；固定正例、无见证与篡改证据 `e40e077a9ad8954773e0a2bb28655f15b82a0881`；拒绝没有完成参考局的最小修复与回归 `2eac952e24c7beeabdb4ee0ff0c54dbd4de2016c`；最终报告 SHA 在交接回复给出。

## 搜索的含义

输入只接受显式 catalog 的 S39 v3；`arena.verify` 先把全部原局和策略决策链重新双层验真。参考策略正常完成局按 seed 数值升序，咨询步升序，挑战者 ID 字典序。预算是跨对局的参考咨询数，最多 32；两位挑战者同看一次观察只计一次。每个参考对局由新的 LWT 游戏进程重放；参考和挑战者各用独立长驻 LWT 策略进程读取**同一观察前缀**。搜索只比较方向或 MOVE/NONE，不把同方向 FOOD/SPACE 的原因差算方向分歧。策略故障、源码变化、验真错误不会被记成无见证。

命中后调用 S40 `analyze` 保存参考与命中挑战者的一步游戏分支，再调用 S40 `verify` 重验。`witness.json`、`agent-feedback.json`、`report.md` 使用固定 schema、原始结果/catalog/策略摘要及原子写；验真重新搜索并重验嵌套 S40 证据，不采信自述 `found`。整个 CLI 的外层进程树监督有 120 秒硬期限。可信目录和超时**不是陌生源码沙箱**。这一见证只是在给定清单、顺序和预算内最早，不能删去早期观察或推断整局优势。

## 固定 CLI 证据

```powershell
python -m app.lwt_snake.witness --result reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json --reference baseline --challengers bfs,mobility-lookahead --max-observations 32 --output 新目录
python -m app.lwt_snake.witness --verify reports/s41-found --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual --explain reports/s41-found/analysis --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.witness --verify reports/s41-none --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.witness --verify reports/s41-tampered --catalog app/lwt_snake/strategies/strategy-catalog.json
```

[固定正例](../reports/s41-found/witness.json)的真实生成退出 0，输出 `found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs`；BFS 响应 `LWA1|000002|MOVE|D|FOOD`，baseline 响应 `LWA1|000002|MOVE|R|SPACE`。嵌套 S40 两条一步分支由新 LWT 游戏进程验真。[预算 1 反例](../reports/s41-none/witness.json)生成退出 0，输出 `found=false scanned=1/1 case=None step=None challenger=None`，仅表示这一次观察未发现方向分歧。[故意篡改反馈](../reports/s41-tampered/agent-feedback.json)把 BFS 响应改成 R，`--verify` 原生退出码 3，诊断 `WitnessError: agent feedback evidence mismatch`。

可在 2–3 分钟答辩中展示 Agent 的 `mobility-lookahead.lwt` 源码及 `arena --check-strategy`，再展示 S39 已验对局、上述搜索、`agent-feedback.json` 的中性问题、S40 `--explain` 与一次篡改拒绝。无 Tk 时全部用上述公开 CLI；Tk 的“加载见证目录”按钮可在后台验真并显示搜索顺序、命中和一步分支，但它是 Python 教学前端，不是 LWT 策略本体。

## 修改文件与实测

| 文件 | 作用 |
|---|---|
| `docs/s41-witness-contract.md` | 编码前冻结顺序、预算、证据与退出口径 |
| `app/lwt_snake/witness.py` | 真实 LWT 搜索、严格验真、Agent 反馈与硬期限 |
| `app/lwt_snake/counterfactual_ui.py` | S40 固定演示之外，显式加载 S41 本地目录 |
| `tests/test_lwt_snake_witness.py`、`tests/test_lwt_snake_counterfactual_gui.py` | 真实 CLI、确定性、篡改、超时、真实 Tk 控件回归 |
| `reports/s41-found/`、`reports/s41-none/`、`reports/s41-tampered/` | 共 15 份固定 JSON/Markdown 证据 |
| `.gitattributes` | 证据原始字节不做 Git 换行转换 |
| `README.md`、`app/README.md`、`project.md`、`阶段执行与审查路线图.md`、本报告 | 使用命令与待审查状态 |

定向 `python -m unittest tests.test_lwt_snake_witness tests.test_lwt_snake_counterfactual_gui -q` 首轮退出 0，6/6，131.030 秒。新增“无完成参考局应报错”回归单项退出 0、1/1（0.017 秒），此前搜索会把全失败参考局误写成 `found=false`，已作独立修复提交。初次全量 unittest 退出 0、519/519、512.554 秒；新增第 520 项后最终复跑退出 0、520/520、500.967 秒。

| 本轮实际命令 | 结果 |
|---|---|
| `python tools/run_tests.py` | exit 0，287/287，9 类全部通过，53.520 秒 |
| `python tools/check_project_integrity.py` | exit 0，287 cases、384 matrix links、287 referenced cases |
| `python tools/run_gui_integration.py --require-no-skips` | exit 0，Tk 8.6.15，26 run / 26 pass / 0 fail / 0 skip，85.096 秒；真实 Tk 控件与合成事件，不是人工键鼠 |
| `python -m unittest tests.test_lwt_snake_counterfactual -q` | exit 0，S40 定向 4/4，98.978 秒 |
| `python -m unittest discover -s tests -q` | exit 0，最终 520/520，500.967 秒 |
| 三份 LWT 策略逐一 `python -m lwt --check`；`python -m compileall -q lwt tests tools bench app` | 四条各 exit 0 |
| 6 份变更 Markdown 相对链接与围栏 | 240 条相对链接，坏链 0，围栏成对，exit 0 |
| 保护路径 `git diff --exit-code main -- <路径>`、进程清单 | exit 0，解释器、规范、287 黑盒、S35–S40 固定证据及 S10/S11/S28/S29 原始数据均无差异；无残留 `app.lwt_snake`/`-m lwt` 子进程 |
| `git diff --check` | exit 0；提交后再查 `main...HEAD` |

## 证据边界

执行窗口的自动真实 CLI、合成 Tk 控件事件、无见证预算及篡改拒绝与主窗口审查、远端 CI、人工物理键鼠是不同证据层。S41 精确提交尚未推送，远端 Actions 未验证。Linux/Python 3.10、本地物理键鼠/视觉和 S12 新克隆/PPT 均未在本窗口执行。固定种子分歧不证明策略优劣。
