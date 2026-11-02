# S37 主窗口复核：策略归属尚未得到验证

日期：2026-11-02。对象：`feature/lwt-strategy-arena`，执行窗口最终提交 `3ed956d977f504a8854dac9feb34231fa862dad8`；基线为 `main` 的 `65994968732f017e84821bf82a4baf1184637b93`。本记录区分游戏命令回放与策略决策来源。S37 **暂不通过、不合入或推送**；S12 未开始。

## 独立核查

- Git 工作区干净；功能分支相对基线新增 baseline LWT、擂台和测试。实时远端 `main` 仍在基线，未见远端功能分支。原游戏、BFS 策略、S35 固定回放、语言实现、旧应用和历史原始数据在本阶段无差异。
- 本窗口 `python -m unittest tests.test_lwt_snake_arena -q`：4 项通过；`python -m app.lwt_snake.arena --verify reports/s37-demo/result.json`：6 局游戏事务重放通过；`python tools/check_project_integrity.py`：287 cases、384 links、287 referenced；`git diff --check main...HEAD` 通过。执行窗口报告的 497 项全量和 287 项语言黑盒尚未由本窗口重跑，也没有 S37 精确 SHA 的远端 CI。
- 源码 `app/lwt_snake/arena.py` 的 `verify()` 对每局调用 `reconstruct(record)` 核对游戏事务，仅当 `stop_reason == 'trapped'` 时再调用一次 LWT 策略。对普通 `limit`、`won`、`game_over` 局，未复算每一步策略建议。因此源码 digest 绑定了文件字节，却没有证明回放命令是该策略产生的。

## 可复现反例

在仓库外临时目录运行 `python -m app.lwt_snake.arena --strategies baseline --seeds 4 --max-ticks 12 --output <临时目录>`，原结果分数为 10。将结果中的策略 ID、策略源码摘要及白名单路径改为 `bfs`，把回放文件名从 `baseline-4.json` 改为 `bfs-4.json`，按现有 `summary()` 重算摘要，**保持真实游戏回放内容不变**。运行 `python -m app.lwt_snake.arena --verify <临时目录>/result.json`：退出码 0，显示 `bfs 4 10 12 limit true` 与 `Verified 1 matches.`。同阶段固定样例里真正的 `bfs/4` 分数是 40。该反例说明“游戏回放可重现”与“标注策略产生了这局决策”是两种不同命题。

另造合法外形但策略、种子、对局列表均为空的 schema v1 结果，`--verify` 退出码 0 并显示 `Verified 0 matches.`。这是验证输入完整性缺口。

上述反例只在自动生成的临时目录操作；未改仓库固定样例。现有六局仍可由游戏引擎复算，且没有证据表明原始结果造假。需修正的是验证能力和措辞，而非否定已实现的 LWT 基线策略或游戏回放。

## 审查决定

将 S37 保留在现有功能分支，先按 [S38 派发提示](s38-policy-verification-handoff.md)补策略决策链核验、严格 inventory 和可解释的逐步证据。完成后复审 S37/S38 的合并成果，再决定远端推送和 CI。旧 S37 固定结果作为历史 game-only 证据保留；新结果不得静默改写旧文件或声称密码学来源认证。人工 GUI 操作仍交 S12。
