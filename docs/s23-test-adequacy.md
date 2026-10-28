# S23：黑盒测试强度审计与确定性语义性质验证

状态：**实施完成，等待主窗口审查。** 本阶段未开始 S12；没有合并、推送、改写 main、打标签或发布。

## 1. 基线与范围

- 仓库基线：本地已审查 main 为 aadb8f7a2348dad3205c523d4ab1cb4ad5bda063；S22 复核提交 761ce331b0257fe0128a6ba9b190c2ba6f9f30e1 是基线祖先。
- 分支：stage/s23-test-adequacy，从该本地 main 创建。开工时工作区干净，目标分支不存在。
- 远端：只读 `git ls-remote --heads origin main` 得到 `de608f7fbf50946715d370df014657169eb8f26d`；该提交对象已在本地，确认它是本地 main 的祖先，二者相差 84 个提交。本阶段未 fetch/pull/push，未改动远端。
- 环境：Windows 11 build 26200，CPython 3.13.7；解释器路径为 C:\Users\28641\AppData\Local\Programs\Python\Python313\python.exe。
- 基线实测：黑盒 194/194；完整性检查 194 cases、287 matrix links、194 referenced cases；unittest 286 项；compileall 退出码 0；app/log_report.lwt 有效 LWT 246 行。
- 课程依据：大作业内容.md 要求以 LWT 编写覆盖语言功能的完整黑盒测试集，并提供单命令执行；评分表把解释器自动测试脚本列为 20 分。S23 强化可复现性和故障发现能力，不替代语言实现、课程评分或最终验收。

本阶段边界是测试质量审计。性质检查及变异探针只补充证据；不改变正式语义，不将变异数量解释为真实缺陷率或正确性保证。

## 2. 高风险规范条款与覆盖

| 规范 | 基线黑盒证据 | S23 性质/探针 | 选择理由与结果 |
|---|---|---|---|
| §4.2 负数除法向负无穷取整，余数与除数同号或为零 | negative-floor-division-modulo、division-by-zero、modulo-by-zero | 结构化整数表达式；toward-zero 与错误余数变异 | 一个运算或符号错误会产生静默数值偏差；两个变异均被捕获。 |
| §3、§4.2 运算优先级、同级左结合、比较及布尔层级 | arithmetic-precedence、left-associativity、chained-comparison、right-associative-assignment | 节点树渲染为带必要括号的源码，并按节点 oracle 计算 | 验证生成源码保持树结构；覆盖固定表达式与有界随机树。 |
| §4.2 严格布尔类型、and/or 短路及右侧求值 | short-circuit-and、short-circuit-or、boolean-left-is-strict、boolean-right-is-strict、boolean-or-right-is-strict、boolean-and-right-evaluated、or-right-evaluated | fail() 副作用模板；去掉短路及放宽左值类型的变异 | 错误会改变执行路径或退出码；目标变异均被捕获。 |
| §4.2、§4.3 数组和 record 按对象身份相等，别名可观察 | arrays-identity-equality、record-instance-identity、different-record-types-not-equal | 别名模板；数组/record 结构相等变异 | 相同内容不代表同一个对象；数组和 record 的目标用例均捕获变异。 |
| §5 each 进入时浅快照并保留元素引用 | each-snapshot-append、each-snapshot-replacement、each-snapshot-keeps-object-reference、each-variable-reassignment-does-not-replace-element | 替换元素模板；实时遍历变异 | 迭代中修改源数组可能造成静默漏项或值变化；变异被捕获。 |
| §4.1、§5、§6 数组元素、record 字段、函数实参按源码顺序求值 | argument-evaluation-order、record-fields-evaluate-in-source-order、call-arguments-left-to-right-before-arity；新增 argument-evaluation-order-distinct-effects | 非对称实参副作用模板；逆序变异 | 发现旧实参案例的输入对称，新增可区分逆序的静态回归，详见第 5 节。 |
| §6 len 按 Unicode 码点计数；split、trim、to_int 边界 | len-unicode-codepoints、split-preserves-empty-fields、split-overlap-is-nonoverlapping、split-empty-separator、trim-only-ascii-whitespace、to-int-sign-and-leading-zero、to-int-plus-rejected、to-int-whitespace-rejected、to-int-empty-rejected | Unicode 长度与文本内置函数模板；UTF-8 字节长度变异 | ASCII 示例可能藏住长度口径错误；长度变异被捕获，其他边界已有逐项黑盒结果。 |

