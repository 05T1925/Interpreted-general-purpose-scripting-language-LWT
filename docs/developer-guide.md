# LWT 开发指南

本指南面向第一次使用 LWT 的人和编程 Agent，介绍如何启动解释器、编写小程序、核对运行结果和查找语义。**语言规则以 [LWT 0.1 正式语言规范](language-spec.md) 为准**；本指南只做操作性摘要。

## 1. 先运行

本项目解释器使用 Python 3.10+ 标准库，不需要安装第三方依赖。从仓库根目录打开终端：

```powershell
python --version
python -m lwt examples/guide/hello.lwt
```

成功时 stdout 为：

```text
hello, LWT
42
```

`examples/guide/hello.lwt` 是完整可运行程序。运行 `.lwt` 文件应始终使用公开入口 `python -m lwt`，而不是把 LWT 内容当作 Python 执行。

### CLI、参数和输入

命令形式：

```text
python -m lwt SOURCE [-- ARGS...]
```

- `SOURCE` 是源文件路径；相对路径以进程当前工作目录为基准。
- `--` 之前是解释器 CLI 参数，之后的原样参数属于 LWT 程序。没有 `--` 时不能在源文件后添加参数。`--` 不会传给程序，源文件名也不包含在程序参数中。
- 在 LWT 中用 `args()` 读取参数；它返回一个新的字符串数组。例子见 [text_tools.lwt](../examples/text_tools.lwt) 的运行命令。
- `input()` 从标准输入读取一行；去掉 LF 以及紧邻它之前的一个 CR，末行没有 LF 时保留原文，空行返回空字符串，EOF 返回 `null`。读取失败是运行时错误。
- `read_text(path)` 读取整个 UTF-8 文本文件。相对路径也以**进程当前工作目录**为基准，不以 `.lwt` 文件所在目录为基准。文件开头一个 BOM 会去除，CRLF/CR 会规范成 LF。

从仓库根目录运行文本示例：

```powershell
python -m lwt examples/text_tools.lwt -- examples/fixtures/text_tools.txt preview
```

当前示例 stdout：

```text
2
[12, "apple", 5]
[7, "pear", 4]
```

### 退出码和诊断

| 退出码 | 含义 | 常见例子 |
|---:|---|---|
| 0 | 程序成功完成；空程序也成功 | `emit 42;` |
| 2 | 词法或语法错误 | 非法字符、未知字符串转义、缺分号、非法左值 |
| 3 | 运行时错误 | 未定义变量、类型错误、越界、除零、`fail()` |
| 4 | CLI 或源文件读取错误 | 缺少源文件参数、路径不存在、源文件不是有效 UTF-8 |

源码错误写入 stderr，格式为 `<源路径>:<行>:<列>: <错误类别>: <消息>`；CLI/源文件错误写入 stderr，格式为 `lwt: <错误类别>: <消息>`。行和列从 1 开始。stdout 只放 `emit` 的结果；错误不应产生 Python traceback。可用下面的既有坏例查看一条实际词法诊断：

```powershell
python -m lwt tests/cases/cli-errors/lex-location-invalid-character.lwt
```

它应以退出码 2 结束，诊断形如：

```text
tests/cases/cli-errors/lex-location-invalid-character.lwt:1:6: LexError: unexpected character U+0040
```

实际错误消息和触发位置由输入决定；完整规则见规范第 7 节。

## 2. 从小程序开始

### 值、变量、表达式和注释

[`examples/guide/hello.lwt`](../examples/guide/hello.lwt) 是完整文件：

```lwt
# A complete first program: comments, values, variables, expressions, and output.
let name = "LWT";
let answer = 6 * 7;
emit "hello, " + name;
emit answer;
```

它展示整数、字符串、变量声明、整数乘法、字符串拼接、注释和 `emit`。变量用 `let name = expression;` 声明，后续用 `name = expression;` 赋值。分号必须写出。LWT 还支持布尔、`null`、数组和命名 `record`。

### 分支、循环和函数

下列都是从现有完整示例中摘出的**代码片段**；请运行链接中的完整文件查看上下文和输出。

分支和循环片段（完整程序：[control_flow.lwt](../examples/control_flow.lwt)）：

```lwt
while (i < 4) {
    when (i % 2 == 0) {
        emit i;
    } otherwise {
        emit -i;
    }
    i = i + 1;
}
```

函数调用和递归片段（完整程序：[functions.lwt](../examples/functions.lwt)）：

```lwt
emit factorial(5);

fn factorial(n) {
    when (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
```

函数只在顶层声明；声明会在顶层普通语句执行前登记，因此可前向调用和递归。函数正常走到末尾或执行 `return;` 都返回 `null`；`return expression;` 返回该表达式的值。

### 数组、record 和 `each`

下面是从 [collections.lwt](../examples/collections.lwt) 摘出的**片段**，完整文件还有浅快照修改演示：

```lwt
record Task { name, done };
let tasks = [Task{name: "draft", done: false}];
each (task in tasks) {
    emit task.name;
}
```

数组从索引 0 开始。数组和 record 是可变引用对象：赋值和函数传参不会复制它们。`each` 开始时保存数组元素引用序列的浅快照；本轮向原数组追加或替换元素不会改变这份快照，对快照内对象的修改仍可被观察到。`push(array, value)` 原地追加并返回 `null`。

### 文本和参数

