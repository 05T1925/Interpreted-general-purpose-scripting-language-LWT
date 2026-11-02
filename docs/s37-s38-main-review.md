# S37/S38 主窗口联合复审

日期：2026-11-02。审查对象 `feature/lwt-strategy-arena`；执行窗口 S38 tip `51317e513d68a098da2370075d9aad9102bf27df`，基线 `main` 为 `65994968732f017e84821bf82a4baf1184637b93`。S12 未开始。

## 结论

S37 的两项审查缺口已有针对性修复：v2 用全新 LWT 游戏进程重放事务，再用全新 LWT 策略进程按查询前快照逐步重算建议；v1 固定证据仅可显式按 game-only 验证；空 inventory 被拒绝。主窗口审阅 `arena.py` 的查询/事务映射、终局边界、分级证明和严格输入，并独立复跑定向测试，未发现新的阻断问题。**S37/S38 联合审查通过，待精确 SHA 远端 CI 与主分支集成结果独立登记。**人工桌面操作不在本次自动验真结论内。

## 本窗口独立证据

- Git：工作区干净，`feature/lwt-strategy-arena` 相对基线只增 S37/S38 文件；原游戏、BFS 策略、S35 固定回放、日志应用、LWT 解释器/规范及历史原始证据未改。实时远端 `main` 为基线，S38 工作尚未推送。
- `python -m unittest tests.test_lwt_snake_arena -q`：10/10 通过，约 84 秒；包含错标策略与空 inventory 回归。执行窗口报告全量 unittest 503/503、语言黑盒 287/287、严格 GUI 23/23，本窗口未重跑这三项，须由精确 SHA CI 核验自动门禁。
- `python -m app.lwt_snake.arena --verify reports/s38-demo/result.json`：六局 `game_verified=true, policy_verified=true`，退出 0；`--game-only --verify reports/s37-demo/result.json`：六局仅 game true，明确显示策略决策未验证；`--explain reports/s38-demo/result.json --case bfs/4 --step 3`：显示查询前快照、LWT `MOVE|L|FOOD`、TURN/TICK 后分数增 10；均退出 0。
- `python tools/check_project_integrity.py`：287 cases、384 matrix links、287 referenced；`git diff --check main...HEAD` 通过。

## 证明边界与后续

v2 证明当前仓库中白名单、无导入的 LWT 策略源码对固定输入序列能确定性复现记录的建议；普通 SHA-256 不等于历史执行者的签名或受信任来源认证。失败局只声明完整前缀达到的证明层级。S37 v1 样例原样保留，不能称为双层证明。S39 最后功能增量见[策略编程工作坊派发提示](s39-strategy-workshop-handoff.md)；S39 审查后应进入 S12 新克隆、人工演示、PPT 和最终交付。
