# S54 收官：PPT 真渲染、dict 键序盲区闭环与验收准备

> 本阶段之后停止新增功能。语言语义、§1–§11、既有 400 项期望与 S53 时点的 747 项 unittest 内容均未改动；B1 只**新增** 1 个黑盒用例。**当前计数：401 黑盒 / 752 unittest / 21 页**（以 `docs/delivery-manifest.json` 为准）。

## 1. 裁决

| 裁决 | 结果 |
|---|---|
| A 分支 | 直接在 `main`（`26fed8c`）上工作 |
| B 键序盲区 | **B1**：新增 `dict-display-insertion-order`，黑盒 400 → **401**，全链同步 |
| C GUI A–E | 仍由本人执行；本轮只做**只读启动预检**，保持 `REGISTERED 0/5`、`NOT_RUN` |

## 2. WP1：PPT 真渲染（8 项交付物最后一个未验证项）

### 2.1 工具与两次失败

`tools/render_ppt.py` 用 PowerShell 调 PowerPoint COM：只读、无窗口打开 `slides/LWT介绍.pptx`，`SaveAs(pdf, 32)` 导出 PDF，逐页 `Export(png, "PNG", 1280, 720)`，再用 PIL 算每页灰度均值/方差/墨迹比/饱和度，`near_blank = variance < 50`。

写工具时踩了两个真实错误，都留在代码注释里：

1. **PowerShell 变量大小写**：脚本里 `$ppt = $null` 与参数 `$Ppt` 是**同一个变量**（PowerShell 不区分大小写），于是 `Open($Ppt, …)` 收到的是 COM 对象而不是路径，报“不能对 Null 值表达式调用方法”。改名为 `$DeckPath/$app/$pres` 后正常。
2. **脚本文件编码**：含中文的 `.ps1` 在 PowerShell 5.1 下按 ANSI 读取，路径被拆坏（`系统找不到指定的路径`）。改为脚本只含 ASCII、路径由参数传入。

### 2.2 判据为什么不用“暗像素比最高”

任务书给的观测是“第 10 页方差 1977、暗像素 6.9%、最高”。本机 1280×720 导出实测：

| 指标 | 第 10 页 | 排名 |
|---|---|---|
| 方差 | **1975.1**（中位 923.2） | **1** |
| 墨迹比（灰度 < 240） | **0.1036** | **1** |
| 平均饱和度 | **18.5** | **1** |
| 暗像素比（灰度 < 64） | 0.0066 | 21 |

原因：第 10 页是**彩色柱状图**，柱子是彩色（高饱和）而不是黑色，所以“暗像素”反而不高。把判据改为“方差高于中位且方差、墨迹比均排第一”，同时保留 `dark_ratio` 与四项排名，理由写进 JSON 的 `html` 字段。这是换了一个**更有解释力**的指标，不是把阈值调到数字好看。

### 2.3 渲染结果

| 项 | 值 |
|---|---|
| 渲染器 | PowerPoint COM 16.0 |
| 页数 | **21/21 导出成功** |
| 空白页 | **0**（`blank_pages=[]`） |
| PDF | **395,794 B**，21 页 |
| 第 10 页图表 | 方差/墨迹比/饱和度均第 1；XML 交叉校验 **12 个数值点** |
| SHA（S54 改文案后） | `809320b2…`（旧 `7cb28b13…`） |
| 证据 | `reports/s54-closeout/ppt-render.json`，页图 `reports/s54-closeout/ppt-pages/slide-01..21.png` |

`tests/test_ppt_render.py` **5/5**：字段完整、无空白、页数与 SHA 与 manifest 一致、PDF 存在、第 10 页信号达标；COM 不可用时 `skip` 并写明原因（不判通过）。

## 3. WP2：dict 键序盲区闭环（B1）

S53 记录的真实盲区：所有显示类用例的键恰好是字典序，所以“按 key 排序”的变异 survived。

1. 新增 `tests/cases/dict-maps/dict-display-insertion-order.lwt`：`dict{"b": 1, "a": 2, "c": 3}` 后 `emit`，用公开 CLI 实测得到 `dict{"b": 1, "a": 2, "c": 3}`、exit 0，再写入 `.json`（expected 不是手写的）。
2. 黑盒 **400 → 401**，全链同步：manifest、README、SUBMISSION（生成模板）、清单、矩阵、答辩卡、runbook、onsite、`defense-claims.json`、`build_submission.py` 文案、平台清单文案。
3. 把该变异加回探针集：`dict-display-sorts-keys` 由新用例 **killed**；探针 **18 → 19**，`killed 19 / survived 0 / invalid 0`。
4. **PPT 改数字**：第 14、17、18、20 四页的 `400` 文案改为 `401`（`TextRange.Replace`，保留原格式），保存后**立即重新渲染**：21/21、无空白、第 10 页图表 12 点仍在，SHA 变为 `809320b2…` 并写入 manifest。

## 4. WP3：验收收官

### 4.1 CI（`26fed8c`，逐格）

| 平台 | Python | 结论 | 耗时 |
|---|---|---|---|
| ubuntu-latest | 3.10 | success | 7m 50s |
| ubuntu-latest | 3.13 | success | 6m 33s |
| windows-latest | 3.10 | success | 7m 01s |
| windows-latest | 3.13 | success | 7m 47s |

证据：`reports/s54-closeout/ci-cells.json`（REST check-runs 逐格，不用徽章）。

### 4.2 彩排与平台包

| 项 | 结果 |
|---|---|
| 彩排（21 页 dry-run） | `--pages 1-21 --dry-run`：**32 条断言**计划（21 页共 32 条），0 执行 |
| 彩排（random 5 实跑） | seed 54：**5/5 PASS**（page 4 check、16 no-concurrency、10 s11、12 doc-consistency、21 ppt） |
| 平台包终核 | 待回填 |
| GUI 启动预检 | **4/4 窗口出现**（0.5 s 内）：语义实验室 / 日志侦探 / 贪吃蛇 / 反事实实验台；只读预检，**不是**人工验收 |

## 5. 验证记录

| 项 | 结果 |
|---|---|
| 401 黑盒 | **401/401**（115.3 s，`dict-maps=44/44`） |
| 单命令全量 | **752 项 OK，exit 0，740.4 s**（`py -3.13`，Tk 8.6） |
| 探针 | 19/19（见 §3；`dict-display-sorts-keys` 由新用例判红） |
| 自检 | **all_pass=true**：11 步 PASS、0 FAIL、2 步 N/A（GUI/agent）；`selfcheck-20261111T164054Z` |
| 文档一致性 | 全绿（含新用例的矩阵链接、401 计数、S54 报告指针） |

## 6. 未验证项（如实）

- **人工 GUI A–E**：未执行，`REGISTERED 0/5`、`NOT_RUN`；启动预检不等于人工验收。
- **教师线下验收与评分**：未发生。
- **逐页目视排版**：像素统计只能证明“渲染出内容、不是空白”，页脚是否被裁切仍需人眼在 GUI-E 里看。
- **教学云平台上传**：未执行（`uploaded=false`）。
