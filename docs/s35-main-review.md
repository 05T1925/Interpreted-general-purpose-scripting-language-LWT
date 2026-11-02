# S35 主窗口独立复核

日期：2026-11-02。审查对象：`feature/lwt-snake-game` 的 S35 实现提交 `451fb490f7cc2193b4fe7b4a7032179396389ddb`，以及主窗口单独提交的测试稳定性修正 `7ced2a8`。本记录中的“通过”仅指本地复核；远端 Actions 和人工桌面验收另行核对。

## 结论与课程关系

S34 已发现的两个问题有可复现的修复证据：持续 TURN 不再饿死移动时钟；失焦测试在确认新窗口映射与实际焦点归属后仍检查暂停。S35 在同一 LWT 驱动游戏上增加了真实事务录制、严格文件契约、新进程重放验证、GUI 单步复盘和指定前缀接管。未发现阻止进入下一阶段的产品缺陷。游戏规则仍由 313 行有效 LWT 源码计算；Python 承担协议、进程、绘图和复盘控制。它可增强课程的 Agent LWT 应用展示，但不替代完整黑盒、性能、指南、PPT 等其他交付。

## 独立核查证据

| 核查 | 本窗口实际结果 |
|---|---|
| 源码与协议审阅 | 核对 `clock.py`、`bridge.py`、`session.py`、`replay.py`、`ui.py`、格式文档及相关测试；录制位置在 bridge 完整响应校验之后，含错误和被 UI 新请求遮蔽的已完成事务；新 LWT 进程逐笔比较响应；接管重新执行前缀。未发现改变 `game.lwt` 或正式语言语义的改动。 |
| 全量 Python 测试 | `python -m unittest discover -s tests -q`：S35 原提交下 481 项通过，exit 0，约 192 秒。该命令在主窗口的测试稳定性修正后未再次运行。 |
| LWT 黑盒 | `python tools/run_tests.py`：287/287 通过，exit 0；S35 复核阶段没有修改语言运行时或黑盒案例。 |
| 项目完整性和游戏静态检查 | `python tools/check_project_integrity.py`：287 cases、384 links、287 referenced；`python -m lwt --check app/lwt_snake/game.lwt`：1 source passed；均 exit 0。 |
| 固定回放 | `demo-parent.json`、`demo-child.json` 均由真实 LWT 新进程验证，分别报告 10、12 笔；`demo-divergent.json` 在第 3 笔 TICK 的 score 字段报告预期 20、实际 10。后者的失败是样例预期行为。 |
| 严格 GUI 组 | 与全量测试和黑盒并行时曾有 1 项失败：1.15 秒内只收到 4 笔 TURN，旧断言要求超过 5 笔。独立串行复跑 19/19 通过。主窗口发现该测试还受到桌面焦点事件影响；修正为直接调用应用命令入口，独立单测 1/1、严格 GUI 组 19/19、skip 0，均通过。 |
| Git 差异 | 主窗口修正单独提交为 `7ced2a8`，只改 `tests/test_lwt_snake_gui.py`；`git diff --check` 通过。 |

## 首次远端 CI 失败与跨平台修复

功能分支第一次推送的精确 SHA 为 `d6b6a3b796b2f725e0fa0359d7e4ec269e3f6c02`，[Actions run 41380436598](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41380436598) 的 Windows 3.10/3.13 两格成功，Ubuntu 3.10/3.13 两格在 `Run Tk GUI integration tests (Linux)` 失败。通过 GitHub 原始 job log 核对：19 项中 18 项通过，`test_real_buttons_keys_focus_reset_and_close` 在等待真实失焦后 `PAUSED` 时超时；此前修正的连续 TURN 用例在 Linux 通过。**该次 2/4 不能记为远端全绿。**

主窗口在 WSL Ubuntu 24.04 / Python 3.12.3 + Xvfb/Tk 8.6 复现了同一失败。根因是 Tk 根窗口绑定接收来自焦点子控件的 FocusOut，但 `on_focus_out` 只接受 `event.widget is root`；按钮持有焦点并移到外部窗口时，该事件被丢弃。`33d5c048cbc8e8987041cbcbabb018a5af42bf7a` 移除此错误过滤，保留 idle 后判断焦点是否离开整个游戏窗口，因此同窗子控件切换不会误暂停。测试改为真实转移焦点到已映射的另一 Toplevel，不再人工生成根窗口 FocusOut 充数。

修复后独立运行该用例：WSL/Xvfb 1/1、Windows 1/1；两个环境的 `python tools/run_gui_integration.py --require-no-skips` 均为 19/19、fail 0、skip 0。此处尚未把修复 SHA 的远端 CI 记为通过，需推送后再核实。完整 unittest 与 287 个语言黑盒在修复前的本窗口结果见上表；本修复只涉及 Tk 焦点处理与一条 GUI 测试，后续精确 SHA CI 应覆盖全量。

旧的“1.15 秒内超过 5 笔 TURN”混合了机器负载与功能判定；未映射/焦点转移也能让测试在开始阶段暂停，使 TURN 数为 0。现在该测试断言重复真实 TURN、拒绝逆向 TURN、仍能发生真实 TICK 后蛇头移动；键盘映射和焦点行为由其他独立 Tk 测试负责。修正降低环境敏感性，不改变产品行为。S35 报告里的历史测试结果按当时版本保留，不倒写为本轮结果。

## 边界与交接

- S35 的文件摘要用于识别源码兼容性，不是签名或防篡改保证；故意篡改必须靠真实新进程逐笔验证发现。
- 保存只保证同目录临时文件替换的正常错误处理，不承诺断电持久性。回放最多 5000 笔、文件最多 16 MiB；复盘缓存有界。
- 现有自动 Tk 控件与合成事件通过，不等于人工键鼠、中文输入法、窗口缩放和视觉验收。
- 本轮未完成 Python 3.10、Linux 或精确 S35 SHA 的远端 CI；需在同步后按实际提交核对。S12 仍保留最终新克隆、PPT、现场演示与交付。
- 若继续新增功能，优先做能直接体现“LWT 编写应用”的独立能力，保持 `game.lwt` 和 S35 回放格式不变，以免无故失效已有固定回放证据。下一候选见 [S36 派发提示](s36-strategy-handoff.md)。
