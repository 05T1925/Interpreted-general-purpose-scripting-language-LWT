# S52 课程口径对照：第 8 章任务 / 提交 / 评分

> 依据课件《第 8 章：课程回顾_大作业》页 14–29、《第 7 章：性能》7.1–7.2、《第 6 章：部署与排错》。本文件只做“口径 → 仓库证据 → 复算命令”的对照；现场 GUI、教师评分、PPT 渲染仍是未验证项。当前数字来源：`docs/delivery-manifest.json`（400 黑盒 / 731 unittest / 21 页）。

## 1. 第 8 章任务 1–5（“逐项打勾”）

| 任务 | 课件要求 | 仓库证据 | 一条复算命令 | 状态 |
|---|---|---|---|---|
| 1 解释器 | 解释型通用脚本语言，至少五类基本功能，体现特色 | `docs/language-spec.md` §1–§11；`lwt/`；400 项黑盒 | `python -m lwt examples/guide/hello.lwt` | 完成 |
| 2 黑盒测试集 | **用 LWT 测试 LWT**；覆盖全部功能；一个命令；测试名与功能清单一一对应，**缺一项不算完整覆盖** | 426 个 `tests/cases/**/*.lwt`（400 个 `.json`）；`docs/test-matrix.md` 的 §8 表（8.1–8.8）与 §9/§10/§11 小节映射；`tests/test_course_coverage_matrix.py` 机械门禁 | `python tools/run_tests.py` | 完成 |
| 3 性能测试 | LWT 脚本 vs 同功能 Python；同一机器同一负载；重点是测量方法 | S11 `reports/performance.md`（中位数）、S44 分层加速、**S52 `reports/s52-course-align/performance-space.json`（P95/P99 + 峰值内存）** | `python tools/compare_perf.py` | 完成（Ubuntu RSS 未验证） |
| 4 Agent 开发指南 | Skills/Rules 形式；覆盖运行方式、语法、语义、内置函数；**Agent 能否写对是指南试金石** | `.agents/skills/lwt-app/SKILL.md`、`docs/developer-guide.md`；S48 60 会话消融（区间含 0，观察性） | `python -m lwt --check examples/modules/main.lwt` | 完成（消融不外推因果） |
| 5 Agent 应用 | ≥200 行、功能完整；**重点不是凑行数，是协作过程** | 243 / 233 / 313 行 LWT 应用；`docs/agent-dev-log.md`、`docs/s42-app-dev-log.md`（需求→架构→编码→测试→文档→排错，人负责设计与审查） | `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | 完成 |

## 2. 提交内容 8 项

| # | 提交内容 | 仓库位置 | 状态 |
|---|---|---|---|
| 1 | 语法规则文档 | `docs/language-spec.md` | 完成 |
| 2 | 解释器源程序 | `lwt/` | 完成 |
| 3 | 完整黑盒测试集 | `tests/cases/`（400 项 / 426 个 LWT 脚本） | 完成 |
| 4 | 性能测试报告 | `reports/performance.md`、`reports/s44-performance/`、`reports/s52-course-align/` | 完成（补充测量） |
| 5 | 开发指南（人 + AI） | `docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md` | 完成 |
| 6 | Agent 应用与开发记录 | `app/log_report.lwt`、`app/concurrent_log_report.lwt`、`app/lwt_snake/game.lwt`、`docs/agent-dev-log.md` | 完成 |
| 7 | Git 历史 | `dist/` 的 bundle/zip（gitignore）+ 活跃索引 `reports/s48-defense/package-index.json` | 完成（包需现场重建或携带 `dist/`） |
| 8 | 系统介绍 PPT | `slides/LWT介绍.pptx`（21 页，第 10 页 12 数值点） | 静态完成；**未渲染** |

## 3. 评分 5 项（20/20/10/20/30）

| 分值 | 评分项 | 对应证据 | 自评边界 |
|---|---|---|---|
| 20 | 解释器实现 | §1–§11、400 黑盒、46×10 确定性 | 不与现存语言完全相同；未声称形式化证明 |
| 20 | 自动测试脚本 | 400/400；§8 逐项矩阵；426 个 LWT 脚本 | “完整”指规范可执行小节全覆盖，不含纯设计取舍（8.6/11.9） |
| 10 | 性能测试 | S11 正式 + S44 分层 + S52 分位数/空间 | 仍慢于 CPython；重点是测量方法与空间维度 |
| 20 | 语法说明 + 开发指南 | 规范 §1–§11、开发者指南、Skill | 指南有效性由 S48 观察性消融支撑，非因果证明 |
| 30 | Agent 应用 | 243/233/313 行 + 协作记录 | 行数可复算；功能完整由 CLI 复现，非口头声明 |

## 4. 第 7 章：观察 → 假设 → 验证

| 阶段 | 观察 | 假设 | 验证 | 结论/停手 |
|---|---|---|---|---|
| S11 | 端到端中位数 2.7–5.0×（未优化） | 差距主要来自解释器成熟度与热路径 | `compare_perf` 固定环境复测 | 不做无目标优化；先立基线 |
| S44 | 启动与热路径有可测开销 | 预分配/减少分派能降启动与执行 | 分层对照；达到门槛即停，无收益回滚 | 纯执行 1.45–2.99×、启动 1.26× |
| S52 | 中位数不足以描述尾部；空间未测 | 尾部与峰值内存能揭示规模效应 | 3 负载 × N=100/1000/5000，P95/P99 + tracemalloc/RSS | 见 `performance-space.md`；有界压力非 soak |

## 5. 第 6 章：排错七步与复盘的实例

S50 的两次“覆盖冻结证据”事故按第 6 章流程处理，并留下防复发改动：

1. **发现**：证据文件被新运行改写（日志/变更可见）；
2. **止血**：立即停止运行，`git show HEAD:` 还原；
3. **定位**：默认输出路径未区分阶段（`--out` 缺省）；
4. **根因**：工具默认值跨阶段复用，调用方未显式指定；
5. **修复**：默认输出改到当前阶段目录，调用一律显式 `--out`；
6. **验证**：还原后哈希/行数与提交态一致（24/24、719/717.466 s）；
7. **防复发**：报告记录事故与“禁止覆盖旧证据”红线，后续阶段先查路径。

## 6. S52 验证记录（红 → 绿）

| 项 | 结果 |
|---|---|
| 基线 400 黑盒 | **400/400**，`elapsed=249.539s`（S52 开工实测） |
| 文档一致性（旧规则） | 28/28 绿——但这是“日期豁免”漏洞下的绿 |
| 新覆盖门禁（红） | **20 个缺口**：18 个小节无 refs + §8.6/§11.9 无理由行；另无 §8 表、无“用 LWT 测试 LWT”声明 |
| 修后（绿） | `test_course_coverage_matrix` **5/5**；矩阵 §8 表 8 行；18 个既有用例补 `spec_refs`；`test_runner` 35/35 |
| 白名单 | `VALID_SPEC_REFS` 注册 §8.1–§8.6、§9.1–§9.5、§10.1–§10.5；未知 `12` 仍拒绝 |
| 性能补充 | `performance-space.json`：3 负载 × N=100/1000/5000 + 压力 N=1000/5000/20000；`peak_bytes_monotonic=true`；证据测试 4/4 |
| 探针（非 heavy） | **21/21 PASS**（`reports/s52-course-align/baseline-probe.json`） |
| 单命令全量 | **731 项 OK，exit 0，748.4 s**（`py -3.13`，Tk 8.6；`reports/s52-course-align/unittest-single-command.json`） |
| 自检 / CI | 待回填 |

**红→绿留证**：先只加 `tests/test_course_coverage_matrix.py` 并运行，报出 `§8.1…§11.9` 共 20 条缺口；随后登记白名单、给 18 个真实用例补 refs、补矩阵与声明，5/5 转绿。没有新增黑盒用例，也没有伪造 §8.6/§11.9 的可执行语义。

## 7. 未验证项（如实）

- 现场人工 GUI A–E：`REGISTERED 0/5`、`NOT_RUN`。
- 教师线下验收与评分：未发生。
- PPT 页脚渲染：只做 zip/XML 静态校验（21 页 / 12 点 / SHA），**未渲染**。
- Ubuntu 峰值 RSS：未在 CI 采集，JSON 的 `platforms.ubuntu.maximum_resident_set_kb = null`。
- 压力实验是有界规模扫描，**不是**长时间 soak，不证明 7×24 稳定。
