# LWT 原生自测（用 LWT 测试 LWT）

- 脚本：`tests/selftest/lwt_selftest.lwt`（SHA-256 `1cb689ce87cc4d50…`）
- 命令：`python -m lwt tests/selftest/lwt_selftest.lwt`
- 结果：**38/38**，失败 0，退出码 0
- 结论：**PASS**
- 记录时间（UTC）：2026-11-11T18:28:14Z

## 逐项结果

| # | 结果 | 项目 |
|---:|---|---|
| 1 | PASS | 基本类型：整数算术与优先级 |
| 2 | PASS | 基本类型：整除与取余 |
| 3 | PASS | 基本类型：任意精度整数 |
| 4 | PASS | 基本类型：字符串拼接与 Unicode 长度 |
| 5 | PASS | 基本类型：布尔不是整数且无隐式转换 |
| 6 | PASS | 基本类型：str 与 emit 的值显示 |
| 7 | PASS | 数组：字面量、索引与长度 |
| 8 | PASS | 数组：push 追加元素 |
| 9 | PASS | 数组：按引用传递，别名修改可见 |
| 10 | PASS | 数组：嵌套下标 |
| 11 | PASS | 结构：record 声明、构造与字段访问 |
| 12 | PASS | 结构：字段可运行时写入 |
| 13 | PASS | 结构：显示按声明字段顺序 |
| 14 | PASS | 基本输入：input() 读取一行标准输入 |
| 15 | PASS | 基本输出：字符串拼接构成结果行 |
| 16 | PASS | 分支：when / otherwise |
| 17 | PASS | 循环：while 重复求值条件 |
| 18 | PASS | 循环：each 遍历数组 |
| 19 | PASS | 循环：break 与 continue |
| 20 | PASS | 函数：定义与调用 |
| 21 | PASS | 函数：递归 |
| 22 | PASS | 作用域：函数内更新外层绑定 |
| 23 | PASS | 特色：dict 显示与遍历按插入顺序 |
| 24 | PASS | 特色：dict has 判断键存在 |
| 25 | PASS | 特色：dict get 缺键返回默认值 |
| 26 | PASS | 特色：dict put / delete |
| 27 | PASS | 特色：dict 身份相等 |
| 28 | PASS | 特色：throw 与 attempt / recover |
| 29 | PASS | 特色：finally 在异常路径执行 |
| 30 | PASS | 特色：finally 在正常路径也执行 |
| 31 | PASS | 特色：模块导入 import |
| 32 | PASS | 特色：模块内函数调用 |
| 33 | PASS | 特色：并发 spawn 与 join 返回值 |
| 34 | PASS | 特色：通道 send / receive |
| 35 | PASS | 特色：通道关闭后 receive 返回 null |
| 36 | PASS | 特色：字符串 split |
| 37 | PASS | 特色：字符串 trim |
| 38 | PASS | 特色：字符串转整数 |

判定只依赖脚本自身输出的 `[PASS]/[FAIL]` 与末尾总数行；
本工具不重算任何断言，也不比对 Python 侧的期望输出。
