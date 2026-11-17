# 更新日志

本项目的所有重要变更都记录在此文件中。

格式基于 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。每条写给人看，细节与复算命令见所链接的阶段报告；本文件不是 `git log` 的摘抄。

## [Unreleased]

### Changed

- 答辩断言 `fresh-clone` 的期望黑盒数改为读取 manifest：原先写死 400，S54 黑盒增至 401 后它一直输出 MISS。自检的探针步骤与离线证据台改为优先读取 `reports/s56-hotfix/`，并显示记录路径与生成时间，旧记录不再冒充当天的通过。属于测试与工具问题，不是产品缺陷（S56.1，[发布报告 §8](docs/s56-release.md)）。

## [0.3.0] - 2026-11-17

### Added

- 映射类型 `dict`、结构化错误传播 `throw` / `finally`、交互入口 `python -m lwt --repl`（S42，[执行报告](docs/s42-execution-report.md)）。
- 规范 §11 协作式确定性并发：`spawn` / `join` / `yield()` / 通道，配合 `--schedule` / `--schedule-log` / `--schedule-replay` 记录并重放调度轨迹（S43，[执行报告](docs/s42-deterministic-concurrency.md)）。
- `python -m lwt --help` 与 `--version` 两个只在单独出现时生效的早退开关（S45，[最终加固报告](docs/s45-final-hardening.md)）。
- 并发有界调度探索与反例最小化工具 `tools/explore_lwt_schedules.py`、`tools/model_check_concurrency.py`（S46，[验证报告](docs/s46-concurrency-verification.md)）。
- 协议级 MCP 服务 `lwt/mcp_server.py`，提供 `lwt_check` / `lwt_run` / `lwt_profile` 三个工具；只做了协议级测试，没有做真实 MCP 宿主的端到端演示（S53，[报告](docs/s53-mutation-interface.md)）。
- 用 LWT 测试 LWT：38 项原生自测（断言函数 `expect` 用 LWT 编写）与 77 行逐项打勾的功能清单（S55，[报告](docs/s55-selftest.md)、[功能清单](docs/feature-checklist.md)）。

### Changed

- 启动惰性化：`--help` 1.256×、`hello` 1.224×；热路径纯执行在 N=5000 三类负载上 1.45–2.99×，任何负载无回归（S44，[性能报告](docs/s44-performance.md)、[优化台账](docs/s44-optimization-ledger.md)）。
- 黑盒用例 287 → 401；最后一项 `dict-display-insertion-order` 闭环了 S53 变异探针暴露的 dict 键序盲区（S54，[收口报告](docs/s54-closeout.md)）。
- 测试与工具链（不是产品缺陷，因此不列入 Fixed）：单命令 unittest 的失败运行另存，不再覆盖上一次成功证据（S53）；新克隆校验改为读取被克隆仓库 manifest 中的黑盒期望数（S54）。

### Fixed

- 通道重复投递（违反规范 §11.5）：接收者已阻塞时，`send` 先把值入队又直接交给接收者，导致下一次 `receive` 再次取到同一个值；改为有阻塞接收者时直接交接、不入队（S45，[最终加固报告 §6](docs/s45-final-hardening.md)）。

0.2 为 S42 内部里程碑（分支 `feature/lwt-core-0.2`），包内版本号当时仍为 0.1.0，未单独发布，内容并入 0.3.0。

## [0.1.0] - 2026-11-06

### Added

- S12 交付：解释器与核心语言（[语言规范](docs/language-spec.md)）、287 项黑盒（新克隆 287/287）、S11 正式性能报告（[reports/performance.md](reports/performance.md)）、给人和 Agent 用的[开发指南](docs/developer-guide.md)与 LWT 应用 [app/log_report.lwt](app/log_report.lwt)（[S12 交付报告](docs/s12-final-delivery.md)）。

[Unreleased]: https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/compare/v0.1.0...v0.3.0
[0.1.0]: https://github.com/05T1925/Interpreted-general-purpose-scripting-language-LWT/releases/tag/v0.1.0
