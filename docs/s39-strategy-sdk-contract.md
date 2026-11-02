# S39 策略 SDK 与可信目录契约（编码前冻结）

依据 [LWT 正式规范](language-spec.md)、[S36 LWA1](snake-strategy-protocol.md)及 [S38 双层证据](s38-policy-proof-contract.md)。这是开发工具与课程应用扩展，不改变 LWT 语义。自定义 LWT 源码是可执行程序；目录/超时检查**不是安全沙箱**，仅用于明确选择的可信本地源码。

## 目录与身份

- 内置 `baseline`、`bfs` 无须 catalog，维持 S38 默认行为。自定义策略仅在 CLI 明确传入 `--catalog FILE` 时可见。FILE 必须是仓库 `app/lwt_snake/strategies/` 内的普通 `.json` 文件，不接受软链接或越界解析。无 catalog 的 `--verify`/`--explain` 不得根据结果自动运行自定义路径。
- manifest 为严格 UTF-8 JSON，最多 64 KiB，固定顶层键 `schema_version: 1`、`strategies: [...]`；每项键固定 `id,path,sha256,protocol`。ID 为小写 ASCII `[a-z][a-z0-9-]{0,31}`，不重复，不覆盖内置；目录至多 8 项。`protocol` 必须 `LWA1`。`path` 是策略目录内**单个文件名**，须以 `.lwt` 结尾，允许空格及 Unicode，拒绝斜杠、反斜杠、`..`、绝对路径、软链接和非普通文件。源码最多 64 KiB，严格 UTF-8，最多一个开头 BOM；规范化 CRLF/CR 为 LF 后计算 `lwt-utf8-lf-sha256-v1`，manifest 中小写 64 hex digest 必须一致。
- 自定义源码必须可被公开 `python -m lwt --check` 静态检查，且经 LWT lexer/parser 生成的 AST 中不得有 `ImportDeclaration`。字符串或注释中的 `import` 不是拒绝理由。本版只接受无 import 的单文件策略，避免未绑定依赖闭包。运行/验真每次启动前和结束后复核 manifest 与源码摘要；期间变化整局失败，不写正常得分或伪造策略归属。

## CLI、运行及版本

- `python -m app.lwt_snake.arena --check-strategy ID --catalog FILE`：先校验目录、AST 与公开静态检查，再以真实长驻 `python -u -m lwt` 发送固定 LWA1 帧，包括合法移动、墙/身体、非法帧、序号与 EOF。成功 exit 0，配置/静态/协议失败 exit 2；诊断给帧序号和字段。仅证明这些固定帧和基础协议，不承诺胜利、无碰撞或陌生程序安全。
- `python -m app.lwt_snake.arena --catalog FILE --strategies baseline,bfs,ID --seeds 4,7,11 --max-ticks 12 --workers 1 --output NEW_DIR`：每对策略/种子独立长驻游戏和策略进程。选中自定义项时必须给 catalog；显式 catalog 触发结果 `schema_version:3`。游戏、决策、回放、分数仍由现有 S38 流程取得。workers 仅 1/2/4，最多 16 局、8 seed、100 TICK、请求 5 秒、整局 60 秒；进程 argv 列表、`shell=False`、固定仓库 cwd 和关闭回收。
- v3 顶层在 v2 键外增加 `catalog:{schema_version:1,path,sha256}`；manifest path 为仓库相对路径，sha256 为规范化 manifest UTF-8 字节摘要。策略元数据及每局源码摘要继续沿用 v2。`--verify RESULT --catalog FILE` 与 `--explain RESULT --catalog FILE --case ID/seed --step N` 必须先校验当前可信目录文件与结果绑定，并用当前目录映射启动全新 LWT 策略进程双层验真。v3 缺 catalog、路径/digest/源码变化或策略归属伪造 exit 3；不可用结果 JSON 中的路径自动选执行文件。v2 仅使用两内置策略且保持原样，v1 仍需 `--game-only --verify`，只有游戏证明。
- 输出目录须全新，文件大小维持 S38 结果/决策 1 MiB、S35 回放 16 MiB；错误时保留完整前缀并标实际证明层级。配置/输出错误 exit 2、含失败局的运行 exit 1、验真/解释失败 exit 3、成功 exit 0、取消 exit 130。相同 seed 不保证不同策略有相同后续食物序列；小样本分数不是策略优越性证明。

## 模板与 Agent 实验

复制 `app/lwt_snake/strategies/strategy-template.lwt` 作为新文件，再实现完整解析、合法性与决策；模板本身不是注册策略。开发者先用 `--check-strategy`，再用固定种子小局、`--verify`、`--explain` 形成可复核闭环。独立 Agent 只能收到本契约、[策略 SDK](strategy-sdk.md)、模板、语言规范/开发指南和原始任务，不收到执行窗口的第三策略答案。自动 Skill 选择与逐事件时间线若不可观察，报告中必须标明。
