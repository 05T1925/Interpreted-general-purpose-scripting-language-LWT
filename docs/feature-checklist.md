# LWT 功能清单与逐项打勾（课程第 8 章任务 2）

> 课程任务 2 的原文要求是：「测试脚本使用 ZS 语言编写——用 ZS 测试 ZS」「覆盖 ZS 语言的所有功能——包括任务 1 的五项基本功能与自己追加的特色功能」「一个命令执行所有测试，自动输出每一项的结果与总数」，并强调「**测试名与功能清单一一对应——逐项打勾，缺一项就不算完整覆盖**」。
>
> 本文件就是那张「功能清单」：每个功能项对应一个 **LWT 原生自测项**（名字与脚本输出逐字一致）、若干**黑盒用例**（边界与错误路径）和**规范小节**。打勾表示该功能项在两层验证中都可复算。

## 一条命令复算

```bash
python tools/run_selftest.py     # LWT 原生自测：逐项 [PASS]/[FAIL] + 末尾总数（38/38 全部通过）
python tools/run_tests.py        # 401 项黑盒：逐用例结果 + 分类汇总
```

- 自测脚本：[`tests/selftest/lwt_selftest.lwt`](../tests/selftest/lwt_selftest.lwt)（LWT 编写，断言函数 `expect` 由 LWT 的 `fn`/`when`/`emit` 实现）
- 自测证据：[`reports/s55-selftest/selftest.json`](../reports/s55-selftest/selftest.json)、[`selftest.md`](../reports/s55-selftest/selftest.md)
- 黑盒用例根目录：[`tests/cases/`](../tests/cases/)；规范小节映射见[覆盖矩阵](test-matrix.md)

两层验证的分工要讲清楚，避免重复计数的误解：**LWT 原生自测**证明「每个功能项在语言层面确实可用、名字与清单一一对应」；**401 项黑盒**证明「同一功能的边界、类型错误、错误恢复、CLI 行为正确」。前者是功能清单，后者是它的判别力来源（变异探针 19/19 见 [`reports/s54-closeout/mutation-report.json`](../reports/s54-closeout/mutation-report.json)）。

## 一、任务 1 的五项基本功能

