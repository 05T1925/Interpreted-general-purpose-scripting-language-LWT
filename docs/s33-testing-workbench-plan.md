# S33 提案：LWT 黑盒测试工作台

状态：阶段范围与原计划一致；S33 已通过主窗口复核并快进进入本地 `main`。实测、修复和交接见 [S33 主窗口复核](s33-main-review.md)及[执行报告](s33-testing-workbench.md)。后续先执行 [S34](s34-lwt-snake-plan.md)，S12 仍负责最终新克隆、PPT、现场验收和交付。

## 价值与范围

现有 `tools/run_tests.py` 可一次执行 287 项黑盒测试，但仅提供人读文本汇总。S33 在不改变默认一键入口和 LWT 语义的前提下，增加稳定的单项/类别选择与机器可读结果，再通过 VS Code Testing API 将用例按类别显示到 Test Explorer。用户可运行全部、类别或单项，定位 `.lwt` 源文件、看到精确 stdout/stderr/退出码差异，并对适用用例使用 S32 DAP 启动调试。

课程自动测试占 20 分；此功能提供更直观的测试证据和 Agent 修复闭环。它不替代原有公开 CLI 黑盒集，也不新增 LWT 语法。

## 契约

1. 保留无参数 `python tools/run_tests.py` 的输出和退出码。新增 `--list-json`、`--case ID`（可重复）、可选 `--category NAME` 和 `--format json`。先对完整 inventory 做严格配对/元数据/重复 ID 检查，再筛选；不存在的 ID/类别返回配置错误，不静默跑 0 项。
2. JSON schema 要有版本号、所选用例、仓库相对路径、类别、标签/规范引用、运行状态、退出码、耗时、失败细节；stdout/stderr 的原始字节用 Base64 表示，避免错误解码丢失黑盒字节契约。标准输出只含 JSON，配置诊断走 stderr。文本与 JSON 结果应来自同一 `run_case` 比较逻辑。
3. Test Explorer 使用官方 `TestController` / `TestItem` / `TestRunProfile`，在可识别的 LWT 仓库工作区注册。发现结果以 runner 的 `--list-json` 为权威；文件变动后刷新。Run 全部、类别、单项时精确处理 include/exclude、取消与进程失败，报告真实通过/失败/跳过状态。批量运行须避免为每项重复扫描完整 inventory；取消后不能留下仍在运行的被测 LWT 子进程。
4. Debug 首版仅用于预期成功、使用标准 `python -m lwt SOURCE` 入口、且 stdin 字节可严格 UTF-8 解码的 `.lwt` 配对案例；从已验证元数据构造 program、args、cwd 和 stdinFile，并交给 S32 DAP。5 个 `cli_args_override` 案例、预期错误案例及二进制非法 UTF-8 stdin 案例不显示或禁用调试入口并说明原因。临时 stdin 文件需清理；不得把 raw stdin 或其他敏感输入写入日志。调试启动本身不算测试通过，只有 runner 的比较结果可标为通过。
5. 不新增第三方 Python 依赖、不修改 LWT 解释器语义、不重写 287 个现有用例、不覆盖 S10/S11/S28/S29 原始证据。

## 验收

- Runner 新旧 CLI 契约测试：默认文本逐字兼容；列表不执行程序；单项/类别/全量筛选及 JSON schema；失败差异、timeout、配置错误、Unicode/空格路径。
- VS Code Node 单测与真实 Extension Host：Test Explorer 发现 287 项、按类别树展示、单项和批量运行、错误详情、取消、刷新、打开源文件、适用用例的 DAP 调试及不适用例的说明。
- 287/287 黑盒、项目完整性、全量 unittest、S30/S32 调试回归、扩展 `npm test`、VSIX 打包、CI 四格和文档链接均应按实际 SHA 记录。
- 完成后主窗口复核，再逐阶段集成。S12 保留现场 VSIX、GUI、PPT、新克隆与最终远端验收。

设计依据：[VS Code Testing API](https://code.visualstudio.com/api/extension-guides/testing)明确提供测试发现、运行、调试 profile、结果及差异显示；本项目继续以原公开黑盒 runner 和元数据为事实来源。
