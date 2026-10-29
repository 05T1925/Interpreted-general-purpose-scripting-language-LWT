# S25 执行报告：可验证的多文件函数模块

**阶段状态：实施完成，等待主窗口审查。** 本报告记录阶段分支上的实际实现和验证，不代表主窗口已批准或合并。S25 未合并、未推送、未开始 S12，也未修改 S10/S11 原始证据。

## 基线、分支与提交

| 项目 | 实际状态 |
|---|---|
| 仓库目录 | `C:\Users\28641\Desktop\大三上\程序设计实践\大作业` |
| S25 基线 | S24 tip `5f899d952bacc91e22e1db99dba6e369153bdbc6`，分支 `stage/s24-loop-control`；开工时工作区干净。 |
| S25 工作分支 | `stage/s25-modules`，从上述本地 S24 tip 建立；未从落后的远端创建或重置。 |
| 本地 `main` | `aadb8f7a2348dad3205c523d4ab1cb4ad5bda063`。S24 tip 不是本地 `main` 的祖先，故 S24 尚未合入；本报告不声称 S24/S25 已合并。 |
| 远端只读核对 | 本地 `origin/main` 与 `git ls-remote --heads origin main` 均为 `de608f7fbf50946715d370df014657169eb8f26d`，是本地 `main` 的祖先；本地 main 相对 origin 为 ahead 84 / behind 0。未 fetch、pull、push 或同步远端。 |
| 分层提交 | `0e769e07e3cc5aa32fddcd48be3dc016fc0c99e5`：模块实现与定向单测；`dab34bfd8c12305fad2b8542407f23a75f196e1e`：初始黑盒用例、runner 与变异审计探针适配；`99895dc658b0620bd26e328eda68133627d0d921`：模块调用结果不可继续调用的黑盒反例；第四层为示例、规范、指南、阶段报告和状态文档，最终 SHA 在执行交接中列出。 |
| 最终工作区 | 阶段提交后应保持干净；未合并、未推送。 |

## 设计和实现

S25 实现的是声明式静态函数库子集。入口文件可以导入模块、声明 `record` 和函数并执行普通语句。库文件只能在开头导入依赖，之后声明函数；库文件不能定义 `record`、顶层变量或任何可执行语句，因此导入不会执行模块初始化代码。

- 新语法是保留字 `import` 和 `import "相对路径" as alias;`。导入必须位于入口/模块的连续前置区；限定函数调用写作 `alias.name(arguments)`。`as` 是上下文词。新增 `import` 保留字会让过去同名的变量、参数或函数声明变为语法错误，新增黑盒反例已锁定此兼容性变化；对 S24 基线 `.lwt` 文件做 `git grep`，未发现既有 `import` 标识符冲突。
- 每条路径相对声明它的文件目录解析，允许 `..`、空格和 Unicode；入口路径仍相对进程工作目录。绝对路径、目录、缺失文件、不可读文件和非法 UTF-8 在依赖导入处形成退出码 4 的单行错误。`read_text()` 仍相对进程 cwd。
- Loader 先读取、严格 UTF-8 解码、扫描并解析完整静态依赖图，再链接 alias/member。规范化 canonical path 用于去重；同一文件可由不同 alias 引用且只解析一次。直接循环、间接循环及依赖反向导入入口都在入口执行前拒绝，诊断包含 import 位置和依赖链。任何加载/解析/链接失败均不会留下入口 stdout。
- 每个源文件有独立函数表和变量根环境。未限定函数调用查找所属模块自身和内置函数，不会导入主程序/调用者的名字，也不捕获调用者局部作用域；函数可前向调用、递归或相互调用。限定调用的目标函数在其所属模块上下文中运行，后续依赖调用使用该模块自己的 alias 表。
- 数组和 record 作为既有 LWT 引用值传参，允许模块修改传入对象。各模块共享同一进程级 stdout、stdin 和 `args()`；`read_text()` 路径规则不变。模块不能定义 record 类型，但能接收并访问入口构造的 record。
- SourceLocation 增加可选 source path，Token 与 AST 延续该身份。入口诊断仍按 CLI 原始 source 参数显示；模块诊断按入口目录相对路径显示，分隔符统一 `/`，行列从 1 开始。模块内词法/语法错误退出码 2，运行时错误退出码 3；错误路径指向真实模块源码。
- 运行时对整个模块图预登记函数并进行 AST capability/link 检查，再执行入口普通语句。禁止以 Python `eval()`/`exec()` 执行 LWT 源码；这是宿主实现约束。

选择这组小语义是为了让导入路径、执行顺序、命名空间和错误来源都可预测；没有引入完整包管理、动态导入、from/star 导入、模块值、循环代理或顶层初始化状态。

## 黑盒覆盖与示例

