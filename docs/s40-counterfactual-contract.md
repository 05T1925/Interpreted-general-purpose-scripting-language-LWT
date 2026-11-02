# S40 反事实实验契约 v1

本文件先于实现冻结。输入仅为通过 `arena.verify(result, catalog_path=显式路径)` 双层验真的 S39 v3 完成局。选择一基 LWA1 咨询序号，不接受失败局。可信 catalog 必须由用户显式指定；结果文件中的路径不授权执行源码。

## 意义

每个候选 LWT 策略由全新长驻进程依次接收原局第 1..N 次**同一已验证观察**，只取第 N 次建议。此结果不是候选策略自然对局第 N 步。候选建议为 MOVE 时，使用 S35 `reconstruct(..., prefix=咨询前事务数, keep=True)` 创建新游戏进程，从该状态执行必要 TURN 和恰好一次 TICK；NONE/TRAPPED 不推进。分支回放由游戏桥接器录制，再用另一个新游戏进程重放确认。分数、食物、碰撞和方向建议均不由 Python 计算。

## CLI 与文件

- `python -m app.lwt_snake.counterfactual --analyze RESULT --catalog FILE --case ID/SEED --step N --strategies ID[,ID] --output NEW_DIR`
- `python -m app.lwt_snake.counterfactual --verify DIR --catalog FILE`
- `python -m app.lwt_snake.counterfactual --explain DIR --catalog FILE`

ID 必须属于已验证 v3 策略清单；候选最多 3、不可重复；step 为真整数且 1..100。输出目录必须不存在。正常退出 0，参数/创建错误 2，验真/证据错误 3，取消 130。请求使用既有桥接超时；整次操作限 120 秒。输入结果遵守 arena 的 1 MiB 上限，分析 JSON 上限 1 MiB，分支回放遵守 S35 的 16 MiB 上限。

`analysis.json` 为 UTF-8 JSON，schema_version=1，固定顶层字段：`schema_version, result_path, result_sha256, catalog_path, catalog_sha256, case, step, game_transaction, candidates`。原结果/目录路径是仓库相对路径，只作为重验定位；验证时还要求显式 catalog，不能从分析文件获得执行授权。每个候选固定字段：`strategy_id, strategy_sha256, request, response, replay_path, replay_sha256, before_score, after_score, after_phase`。回放路径只能是 `branches/<ID>.json`；TRAPPED 的回放路径/摘要和 after 字段为 null。结果原始字节 SHA-256、catalog 规范化摘要及策略源码摘要必须逐项核对。所有 JSON 拒绝重复键、未知字段、bool 冒充整数、无界数字、非有限数、路径穿越和符号链接；文件原子写入。分析文件不存可信的 `verified` 布尔值，加载时完整重算。

## 证明边界

`--verify` 首先重新执行原 v3 全局双层验真，再用新策略进程重新发送同一观察序列，逐字比对目标响应，且用新游戏进程逐笔复核每条分支回放。`--explain` 仅在上述验证完成后展示观察、建议、一步后局面和分数变化。摘要仅是字节完整性标识，不是签名或历史主体认证。单步效果不推出整局结果或策略优越性。可信目录和超时不是陌生 LWT 源码的安全沙箱。