| 功能项 | 打勾 | LWT 原生自测项 | 代表黑盒用例 | 规范节 |
|---|:--:|---|---|---|
| 整数与算术优先级 | ✅ | 基本类型：整数算术与优先级 | `arithmetic-precedence`、`left-associativity` | §2、§4 |
| 整除、取余与负数语义 | ✅ | 基本类型：整除与取余 | `negative-floor-division-modulo`、`division-requires-integers`、`modulo-by-zero` | §4.2 |
| 任意精度整数 | ✅ | 基本类型：任意精度整数 | `arbitrary-precision-integer`、`to-int-large-decimal` | §2.1 |
| 字符串拼接、长度与 Unicode | ✅ | 基本类型：字符串拼接与 Unicode 长度 | `integer-and-string-plus`、`len-unicode-codepoints`、`string-codepoint-comparison` | §2.2、§4.2 |
| 布尔与严格条件（无隐式转换） | ✅ | 基本类型：布尔不是整数且无隐式转换 | `boolean-left-is-strict`、`when-condition-strict`、`while-condition-strict` | §2.2、§5.2 |
| 值的显示与 `str` | ✅ | 基本类型：str 与 emit 的值显示 | `emit-and-str-match`、`display-control-characters` | §7 |
| 数组字面量、下标与长度 | ✅ | 数组：字面量、索引与长度 | `array-zero-index-and-nesting`、`array-upper-bound`、`array-noninteger-index` | §3.2、§4.3 |
| 数组 `push` 与引用语义 | ✅ | 数组：push 追加元素 | `push-mutates-and-returns-null`、`array-alias-and-assignment-value` | §3.2、§4.3 |
| 数组别名可见性 | ✅ | 数组：按引用传递，别名修改可见 | `array-alias-and-assignment-value`、`each-snapshot-keeps-object-reference` | §4.3 |
| 嵌套数组下标 | ✅ | 数组：嵌套下标 | `array-zero-index-and-nesting` | §4.3 |
| `record` 声明、构造与字段访问 | ✅ | 结构：record 声明、构造与字段访问 | `record-fields-accept-any-values`、`missing-record-field`、`unknown-record-type` | §3.3、§4.4 |
| 字段运行时写入与别名 | ✅ | 结构：字段可运行时写入 | `record-field-mutation-and-alias`、`record-instance-identity` | §4.4 |
| 结构显示按声明字段顺序 | ✅ | 结构：显示按声明字段顺序 | `record-field-declaration-order`、`record-self-cycle-display` | §7 |
| 基本输入 `input()` | ✅ | 基本输入：input() 读取一行标准输入 | `input-empty-line-and-eof`、`input-lf-and-crlf`、`input-final-line-without-lf` | §7 |
| 基本输出 `emit` | ✅ | 基本输出：字符串拼接构成结果行 | `emit-and-str-match`、`nonselected-branch-has-no-side-effect` | §5、§7 |
| 分支 `when / otherwise` | ✅ | 分支：when / otherwise | `when-otherwise`、`when-without-otherwise` | §5.3 |
| 循环 `while` | ✅ | 循环：while 重复求值条件 | `while-rechecks-condition`、`while-condition-strict` | §5.4 |
| 循环 `each` 遍历数组 | ✅ | 循环：each 遍历数组 | `each-snapshot-append`、`each-snapshot-replacement`、`empty-each` | §5.4 |
| `break` 与 `continue` | ✅ | 循环：break 与 continue | `while-break`、`while-continue`、`nested-loop-break`、`nested-loop-continue` | §5.4 |
| 函数定义与调用 | ✅ | 函数：定义与调用 | `function-forward-call`、`function-arity`、`builtin-name-is-not-keyword` | §5.1 |
| 函数递归 | ✅ | 函数：递归 | `recursive-factorial`、`mutual-recursion` | §5.1 |
| 作用域与外层绑定 | ✅ | 作用域：函数内更新外层绑定 | `assignment-updates-nearest-binding`、`block-shadow-and-lifetime`、`function-local-lifetime` | §5.5 |

## 二、LWT 追加的特色功能

