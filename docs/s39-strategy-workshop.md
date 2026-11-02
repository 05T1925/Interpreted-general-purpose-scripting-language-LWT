# S39 LWT 策略编程工作坊执行报告

状态：**实施完成，等待主窗口审查**。日期 2026-11-02。S39 停在 `feature/lwt-strategy-workshop`；未合入、未推送，S12 未开始。课程范围以[作业原文](../大作业内容.md)为准，语言语义以[正式规范](language-spec.md)为准。

## 基线与信任边界

开工 `git status -sb` 为干净 `main...origin/main`；HEAD、本地 `main`、`origin/main`、实时 `git ls-remote origin refs/heads/main`、merge-base 均为 `a4157c42d3c6df1dbe2288384aa6ac5f3063c0b3`。S37/S38 [联合复审](s37-s38-main-review.md)已通过；实时 GitHub API 显示功能分支 SHA `d8d28754a46b8b957fd2ba7a0bf41b7b3d0725fb` 的 Actions run 41397904378 为 completed/success，Ubuntu/Windows × Python 3.10/3.13 四个 job 均 success；当前 main SHA 的 run 41398604687 也 completed/success。这是前置基线证据，**不是 S39 精确 SHA 的远端 CI**。

分层提交（完整 SHA；最终报告收尾提交在交接回复给出）：契约 `db0e4a28f36a0bba9b064fbf3204318a048383e9`；SDK/模板 `9c93420bb2156033e7ebb35558b10057d56d1e98`；catalog/v3 `5c85058f7620045446c859902b36abf78d8a7594`；独立 Agent 首次集成 `684e70fca2ac5ac408c7630eafdf9b5605f2cd8d`；空检查 ID 修正 `24c9e548f59b714849c0e0a09eab8a42842a301b`；Agent 协议修正集成 `d2acac2403c98ab6cc8ea2545d1a7ecee5d1e63e`；路径映射修正 `e8fed9f1d05578494ae67b21834e87ead5ac3476`；目录与真实 CLI 测试 `cd249338817ba667920cc4ca92cab6b4e23219ac`；九局固定证据 `b7eaa47242d8f5fe62416c168c02e1a7bc113b0e`；归属篡改回归 `d1d8d4c5fb026fe569fc0b43dcbb16b089e306e0`；人/Agent 文档 `f87fa8878576f242be18dbd1a8f5d6b623a25ad3`；无符号链接权限时的拒绝分支回归 `dafd7d0eb562454044d67a1614bb10d192a1c678`。原 Agent 在隔离分支的 SHA 与集成后的 SHA 均可查，未改写共享提交。

先独立提交[SDK/目录契约](s39-strategy-sdk-contract.md)，再提交[公开指南](strategy-sdk.md)、[模板](../app/lwt_snake/strategies/strategy-template.lwt)和空 manifest。自定义策略必须显式 `--catalog`，manifest 与源码只允许在仓库 `app/lwt_snake/strategies/` 内，单文件、无 `import`、严格 UTF-8、大小有界；LWT AST 的 `ImportDeclaration` 决定是否拒绝 import，字符串或注释中的该词不触发。路径与超时只防误用，**不隔离不可信程序**，不能运行陌生下载源码。

默认 `baseline,bfs` 不需要 catalog，继续生成 v2；显式 catalog 生成 v3，结果多出规范化 manifest SHA-256 与仓库相对路径，逐策略仍绑定源码路径/摘要，每局仍有 S35 回放与 S38 决策证据。`--verify`/`--explain` 对 v3 必须重新显式提供同一可信目录文件，绝不依结果 JSON 路径执行策略。当前目录改变、源码改变、结果重标或决策不一致均非零。v1 仍仅显式 `--game-only`，v2 固定六局仍双层验真；新 v3 的 `game_verified`/`policy_verified` 不是自述即可信，均由新 LWT 进程重算。

## 独立 Agent 与实际修正

[完整 Agent 记录](s39-agent-record.md)保留了原始派发提示、隔离工作树、首次工具限制、静态/协议烟测、两次提交及执行窗口反馈。Agent 只收到公开规范、SDK、模板与任务，不继承执行窗口对话；自动 Skill 选择/逐事件时间线不可观察，未宣称盲测全过程可见。独立原提交 `a7c115a62f6902465e75a99d4ca21992ca3cdf00` 产出 203 物理行、156 有效行的 LWT `mobility-lookahead.lwt`，使用两步出口数、直接食物与曼哈顿距离的局部启发式，不用 BFS。执行窗口首次新 CLI 检查失败：错误版本帧序号可辨认时源码回 `000000` 而非 `000001`。独立 Agent 在原工作树修正，追加原提交 `86ba3d29487afb47da05d7e4048e624b76df5c6b`，manifest 新源码摘要为 `6123507d1dec3d3079aa6d5d3072184a87816545971e63198dde702567a61404`。执行窗口分别 cherry-pick 保留两笔原改动；修正后 `--check-strategy` exit 0，三条有效固定帧输出 R/SPACE、L/SPACE、NONE/TRAPPED，错误帧为 BAD_FRAME/BAD_SEQUENCE，EOF 清洁。