按“错误能否改变可观察输出或退出码”审视覆盖，而不是按某条规范链接了多少用例判断充分性。S23 未重复新增 split、trim、to_int 静态案例。

## 3. 确定性性质工具

新增工具：tools/run_semantic_properties.py。默认命令：

~~~text
python tools/run_semantic_properties.py --seed 20261028 --cases 150
~~~

生成内容和限制：

- 默认 seed 为 20261028；seed 范围为 0 至 2^32-1，表达式数范围为 1 至 2000。case-index 可单独运行指定零基表达式或模板；失败诊断会给可直接重跑的命令。
- 默认 150 个表达式含 10 个固定优先级、结合性和负数边界，以及 140 个由 random.Random(seed) 生成的算术、比较、布尔表达式。表达式树最大深度 4，整数叶范围 -9 至 9；输入及中间数值有界。
- 源码渲染器从节点优先级生成必要括号；oracle 对节点显式计算，不解析或执行 LWT 源码，不调用 Python eval()/exec()。负数除法以绝对值商/余数和符号推导 floor quotient；余数按 r = a - q*b 计算，并核对数学关系及符号，不复用解释器 runtime。
- 另有 6 个固定结构、部分由 seed 参数化的语义模板：短路副作用、数组/record 身份与别名、each 替换快照、非对称函数实参副作用、Unicode 码点长度、split/trim/to_int 边界。
- 完整运行把表达式合并为一个 LWT 程序，6 个模板各一程序，共 7 次公开 CLI 调用。每次使用 [sys.executable, "-m", "lwt", source_path]、显式仓库根 cwd、shell=False、UTF-8 源码与 stdio、5 秒 timeout；精确比较 stdout、stderr 字节及退出码。生成源码写入自动清理的临时目录。
- 失败输出包含 seed、case index、源码、预期/实际字节表示、退出码及重跑命令。固定 seed 全量重复两次，摘要 hash 一致。

两次完整运行摘要一致：

~~~text
semantic-properties: seed=20261028 expression_checks=150 semantic_checks=6 checks=156 programs=7 max_depth=4 leaf_range=[-9,9] timeout=5s
oracle_sha256=6d4f42d5db1e00ee555f2e915d989d20c6779fa7b467490e352d6b4e03a07ce0
semantic-properties: PASS programs=7 checks=156
~~~

性质检查是有限、确定的抽样，不是穷举、形式化证明或语言正确性保证。该工具不计入静态黑盒数；生成器和 CLI 路径另由 6 项 S23 unittest 检查。

## 4. 隔离故障探针

新增工具：tools/audit_semantic_mutants.py。命令为 python tools/audit_semantic_mutants.py。每项探针从实际 lwt/runtime.py 代码片段出发，要求 patch 目标唯一；在 TemporaryDirectory 中分别建立正确基线副本和单点变异副本，只复制 lwt/、项目 tools/run_tests.py 与指定 .lwt/JSON 对。正确副本先通过相同目标用例，随后 mutant 经项目 runner 和公开 CLI 执行。两边均验证 lwt.runtime.__file__ 指向对应临时副本。临时目录自动清理，正式工作树没有注入变异。

