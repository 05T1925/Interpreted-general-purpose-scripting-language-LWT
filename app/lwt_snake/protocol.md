# LWT 驱动贪吃蛇：协议与规则冻结

状态：S34 实施基线。本文先于游戏与 Python bridge 编码冻结；实现或测试与本文不一致时先修实现/测试，不暗中更改协议。

## 1. 进程与帧

- Python 以参数数组启动一个长期进程：`sys.executable -u -m lwt <仓库内游戏源码>`，`cwd` 为仓库根目录，`shell=False`。GUI 生命周期内不按帧重启解释器。
- stdin/stdout/stderr 均为 UTF-8 字节流。Python 每次写一条 ASCII 请求并附 LF、flush；stdout 每个 LF 帧必须是 ASCII。stderr 仅作诊断，不并入协议 stdout。LWT `input()` 在 EOF 返回 `null` 并静默退出；收到 `QUIT` 时先响应再正常退出。
- bridge 始终发送 LF；直接从公开 CLI 输入 CRLF 时，沿用正式 `input()` 剥除终止 CRLF 的行为。该兼容性不允许响应使用 CRLF，或字段内含 CR。
- 请求帧不含 LF 最多 128 字节；响应帧不含 LF 最多 4096 字节。超长、非 UTF-8/非 ASCII、超时、EOF、额外输出、协议错误均由 bridge 作为失败处理，保留最近的 stderr 诊断，不伪造游戏状态。
- 所有请求恰好 6 个 `|` 分隔字段：`LWS1|SSSSSS|COMMAND|A|B|C`。版本固定 `LWS1`；序号是从 `000001` 开始、每请求递增的 6 位 ASCII 十进制数，每进程最多 999999 个请求。
- 除字段个数不同的错误帧外，字段内禁止 `|`、CR 和 LF。输入严格限 ASCII；协议不接受用户文本。游戏源码/异常诊断走 stderr，不在响应中插入额外文字。

### 请求

| 请求 | A | B | C | 行为 |
|---|---|---|---|---|
| `INIT` | 宽度 | 高度 | 10 位种子 | 仅未初始化时有效；宽度 4–24，高度 1–18，面积不超过 432；种子为 1–2147483646。 |
| `START` | `-` | `-` | `-` | READY → RUNNING。 |
| `TURN` | `U`/`R`/`D`/`L` | `-` | `-` | 仅 RUNNING 接收；规则见下文。 |
| `TICK` | `-` | `-` | `-` | RUNNING 推进一步；其它已初始化状态为无副作用 no-op。 |
| `PAUSE` | `-` | `-` | `-` | RUNNING → PAUSED，并丢弃尚未消费的转向。 |
| `RESUME` | `-` | `-` | `-` | PAUSED → RUNNING。 |
| `RESET` | `-` | `-` | `-` | 任一已初始化状态复位到同尺寸、同种子 READY 初始局。 |
| `QUIT` | `-` | `-` | `-` | 已初始化时返回当前快照后正常退出。 |

序号正确且版本有效的完整 6 字段请求会先消费序号；随后若命令、参数或当前状态不允许，游戏状态保持不变并返回错误帧。序号错误、版本错误、字段数错误不消费序号。错误码固定为 `BAD_FIELD_COUNT`、`BAD_VERSION`、`BAD_SEQUENCE`、`FRAME_TOO_LONG`、`BAD_COMMAND`、`BAD_ARGUMENT`、`BAD_STATE`、`NOT_INITIALIZED`、`BAD_TURN`。错误响应固定 4 字段：`LWS1|ERR|SSSSSS|CODE`；若请求中没有可识别的 6 位序号，使用 `000000`。错误行不会伪装成状态快照。

### 响应

正常响应恰好 10 字段：

```text
LWS1|SSSSSS|STATE|PHASE|SCORE|DIR|FOOD_X|FOOD_Y|BODY_LEN|BODY
```

`PHASE` 为 `READY`、`RUNNING`、`PAUSED`、`GAME_OVER` 或 `WON`；`SCORE` 为非负十进制数；`DIR` 为 `U/R/D/L`。DIR 表示下一次移动方向：若有待消费的合法 TURN 则显示该方向，否则显示当前方向。无食物时 `FOOD_X` 和 `FOOD_Y` 必须同时为 `-`，且仅 WON 状态无食物；否则它们是棋盘内坐标。蛇身按头到尾排列：`x,y;x,y;...`，长度等于 `BODY_LEN`，READY 状态至少 3 节。坐标原点在左上角，x 向右、y 向下；宽高由 INIT 决定。bridge 逐字段严格校验数量、序号、范围、状态、方向、长度、坐标唯一性以及蛇头/食物不重叠；拒绝任何额外 stdout 帧。

## 2. 游戏语义与确定性

- 初始蛇长 3，头位于 `(floor(width/2), floor(height/2))`，另两节沿头部反方向水平排列；初始方向 RIGHT，得分为 0，状态 READY。
- 直接反向相对于最近一次已接受的转向（否则当前方向）判断。每个 TICK 前多次合法 TURN 按“最后一个合法转向生效”合并；逆向 TURN 返回 `BAD_TURN`，保留之前待消费的转向。TICK 将待消费方向设为当前方向后移动一格，并清空待消费方向。
- 普通移动时尾节离开；新头进入墙外或当前蛇身非尾部格时变为 GAME_OVER，碰撞步不移动蛇身。若新头进入本步将离开的尾格且本步不吃食物，允许移动；若要吃食物，尾格保留并参与碰撞判断。
- 吃到食物时蛇身增长一节、得分加 10。新食物只从未占用格子中选。若没有空格则食物为空、状态 WON。
- PRNG 使用 Park–Miller：`state = (state * 48271) % 2147483647`，以 `state % empty_count` 选取按 y 再 x 排序的空格序号。RESET 恢复 INIT 的原种子。此算法只为确定性重放，不是密码学安全随机数。
- PAUSE 只在 RUNNING 有效，并清除待消费转向；RESUME 只在 PAUSED 有效。GUI 失焦时请求 PAUSE；重新获得焦点不会自动继续，需用户按键或点击“继续”。终局需要 RESET 后再 START。
- LWT 只捕获协议层畸形用户帧并返回稳定错误；内部运行时异常不被 `attempt/recover` 吞掉，解释器以非零码退出并将真实诊断写 stderr。bridge 看到异常/早退即显示错误并停止本局。

## 3. 实现职责

`app/lwt_snake/game.lwt` 是唯一的生产游戏规则与状态源，负责命令校验、种子随机、转向、移动、吃食物、碰撞、得分、暂停、复位和状态帧。Python bridge 只负责子进程、LF 帧、UTF-8/ASCII/字段/序号/坐标边界校验、请求超时与线程消息；Tk UI 只转发控件事件、定时 TICK、消费经校验的状态快照、绘制和显示诊断。原 `app/snake_game_core.py` 仅保留为独立 Python 演示和测试参考，不供新入口调用作规则后备。