目录/v3 实现首次真实 3×3 试跑曾因执行窗口把“策略路径映射”变量误用为“对局列表”，出现 `TypeError: list indices must be integers or slices, not str`，异常清理又触发 `UnboundLocalError: futures`。独立修复提交把二者分名并预置 futures；再次真实试跑与验真均 exit 0，保留该失败—修复证据。测试进一步覆盖运行中源码变化，失败局保留已完成游戏前缀，归类 CatalogError，不记为正常得分。当前 Windows 账户创建符号链接需管理员权限，故本地真实 symlink 逃逸未执行；用受控 `Path.is_symlink` 注入验证拒绝分支，Linux 的真实 symlink 测试留待本阶段 CI。

## 固定九局与无 GUI 演示

[固定 v3 结果](../reports/s39-demo/result.json)由三种 LWT 策略 × seed 4/7/11、8×5、每局上限 6 TICK、workers 2 一次生成；九份回放与九份决策文件分别存于同目录 `replays/`、`decisions/`，由 `.gitattributes -text` 保留 SHA 对应的原始字节。manifest 规范化 SHA-256 为 `b2cf48dbc807ba3033d99d62d1ae2f12fb5e54c029e491c77acecfb3acde4008`，新增策略规范化源码摘要为 `6123507d1dec3d3079aa6d5d3072184a87816545971e63198dde702567a61404`。九局均为 `limit`（非胜利）、ticks 6、双层证明 true：

| 策略 | seed 4 | seed 7 | seed 11 | median/min/max |
|---|---:|---:|---:|---|
| baseline | 10 | 0 | 0 | 0/0/10 |
| bfs | 20 | 20 | 10 | 20/10/20 |
| mobility-lookahead | 20 | 20 | 20 | 20/20/20 |

workers 1/2/4 的测试使用同三策略、三 seed 和 6 TICK，结果、回放、决策 JSON 按相对路径逐字节相同，且每次用新游戏/策略进程验真。相同 seed 只固定初始伪随机状态；走法改变后食物路径不一定相同，小样本不证明任何策略普遍更强或解释器性能优越。

```powershell
python -m app.lwt_snake.arena --check-strategy mobility-lookahead --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.arena --catalog app/lwt_snake/strategies/strategy-catalog.json --strategies baseline,bfs,mobility-lookahead --seeds 4,7,11 --max-ticks 6 --workers 2 --output 新目录
python -m app.lwt_snake.arena --verify reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.arena --explain reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json --case mobility-lookahead/4 --step 1
```

固定样例生成 exit 0；验证 exit 0、末行 `Verified 9 matches: game and policy decisions.`；解释 exit 0，实际输出为：

```text
case=mobility-lookahead/4 step=1 strategy_sha256=6123507d1dec3d3079aa6d5d3072184a87816545971e63198dde702567a61404
before_tx=2 phase=RUNNING score=0 direction=R head=(4, 2) food=(5, 2)
LWT_advice=LWA1|000001|MOVE|R|FOOD commands=TICK
after_tx=3 phase=RUNNING score=10 delta=10 head=(5, 2)
```

答辩约 2–3 分钟可按“打开模板/Agent 源码 → `--check-strategy` → 固定结果表 → `--verify` → `--explain` → 在仓库外副本篡改策略 digest 并看非零诊断”执行。若现场无法生成新目录，固定结果与命令可离线展示；尚未声称人工现场演示完成。

## 变更文件

