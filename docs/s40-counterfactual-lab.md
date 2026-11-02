# S40 可验证的 LWT 策略反事实实验台：执行报告

状态：**实施完成，等待主窗口审查**。2026-11-02，Windows / Python 3.13.7。本阶段未合入、未推送，S12 未开始。

## 基线与提交

开工工作区干净 `main...origin/main`；HEAD、本地 `main`、`origin/main`、实时 `git ls-remote origin refs/heads/main`、merge-base 均为 `fb841f8654a816b644839ccee6728c97154f97fc`。分支 `feature/lwt-counterfactual-lab`。提交依次为：冻结契约 `fe6444407e759a7aaa482ffe4d4ff079840b660c`；CLI/固定证据 `665dd370ab480569afbe67b0569600fb3a041cb0`；Tk/控件测试 `6a6322f1dfabc45e093c1a72fa6bd8eed573e741`；硬期限与源码稳定性修正 `1db7618f3e6d3398b03ea200d3927fe477ff255b`。最终报告提交 SHA 在交接回复给出。

## 课程关系与含义

课程第 5 项要求 Agent 编写完整 LWT 应用及开发记录。原游戏规则 `game.lwt`（313 有效行）与三份 LWT 策略已构成该应用展示；S40 用真正的 LWT 游戏与策略进程解释“同一观察轨迹上，不同策略这一步会如何建议，以及单步替代会发生什么”。Python 仅校验、重放、保存证据及 Tk 展示，不计算方向、碰撞、食物或分数。[冻结契约](s40-counterfactual-contract.md)明确这不是整局因果实验、策略优越性证明或不可信代码沙箱。

`arena.verify` 先对完整 S39 v3 结果进行游戏/策略双层验真。选中完成局后，S35 `reconstruct` 在新游戏进程中恢复真实咨询前状态；每份候选 LWT 策略独占新长驻进程，按原局顺序接收第 1..N 次观察。候选 MOVE 使用另一新游戏进程执行必要 TURN 和一次 TICK，分支回放再由新进程复核。分析文件没有可信的 `verified` 标志；`--verify` 对原结果、目录、策略响应及回放全部重算。

## 真实固定演示

先扫描 S39 `baseline/4` 已验观察轨迹，第 2 次咨询的真实响应首次出现方向分歧：原局事务 3 后，baseline 为 `R/SPACE`，BFS 为 `D/FOOD`，Agent 新策略为 `D/SPACE`。这是同一局面上的咨询，不是三局自然对局之间的比较。[固定分歧证据](../reports/s40-divergence/analysis.json)对应三条一 TICK 分支；[第 1 步证据](../reports/s40-demo/analysis.json)展示同方向不同原因；[篡改证据](../reports/s40-tampered/analysis.json)将 BFS 响应改为 R，按实际命令非零拒绝。

```powershell
python -m app.lwt_snake.counterfactual --analyze reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json --case baseline/4 --step 2 --strategies baseline,bfs,mobility-lookahead --output 新目录
python -m app.lwt_snake.counterfactual --verify reports/s40-divergence --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual --explain reports/s40-divergence --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.counterfactual --verify reports/s40-tampered --catalog app/lwt_snake/strategies/strategy-catalog.json
```

实际 `--explain` exit 0：

```text
case=baseline/4 step=2 before_tx=3
same verified observation trace; one-step branch only
baseline: LWA1|000002|MOVE|R|SPACE score=10->10 phase=RUNNING replay=branches/baseline.json
bfs: LWA1|000002|MOVE|D|FOOD score=10->10 phase=RUNNING replay=branches/bfs.json
mobility-lookahead: LWA1|000002|MOVE|D|SPACE score=10->10 phase=RUNNING replay=branches/mobility-lookahead.json
```

三个分支这一步得分都保持 10；`FOOD` 是策略建议理由，不是这一步已经吃到食物。篡改样例 exit 3，诊断 `bfs: response evidence mismatch`。`--analyze` 真实生成 exit 0，自动验真成功；第 1 步与第 2 步各保留独立目录，不覆盖 S39 证据。同输入生成两次的分析与三份分支回放字节一致，由定向测试逐文件比对。

