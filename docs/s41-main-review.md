# S41 主窗口复核

日期：2026-11-03。共同基线为 `2e755914400d094694dc29bb81a863f94b1f28f5`，阶段分支为 `feature/lwt-witness-discovery`。原执行证据和适用边界见 [S41 报告](s41-witness-discovery.md)及[冻结契约](s41-witness-contract.md)。

## 复核与修正

审阅了真实 LWT 策略和游戏进程的有界搜索、固定命中/无见证/篡改证据、重新搜索验真、Tk 只读载入及回归测试。固定命中是 `baseline/4` 第 2 次咨询处的方向分歧：baseline `R/SPACE`，BFS `D/FOOD`；只说明同一已验证观察前缀上的差异，不证明整局策略优劣或策略等价。

发现两项与冻结契约不符的边界：无效参考/挑战者、预算和输出目标原先返回证据错误码 3，而契约要求配置/写入错误码 2；无见证证据目录可附带不应存在的 `analysis`。审查提交 `10e6a82788ecb59f768d2cb4968e5597728060b2` 将配置与输出创建/写入错误归为 2，并拒绝无见证目录中的分支分析目录或软链接；保留真实证据和执行错误码 3。新增/更新定向回归，未改 LWT 游戏、策略、解释器语义或既有固定证据。

## 实际验证与集成

- `python -m unittest tests.test_lwt_snake_witness -q`：6 项通过，退出 0；其中包含真实固定命中、无见证、篡改、重复生成、截止时间与新增边界。
- 无效参考的公开 CLI 原生退出码为 2；固定命中 `--verify` 原生退出码为 0，输出 `found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs`。
- 新增输出创建/写入错误单测与无见证附带分析目录的真实 CLI 测试均通过。
- `git diff --cached --check`：退出 0；修正提交前工作区干净。
- 审查修正精确提交的[功能分支 Actions run 41481213153](https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/actions/runs/41481213153)在 Ubuntu/Windows × Python 3.10/3.13 四格完成且均为 success。
- 只读远端查询确认合入前 `origin/main` 仍为共同基线，远端功能分支为审查修正提交。本地 `main` 以 `git merge --ff-only feature/lwt-witness-discovery` 快进到该提交，保留 S41 原有五笔阶段提交及审查修正提交。

因此 S41 通过主窗口复核并已进入本地 `main`。远端 `main` 的同步及**本次状态文档提交**的精确 CI 结果另行核对，不能从功能分支成功推断。S12 新克隆、系统 PPT、完整人工物理键鼠/视觉验收与最终交付均尚未完成。