| 文件 | 内容 |
|---|---|
| `.gitattributes` | 固定证据按原始字节保存 |
| `app/lwt_snake/arena.py` | opt-in catalog、v3 生成/验真/解释、源码变更拒绝 |
| `app/lwt_snake/catalog.py` | 可信目录、AST、静态与真实 CLI 协议检查 |
| `app/lwt_snake/strategies/strategy-template.lwt` | 可复制的 LWA1 单文件模板 |
| `app/lwt_snake/strategies/strategy-catalog.json` | 版本化自定义策略清单 |
| `app/lwt_snake/strategies/mobility-lookahead.lwt` | 独立 Agent 编写的两步局部启发式策略 |
| `tests/test_lwt_snake_workshop.py` | 六项目录、协议、对局、并发、归属及故障回归 |
| `docs/s39-strategy-sdk-contract.md`、`docs/strategy-sdk.md` | 先冻结的契约与编写指南 |
| `docs/s39-agent-record.md`、`docs/s39-strategy-workshop.md` | Agent 原始提示/修正链与本阶段报告 |
| `README.md`、`app/README.md`、`docs/developer-guide.md`、`docs/agent-dev-log.md`、`project.md`、`阶段执行与审查路线图.md` | 用户命令、开发指引与待审查状态 |
| `reports/s39-demo/result.json` | v3 九局汇总与源码/目录摘要 |
| `reports/s39-demo/replays/baseline-{4,7,11}.json`、`bfs-{4,7,11}.json`、`mobility-lookahead-{4,7,11}.json` | 九份 S35 游戏事务回放；花括号逐项展开为 9 个文件 |
| `reports/s39-demo/decisions/baseline-{4,7,11}.json`、`bfs-{4,7,11}.json`、`mobility-lookahead-{4,7,11}.json` | 九份 S38 LWA1 决策证据；花括号逐项展开为 9 个文件 |

## 验证、保护与待审查

本轮环境 Windows、Python 3.13.7、Tk 8.6.15；Linux/Python 3.10 的 **S39 精确提交**及远端 CI 未验证。定向测试对真实 CLI 做协议烟测、3×3 worker/双层验真、Unicode/空格路径、非法 manifest/AST import、源码运行前后变化、catalog 缺失/路径/摘要变更和策略归属伪造；S37/S38 原故障测试还覆盖坏帧、超时、stderr 洪流、取消、写盘失败和失败前缀。以下命令/结果在最终收尾后填实，不把中间运行或旧阶段 CI 写作本轮通过：

| 命令 | 实际退出码和结果 |
|---|---|
| `python -m unittest tests.test_lwt_snake_workshop -q` | exit 0，6/6，57.603s（增强无符号链接权限分支后） |
| `python -m unittest tests.test_lwt_snake_arena -q` | exit 0，10/10，65.734s；此前未修路径映射时定向失败 5 项，已修后复跑 |
| `python -m unittest discover -s tests -q` | exit 0，509/509，323.043s（包含增强后的符号链接拒绝分支回归）；增强前的一次全量运行亦 exit 0、509/509、268.979s |
| `python tools/run_tests.py` | exit 0，287/287，9 类全部通过，75.792s |
| `python tools/check_project_integrity.py` | exit 0，287 cases、384 matrix links、287 referenced cases |
| `python tools/run_gui_integration.py --require-no-skips` | exit 0，Tk 显示可用，23 run / 23 pass / 0 fail / 0 skip，52.006s；属于合成控件事件，不等同人工键鼠验收 |
| `python -m unittest discover -s tests -p test_app.py -q` | exit 0，25/25，8.949s |
| `python -m unittest tests.test_lwt_snake_strategy tests.test_lwt_snake_replay tests.test_lwt_snake_clock -q` | exit 0，17/17，31.870s |
| `python -m lwt --check` 对三份策略；`python -m compileall -q lwt tests tools bench app` | 四条各 exit 0；三份策略各 `Check passed: 1 source file(s).` |
| `python tools/count_lwt_lines.py <单个文件>` 分别对日志、游戏、BFS、baseline、新策略 | 五条各 exit 0；有效行数分别 246、313、141、107、156。工具只接收一个文件；先前一次错误地传五个参数得到 argparse exit 1，随后逐项重跑成功 |
| Markdown 相对链接/围栏、`git diff --check main...HEAD`、保护路径差异 | 10 个变更 Markdown、306 个相对链接，损坏 0、围栏成对；两条 Git 检查 exit 0、保护路径无差异；提交报告后重查 |

保护范围：原 `app/log_report.lwt`、`game.lwt`、原 `strategy.lwt`、baseline、S35/S37/S38 固定回放、S10/S11/S28/S29 原始证据、解释器/正式规范/黑盒与覆盖矩阵相对 S39 基线均零差异（最终 `git diff --exit-code main -- <保护路径>` exit 0）；没有运行证据重生成器。测试完成后的 Windows 进程清单中无 `app.lwt_snake` 或 `-m lwt` 子进程。最终只读远端复核中一次 `git ls-remote` 遇到 Schannel TLS 握手临时失败，保持 TLS 验证并重试后 exit 0；GitHub API 同时确认 `origin/main` 仍为基线 `a4157c42d3c6df1dbe2288384aa6ac5f3063c0b3`。主要待审：可信目录的安全边界、失败前缀与 v3 验真、Agent 证据边界、远端 CI 和人工桌面；S12 新克隆、PPT 与最终交付不在本窗口。
