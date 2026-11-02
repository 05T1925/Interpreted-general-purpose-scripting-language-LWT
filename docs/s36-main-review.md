# S36 主窗口独立复核

日期：2026-11-02。审查对象：`feature/lwt-snake-strategy`，执行窗口最终提交 `eb375b06d274f13c6225ddcdad791734c2b8bc47`；基线为已审查 `main` 的 `7bc0a13524b22eb26a0daaba67a9af3f409effb1`。本记录区分执行窗口报告、主窗口本次实测、远端 CI 和人工 GUI。S12 未开始。

## 结论

阶段实现与课程“Agent 编写 LWT 应用”的目标直接相关：新增 141 行有效 LWT 的独立长驻策略，游戏规则仍由 313 行有效 LWT `game.lwt` 计算；Python 仅负责协议、进程、Tk 调度与显示。静态 BFS 依据预测后的占用计算方向，属于确定性单步启发式，不保证未来存活或最优。审阅、定向复跑和精确 SHA 的远端 CI 均未发现阻断问题。S36 于 2026-11-02 通过主窗口审查，保留全部原提交快进合入本地 `main`；人工桌面交互仍待最终验收。后续应用增量见 [S37 策略擂台派发提示](s37-strategy-arena-handoff.md)。

## 独立核查

| 核查 | 本窗口证据 |
|---|---|
| Git 与保护范围 | 分支干净，`main` 和 `origin/main` 均为 `7bc0a13`，阶段 tip `eb375b0`，领先 6 提交；`git diff main...HEAD` 仅 16 个阶段文件。`game.lwt`、S35 固定回放、LWT 解释器/正式规范/黑盒、日志应用及 S10/S11 原始证据无差异。 |
| 代码审阅 | 核对 `strategy.lwt` 的逆向/墙/身体及尾格规则、预测占用、有限队列 BFS、固定方向平局；核对 `strategy.py` 的 ASCII/长度/序号验证、双管道排空、取消和进程回收；核对 `ui.py` 的手动时钟与自动串行链互斥、代号拒绝旧结果、错误后停止推进。未发现 Python 寻路后备。 |
| Windows 定向 | `python -m unittest tests.test_lwt_snake_strategy -q`：8/8、exit 0；`python -m lwt --check app/lwt_snake/strategy.lwt`：1 source passed；`compileall` 与 `git diff --check main...HEAD`：exit 0。 |
| Linux 定向 | WSL Ubuntu 24.04 / Python 3.12.3 下，`python3 -m unittest tests.test_lwt_snake_strategy -q`：8/8；策略静态检查通过；Xvfb/Tk 8.6.14 下 `python3 tools/run_gui_integration.py --require-no-skips`：23/23、fail 0、skip 0。此为本机 WSL 定向验证，不代替远端 3.10/3.13 四格。 |
| 课程与旧应用门禁 | 主窗口 `python tools/check_project_integrity.py`：287 cases、384 matrix links、287 referenced；策略/游戏有效 LWT 行数分别 141/313。执行窗口报告全量 unittest 493/493、语言黑盒 287/287、S10 25/25；这些全量数字尚未在本窗口复跑，后续以精确 SHA CI 验证。 |
| 远端功能分支 CI | `3bf7effa4fc3bf9a1c2f117e174a7a5a1c0182f0` 的 [Actions run 41388553619](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41388553619)：Ubuntu/Windows × Python 3.10/3.13 四格均为 `completed/success`。功能分支已推送，随后本地 `main` 快进至该提交。主分支推送与 CI 单独核验。 |

## 审查边界

- `GameSnapshot.direction` 表示下一次实际移动方向，含待消费的 TURN；策略和真实游戏的联合测试覆盖此点。固定方向序、合法候选、食物路线和最大可达空间只是静态网格规则，不是未来蛇身与新食物的全局搜索。
- S36 时延文件是 Windows 上九次请求与独立自动链采样；最大棋盘暖查询约 0.14 秒。它不能代表其他硬件、硬实时性能或 S11 解释器对比。
- Tk 自动控件测试不等于物理键鼠/输入法/视觉验收。用户要求继续一阶段应用创新，S37 应限定为复用现有游戏/策略协议的可复现扩展；完成后立即进入 S12 最终交付，不无限增加功能。
