# S37 擂台契约 v1（编码前冻结）

只接受固定 ID `baseline`（`app/lwt_snake/strategy_baseline.lwt`）和 `bfs`（`app/lwt_snake/strategy.lwt`）。源码摘要沿用 S35 `lwt-utf8-lf-sha256-v1`：严格 UTF-8、去首个 BOM、CRLF/CR 归一 LF、SHA-256。白名单在程序内固定路径；结果记录各源码摘要及 LWA1。用户参数不作为命令或源码路径。游戏固定为 `game.lwt`，所有状态和真实事务来自原 bridge/recorder。

运行 CLI：`python -m app.lwt_snake.arena --strategies baseline,bfs --seeds 4,7,11 --width 8 --height 5 --max-ticks 40 --workers 1 --output NEW_DIR`。默认值如示例。宽 4–24、高 1–18、面积至多 432；seed 各为 1–2147483646，1–8 个且不重复；max-ticks 1–100；workers 仅 1、2、4 且至多局数；每次游戏和策略请求最多 5 秒、整局最多 60 秒。策略 ID 不重复；局数至多 16。参数错误 exit 2，创建输出前拒绝。输出必须是尚不存在的新目录；已有目录（包括空目录）均拒绝，防止覆盖用户数据。运行配置受限，最多每局 202 笔游戏事务，低于 S35 上限。

每个 `(策略,seed)` 独立拥有游戏与策略两个长驻公开 LWT CLI 子进程、recorder 和单独回放文件。流程 INIT、START，然后串行查询 LWA1、可选 TURN、TICK，直到 WON/GAME_OVER、NONE、max-ticks 或故障。NONE 记 `trapped`，达到上限记 `limit`，真正终局分别记 `won`/`game_over`；策略/游戏/文件/总时限错误记 `failed` 且附类别与有界消息，不能作为正常零分。取消停止启动新局，当前进程回收；未启动局不伪造结果。每局尝试保存已完整录制前缀。两个子进程退出和回收后才用新游戏进程 `reconstruct` 验证前缀。

输出目录含 `result.json` 与 `replays/<strategy>-<seed>.json`；相对路径固定、无用户路径插入。结果 JSON UTF-8、schema_version=1，顶层字段固定 `schema_version,protocol_version,board,seeds,max_ticks,strategies,cases,summary`；case 固定 `strategy_id,strategy_sha256,game_sha256,seed,ticks,phase,stop_reason,score,replay_path,replay_sha256,verified,error_category,error_message`。`phase/score` 仅来自最后已确认的游戏快照；如尚无快照则 null。失败前缀的 replay 可验证时 `verified=true`，即使业务失败也不能改记成功。回放文件哈希是文件原始字节 SHA-256；`--verify result.json` 必须重新计算所有源码/文件摘要、逐笔执行真实游戏、检查末快照/score/ticks/INIT设置与元数据。只读 verify 不信任文件内 verified 声明。损坏、缺失、元数据分歧 exit 3，定位策略/seed、字段或事务；使用固定路径解析并拒绝相对路径越界。正常运行全部局写入成功后 exit 0；有失败局但摘要成功写入 exit 1；CLI/输出目录错误 exit 2；验证错误 exit 3。JSON 原子替换，单局文件先写到专用新目录；写入失败 exit 2 并保留已成功写入的局文件与可得前缀。

并发只用最多四个 Python worker，各自独占两个 LWT 子进程。按 `baseline,bfs` 与升序 seed 的固定键输出，不以完成顺序输出；结果不写 PID/耗时，workers=1/2/4 的 JSON 逻辑结果应字节一致。错误消息裁剪为 512 字符、排除临时绝对路径。只对 `won,game_over,trapped,limit` 的已验证局分数计算 median/min/max，另列每种停止类别和失败数，不生成误导性的胜率。相同 seed 只固定初始 PRNG；两种策略后续食物序列可能不同。实验无法证明算法优越性或解释器性能。可选端到端时间只在控制台展示，不进入逻辑结果或 S11。
