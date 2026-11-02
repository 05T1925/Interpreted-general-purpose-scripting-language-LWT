# S40 主窗口复核

日期：2026-11-02。复核 `feature/lwt-counterfactual-lab`，共同基线为 `fb841f8654a816b644839ccee6728c97154f97fc`。本记录只把实际执行的检查列为主窗口证据；执行窗口的完整 514 项 unittest、287 项语言黑盒及 25 项 Tk 集成结果仍见 [S40 报告](s40-counterfactual-lab.md)。

## 复核范围与发现

检查了冻结契约、CLI/Tk 实现、固定原始结果与三条一步分支、定向测试以及受保护路径。主窗口重验 `reports/s40-divergence` 成功：`baseline/4` 第 2 次相同观察上，baseline 为 `R/SPACE`，BFS 为 `D/FOOD`，Agent 的 mobility-lookahead 为 `D/SPACE`；三条单步分支分数都是 10→10。篡改样例以原生退出码 3 和 `bfs: response evidence mismatch` 被拒绝。`FOOD` 是建议理由，不代表这一步得分。

静态复核发现，输入结果及分支回放拒绝文件本身的软链接，但未逐级拒绝父目录软链接，与 S40 契约不符。已将仓库输入与分支文件统一检查为允许目录内的规范路径，逐级拒绝软链接，要求目标是普通文件；新增两类父目录软链接的受控回归。未改变 LWT 游戏、策略或单步实验语义。

## 主窗口实际运行

- `python -m unittest tests.test_lwt_snake_counterfactual -q`：修正后 4 项通过；原阶段为 3 项。
- `python -m unittest tests.test_lwt_snake_counterfactual_gui -q`：2 项通过。
- 新增父目录软链接回归单项：通过。
- 固定分歧 `--verify`：退出 0，三条 LWT 单步分支与原局双层证据重新通过。
- 固定分歧 `--explain`：退出 0，逐字显示三个响应与 10→10 即时分数。
- 篡改 `--verify`：原生退出码 3，拒绝 BFS 响应证据。
- `python tools/check_project_integrity.py`：退出 0，287 cases、384 matrix links、287 referenced cases。
- `git diff --check main...HEAD`：退出 0。

主窗口未完成物理键鼠/视觉验收。固定 Tk 界面是只读文本展示，不能称为棋盘动画；S40 仅证明同一观察轨迹的响应与一步替代效果，不证明整局优势或陌生策略安全。功能分支精确 SHA 的远端 CI、主线集成及 S12 最终交付需在后续核对，不能由本地结果推断。
