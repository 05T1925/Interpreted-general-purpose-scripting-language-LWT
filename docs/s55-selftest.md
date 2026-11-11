# S55 执行报告：用 LWT 测试 LWT 的原生自测与功能清单逐项打勾

> 本阶段**不改语言语义、不改 §1–§11、不改 401 项黑盒期望**，只补课程第 8 章任务 2 的两处口径缺口。
> **当前计数：401 黑盒 / 758 unittest / 38 项 LWT 原生自测 / 21 页 PPT**（以 [`delivery-manifest.json`](delivery-manifest.json) 为准）。

## 1. 复核发现的两个缺口

读课程第 8 章（`第 8 章：课程回顾_大作业.pdf`，页 16–17）后逐条对照仓库：

| 课件原话 | 仓库现状（复核实测） | 判定 |
|---|---|---|
| 「测试脚本使用 ZS 语言编写——用 ZS 测试 ZS」，示例是 `tests.zs` 里定义 `expect()`、逐项打印 `[PASS]`、末尾 `6/6 全部通过` | 401 项黑盒的**被测程序**是 `.lwt`，但**断言在 Python 侧**用 `.json` 期望输出逐字节比对；全仓 `grep -rln "expect(" --include=*.lwt` **零命中** | **缺口**：没有 LWT 原生的自断言脚本 |
| 「一个命令执行所有测试，自动输出每一项的结果与总数」 | `python tools/run_tests.py` 确实一条命令输出 401 项与分类汇总 | 满足，但输出形态不是课件示例的 `[PASS] 名字` + `N/N` |
| 「测试名与功能清单一一对应——逐项打勾，缺一项就不算完整覆盖」 | `docs/test-matrix.md` 是**规范小节 → 用例**的映射（S52 补齐了 §8 与 20 个小节）；没有**课程功能清单 → 测试名**的打勾表 | **缺口**：没有功能清单文档 |
| 「覆盖五项基本功能与自己追加的特色功能」 | 401 项黑盒覆盖面足够，但读者要自己从 427 个文件名里推断哪条对应哪项功能 | 缺一张可核对的清单 |

上一版 README 曾写「符合第 8 章任务 2『用 LWT 测试 LWT』口径」，依据是「用例程序由 LWT 编写、runner 只驱动公开 CLI」。这个读法**站得住但不充分**：课件给的是自断言脚本，而我们的断言确实在 Python 侧。本阶段把这个说法补成事实，而不是改措辞绕过去。

## 2. 交付

### 2.1 LWT 原生自测脚本（38 项）

`tests/selftest/lwt_selftest.lwt`，断言函数由 LWT 自己实现：

```lwt
let passed = 0;
let total = 0;

fn expect(cond, name) {
    total = total + 1;
    when (cond) {
        passed = passed + 1;
        emit "[PASS] " + name;
    } otherwise {
        emit "[FAIL] " + name;
    }
}
```

- 覆盖**任务 1 五项基本功能**：整数/字符串/布尔（含任意精度整数与无隐式转换）、数组/record、`input()`/`emit`、`when-otherwise`/`while`/`each`/`break`/`continue`、函数定义/递归/作用域。
- 覆盖**追加的特色功能**：dict 插入序与 `has`/`get`/`put`/`delete`/身份相等、`throw`+`attempt/recover`、`finally` 两条路径、模块 `import`、`spawn`/`join`、通道 `send`/`receive`/`close`、`split`/`trim`/`to_int`。
- 末尾按 `passed == total` 打印 `38/38 全部通过` 或 `k/N 有失败`。
- 「基本输入」项用 `attempt { input() } recover { … }` 包住：**不给标准输入时该项记 FAIL 而不中断整套**，避免直接运行脚本时卡死或整段崩掉。

### 2.2 一条命令 + 机器可读证据

`tools/run_selftest.py`：

```bash
python tools/run_selftest.py
# [PASS] 基本类型：整数算术与优先级
# …
# 38/38 全部通过
# run_selftest: 38/38 通过，失败 0，exit=0 -> reports/s55-selftest/selftest.json
```

它只做三件事：用 `sys.executable -m lwt` 启动公开 CLI、核对输出**形状**（0 个 `[FAIL]`、`passed == total`、末行 `k/N` 与计数自洽）、写 JSON+MD 证据。**不复算任何断言**——断言结论完全来自 LWT 脚本自己打印的行。工具还拒绝把 `tests/cases/**` 里的黑盒用例当自测脚本（退出 2），防止误用。

证据：[`reports/s55-selftest/selftest.json`](../reports/s55-selftest/selftest.json) 记录脚本 SHA-256、命令、Python 版本、stdin、逐项结果、耗时与汇总行。

### 2.3 功能清单逐项打勾

[`docs/feature-checklist.md`](feature-checklist.md)：两张表共 **40 行**，每行给出「功能项 → ✅ → LWT 原生自测项名字（与脚本输出逐字一致）→ 代表黑盒用例 → 规范节」。