| 功能项 | 打勾 | LWT 原生自测项 | 代表黑盒用例 | 规范节 |
|---|:--:|---|---|---|
| `dict` 字面量与插入序显示 | ✅ | 特色：dict 显示与遍历按插入顺序 | `dict-display-insertion-order`、`dict-literal-display-order`、`dict-put-update-keeps-position` | §3.4、§4.6 |
| `dict` 键存在判定 | ✅ | 特色：dict has 判断键存在 | `dict-has-true`、`dict-has-false`、`dict-has-non-dict` | §7 |
| `dict` 缺键默认值 | ✅ | 特色：dict get 缺键返回默认值 | `dict-get-missing-default`、`dict-get-default-expression`、`dict-get-present` | §7 |
| `dict` 增删与长度 | ✅ | 特色：dict put / delete | `dict-put-new-append`、`dict-delete-present`、`dict-delete-missing`、`dict-len` | §4.6、§7 |
| `dict` 身份相等 | ✅ | 特色：dict 身份相等 | `dict-identity-equal`、`dict-identity-not-equal`、`dict-neq-identity` | §4.5 |
| `throw` 与 `attempt/recover` | ✅ | 特色：throw 与 attempt / recover | `throw-string-recovered`、`recover-type-error`、`recover-nearest-handler` | §10.2–§10.4 |
| `finally` 异常路径必执行 | ✅ | 特色：finally 在异常路径执行 | `finally-handler-emits-then-fin`、`finally-overrides-body-return` | §10.5 |
| `finally` 正常路径也执行 | ✅ | 特色：finally 在正常路径也执行 | `finally-on-normal-flow`、`attempt-normal-flow` | §10.5 |
| 错误 `category` / `message` | ✅ | 特色：throw 与 attempt / recover | `uncaught-throw-error-category`、`recover-error-fields-display`、`throw-error-rethrow` | §10.3 |
| 模块 `import` | ✅ | 特色：模块导入 import | `simple-alias-call`、`same-name-namespaces`、`missing-dependency-no-partial-output` | §9 |
| 跨模块函数调用 | ✅ | 特色：模块内函数调用 | `module-call-result-not-callable`、`multi-level-relative-import` | §9 |
| 协作式并发 `spawn` / `join` | ✅ | 特色：并发 spawn 与 join 返回值 | `spawn-join-return`、`spawn-multi-args`、`join-reraises-location` | §11.2–§11.3 |
| 通道 `send` / `receive` | ✅ | 特色：通道 send / receive | `channel-fifo`、`channel-multi-producer`、`channel-block-receive` | §11.5 |
| 通道 `close` 与排空 | ✅ | 特色：通道关闭后 receive 返回 null | `channel-close-drain`、`channel-close-idempotent`、`channel-send-closed-error` | §11.6 |
| 字符串 `split` | ✅ | 特色：字符串 split | `split-preserves-empty-fields`、`split-overlap-is-nonoverlapping` | §7 |
| 字符串 `trim` | ✅ | 特色：字符串 trim | `trim-only-ascii-whitespace`、`trim-arity` | §7 |
| 字符串转整数 `to_int` | ✅ | 特色：字符串转整数 | `to-int-sign-and-leading-zero`、`to-int-whitespace-rejected`、`to-int-plus-rejected` | §7 |
| 确定性调度与轨迹重放 | ✅ | 特色：并发 spawn 与 join 返回值（最小形态） | 46 项 `concurrency` 用例 + [`reports/s42-schedules/`](../reports/s42-schedules/summary.md) | §11.4 |

> 说明：`dict` 的存在性判定、`finally` 的正常/异常两条路径，在自测里各拆成独立项，因此自测项数（38）多于上表的功能行数；这是「一项功能多条断言」而不是「重复计数」。上表每一行的自测项名字都**逐字**出现在 `python tools/run_selftest.py` 的输出里，可直接核对。

## 三、课程任务 2 三点要求 → 证据

| 课程要求 | 仓库证据 | 复算命令 |
|---|---|---|
| 测试脚本使用 LWT 编写（用 LWT 测试 LWT） | `tests/selftest/lwt_selftest.lwt`：断言函数 `fn expect(cond, name)` 由 LWT 实现；另有 427 个 `.lwt` 黑盒程序 | `python tools/run_selftest.py` |
| 覆盖所有功能（五项基本功能 + 特色功能） | 本文件两张表共 40 行、全部打勾；黑盒 401 项覆盖 §1–§11（含 §8 规范性示例） | `python tools/run_tests.py`；[覆盖矩阵](test-matrix.md) |
| 一个命令执行所有测试，输出每项结果与总数 | `run_selftest.py` 打印 38 行 `[PASS]` 与 `38/38 全部通过`；`run_tests.py` 打印 401 项与分类汇总 | 同上 |

## 四、没有做的事（如实）

- 本清单**不是**形式化证明：它证明「清单里的每一项都有可执行证据」，不证明「语言没有其它缺陷」。缺陷发现依赖黑盒边界用例与 19 条语义变异探针（[`reports/s54-closeout/mutation-report.json`](../reports/s54-closeout/mutation-report.json)）。
- 自测的「基本输入」项需要一行标准输入；直接运行 `.lwt` 而不提供输入时该项会打印 `[FAIL]`，这是**有意的降级**（不会中断整套测试），一键命令 `python tools/run_selftest.py` 会自动提供 `42\n`。
- 并发在自测里只做最小形态（`spawn`/`join`/通道收发），完整交错语义由 46 项并发黑盒与有界模型检查负责，见[并发契约卡](concurrency.md)。