黑盒从 S24 的 217 项增至 **247 项**：`modules` 30 项；其它类别保持 `arrays-records-each` 32、`builtins-text-io` 43、`cli-errors` 13、`control-functions` 43、`integrated` 3、`lexer-parser` 52、`values-operators` 31。当前集合有 **242 个配对 LWT 程序和 5 个 CLI argv override**。S8、S23、S24 的历史快照在矩阵中单独保留。

新增模块案例 ID：

`module-alias-is-not-value`、`module-array-record-aliasing`、`module-call-result-not-callable`、`module-cannot-call-main-function`、`module-cannot-read-main-global`、`module-direct-cycle`、`module-directory-dependency`、`module-dot-dot-module-path`、`module-duplicate-alias`、`module-entry-self-cycle`、`module-forward-recursion`、`module-import-after-top-level-item`、`module-import-in-function`、`module-import-reserved-identifier`、`module-indirect-cycle`、`module-missing-dependency-no-partial-output`、`module-module-lexer-source-location`、`module-module-parser-source-location`、`module-multi-level-relative-import`、`module-process-io`、`module-runtime-source-location`、`module-same-name-namespaces`、`module-simple-alias-call`、`module-top-level-emit`、`module-top-level-let`、`module-top-level-record`、`module-undefined-alias-link-error`、`module-undefined-member-link-error`、`module-unicode-space-module-path`、`module-unqualified-import-is-not-visible`。

额外定向 CLI 集成测试验证 Windows/POSIX 绝对路径拒绝、含 NUL 的无效路径、非法 UTF-8 依赖在任何入口输出前失败、模块 `read_text()` 仍使用进程 cwd、同一 canonical 文件多个 alias。Parser 单测验证 import/限定调用/record 字段 AST 的区分和库文件顶层限制；runtime/loader 单测验证模块错误位置和 canonical 去重。模块定向 unittest 共 9 项。

开发中的首次定向测试曾暴露测试夹具自身问题：测试文件漏导入 `io`；后续用例把保留内置名 `fail` 当作用户函数名；NUL 路径测试最初写成 LWT 不支持的 `\0` 转义。分别补导入、改用普通函数名 `explode` 并直接在字符串字面量写 NUL 后，测试符合预期；未放宽语言实现或断言，最终模块定向单测为 9/9。最后补入的非法链式模块调用黑盒初次运行时只发现期望诊断文案写错：实际稳定输出为 `expected ';' after emit statement`；修正 JSON 期望后，完整运行器实测 247/247 通过，没有改动实现代码。

新增可复现多文件演示 `examples/modules/main.lwt`、`stats_utils.lwt`、`text_utils.lwt`，体现两层依赖、别名调用和数组/record 参数。实际公开 CLI 命令：

```powershell
python -m lwt examples/modules/main.lwt
```

Windows CPython 3.13.7 实际退出码 **0**，stdout 为 `demo:2\n`，stderr 为空。S24 循环控制示例仍可通过：

```powershell
python -m lwt examples/loop_control.lwt
```

实际退出码 **0**、stderr 为空，stdout 为 `1\n3\n2\n[1, 2, 3, 4]\n`。

## 实际验证结果

环境为 Windows、CPython 3.13.7。`py -0p` 显示本机有 Python 3.11、3.12、3.13，但没有 Python 3.10；S25 新增语义未在 Python 3.10 或 Linux 上实跑，远端 GitHub Actions 也没有运行。