## 变更文件与验证

| 文件 | 作用 |
|---|---|
| `docs/s40-counterfactual-contract.md` | 编码前冻结语义、CLI、证据格式、边界 |
| `app/lwt_snake/counterfactual.py` | 真实 LWT 进程咨询、单步分支、严格加载与重验 CLI |
| `app/lwt_snake/counterfactual_ui.py` | Python/Tk 只读、可步进固定演示；后台 CLI 验真 |
| `tests/test_lwt_snake_counterfactual.py`、`tests/test_lwt_snake_counterfactual_gui.py` | 真实子进程、字节确定性、篡改与 Tk 控件/过期结果回归 |
| `reports/s40-demo/`、`reports/s40-divergence/`、`reports/s40-tampered/` 各 4 个 JSON | 两套真实分支与故意损坏样例 |
| `.gitattributes` | 固定 JSON 原始字节不做 Git 换行转换 |
| `README.md`、`app/README.md`、`project.md`、`阶段执行与审查路线图.md`、本报告 | 使用入口与状态 |

定向 CLI 首轮两项测试 exit 0、2/2（92.797 秒）；增加总期限监督进程后的真实超时回收单项测试 exit 0、1/1（0.764 秒）。真实 Tk 控件两项首次因测试清理在窗口销毁后调用 `winfo_exists` 报错，修正测试清理后 exit 0、2/2（16.484 秒）。

| 实际命令 | 退出码与关键结果 |
|---|---|
| `python -m unittest discover -s tests -q` | 0；最终 514/514，371.261 秒；硬期限前一次 513/513，412.691 秒 |
| `python tools/run_tests.py` | 0；287/287，9 类全部通过，57.881 秒 |
| `python tools/check_project_integrity.py` | 0；287 cases、384 matrix links、287 referenced cases |
| `python tools/run_gui_integration.py --require-no-skips` | 0；最终 Tk 8.6.15，25 run / 25 pass / 0 fail / 0 skip，52.049 秒；硬期限前亦 25/25。合成控件事件，不是人工键鼠 |
| 三份策略逐一 `python -m lwt --check` | 三条各 0，均输出 `Check passed: 1 source file(s).` |
| `python -m compileall -q lwt tests tools bench app` | 0 |
| `python -m app.lwt_snake.counterfactual --verify reports/s40-divergence --catalog app/lwt_snake/strategies/strategy-catalog.json` | 0；`Verified baseline/4 step 2: original game/policy and 3 one-step branches.` |
| `python -m app.lwt_snake.counterfactual --verify reports/s40-tampered --catalog app/lwt_snake/strategies/strategy-catalog.json` | 3；`bfs: response evidence mismatch` |
| 保护路径 `git diff --exit-code main -- <路径>`；进程清单 | 0、无差异；无残留游戏/策略 Python 子进程 |
| 变更 Markdown 相对链接/围栏 | 6 个文件、230 个相对链接，损坏 0、围栏成对 |

变更的 6 份 Markdown 共核对 230 条相对链接，损坏 0、代码围栏成对；未提交差异的 `git diff --check` exit 0，提交后再查 `main...HEAD`。CLI 外层监督进程对完整分析/验真设 120 秒硬期限；超时通过进程树清理，真实 0.01 秒超时注入已回归通过。Tk 关闭也会取消其 CLI 子进程树；真实物理关闭过程与 Linux/Python 3.10 环境仍未实测，应由主窗口和 S12 现场复核。

## 证据层级与交接

自动 CLI、Tk 合成控件事件、固定分支重算属于本窗口实际验证；人工物理键鼠、视觉可读性、Linux/Python 3.10 与 S40 精确提交远端 Actions 均未验证。Tk 成功创建或控件事件通过不等于人工桌面体验。S12 新克隆、PPT、最终交付仍未开始。