| 变异 | 目标用例 | 分类与实际差异 |
|---|---|---|
| / 从 floor 改为 toward-zero | negative-floor-division-modulo | killed；mutant stdout 为 -2、2、-2、-2，预期为 -3、2、-3、-2。 |
| % 对所有除数符号都返回非负余数 | negative-floor-division-modulo | killed；mutant stdout 为 -3、1、-3、1，预期为 -3、2、-3、-2。 |
| 去掉 and 的 false-left 提前返回 | short-circuit-and | killed；进入 fail("skip")，退出码 3，产生 RuntimeError。 |
| 去掉 or 的 true-left 提前返回 | short-circuit-or | killed；进入 fail("skip")，退出码 3，产生 RuntimeError。 |
| 数组和 record 身份比较改为结构比较 | arrays-identity-equality、record-instance-identity | killed；不同对象被误报为相等，输出 true/true 而不是 true/false。 |
| each 由浅快照改成实时源数组 | each-snapshot-replacement | killed；实际输出 1、8、[1, 8]，快照预期是 1、2、[1, 8]。 |
| 用户函数实参逆序求值 | argument-evaluation-order | survived；相同副作用实参仍输出 [1, 2] 和 2。见下方缺口分析。 |
| 相同逆序变异，改用不同副作用 | argument-evaluation-order-distinct-effects | killed；mutant 退出码 0，但输出 [22, 11]、[22, 11]，预期为 [11, 22]、[11, 22]。 |
| and 左操作数接受宿主 truthiness | boolean-left-is-strict | killed；mutant 成功并输出 true，规范用例要求 RuntimeError/3。 |
| len(string) 按 UTF-8 字节计数 | len-unicode-codepoints | killed；mutant 首行输出 7，规范码点结果为 3；数组长度仍为 2。 |

最终分类：killed=9、survived=1、equivalent=0、invalid=0。唯一 survived 是旧实参顺序用例单独运行；同一错误变异被新增案例击杀，因此最终静态测试集可以区分该回归。没有把这个比例当作总体质量指标。

## 5. 已证实的覆盖缺口与闭环

正式规范 §4.1、§5、§6 明确要求实参从左到右求值。旧案例以两个相同表达式 n = n + 1 调用函数。若运行时反向遍历，先算右侧得到 1，再算左侧得到 2；反向排列的形参值仍为 [1, 2]，所以旧案例无法观察顺序。

新增 tests/cases/control-functions/argument-evaluation-order-distinct-effects.lwt 和同名 JSON：两个调用分别向不同槽位写入不同值 11、22 并返回，再输出调用结果和副作用记录。标准 CLI 的预期 stdout：

~~~text
[11, 22]
[11, 22]
~~~

逆序 mutant 的 stdout：

~~~text
[22, 11]
[22, 11]
~~~

两边退出码均为 0，差异直接来自顺序语义，不是错误处理。测试矩阵 §4.1、§5、§6 均链接新案例并说明旧案例的对称问题。静态黑盒现有 195 项；原 194 项源码、metadata 和 expected 保持不变。

没有解释器语义偏差，没有 runtime 修复，也没有修改正式语言规范。课程作业原文、既定 S23 范围和 S12 交接一致。

## 6. 实际验证结果

环境为 Windows 11 build 26200、CPython 3.13.7。下表记录本阶段最终执行结果；基线数字见第 1 节。

