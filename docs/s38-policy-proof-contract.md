# S38 策略决策证据契约 v2

本文件在编码前冻结。承接 [S37 擂台契约](s37-arena-contract.md)、[S35 游戏回放](snake-replay-format.md)和 [S36 LWA1](snake-strategy-protocol.md)。只接受现有两份无 import 的独立 LWT 策略 `baseline`、`bfs`；当前 digest 是规范化源字节 SHA-256，不代表对将来模块依赖的闭包承诺，更不是签名或历史执行主体认证。

## 版本与证明层级

- v2 顶层延续 v1 配置及 summary，`schema_version=2`。每局以 `game_verified`、`policy_verified` 两个布尔字段代替含混的 `verified`；增加 `decision_path` 和 `decision_sha256`。正常停止 (`won/game_over/trapped/limit`) 必须两者均为 true；失败局只陈述已完成前缀实际通过的层级，错误类别及消息必填。失败局没有完整前缀时两者 false，路径与摘要可为 null。
- `game_verified` 仅指全新 `game.lwt` 进程逐笔重放 S35 事务、分数与阶段一致。`policy_verified` 仅指全新长驻白名单 LWT 策略进程从逐笔重放得到的查询前快照重新响应、并与随后 TURN/TICK 链一致。运行时标志只是已执行检查的记录；`--verify` 必须重新执行，不能信任自述。
- v1 原样保留。普通 `--verify` 对 v1 非零退出 3，提示仅能验游戏且须显式 `--game-only`；`--game-only --verify` 可逐笔验游戏，输出 `game replay only; strategy decisions unverified`，成功退出 0。v1 也须通过严格 inventory；重标策略的 v1 文件只可证明游戏，不可声称策略归属。`--explain` 仅接受 v2 完整双层验真局。

## 决策文件

每局 `decisions/<ID>-<seed>.json`，UTF-8 JSON，固定键：`schema_version=1, protocol_version=LWA1, strategy_id, strategy_sha256, game_sha256, replay_sha256, decisions`。每条决策固定键 `sequence, game_transaction, request, response`，均按时间顺序。`game_transaction` 是咨询前已完成的 S35 事务数；首个为 2 (`INIT,START`)。`request`/`response` 是精确 ASCII 帧，不含 LF，LWA1 请求由 `encode_snapshot` 规范生成；策略响应由同一长驻进程取得并严格解析。序号从 1 连续；每局最多 101 条咨询、每帧不超过现有 LWA1 4096/128 字节。决策文件最大 1 MiB；结果最大 1 MiB，回放遵守 S35 16 MiB 上限。JSON 拒绝重复键、非有限数、过长整数、额外或缺失键。文件先写临时文件并原子替换；结果只引用固定相对路径，禁止 symlink/目录越界。输出必须是全新目录。

从 `INIT → START` 后 RUNNING 快照开始：每个 TICK 前必须恰好有一次咨询。若 MOVE 方向不同，紧跟成功的同方向 TURN 再 TICK；方向相同则直接 TICK。查询输入始终是 TURN **之前**的快照。TICK 到终局后无更多咨询。`limit` 的咨询数等于 TICK 数且末态 RUNNING；`trapped` 在末态 RUNNING 有额外一条 `NONE|-|TRAPPED`，其后无游戏事务。禁止额外 PAUSE、RESET、手动 TURN、错序、缺失或重复决策。核对精确方向与 FOOD/SPACE/TRAPPED 原因、响应序号及游戏事务索引。

失败局允许已完成咨询但 TICK 尚未成功，或已完成 TURN 后 TICK 失败；仅验证可确定的前缀。尚未收到完整响应的咨询不写入决策；故障本身不要求重现，也不能被解释为正常终局。失败前缀若出现拒绝的游戏事务或其他不符合上述前缀形状的命令，可达到 `game_verified=true, policy_verified=false`，不得强行宣称完整策略链。无证据时两个标志为 false。已完成的咨询必须从新策略进程复算，末尾可有至多一条未跟 TICK 的咨询；若已 TURN，则其方向必须与该咨询一致。

## 输入与退出

清单 ID 非空、唯一、排序且在白名单；种子非空、唯一、升序、1..2147483646；二者笛卡尔积必须完整、排序且至多 16 局。棋盘宽 4..24、高 1..18、面积 ≤432；TICK 1..100。整数必须真 `int`，不接受 bool、负数或超界。每局路径固定，摘要为 64 个小写 hex；空集合、额外键、重复 ID、重复 JSON key、NaN/Infinity、超大文件或路径越界均非零诊断。普通运行全部正常退出 0、含失败局退出 1、参数或写入错误退出 2、验真/解释错误退出 3、取消退出 130。请求 5 秒、整局 60 秒，策略与游戏进程都须在关闭或异常时回收；workers 仅 1/2/4，结果按 ID/seed 排序。

`--explain RESULT --case ID/seed --step N` 先完成 v2 双层验真，再显示该次查询前真实快照、LWT 响应、TURN/无 TURN、TICK 后快照与得分差及事务编号。不重新计算规则。若该步为 trapped、没有 TICK，明确显示无 TICK。旧 v1 与失败局拒绝作为已确认决策展示。
