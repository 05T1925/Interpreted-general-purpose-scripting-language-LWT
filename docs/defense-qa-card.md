# LWT 答辩问答卡

| 提问 | 简要回答与可指向的证据 |
|---|---|
| 为什么不使用 Python `eval`/`exec`？ | LWT 有自己的词法、语法、AST 和运行时；`eval`/`exec` 会绕开语言的作用域、类型、位置诊断和黑盒契约。见 [规范](language-spec.md)和 `lwt/`。 |
| 语法如何解析？ | 手写词法器和递归下降 parser 按优先级生成 AST；`when/otherwise` 与块等遵循规范 EBNF。 |
| 变量/函数作用域？ | 词法作用域、块级局部绑定；函数可递归和前向调用；重复绑定与遮蔽按规范处理。 |
| `each` 与复合值？ | `each` 进入时对数组取浅快照，元素仍可能引用可变记录；数组和 record 相等按身份，显示处理循环引用。 |
| 短路与整数除法？ | `and`/`or` 要求布尔值并短路；整数 `/` 向负无穷取整，`%` 与其一致。 |
| 错误退出码？ | 正常 0，语法 2，运行时 3，CLI/文件 4。位置从 1 起，诊断在 stderr。 |
| 黑盒 400 例证明什么？ | 逐字节检查 393 项配对 `.lwt` 与 7 项 CLI 参数契约用例（`cli_args_override`），并由矩阵链接到规范（`referenced_cases=400/400`）；不能证明所有可能输入正确。 |
| 性能数字为何较慢？ | S11 在一台 Windows/Python 3.13.7 机器上每组每语言 10 次新进程；计时含启动、导入、解析和执行，不是纯解释器速度。历史源码摘要与当时提交匹配。 |
| 并发读取证明什么？ | 两层证据：S10 的旧证据是固定只读日志在 1、2、4 个**独立操作系统进程**输出一致，只说明外部编排的确定性；S43 新增的 `app/concurrent_log_report.lwt` 则是**LWT 语言级**协作并发，每个文件一个任务、按输入顺序归并，与 `app/log_report.lwt` 逐字节差分等价，并附 I/O 重叠性能实验（见 `reports/concurrency-performance.*`）。 |
| Agent 代码如何复核？ | 提示与产出链、独立策略源码、静态/协议检查、真实对局和新进程双层验真逐层留证；普通 SHA-256 不是签名。 |
| 游戏为何算 LWT 应用？ | `game.lwt` 计算移动、碰撞、食物、随机与计分；策略 `.lwt` 决定方向。Python 负责进程、协议、录制和绘图。原 Python Snake 另列。 |
| S41 见证证明范围？ | 对已验参考局按种子、咨询步和挑战者排序，在最多 32 次参考咨询内找到首个方向分歧；同一观察前缀与一步分支可重验。它不是全局最小反例，也不能推出策略胜率。 |
| 为什么不做抢占式多线程？ | LWT 用单令牌 + 宿主线程协作调度：五个调度点之外语句原子完成，`emit` 不半行、`x=x+1` 不中途被切。抢占式需要语句级钩子与锁，会破坏确定性重放与「无 spawn 零开销」。见规范 §11.1/§11.4 与 `lwt/concurrency.py`。 |
| 确定性怎么保证？ | 选择只看（就绪集合、策略、决策序号、PRNG 状态），不看时间/线程 id/字典序；fifo 用真 FIFO 队列，random:SEED 用自带 splitmix64。轨迹绑定源摘要、实参、策略、每条决策与输出摘要，重放逐项校验，篡改以 CliError/4 拒绝。见规范 §11.4 与 `reports/s42-schedules/`。 |
| GIL 下并发有什么意义？ | 意义在**等待型 I/O 重叠**与**交错可复现**，不是 CPU 加速：`read_text` 提交内部线程池、任务转 `io_pending`，批次屏障后按编号恢复；CPU 仍在单令牌下串行。Amdahl 上限 `1/(1-p)`（p 为 I/O 等待占比），实测四组对照见 `reports/concurrency-performance.*`。 |
| 创新点与既有工作边界？ | 既有 S38/S40/S41 的「分歧—见证—重放—验真」针对**策略决策**；S43 把它推广到**调度交错**：200 种子 found 2 类、absent 1 类、tampered 三种篡改被拒。不是新解释器 VM，也不改 S11 性能原始数字；见 `docs/s42-feasibility.md` 与三态摘要。 |
| 怎么测并发？ | 46 项 `concurrency` 黑盒（fifo 下输出确定）+ 19 项 `test_concurrency.py`（PRNG 向量、确定性 10×、I/O 批次屏障、死锁、线程无泄漏三路径、轨迹三态）+ `run_concurrency_determinism.py` 对 46 项各 10 次逐字节比对；全量 400/400，既有 354 项零回归。 |
| S44 优化后为什么端到端仍比 Python 慢？ | S11-v2 分层显示：慢在「解释器的节点分派 + 对象分配 + 包导入」这些结构性成本，纯执行已提速（N=5000 三负载 1.45–2.99×）但基线差距大。S44 优化的是启动导入与树遍历热路径，不是把解释器变成编译执行；端到端仍带 Python 启动和解析，不能把分层倍率说成端到端倍率。见 `reports/s44-performance/benchmark-v2.md`。 |
| S44 具体优化了什么？ | 四类：①非 spawn 程序不再导入 `lwt.concurrency`/`concurrent.futures`（惰性化，启动 `--help` 1.256×）；②热路径 AST 分派改用 `type() is` 精确判断、运算符集合提为模块常量；③INT 字面量解析期预解码、执行期直接取值；④小整数显示走 CPython `str(int)` 快路径。逐项假设/测量/保留或回滚见 `docs/s44-optimization-ledger.md`。 |
| 如何证明优化没改变语义？ | 四层：400 项黑盒逐字节不变、46×10 并发确定性稳定、S28 固定 profile 事件计数不变、`--check`/`--profile`/debugger/DAP/LSP 不回归；另加 `tests/test_dispatch_completeness.py` 保证每个 AST 节点类型都有分派分支、未知类型仍 `AssertionError`，6000 位/前导零/负数整数用例保持。P1-2 无收益已回滚，不留无证据改动。 |
| 为什么不做字节码 VM？ | S42 画像明确：先优化树遍历热点而非上 VM；VM 的首要价值是双后端交叉验证正确性，性能只是副产物，且结论绑定具体 CPython 版本（PEP 659 特化会改倍率）。S44 用最小风险的精确分派 + 字面量预解码已使纯执行三负载 ≥1.45×，无需引入新执行后端，也不污染 S11 正式性能口径。 |
| 并发与启动有什么关系？ | S43 并发模块（`concurrent.futures`/`hashlib`/`json`/`tempfile`）原本被 `runtime.py` 顶层导入，所有程序都要付约 100–200 ms 导入成本。S44 P0-1 把它拆到轻量 `_sched_support` + spawn 分支延迟加载：非 spawn 程序 `sys.modules` 无 `lwt.concurrency`，而 spawn 程序仍完整工作（`tests/test_startup.py` 断言）。这是「并发能力可选付费」，与并发语义无关。 |
| 版本为什么是 0.3.0？ | S42 给语言加了 dict/throw/finally/REPL，S43 加了规范 §11 的并发子语言——都是**新增语言特性**；S44 只是性能与导入结构。按语义化版本应升次版本，故 0.3.0（若认为 0.2 已含并发可用 0.2.1）。号由主窗口裁决，`docs/delivery-manifest.json` 是唯一来源，`lwt.__version__`、`--version`、规范标题、README 都由 `tests/test_doc_consistency.py` 校验一致。 |
| S44 性能和 S11 是什么关系？ | 两套**不同口径**：S11 是课程正式报告，测新进程端到端墙钟（含启动/导入/解析/执行），结论 2.7–5.0× 且明确「未实施解释器优化」；S44 是优化验证附录，用 micro_bench 单进程纯执行前后对照（N=5000 提升 1.45–2.99×）和 S11-v2 分层基准（端到端 1.48–1.79×）。原始数据互不覆盖，报告也不把端到端倍率说成纯执行倍率。 |
| `--help`/`--version` 是什么？ | S45 新增的 CLI 早退开关：只在**单独出现**时生效，退出 0，不执行任何 LWT 源码；`--` 之后的同名参数仍属于程序实参。S44 时代 `python -m lwt --help` 会当源路径报 FileError/4，那是历史行为，不能与 S45 的 exit 0 直接比；S45 启动重测单独保存在 `reports/s45-acceptance/startup.*`。 |
| Agent 盲测结果是多少？ | **未执行（NOT_RUN）**。任务书要求由用户开新的无上下文会话跑；执行窗口只准备了 6 题（`docs/agent-eval/tasks.json`）和客观判分器（`tools/run_agent_eval.py`），并用参考解验证过判分器能让 6 题 ALL_PASS（验证后删除参考解，避免污染盲测）。没有提交时判分器报 NOT_RUN，绝不填 pass@1。 |
| CI 和跨平台验证到哪一步？ | 本机实测 Python 3.13.14（计时/黑盒）与 3.13.7+Tk（unittest 664）；另用 3.11.16 跑了 compileall、`--version`、hello、`--check` 和定向单测。**本机没有 Python 3.10，Linux 只能靠 GitHub Actions**：S45 已推送功能分支并核对精确 SHA 的四格（S46 推送后按新 SHA 重查）；未跑过的环境如实写「未验证」，不把本地通过当 CI 通过。 |
| 现场 GUI 没验怎么办？ | 直接说「人工桌面 A–E 未验证」。给出替代证据：CLI 自检包 `python tools/run_acceptance_selfcheck.py`（Git/保护路径/完整性/黑盒/确定性/性能门槛/文档一致性/PPT 静态检查/有界调度探索）与 GUI 自动化测试；并列出待人工项：语义实验室、日志工作台、LWT Snake、S41 查看器、PPT 逐页播放、桌面无遮挡与输入归属。不用自动 GUI 测试冒充人工验收。 |
| 和随机种子 / CHESS 有什么区别？ | `random:SEED` 只做采样：每个种子一条交错，回答"这些采样里有没有分歧"；S46 的 `model_check_concurrency.py` 做**有界系统化枚举**：从每个 `ready` 备选集展开前缀，按前缀重跑，回答"在 max_runs × max_decisions 内，每条已发现路径是否满足不变量"。CHESS 一类工具会做状态空间去重与有界重复；本工具只做前缀去重、不建堆状态哈希，规模定位是小型程序，不宣称达到 CHESS 的覆盖保证。 |
| 为什么有界不是证明？ | 探索只在 `--max-runs/--max-decisions/--time-budget` 内枚举；`COMPLETE` 只表示"已发现的前缀全部跑完"，不代表所有可能调度都正确。预算耗尽写 `BUDGET_EXHAUSTED`，不写 PASS；报告与 PPT 都明确"有界探索 ≠ 形式化证明"。要更强保证需要状态空间建模、状态去重与归纳不变量，那是另一类工作。 |
| S45 的重复投递缺陷怎么被这类检查捕获？ | S45 的缺陷形状是"接收者已阻塞时 `send` 既交接又入队"，下一次 `receive` 又拿到同一元素。46 项黑盒与 S43 的 200 种子都没有这个形状，所以没暴露。S46 在 `tests/concurrency-model/` 放 `channel-exactly-once` 与 `channel-blocked-then-queued`，把"先 7 后 null / 1,2,null"写成不变量；`--mutant duplicate-delivery` 在工具进程内把 S45 的错误行为装回去，检查器在 clean 下 0 违反、mutant 下 4 个程序各 1 违反，最小前缀 `[]`，`--schedule-replay`（工具 harness）复现 `7\n7\n`。这证明检查器对"抽样没覆盖的形状"有效，同时明确是**合成故障注入**，不是当前产品 bug。 |
| 怎么证明 Agent 真能按指南写 0.3.0？ | S47 用 6 个全新子代理会话、6 个独立 detached worktree（基线 `6bc4b21`）做盲测：只发题目与允许文档，worktree 内删除 tasks.json/测试/应用。首轮 5/6 通过（pass@1=0.833），6 题都 0 运行失败；唯一失败是题面没规定 `throw` 的消息文本，澄清题面后单题复跑通过。产物在 `docs/agent-eval/submissions/`，判分器只查客观项。 |
| pass@1 是什么意思，样本量多大？ | 6 题各 1 个样本，pass@1 = 通过题数 / 6 = 5/6 ≈ 0.833。它是点估计，不是统计显著的能力结论；n=1 时无法外推 pass@k。失败题单独标注为题面缺陷，不把澄清后的复跑混进首轮。 |
| 为什么 main 此前没合？ | S42–S46 都是执行窗口完成、等待主窗口复核的阶段分支；按仓库规则未复核不合并、不推送 main。默认分支一直是 S12 的 `5027860`。S47 按主窗口裁决 B1 做 FF 合入并普通推送，精确 SHA 与 CI 四格单独记录。 |