| 命令 | 退出码与实际结果 |
|---|---|
| python tools/run_semantic_properties.py --seed 20261028 --cases 150（运行 1） | 0；156 checks、7 programs；hash 6d4f42d5db1e00ee555f2e915d989d20c6779fa7b467490e352d6b4e03a07ce0。 |
| 同一性质命令（运行 2） | 0；156 checks、7 programs；hash 与运行 1 逐字一致。 |
| python tools/run_semantic_properties.py --seed 20261028 --cases 150 --case-index 153 | 0；独立复跑非对称实参顺序模板，1 个 selected check、1 个程序；suite_checks=156。 |
| python tools/audit_semantic_mutants.py | 0；10 个有效探针，9 killed、1 survived、0 equivalent、0 invalid；逐项见第 4 节。 |
| python -m unittest discover -s tests -p test_semantic_properties.py -v | 0；6 项 S23 定向测试通过，包含生成确定性、数学 oracle、renderer、计数边界和公开 CLI 路径。 |
| python -m lwt tests/cases/control-functions/argument-evaluation-order-distinct-effects.lwt | 0；stdout 为 [11, 22] 和 [11, 22] 两行。 |
| python tools/run_tests.py | 0；195/195 通过。分类：arrays-records-each 32/32、builtins-text-io 43/43、cli-errors 13/13、control-functions 31/31、integrated 3/3、lexer-parser 42/42、values-operators 31/31。 |
| python tools/check_project_integrity.py | 0；195 cases、290 matrix links、195 referenced cases。 |
| python -m unittest discover -s tests -q | 0；Ran 292 tests，OK；基线为 286 项。 |
| python -m compileall -q lwt tests tools bench app | 0；无诊断。 |
| python tools/count_lwt_lines.py app/log_report.lwt | 0；246 行有效 LWT。 |
| git diff --check（分层提交前） | 0；无空白错误。Git 提示 `docs/s23-test-adequacy-plan.md` 工作副本 LF 将在后续 Git 操作时转换为 CRLF，不影响检查结果。最终提交后的 `git diff --check main...HEAD`、保护路径差异和干净状态由最终交接复核。 |

已对比 `main` 与阶段工作树：lwt/、docs/language-spec.md、app/log_report.lwt、tests/test_app.py、reports/app-concurrency.json、docs/app-concurrency.md、bench/results.json、reports/performance.md 均无差异。`git diff --name-status main -- tests/cases` 只列出本阶段新增的 `.lwt` 与 `.json` 配对；原 194 项用例未修改。`docs/test-matrix.md` 仅新增本次覆盖映射。

## 7. 文件、提交与保护边界

- tools/run_semantic_properties.py：有界表达式树生成、独立 oracle、真实 CLI、失败复现和确定性摘要。
- tests/test_semantic_properties.py：生成器/oracle 回归与小规模公开 CLI 集成验证。
- tools/audit_semantic_mutants.py：10 项显式临时副本探针、baseline-first 和模块导入路径核验。
- tests/cases/control-functions/argument-evaluation-order-distinct-effects.lwt 与同名 JSON：补齐 §4.1/§5/§6 的静态黑盒覆盖。
- docs/test-matrix.md：在实参源码顺序的三个规范行增加案例和说明。
- docs/s23-test-adequacy.md、docs/s23-test-adequacy-plan.md：阶段报告与状态。
- project.md、README.md、阶段执行与审查路线图.md、LWT大作业总体方案与复检.md、详细实施规划.md、docs/s12-final-delivery-plan.md：同步 S23 等待审查及 S12 未开始状态。

分层提交按性质测试、静态缺口/探针、报告与状态文档组织。已完成的前两笔提交为 `ae7ecbeb768c4b5903a2aa54662f9426d28ad97c`（性质工具与单元测试）和 `127b74d4471b00c4a36826d5c6b3b08cebaf2b4c`（变异审计、新增静态案例及矩阵）；报告与状态文档为第三笔，最终 HEAD 与提交后差异检查见执行窗口交接报告。S10/S11 证据没有重新生成；性能基准和并发工具均未运行。没有修改 runtime、语言规范、CI、应用代码或远端。

## 8. 限制与 S12 交接

- 固定 seed 和有限表达式数只验证生成的输入；无法覆盖的语法、超大整数、宿主资源耗尽和其他平台行为不因此得到保证。
- 10 项 probe 是人工选取的可解释代表，不是随机 mutation campaign；9/10 不是缺陷率、覆盖率或正确性分数。唯一 survivor 展示了旧测试输入的具体盲点，已由新增回归闭环。
- 本阶段只在 Windows CPython 3.13.7 执行；Python 3.10、Linux 和远端 GitHub Actions 未验证，也未查询实时远端状态。
- S21/S22 人工桌面验收遗留、新克隆验收、最终 Python/CI 矩阵、PPT、答辩演示、远端同步、标签与发布全部留给 S12；S12 仍未开始。