运行 [text_tools.lwt](../examples/text_tools.lwt) 的上文命令会从参数取得路径、读取 UTF-8 文件、切分文本、转换数字并逐行输出。CLI 参数、fixture 和处理顺序都在该文件中，指南不复制第二份完整程序，以免示例漂移。

## 3. 语义速查

### 值、运算和作用域

- 值有任意精度整数、Unicode 字符串、布尔、`null`、数组和命名 record。没有隐式类型转换。
- `+` 接受两个整数或两个字符串；`-`、`*`、`/`、`%` 接受整数。整数除法向负无穷取整；除零是运行时错误。
- 比较运算要求两个整数或两个字符串；相等对全部值有效。数组和 record 的 `==` 比较对象身份，不递归比较内容。
- `not`、`and`、`or` 都要求布尔值；`and`/`or` 对满足短路条件的右侧不求值。条件不做真值转换。
- 块有词法作用域，块内 `let` 可遮蔽外层绑定；同一作用域不能重复 `let`。初始化表达式在新绑定可见之前求值。
- 所有顶层函数和 record 类型先登记。函数局部作用域的外层是全局作用域，不是调用者局部作用域；LWT 没有闭包。

完整优先级、值显示、比较、赋值求值顺序和错误位置见 [语言规范第 3–7 节](language-spec.md)。

### 内置函数与输出

| 能力 | 形式、结果和易错点 |
|---|---|
| `input()` | 无参数；读一行返回字符串，EOF 返回 `null`；只剥除行末 LF 及其前一个 CR。 |
| `args()` | 无参数；返回只含 CLI `--` 后参数的新字符串数组，不含源路径。 |
| `read_text(path)` | 一个字符串路径；返回全文，路径相对进程工作目录；UTF-8、剥除一个开头 BOM、CRLF/CR 规范为 LF。读取失败是运行时错误。 |
| `len(value)` | 一个字符串或数组；返回整数。字符串按 Unicode 码点计数，不按字节或字形簇。 |
| `split(text, separator)` | 两个字符串；separator 不能为空；按最早的非重叠匹配切分并保留首尾/连续分隔产生的空字段。 |
| `trim(text)` | 一个字符串；只裁剪两端 ASCII 空格、TAB、LF、CR、VT、FF，不删内部字符或其他 Unicode 空白。 |
| `to_int(text)` | 一个字符串；只接受 `-?[0-9]+`，允许前导零，不接受 `+`、空白或空串。非法内容是运行时错误。 |
| `str(value)` | 一个任意值；返回与 `emit` 相同规则生成的显示字符串。顶层字符串不带引号，复合值内部字符串带引号。 |
| `fail(message)` | 一个字符串；在调用位置产生运行时错误。诊断中的 CR/LF 会转义，避免消息拆成多行。 |
| `push(array, value)` | 数组和任意值；修改原数组并返回 `null`；首参非数组是运行时错误。 |
| `emit expression;` | 语句而非函数；把值的显示形式和一个 LF 写到 stdout。成功时 CLI 不额外打印状态文字。 |

函数实参按从左到右求值，然后检查参数个数和类型；未知函数名不会先执行实参。参数个数或类型错误属于运行时错误，退出码 3。

### 不支持的能力

LWT 0.1 不支持浮点、字典、类、闭包、函数值、模块、异常捕获、`break`、`continue`、语言级线程或 REPL。`break`、`continue` 是保留字，写入程序会语法报错。不要从 Python 的能力推断 LWT 也支持某个结构；遇到未列出的语义，先查规范、实现和黑盒证据。

## 4. 调试和验证

从仓库根目录运行：

```powershell
python -m unittest discover -s tests -q
python tools/run_tests.py
python -m compileall -q lwt tests tools
```

第一条运行解释器模块及测试工具的 unittest；第二条通过 `python -m lwt` 执行完整黑盒用例并精确比较退出码、stdout、stderr；第三条检查 Python 文件是否可编译。运行单个程序时直接执行 `python -m lwt path/to/file.lwt`。每次修改后都要运行与修改相关的 CLI 示例或测试；有条件时再运行完整套件。

遇到错误时，先确认命令是在仓库根目录运行，`SOURCE` 和 `read_text` 的路径均按当前工作目录解析；再核对 `--`、分号、保留字和严格类型规则。语法错误不能执行程序；运行时错误会终止程序，但此前已完成的 stdout 保留。规范示例是预期语义，是否实测通过要以实际命令为准。

## 5. 项目资料

- [LWT 语义实验室](../app/language_lab.py)：以 Python/Tkinter 显示固定白名单源码，并通过公开 `python -m lwt` 实际运行分支/循环、递归、集合快照、文本/参数、stdin 和错误定位示例。它不执行任意源码，也不是 LWT 编写的应用。运行 `python -m app.language_lab`；没有 GUI 时可运行 `python -m unittest discover -s tests -p "test_language_lab.py" -v`，或逐个直接运行示例 CLI。
- [完整语言规范](language-spec.md)：语法和可观察语义的权威来源。
- [黑盒覆盖矩阵](test-matrix.md)：规范条款、用例和已知未验证项。
- [仓库 README](../README.md)：常用运行和测试入口。
- [项目状态](../project.md)：阶段进度及证据。
- [现有完整示例](../examples/)：输入输出、控制流、函数、集合和文本处理。
- [课程作业要求](../大作业内容.md)：交付范围和验收要求。
