# S39 主窗口复核

日期：2026-11-02。审查对象为 `feature/lwt-strategy-workshop`，基线为 `a4157c42d3c6df1dbe2288384aa6ac5f3063c0b3`。本文件记录主窗口实际复核，不将执行窗口报告或旧提交的 CI 当作本次远端验证。

## 范围与结论

核对了课程应用要求、S39 的可信本地目录边界、第三份 Agent 编写的 LWT 策略、v3 目录与源码摘要绑定、九局游戏及策略双层验真、旧 v2 验真，以及 S39 的 6 项定向测试。S39 的策略来自独立 Agent 的源码与修正提交；保留了首次协议序号失败和后续修正记录。九局均在 6 TICK 上限停止，不能解释为胜利或普遍策略优势。

静态复核发现 `--game-only --verify` 对 v3 未拒绝。该选项原本仅用于旧 v1 结果；v3 实际仍执行完整验真，因此没有削弱证明，但 CLI 契约不一致。已把拒绝条件扩展到 v3，并在 `tests/test_lwt_snake_workshop.py` 加入公开 CLI 回归。

## 主窗口实际运行

在 Windows / Python 3.13.7 上：

- S39 定向测试：修正前 6/6 通过；新增拒绝断言的单项测试 1/1 通过。
- `--verify reports/s39-demo/result.json --catalog app/lwt_snake/strategies/strategy-catalog.json`：退出 0，九局均为 `game_verified=true`、`policy_verified=true`。
- `--verify reports/s38-demo/result.json`：退出 0，六局保持双层验真。
- `python tools/check_project_integrity.py`：退出 0，287 个用例、384 条矩阵链接、287 个被引用用例。
- `git diff --check main...HEAD`：退出 0。

执行窗口报告的 509 项 unittest、287 项语言黑盒、23 项 Tk 集成测试和其他检查见 [S39 执行报告](s39-strategy-workshop.md)；本轮没有把它们写作主窗口复跑结果。

## 后续门槛

审查修正提交为 `0f543e4b12ff45c34deb6167ed82a2363acf9c44`。功能分支推送后，[Actions run 41434877262](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41434877262) 的 Ubuntu/Windows × Python 3.10/3.13 四格均 `success`；这是精确提交的远端证据。本地主线从共同基线 `a4157c4` 以 `git merge --ff-only` 快进到该提交，未重写历史。远端 `main` 的同步与新提交 Actions 另行核对。

因此 S39 通过主窗口审查。人工桌面、陌生策略隔离、Python 3.10/Linux 本机环境和 S12 新克隆/PPT 仍属于独立验收事项。可信目录限制用于防止误选路径，不能作为安全沙箱使用。