- 表一：任务 1 五项基本功能，22 行；
- 表二：LWT 追加特色功能，18 行；
- 另有一节把课件任务 2 的三点要求逐条对到仓库证据与复算命令；
- 末尾「没有做的事」写明：这是**功能可用性清单**，不是形式化证明，缺陷发现仍靠 401 项边界用例与 19 条语义变异探针。

### 2.4 门禁

`tests/test_lwt_selftest.py`（**6 项**）：

1. 自测必须 exit 0、无 `[FAIL]`、项数 ≥30、末行必须是 `N/N 全部通过`；
2. 检查项名字非空且唯一（防止复制粘贴出现同名项）；
3. `docs/feature-checklist.md` 存在、含五项基本功能关键词、≥30 行打勾；
4. 脚本必须是 LWT 写的（含 `fn expect(`、`import "selftest_helper.lwt"`），且**不得**出现 `unittest`/`def `/`subprocess` 等宿主语言痕迹；
5. 工具必须拒绝把黑盒用例当自测脚本（退出 2）；
6. 工具必须写出证据，且证据里的 `passed == total`、`summary_line` 自洽。

### 2.5 顺手修掉 PPT 里的过期计数

复核时把 21 页 PPT 的文本抽出来对照当前数字，发现前 12 页是早期阶段冻结的，仍写着 **287 例**、**282 项执行配对**、**384 matrix links**、**unittest 632**，与仓库实际的 401/394/498/758 矛盾——老师翻第 2 页就会看到。

| 页 | 原文 | 改为 | 依据 |
|---|---|---|---|
| 2 | 黑盒测试与性能报告：**287 例** | **401 例** | `tools/run_tests.py` |
| 2 | 日志分析器 **246 行** | **243 行** | `tools/count_lwt_lines.py` |
| 6 | **287 / 287** 通过 | **401 / 401** | 黑盒实测 |
| 6 | **282** 项执行配对；**5** 项覆盖 CLI 参数契约 | **394** 项；**7** 项 | `cli_args_override` 实测分解（394 + 7 = 401） |
| 6 | **287** cases、**384** matrix links、**287** referenced | **401** / **498** / **401** | `check_project_integrity.py` |
| 18 | unittest **632**；S49 当前 **695** | **758**；S55 当前 **758** | manifest |
| 21 | S49：**695** unittest | S55：**758** | manifest |

改法：用 COM 自动化打开演示文稿，只对含目标数字的文本框做 `TextRange.Replace`（保留原格式），改完**立即用 `tools/render_ppt.py` 重新渲染**：**21/21 页、0 空白**、PDF 395,643 B、第 10 页方差 1975.1（中位 923.2）与图表 **12 数值点**均未变。SHA `809320b2…` → `329483857513…`。

未改的一处：第 17 页（S44 阶段页）仍写「595 项 unittest」——那是 S44 **当时**的数字，改成 758 反而失实，保留并在本表说明。改动页的渲染图留在 `reports/s55-selftest/ppt-pages/slide-{02,06,18,21}.png` 供人工核对是否溢出，其余页的像素统计在 `ppt-render.json` 的 `pages` 数组里。

## 3. 验证记录

| 项 | 结果 |
|---|---|
| LWT 原生自测 | **38/38 全部通过**，exit 0（`reports/s55-selftest/selftest.json`） |
| 新增门禁 | **6/6 OK** |
| 文档一致性 | 全绿（含本轮新增计数与功能清单） |
| 黑盒 | **401/401 不变**（本阶段只新增 `tests/selftest/`，不进 `tests/cases/`） |
| PPT | 文案修正后重渲染 **21/21、0 空白**，PDF 395,643 B，第 10 页图表 12 点未变；SHA `809320b2…`→`329483857513…` |
| 保护路径 | S11/S44/S46/S48–S54 冻结证据零 diff；`tests/cases/**` 零改动；S54 的渲染证据与 752 计数保留为冻结快照 |

## 4. 计数变化与同步

unittest **752 → 758**（新增 6 项门禁）。按 manifest 单一来源规则同步：`docs/delivery-manifest.json`（`unittest_count`、`evidence.s55_*`、`notes`）、`README.md`（阶段列表与当前状态段）、`project.md`（S55 段）、`SUBMISSION.md`（由生成器模板重生成）、`docs/final-acceptance-checklist.md`（S55 段 + S54 段标为历史值）、`docs/demo-script.md`、`docs/defense-qa-card.md`、`docs/defense-runbook.md`。

S54 报告保留 **752** 作为冻结快照，不重写。

## 5. 未验证项（如实）

- **现场人工 GUI A–E**：仍未执行，`REGISTERED 0/5`、`NOT_RUN`；启动预检不等于人工验收。
- **逐页目视排版**：像素统计只能证明渲染出内容，页脚是否裁切仍需人眼看。
- **教师线下验收与评分**：未发生。
- **教学云平台上传**：未执行（`uploaded=false`）。
- 自测的「基本输入」项依赖 runner 提供一行标准输入；直接跑 `.lwt` 而不给输入时会得到一项 `[FAIL]`，这是有意的降级设计，已在脚本注释与功能清单中写明。
