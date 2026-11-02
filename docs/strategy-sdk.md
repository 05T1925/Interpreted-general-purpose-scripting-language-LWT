# LWT Snake 策略 SDK：可信本地编程工作坊

本指南面向人类和编程 Agent。先读 [正式语言规范](language-spec.md)、[开发指南](developer-guide.md)、[LWA1 协议](snake-strategy-protocol.md)及 [S39 目录契约](s39-strategy-sdk-contract.md)。`game.lwt` 计算蛇的状态；策略是另一个长期运行的 LWT 程序，每行输入一个查询、每行输出一个建议。Python 只校验、传输和展示。**只运行自己信任的本地策略**；有限超时、路径约束和静态检查不是安全沙箱。

## 写一份策略

1. 复制 `app/lwt_snake/strategies/strategy-template.lwt` 到同目录新 `.lwt` 文件。不要写 `import`，本版只支持单文件。实现严格 LWA1 输入校验、连续请求序号和 EOF 退出，然后实现自己的合法方向判断与选择逻辑。模板的 `NONE` 占位输出不是可玩的策略。
2. 输入帧为 `LWA1|000001|WIDTH|HEIGHT|DIR|FOOD_X|FOOD_Y|BODY_LEN|X,Y;...`，LF 结尾。DIR 与 BODY 按 [LWA1](snake-strategy-protocol.md)定义；本步不增长时尾格可离开，吃食物时尾格保留。合法响应只有 `LWA1|000001|MOVE|U/R/D/L|FOOD/SPACE` 或 `LWA1|000001|NONE|-|TRAPPED`；畸形帧的错误响应遵守协议。不要打印调试文字到 stdout。
3. 用 `python -m lwt --check app/lwt_snake/strategies/你的文件.lwt` 检查语法。`--check-strategy` 还会在真实 LWT 进程中发送固定烟测帧。检查通过不代表所有盘面都正确。
4. 使用 `python -c "from pathlib import Path; from app.lwt_snake.replay import source_digest; print(source_digest(Path('app/lwt_snake/strategies/你的文件.lwt').read_bytes()))"` 计算规范化源码摘要；在 `app/lwt_snake/strategies/strategy-catalog.json` 的 `strategies` 列表添加严格项：`{"id":"你的id","path":"你的文件.lwt","sha256":"64位小写hex","protocol":"LWA1"}`。ID 不能与 `baseline`/`bfs` 冲突。文件名可含空格/Unicode，路径只用策略目录内的单个文件名。
5. 从仓库根目录按顺序运行：

```powershell
python -m app.lwt_snake.arena --check-strategy 你的id --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.arena --catalog app/lwt_snake/strategies/strategy-catalog.json --strategies baseline,bfs,你的id --seeds 4,7,11 --max-ticks 12 --workers 1 --output 新目录
python -m app.lwt_snake.arena --verify 新目录/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json
python -m app.lwt_snake.arena --explain 新目录/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json --case 你的id/4 --step 1
```

输出目录必须不存在；不要覆盖固定原始结果。验真时仍需显式给出同一可信 catalog。`--explain` 会先完整验真，再显示一步查询前快照、策略回答和真实游戏结果。旧 S37 v1 只有显式 `--game-only` 游戏证明，S38 v2 内置策略可不带 catalog 验真。

## 固定烟测与诊断

检查命令使用公开 `python -m lwt --check`，再启动一次 `python -u -m lwt` 长驻进程。固定帧包括空地、食物、墙/身体、尾格及错误版本/序号；检查字段数、方向、直接逆向、响应序号、EOF 和 stderr。协议错误会报告第几帧。该过程只覆盖少量盘面，不替代三种 seed 对局与新进程重放。完整契约和信任边界见 [S39 冻结文档](s39-strategy-sdk-contract.md)。
