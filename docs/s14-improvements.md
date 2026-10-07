# S14 改进与优化执行报告

> 状态：执行完成，等待主窗口审查。记录日期：2026-10-07。S14 不改变 LWT 语言语义，也不替代 S12 最终验收。

## 1. 基线、分支与范围

- 本地 `main` 基线：`e6c6f6d777158482985ec86cb5e8c5031bd9b2d4`。开工时在该提交建立 `stage/s14-quality-improvements`，仓库干净。
- 开工时 `git status -sb` 为 `main...origin/main [ahead 35]`；`git rev-parse origin/main` 与只读 `git ls-remote origin refs/heads/main` 均为 `de608f7fbf50946715d370df014657169eb8f26d`。远端仍停在旧 S4 基线，S14 未同步它。
- 第一项实现提交：`9361f37a5c9bcd2bc7d07bbbb24949e38b35d7b6`（`Add project integrity checks to CI`）。文档另行提交；最终阶段分支 SHA 以执行窗口交接记录为准。
- 本轮只做测试库完整性保障、确定性错误回归、CI 和状态文档。未修改 lexer、parser、AST、runtime 或语言规范；未改动 S11 性能 raw、报告和 S10 并发数据。

## 2. S13 风险逐项处置

| 风险 | S14 结论与证据 | 后续责任 |
|---|---|---|
| R-01：Python 3.10、受支持 Linux 格和远端 Actions 未验证 | 发现本机 Windows CPython 3.13.7，以及 WSL Ubuntu 24.04 / Linux CPython 3.12.3；本轮在两者运行完整黑盒、全量 unittest、应用/benchmark 定向测试、编译检查和应用 CLI，均通过。没有 Python 3.10 可执行环境；没有触发远端 workflow。 | S12 在目标最终提交上核验 GitHub Actions 的 Ubuntu/Windows × Python 3.10/3.13 四格。不得把 3.12 的 Linux 结果写成 3.10 结果。 |
| R-02：远端 `origin/main` 落后 | 开工时 `origin/main` 与远端实时值均为 `de608f7…`；S14 从本地已审查 `main` 创建分支，未推送、合并或改写远端历史。 | S12 在最终集成前重新读取 remote 状态并处理同步；本报告中的远端 SHA 是开工时观察值，不代表之后的实时状态。 |
| R-03：`read_text()` 权限拒绝未单独覆盖 | 新增 CLI 层 unittest，替换 `Path.read_bytes`，只对临时测试文件注入 `PermissionError`，不更改系统 ACL。程序通过 `lwt/runtime.py` 现有 `OSError` 映射报告 `RuntimeError`，位置 `1:6`，退出码 3，stdout 为空、stderr 符合诊断格式且没有 Python traceback。 | 代码路径已由可移植注入覆盖；可在 S12 演示机做可选现场 ACL 检查，但不再依赖该检查证明错误映射。 |
| R-04：课程“特色”不可被表述为全球唯一性证明 | 复核 README、正式规范、开发指南和课程映射；只描述 `record`、`when/otherwise`、`each`、`emit` 等语法组合及其项目设计，没有全球唯一性断言，无需改写相关宣传文案。 | S12 延续该表述边界。 |

## 3. 持久化项目完整性门禁

新增 [`tools/check_project_integrity.py`](../tools/check_project_integrity.py)，运行命令：

```console
python tools/check_project_integrity.py
```

实现复用 [`tools/run_tests.py`](../tools/run_tests.py) 的 `discover_cases()`，不复制已有规则。它沿用现有检查来验证 `.lwt`/同名 `.json` 配对、目录内容、JSON metadata、ID 的格式及全库唯一性、源文件可读性；随后扫描 `docs/test-matrix.md` 指向 `tests/cases/` 的 Markdown 链接，确认目标在测试目录内且属于发现到的有效用例文件。成功时输出稳定汇总；用例配置或矩阵链接错误时输出文件/行/用例线索并以非零码退出。

当前仓库结果为 `cases=194; matrix_links=287; referenced_cases=194`。这证明库存和链接结构完整；不会验证每条规范规则的语义充分性，也不会因为某个用例 ID 出现在矩阵中就判定语义覆盖充分。原有黑盒测试和人工覆盖审查仍是必要验证。

新增 [`tests/test_project_integrity.py`](../tests/test_project_integrity.py)，使用临时仓库验证有效配对与矩阵链接、缺失配对、重复 ID、非法 ID、悬空矩阵引用、引用越出测试目录，以及命令失败时写入 stderr 并返回非零。正式用例库不被测试用来制造错误。S13 已人工执行过的目录和矩阵结构核对现在可以重复运行。