| 实际命令 | 退出码与结果 |
|---|---|
| `python tools/run_tests.py` | 0；247/247 通过，0 失败。分类：32/32、43/43、13/13、43/43、3/3、52/52、模块 30/30、31/31；耗时 30.732 秒。 |
| `python tools/check_project_integrity.py` | 0；`cases=247; matrix_links=344; referenced_cases=247`。 |
| `python -m unittest discover -s tests -q` | 0；308 项，`OK`。 |
| `python -m unittest tests.test_parser tests.test_runtime tests.test_modules -q` | 0；40 项通过，包含新增 parser、模块 loader/runtime 与子进程边界测试。 |
| `python -m unittest discover -s tests -p "test_app.py" -q` | 0；S10 应用契约测试 25 项通过。 |
| `python -m compileall -q lwt tests tools bench app` | 0；无编译诊断。 |
| `python tools/run_semantic_properties.py --seed 20261028 --cases 150` | 0；150 个表达式和 6 个语义检查，共 156 项/7 个 CLI 程序；oracle SHA-256 `6d4f42d5db1e00ee555f2e915d989d20c6779fa7b467490e352d6b4e03a07ce0`。 |
| `python tools/audit_semantic_mutants.py` | 修正探针选择后退出码 0；10 项中 9 killed、1 survived、0 equivalent、0 invalid。存活的是原有对称参数顺序用例；不对称副作用用例击杀逆序变异。首次运行出现 2 个 invalid，因为增加模块限定调用后同一代码片段出现两个位置；将探针锚定到普通 `CallExpression` 专属注释后复跑通过，没有改动 runtime 来迁就审计。 |
| `python -m lwt examples/modules/main.lwt` | 0；stdout `demo:2\n`，stderr 空。 |
| `python -m lwt examples/loop_control.lwt` | 0；stdout `1\n3\n2\n[1, 2, 3, 4]\n`，stderr 空。 |
| `python tools/count_lwt_lines.py app/log_report.lwt` | 0；246 行有效 LWT。 |
| `git diff --check` 与 `git diff --check 5f899d952bacc91e22e1db99dba6e369153bdbc6...HEAD` | 最终提交后执行；均应无空白错误。PowerShell/Git 对 LF 文件给出的 CRLF 转换提示不是检查失败。 |
| Markdown 链接、围栏及 Skill metadata | 0；检查 12 份文档/Skill 共 632 个相对链接，0 个缺失目标、0 个围栏错误，Skill YAML frontmatter 分隔符有效。 |
| S10/S11 保护差异 | `git diff --quiet 5f899d952bacc91e22e1db99dba6e369153bdbc6 HEAD -- app/log_report.lwt tests/test_app.py reports/app-concurrency.json docs/app-concurrency.md bench/results.json reports/performance.md` 退出码 0；保护内容未变。 |

性质测试和变异审计仅为有限确定性证据，不构成穷举证明。没有运行 `tools/run_app_concurrency.py` 或正式性能基准；没有将应用耗时称为解释器性能结论。LWT 应用仍为 246 行，`tests/test_app.py` 仍有原 25 项。相对 S24 的现有黑盒源文件没有修改或放宽；新增语义均在 `tests/cases/modules/` 中。

## 文档和文件清单

| 文件 | 修改内容 |
|---|---|
| `lwt/ast_nodes.py`、`lwt/lexer.py`、`lwt/parser.py`、`lwt/errors.py`、`lwt/cli.py`、`lwt/runtime.py` | AST、保留字/token source path、模块语法与限定调用、来源位置、模块图预载和每文件执行命名空间。 |
| `lwt/modules.py` | 新增静态 loader/linker：UTF-8 读取、路径验证/规范化、去重、循环检测及错误归属。 |
| `tests/test_modules.py` | 新增 9 项 parser、loader/runtime 和公开 CLI 边界单测。 |
| `tests/cases/modules/` | 新增 30 对黑盒元数据/程序及只供这些程序导入的 fixtures；`tools/run_tests.py` 排除任意层级 `fixtures/`。 |
| `tools/run_tests.py`、`tests/test_runner.py` | 接受规范 §9、验证嵌套 fixtures 排除规则；新增 runner 回归。 |
| `tools/audit_semantic_mutants.py` | 将参数顺序变异探针锚定普通未限定调用块，避免与新增限定调用实现产生重复匹配。 |
| `examples/modules/main.lwt`、`examples/modules/stats_utils.lwt`、`examples/modules/text_utils.lwt` | 新增可由公开 CLI 执行的两层函数库演示。 |
| `docs/language-spec.md`、`docs/developer-guide.md`、`.agents/skills/lwt-app/SKILL.md` | 正式语法/语义、模块目录指导、路径/命名空间/错误规则及 import 保留字兼容性说明。 |
| `docs/test-matrix.md` | 课程要求映射、30 项模块覆盖和当前/历史测试数量。 |
| `README.md`、`app/README.md`、`project.md`、`详细实施规划.md`、`LWT大作业总体方案与复检.md`、`阶段执行与审查路线图.md` | 模块示例入口与 S25 待审状态；S12 保持最后阶段。 |
| `docs/agent-dev-log.md`、`docs/s25-modules.md` | 阶段开发记录和本报告。 |

对旧“模块不支持”文字逐项搜索后，当前规范、指南和规划只说明不支持**完整包系统**及明确排除的动态/from/star/循环依赖等能力；保留既有历史阶段当时状态，不做全仓替换。实现没有使用 Python `eval()`/`exec()`。

## 遗留和交接

- Python 3.10、Linux、远端 Actions 未验证；Python 3.12 本机虽已列出，但本阶段只执行 CPython 3.13.7 完整验证。
- 主窗口需要独立审阅模块语义、测试矩阵和新增保留字兼容性；本地测试通过不等于最终跨平台验收。
- S24 仍未合入本地 `main`，S25 延续其阶段 tip；请先审查 S23–S25，再按计划进入 S12。
- 未合并、未推送、未制作 PPT、未开始 S12；最终状态为 **S25 实施完成，等待主窗口审查**。
