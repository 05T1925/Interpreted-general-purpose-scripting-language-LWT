# S34 提案：LWT 驱动的交互贪吃蛇

状态：规划中，尚未实施。S33 已通过主窗口复核并快进进入本地 `main`；S12 仍保留最终新克隆、PPT、桌面预检和交付。

## 为什么选择此阶段

课程中 Agent 编写的 LWT 应用占 30 分。现有 `app/log_report.lwt` 已有 246 行有效 LWT，是评分主体；现有 Snake 则由 Python 实现规则。S34 可增加第二个真实 LWT 应用：蛇的位置、方向、食物、计分、碰撞和胜利均由 LWT 程序计算；Python/Tkinter 仅转发输入、定时和绘图。这样能在演示中直接展示 LWT 的数组、record、函数、循环、输入输出、模块及长期运行能力，同时不修改解释器语义。

## 可行性与架构

本轮用临时 LWT 程序实测：`python -u -m lwt <source>` 保持单进程运行，写入 UTF-8 `ping 雪\n` 后立即读到逐行响应，关闭 stdin 后退出码 0、stderr 为空。Python 官方 [`-u` 文档](https://docs.python.org/3.10/using/cmdline.html)说明 stdout/stderr 无缓冲；[subprocess 文档](https://docs.python.org/3.10/library/subprocess.html)提醒双管道读写必须并行排空，避免死锁；[Tkinter 线程模型](https://docs.python.org/3.10/library/tkinter.html#threading-model)要求 UI 更新由运行事件循环的 Tk 线程处理。本轮只验证了通信原型，没有实现或测量完整游戏。

建议使用一个长期存活的 `python -u -m lwt app/lwt_snake/game.lwt` 子进程；LWT 从 `input()` 读取有界、逐行 ASCII 命令并 `emit` 一行固定协议状态。Python bridge 负责参数向量、进程生命周期、UTF-8/协议校验、超时、队列和线程同步；不计算游戏规则。Tk 在主线程消费状态并绘制。每帧不重新启动解释器。保留原 Python Snake 不变，作为独立展示与规则对照；新入口明确命名为“LWT 驱动贪吃蛇”。

## 语义和安全边界

- 协议版本、帧长、字段个数和数值范围固定；建议命令 `INIT`、`TURN`、`TICK`、`PAUSE`、`RESUME`、`RESET`、`QUIT`，响应含请求序号、phase、分数、方向、食物和蛇身坐标。EOF 正常退出；畸形命令返回稳定错误响应，内部异常由桥接层显示并结束会话，不伪装正常状态。
- 食物由 LWT 中的固定种子伪随机数发生器从空格子选择。种子只为可复现，不作密码学或公平性宣传。规则明确尾格离开时可进入、增长时不可进入、禁止直接反向、撞墙/撞身、暂停、重开、填满获胜。
- 游戏循环、状态推进和随机选择不得落在 Python。Python 参考 Snake 可作为独立 oracle 做同种子状态对照，不作为新 GUI 的隐藏后备规则。
- Python bridge 用 `Popen` 参数数组与 `shell=False`，并行排空 stdout/stderr，设定有界队列、响应超时、关闭清理；Tk 控件只在主线程更新。不改 `lwt/`、正式规范、S10/S11/S28/S29 原始证据。

## 验收门槛

1. Agent 编写的 LWT 游戏源码具备可读模块、真实规则和不少于 200 行有效 LWT；行数工具实测，不用空行/注释凑数。记录 Agent 开发、人工复核与修正。
2. 固定命令脚本在公开 CLI 上重放，逐行协议输出和退出码可复现；覆盖食物、尾格、增长、反向、撞墙/撞身、暂停、重启、获胜、畸形输入与 EOF。
3. Python bridge 做真实长进程集成测试，覆盖分帧、UTF-8、序号、超时、早退、stderr、关闭无残留进程、Unicode/空格路径；随机确定性回合可与现有 Python 规则模型对照。
4. 新 Tk GUI 支持方向键/WASD、暂停、重开、得分与结束反馈；非阻塞运行，状态来自 LWT。自动 Tk 控件测试与有条件的人工桌面验收分开记录。
5. 原 287 项语言黑盒、项目完整性、全量 unittest、S10 应用 25 项、原 Snake 回归、VS Code 扩展测试和 CI 按改动范围验证。S11 性能结果不因游戏桥接而改写，不拿游戏时延充当语言基准。