GitHub Actions 在既有黑盒 runner 之前增加独立的 `Check project integrity` 步骤，四格仍是 Ubuntu/Windows × Python 3.10/3.13；原有 `python tools/run_tests.py` 命令、输出和退出码契约未修改。README 和 `project.md` 记录本地命令。工作流文件已更新，但 S14 没有推送分支，也没有远端 Actions 运行结果。

## 4. 权限错误确定性回归

[`tests/test_cli_permission_error.py`](../tests/test_cli_permission_error.py) 在同一进程调用公开 CLI `main()`：真实临时源文件正常读取，只有 LWT `read_text()` 请求的临时目标被 mock 成 `PermissionError`。测试断言完整 stderr 诊断、调用位置、退出码 3、stdout 空和 traceback 缺失。Windows CPython 3.13.7 与 WSL Linux CPython 3.12.3 均通过；未更改 ACL 或系统权限。

## 5. 性能边界

没有进行 runtime profiling，也没有 runtime 优化。S11 测量的是进程启动至退出的端到端时间；S13 没有定位到稳定的 runtime 热点。本轮没有具体、可验证的运行时优化假设，新增完整性检查与权限测试也不属于解释器性能路径，所以不以端到端比值推断热点，不运行无目标 profile，不改写 S11 raw/统计。没有前后性能数字可报告。

## 6. 验证记录

本机环境为 Windows CPython 3.13.7；另有 WSL Ubuntu 24.04 CPython 3.12.3。下表所列命令均在仓库工作树运行；WSL 命令对应 Ubuntu 24.04 的 Python 3.12.3。完整性定向测试为 7 项，权限错误定向测试为 1 项。

| 命令 | Windows 3.13.7 | Ubuntu 24.04 / Linux 3.12.3 |
|---|---|---|
| `python tools/check_project_integrity.py` | exit 0；194 cases、287 links、194 referenced cases | exit 0；同一汇总 |
| `python -m unittest discover -s tests -p "test_project_integrity.py" -v` | exit 0；7 项 | exit 0；7 项 |
| `python -m unittest discover -s tests -p "test_cli_permission_error.py" -v` | exit 0；1 项 | exit 0；1 项 |
| `python tools/run_tests.py` | exit 0；194/194 | exit 0；194/194 |
| `python -m unittest discover -s tests -q` | exit 0；219 项，OK | exit 0；219 项，OK |
| `python -m unittest discover -s tests -p "test_app.py" -q` | exit 0；25 项，OK | exit 0；25 项，OK |
| `python -m unittest discover -s tests -p "test_benchmark.py" -q` | exit 0；12 项，OK | exit 0；12 项，OK |
| `python -m compileall -q lwt tests tools bench` | exit 0 | exit 0 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | exit 0；246 行 | exit 0；246 行 |
| `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` | exit 0；6 条有效、1 条坏记录 | exit 0；相同应用结果 |

此外，`git diff --check` 通过；标准库脚本检查仓库 18 份 Markdown 的 413 个本地链接，断链为 0；项目完整性检查覆盖矩阵中的 287 个用例文件链接。实际可用的 Linux 格是 3.12.3，并非课程要求最低版本 3.10。Python 3.10、GitHub Actions 远端运行仍未验证。本轮没有查阅外部资料。

## 7. 变更文件

- `.github/workflows/tests.yml`：CI 增加项目完整性步骤。
- `tools/check_project_integrity.py`：项目用例库存和覆盖矩阵链接检查入口。
- `tests/test_project_integrity.py`：结构检查成功、失败和命令退出行为的临时目录测试。
- `tests/test_cli_permission_error.py`：注入 `PermissionError` 的 CLI 回归。
- `docs/s14-improvements.md`：本报告。
- `README.md`：本地检查命令、能力边界和 S14 状态。
- `project.md`：阶段状态、平台证据和命令入口。
- `阶段执行与审查路线图.md`：S14 执行结果及审查等待状态。
- `LWT大作业总体方案与复检.md`、`详细实施规划.md`：同步 S14 状态和质量保障进展。

## 8. 留给 S12 的事项与范围声明

1. 主窗口先审查 S14 分支、实现差异、测试与报告；审查通过后再决定 S12。
2. S12 在最终集成提交上触发/检查 GitHub Actions 四格，并实际确认最低受支持 Python 3.10 格；将平台和解释器版本写入结果。
3. 按 S12 要求从全新克隆做最终验收，检查此完整性命令、黑盒、全量 unittest、示例、应用、行数和性能材料；不能把当前工作树称作新克隆。
4. 重新核对 `origin/main`，之后按授权处理最终远端同步、PPT、演示、标签和交付。
5. 若演示环境允许，可选地观察真实 ACL 拒绝行为；确定性错误映射已有跨平台测试保护。

本轮没有制作或修改 PPT，没有执行 S12 最终新克隆验收，没有推送、合并、打标签或发布。阶段分支保留给主窗口审查。
