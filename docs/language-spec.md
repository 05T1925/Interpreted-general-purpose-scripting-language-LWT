# LWT 0.1 正式语言规范（S1/S2 已审查；S24–S26 补充等待主窗口审查）

> 本文是 LWT 源程序语法与可观察行为的规范性来源。2026-10-06 完成 S1 并经主窗口审查通过；S2 已将两项低风险澄清写入正文。S24 的循环控制、S25 的模块语义和 S26 的受控运行时错误恢复已实现并实测，均等待主窗口审查，不代表主窗口已通过。课程依据为[《大作业内容》](../大作业内容.md)，技术背景见[总体方案](../LWT大作业总体方案与复检.md)与[详细规划](../详细实施规划.md)。若规划中的拟定语义与本文不同，后续实现以本文为准。

## 1. 范围、依据与特色

| 作业要求 | LWT 对应设计 | 本文章节 | 性质 |
|---|---|---|---|
| 以本人名字命名、解释型通用脚本语言，语法有特色且不与现存语言完全相同 | 名称 LWT；`record`、`when/otherwise`、`each`、`emit` 组合；解释执行路线 | 本节、2–7 | 课程要求；具体关键字组合是方案选择 |
| 整数、字符串等基本类型 | 整数、字符串、布尔、`null` | 2、4 | 整数和字符串为硬性要求；布尔与 `null` 为设计补充 |
| 数组、结构类型 | 可变数组、命名 `record` | 3–4 | 课程要求；身份相等和构造规则为设计选择 |
| 基本输入输出 | `input()`、`emit` | 6 | 课程要求；`args`、文件和文本函数为应用扩展 |
| 分支循环 | `when/otherwise`、`while`、`each`、`break`、`continue` | 3、5 | 分支循环为课程要求；具体形式及循环跳转是方案扩展 |
| 函数定义与调用 | 顶层 `fn`、前向调用、递归、`return` | 3、5 | 课程要求；具体作用域规则为设计选择 |
| 跨文件复用函数库 | 顶层 `import "相对路径" as alias;` 与限定调用 | 3、5、9 | 方案扩展；不属于课程硬性最低要求 |
| 语法规则文档 | 本规范 | 全文 | 本阶段交付 |
| 解释器、完整黑盒测试、一键测试、性能比较、人/AI 指南、≥200 行 Agent 应用及记录、Git 历史、PPT、线下答辩 | 后续阶段的独立交付物；本规范为实现和测试提供预期 | 8 | 课程交付与验收要求，S1 不宣称完成 |

LWT 的预期标志是命名结构与 `when/otherwise`、数组遍历 `each`、输出 `emit` 组成的可读脚本风格，并由严格布尔条件、无隐式类型转换、明确的数组和结构行为支撑。课程允许自由组合已有语言的优点；本项目不声称已证明全球不存在完全相同的语言。特色将在后续实现、示例和答辩中以具体语法与语义展示。

本版本仅支持第 9 节定义的静态函数库模块；不支持完整包系统、模块值、动态加载、from/star 导入或模块顶层初始化语句。S26 增加第 10 节限定的运行时错误恢复；不支持 `throw`、任意异常类型、类型过滤、多个 handler、`finally` 或事务回滚。另不支持浮点、字典、类、闭包、函数值、标签循环跳转、语言级线程或 REPL。没有隐式类型转换。函数只在顶层声明；程序不能动态创建新函数或结构类型。`read_text` 一次读入整个文件，源文件读取期间若外部程序修改文件，不保证快照一致。这些限制不是未定语义。

## 2. 源文件与词法

### 2.1 编码、位置和空白

源文件必须是 UTF-8；只允许文件开头有一个 UTF-8 BOM，解码后丢弃一个开头的 U+FEFF。词法分析前将 CRLF 和单独 CR 统一为 LF；源码位置按统一后的 Unicode 码点计数，行、列从 1 开始，换行使下一字符位于下一行第 1 列。文件名在诊断中使用 CLI 传入的源路径。

字符串外的空格、水平制表、LF、换页和垂直制表仅作空白；它们不能代替分号。`#` 后直到 LF 之前的全部内容是注释，注释内容不产生 token；注释内的 U+FEFF 和其他字符一样忽略。`#` 在字符串内是普通字符。非首位 U+FEFF 在字符串内原样保留，在注释内忽略，在其他字符串外位置是词法错误。空文件、仅空白或注释的文件是有效程序。

标识符严格匹配 `[A-Za-z_][A-Za-z0-9_]*`，大小写敏感。保留字为 `record fn let when otherwise while each in return emit true false null and or not break continue import attempt recover`；它们不能作标识符。其中 `break`、`continue`、`attempt`、`recover` 是仅用于语句位置的保留字，`import` 只能用于顶层导入声明；语法及合法上下文见第 3、5、9、10 节。`as` 在导入声明中是上下文词，其余位置仍是普通标识符。`input args read_text len split trim to_int str fail push` 是预置函数名，不是词法关键字。整数词素为 `[0-9]+`，十进制且允许前导零；负数由一元 `-` 构成。整数在语义上没有固定宽度。S25 将 `import` 新增为保留字；S26 将 `attempt` 和 `recover` 新增为保留字；旧程序若将这些词用作变量、函数、形参、字段名或模块别名，现在会在词法/语法阶段被拒绝。

字符串以双引号包围，支持且仅支持 `\\`、`\"`、`\n`、`\t` 四种转义。字符串可含其他原始 Unicode 字符（包括制表符和 `#`），不能含原始 CR/LF；未知转义、行末前未闭合或文件末尾未闭合均为词法错误，位置指向反斜杠或开引号。没有单引号字符串或 Unicode 转义语法。

运算与界定符：`+ - * / % == != < <= > >= = ( ) { } [ ] , : ; .`。双字符运算符优先识别。其他非空白字符在字符串外为词法错误。简单语句的结束分号必须显式写出，不存在自动插入；多写的孤立分号不是空语句。

### 2.2 词法错误

非法 UTF-8 属于源文件读取错误（退出码 4）；已解码源码中的非法字符、非法转义和未闭合字符串属于词法错误（退出码 2）。诊断只报告首个错误，格式见第 7 节。

## 3. 语法

下面 EBNF 中，引号内为固定词素，`IDENT`、`INT`、`STRING` 为第 2 节定义的 token，`{ X }` 为零次或多次，`[ X ]` 为可选，`|` 为择一。文法中的 `EOF` 是输入结束标记。列表均允许为空，但**不允许尾随逗号**；`record` 声明的字段名也不允许重复。解析时 `IDENT "("` 优先作为命名调用，`IDENT "{"` 优先作为结构构造；其余 `IDENT` 是变量引用。

```ebnf
program       = { import_decl } { top_item } EOF ;
module_file   = { import_decl } { fn_decl } EOF ;
import_decl   = "import" STRING "as" IDENT ";" ;
top_item      = record_decl | fn_decl | statement ;
record_decl   = "record" IDENT "{" [ name_list ] "}" ";" ;
fn_decl       = "fn" IDENT "(" [ name_list ] ")" block ;
name_list     = IDENT { "," IDENT } ;

statement     = let_stmt | return_stmt | emit_stmt | break_stmt | continue_stmt
              | attempt_stmt
              | when_stmt | while_stmt | each_stmt | block | expr_stmt ;
block         = "{" { statement } "}" ;
let_stmt      = "let" IDENT "=" expression ";" ;
return_stmt   = "return" [ expression ] ";" ;
break_stmt    = "break" ";" ;
continue_stmt = "continue" ";" ;
attempt_stmt  = "attempt" block "recover" "(" IDENT ")" block ;
emit_stmt     = "emit" expression ";" ;
expr_stmt     = expression ";" ;
when_stmt     = "when" "(" expression ")" block [ "otherwise" block ] ;
while_stmt    = "while" "(" expression ")" block ;
each_stmt     = "each" "(" IDENT "in" expression ")" block ;

expression    = assignment ;
assignment    = logic_or [ "=" assignment ] ;
logic_or      = logic_and { "or" logic_and } ;
logic_and     = equality { "and" equality } ;
equality      = comparison { ( "==" | "!=" ) comparison } ;
comparison    = additive { ( "<" | "<=" | ">" | ">=" ) additive } ;
additive      = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative= unary { ( "*" | "/" | "%" ) unary } ;
unary         = ( "not" | "-" ) unary | postfix ;
postfix       = atom { "[" expression "]" | "." IDENT } ;
atom          = INT | STRING | "true" | "false" | "null"
              | "[" [ expression { "," expression } ] "]"
              | module_call
              | IDENT [ "(" [ expression { "," expression } ] ")"
                      | "{" [ field_init { "," field_init } ] "}" ]
              | "(" expression ")" ;
module_call   = IDENT "." IDENT "(" [ expression { "," expression } ] ")" ;
field_init    = IDENT ":" expression ;
```

`fn` 和 `record` 只能作为顶层项；在块内出现是语法错误。`record` 声明中的字段名若重复，解析器报 `SyntaxError`、退出码 2，位置指向第二次出现的重复字段名；包含该错误的程序不能执行。词法分析器只分别产生字段名 token，不负责这项检查。`return` 只能处于函数体及其内层块中，否则是语法错误。`break;` 和 `continue;` 只能出现在某个 `while` 或 `each` 循环体中；它们可以穿过普通块和 `when/otherwise` 分支，作用于最近的外层循环。解析器为函数体从零开始建立循环上下文，因此函数不能借用调用者当前活动的循环；函数体内未进入自身循环时使用二者仍是语法错误。上下文错误指向关键字，退出码为 2。循环体中的内层循环会建立更近的上下文。`attempt` 只能作为语句使用，必须有两个块和一个括号内标识符；`recover` 只能紧跟对应 attempt 块，二者间可有空白和注释。两侧块后均不写分号；`recover` 单独出现、attempt 缺少 recover、参数形式不符或额外分号均为语法错误。嵌套 attempt 合法，且保留当前 return/loop 上下文。分号必需，标签或额外 token 不属于语法。函数形参名重复是语法错误。`otherwise` 只属于紧接在它前面的 `when`，中间可有空白或注释，但不能插入其他语句；由于分支体必须是块，不存在悬空 `otherwise`。`otherwise when (...)` 不在此语法内，要嵌套时须写 `otherwise { when (...) { ... } }`。空块合法。函数声明及控制语句的块后不写分号；`record` 声明后必须写分号。

赋值右结合，`a = b = 1` 先把 1 赋给 `b` 再赋给 `a`，整个赋值表达式的值为右侧值。赋值左侧仅可为变量引用、索引表达式或字段访问表达式；例如 `a[0] = 1` 与 `r.x = 2` 合法，`(a + b) = 1` 是语法错误。索引/字段访问的接收者可以是任意表达式，但左值求值规则见第 4 节。其他二元运算符同级时左结合；一元运算符右结合。优先级由上述文法从低到高给出，后缀索引/字段最高，括号明确覆盖默认优先级。命名调用是 `atom`，不支持在表达式结果上再次调用，例如 `f()(1)` 为语法错误；调用结果仍可索引或访问字段。`import_decl` 只可出现在程序开头的连续导入区；入口与库文件的不同顶层限制见第 9 节。`as` 只要求导入语法中的词素，不单独成为关键字。

结构构造只允许 `Type{field: value}` 形式，不能以匿名 `{...}` 构造；花括号单独出现在语句位置表示块。`record Empty {};`、`Empty{}`、`[]` 和 `f()`（零形参时）均合法。

## 4. 值、表达式与可变对象

### 4.1 值与求值次序

运行时值包括任意精度整数、Unicode 字符串、布尔、唯一的 `null`、可变数组、命名记录实例，以及仅由 recover handler 创建的不可变 Error 值。布尔不属于整数。字符串不可变，不做 Unicode 规范化。数组和记录是按引用传递的可变对象；把它们赋给另一变量或传参不会复制对象。Error 值也按对象身份传递和比较，但其属性只读。数组字面量的元素、函数实参、结构构造字段值按源码从左到右求值。二元非短路运算先求左，再求右；调用先依序求实参，再检查形参数量和类型要求。执行 `let` 时先检查当前作用域是否已有同名绑定，若有则立即报错且不求初始化表达式；否则在已有环境中求初始化表达式，成功后才创建绑定。

索引读取先求接收者再求索引，然后检查类型和范围；字段读取先求接收者再检查字段。赋值时先解析并验证目标：变量须已绑定；索引目标先求接收者、索引并检查数组类型和索引范围；字段目标先求接收者并检查记录字段。随后才求右侧值并写入。目标接收者和索引各只求值一次。赋值表达式返回所写入的值。若右侧求值出错，目标不被写入；右侧先前产生的其他副作用仍保留。

### 4.2 运算与比较

`-` 一元只接受整数；二元 `- * / %` 均只接受两个整数。整数 `/` 为向负无穷取整，`%` 满足 `a == (a / b) * b + (a % b)`，余数与非零除数同号或为零；例如 `-7 / 3` 为 `-3`，`-7 % 3` 为 `2`。除数为零对 `/` 和 `%` 都是运行时错误。`+` 只接受两个整数（求和）或两个字符串（拼接），不做类型转换。

`< <= > >=` 只接受两个整数或两个字符串；字符串按 Unicode 码点序列逐位比较，前缀较短者较小。类型不合是运行时错误。`==` 与 `!=` 对所有值有定义：类型不同为不等；整数、字符串、布尔按值；`null` 只等于 `null`；两个数组或两个记录实例只在指向同一个对象时相等，不做递归结构比较。`!=` 是 `==` 的否定。链式比较按文法左结合，例如 `1 < 2 < 3` 的第二个 `<` 收到布尔左操作数，因而是运行时类型错误，并非数学链式比较。

`not` 只接受布尔。`and`、`or` 的左操作数必须是布尔；`false and ...` 与 `true or ...` 不求右操作数，直接返回布尔；其余情况才求右操作数且要求布尔。条件、循环不使用“真值”转换。

### 4.3 数组、记录和显示

数组从零索引。索引必须是整数且满足 `0 <= i < len(a)`；负索引、越界、非整数索引或对非数组索引均为运行时错误。`push(array, value)` 向原数组末尾追加一个元素、返回 `null`；别名会观察到修改。没有切片或删除操作。

`record Name { f1, f2 };` 声明一个命名结构类型。`Name{f1: v1, f2: v2}` 每次构造新的实例；先查找类型名，再验证构造字段的集合必须与声明完全一致，次序可不同。构造前先检查字段名是否重复、缺失或多余；类型查找或字段验证失败时不求字段值。重复、缺失或多余构造字段均为运行时错误。验证成功后字段值按构造文本顺序求值，实例按**声明顺序**存储和显示字段。`r.f` 读取，`r.f = v` 修改；不存在的字段是运行时错误。字段没有独立类型声明，可保存任何 LWT 值，包括另一种记录实例；把非记录值用于字段访问、用未声明类型名构造、或给构造器提供错误字段集合，均为运行时错误。不同记录类型的实例比较相等时结果为 `false`，没有记录类型转换或字段赋值类型检查。实例的记录类型不会在赋值时改变。调用或访问中的记录类型名大小写敏感。

`str(value)` 返回可显示字符串；`emit value;` 把同一显示字符串后接一个 LF 写到 stdout。顶层字符串直接显示内容，不带引号；其他原子值显示为十进制整数、`true`、`false`、`null`。数组显示为 `[e1, e2]`，记录显示为 `Name{f1: e1, f2: e2}`，字段按声明顺序。复合值内部的字符串带双引号，双引号转义为 `\"`、反斜杠转义为 `\\`、LF 为 `\n`、CR 为 `\r`、TAB 为 `\t`，其余 U+0000–U+001F 与 U+007F 转义为四位大写十六进制 `\uXXXX`；其他字符原样保留。空数组为 `[]`，零字段记录为 `Name{}`。

数组可通过 `push` 自引用，记录可通过字段赋值自引用；显示时沿**当前递归路径**记录对象身份，再次遇到路径上的数组或记录时以 `<cycle>` 代替该处的整个对象。共享但不在当前路径上的对象正常重复展开。例如 `let a = []; push(a, a); emit a;` 预期显示 `[<cycle>]`。这只是显示规则，不改变身份相等，也不要求固定的最大嵌套深度。

recover handler 创建的 Error 值是不可变的身份值，不是用户可声明的记录类型。它的 `category`、`message`、`source`、`line`、`column` 五个字段按此顺序显示，字符串字段使用本节的复合字符串转义规则，数字和 `null` 不加引号。例如 `Error{category: "RuntimeError", message: "division by zero", source: "lib/math.lwt", line: 2, column: 12}`。`str(error)` 与 `emit error;` 使用相同形式。Error 不能作为 `len` 参数或数组索引；字段只读，具体运行时错误见第 10 节。

## 5. 作用域、函数与控制流

入口及每个模块文件分别拥有一个顶层函数名空间和变量根作用域；入口另有记录类型名空间。预置函数与当前源文件的用户函数共用函数名空间；同名用户函数不能覆盖预置函数。变量名可以与函数或记录类型同名，语法位置决定查找：`f(...)` 查当前源文件函数名空间，`T{...}` 查入口文件记录类型名空间，单独的 `f`/`T` 查变量。函数和记录名各自在本名空间不能重复；函数名与记录名相同允许。两个同一源文件内的 `record` 同名、两个 `fn` 同名或与预置函数同名的 `fn`，在任何普通语句执行前产生运行时错误，位置为后一个声明名。模块命名空间、模块函数环境和记录可见性见第 9 节。

所有顶层 `fn` 和 `record` 声明在普通语句执行前一次性登记，允许前向调用、相互调用和递归；登记本身不运行函数体。顶层普通语句按源码顺序执行。`let` 在其初始化成功后才可见；同一作用域再次 `let` 同名是运行时错误，内层作用域可遮蔽外层。读取或赋值找不到变量是运行时错误。即使内层作用域稍后有同名 `let`，它创建绑定之前的读取仍查找当前可见的外层绑定；初始化中的 `let x = x + 1;` 可读取外层 `x`，但若无外层 `x` 则报未定义变量。块每次进入都创建新作用域，退出即销毁其中的绑定；块内赋值修改最近可见绑定。

函数调用创建新的局部作用域，其外层固定为所属源文件的变量根作用域，**不是**调用者局部作用域。形参与函数最外层函数体中的 `let` 处于同一作用域，因此 `let` 不可重声明形参。传参数目必须等于形参数目；参数值按第 4 节传递。函数体结束而未执行 `return` 时返回 `null`；`return;` 也返回 `null`；`return expr;` 先求表达式再立即退出当前函数。入口函数可在顶层 `let` 执行之前被调用；模块函数的变量根作用域独立且初始为空。局部绑定在每次调用结束时销毁。没有函数值或闭包。

`when (cond) { ... } otherwise { ... }` 要求条件是布尔，且只执行所选块；无 `otherwise` 且条件为假时不做事。`while (cond) { ... }` 每轮开始重新求条件并要求布尔，假时结束；每轮块有新作用域。`each (item in expr) { ... }` 先求 `expr`，必须得到数组；进入循环时复制其**元素引用序列**作为浅快照。每个快照元素依原顺序产生一次迭代，迭代变量在该轮新建的循环作用域中绑定，循环体块再创建一个子作用域。对迭代变量重新赋值不会替换原数组元素；循环中追加或替换原数组元素不改变尚待遍历的快照，但快照中引用的嵌套可变对象若被修改，后续迭代可观察到修改。空数组迭代零次。

`break;` 立即结束最近的 `while` 或 `each`，然后执行该循环语句之后的语句。`continue;` 结束最近循环的当前迭代：在 `while` 中立即重新求条件；在 `each` 中推进至进入循环时浅快照的下一个元素，不重建快照，也不纳入循环中新追加的数组元素。块、`when` 和 `otherwise` 不捕获这两种跳转；内层循环只捕获自己的跳转。`return` 仍立即退出当前函数并穿过任意块、分支和循环，循环不会捕获 `return`。运行时错误继续向外传播，已经完成的 `emit` 保留。两种循环正常结束、被 `break` 结束或遍历完成后，均继续执行循环之后的语句。LWT 没有 loop-else。

`attempt { body } recover (problem) { handler }` 的两个块都按普通块创建词法作用域。`problem` 仅在 handler 动态执行期间绑定为 Error；退出 handler 后不可见，handler 内可按通常规则遮蔽它。body 正常结束时跳过 handler。body 抛出的 LWT `RuntimeError`/退出码 3 被最近的动态 attempt 捕获，Error 字段保留原始错误数据；未捕获的其它类别继续传播。recover 正常结束后继续执行 attempt 之后的语句。attempt 不回滚此前的输出、变量、数组/record 修改、输入消费或其它副作用。

`return`、`break`、`continue` 是控制流，不是运行时错误；它们直接穿过 attempt，不运行该 attempt 的 recover。body 内的控制流仍按所属函数和最近循环处理。嵌套 attempt 由最近 handler 捕获；handler 执行不属于同一 attempt 的捕获范围，因此 handler 中再次发生的 RuntimeError 会向外传播，若存在外层动态 attempt 则由外层捕获。

## 6. 预置能力与 CLI

所有预置函数按名字调用；调用时先查找函数名，不存在即在调用位置报运行时错误且不求实参。找到函数后按从左到右求实参，再检查参数数目和类型；数目或类型不符均为调用位置的运行时错误。用户函数也遵循这一查找和实参顺序。除说明外，没有隐式转换。`emit` 是语句，恰好输出一个表达式值。stdout 只承载 `emit` 输出；成功执行不额外输出状态信息。诊断写 stderr，不混入 stdout。

| 能力 | 参数与返回 | 边界和错误 |
|---|---|---|
| `input()` | 读取标准输入一行，返回字符串或 EOF 时 `null` | 以 LF 为行分隔；移除行尾一个 LF，并在它前面有 CR 时一并移除；末行无 LF 时原样返回；空行为 `""`；解码/读取失败是运行时错误 |
| `args()` | 无参数；返回新的字符串数组 | 仅含 CLI 中 `--` 之后的程序实参，不含源文件名和分隔符；每次调用返回新数组，修改返回数组不影响之后调用 |
| `read_text(path)` | 一个字符串路径；返回文件全文字符串 | 相对路径以进程当前工作目录为基准；UTF-8，允许且剥除开头一个 BOM，CRLF/CR 规范化为 LF；不存在、权限、非法 UTF-8 等读取失败是运行时错误（码 3），位置为调用处 |
| `len(x)` | 字符串或数组；返回整数 | 字符串按 Unicode 码点计数，不按 UTF-8 字节或字形簇计数；其他类型报错 |
| `split(text, separator)` | 两个字符串；返回字符串数组 | 分隔符必须非空；从左到右每次取最早的非重叠原文匹配切分，保留首尾及连续分隔产生的空字段；`split("", ",")` 为 `[""]` |
| `trim(text)` | 一个字符串；返回字符串 | 只删除两端的 ASCII 空白：空格、TAB、LF、CR、VT、FF；内部字符及其他 Unicode 空白不变 |
| `to_int(text)` | 一个字符串；返回整数 | 严格匹配 `-?[0-9]+`；不接受前后空白、`+`、空串或其他字符；允许前导零；不合法时运行时错误 |
| `str(value)` | 一个任意值；返回字符串 | 精确格式见 4.3；输入字符串原样返回 |
| `push(array, value)` | 数组与任意值；返回 `null` | 原地追加，首参不是数组时报错 |
| `fail(message)` | 一个字符串；不正常返回 | 在调用处产生运行时错误，诊断消息使用给定文本；其中 CR/LF 转义成 `\r`/`\n`，避免拆成多行 |

命令形式为 `python -m lwt <source-path> [-- <program-arg> ...]`。源路径是必需的；不要求文件扩展名，但首个参数 `--` 不能充当源路径。没有 `--` 时不能在源路径后放额外参数；一旦出现第一个 `--`，其后每个参数都原样属于程序实参，后续字面量 `--` 也会出现在 `args()` 中。解释器不把源文件路径放入 `args()`。源文件路径按进程当前工作目录解析。标准输入、标准输出、标准错误按 UTF-8 文本处理；输出换行统一为 LF。源文件参数缺失、分隔符位置不合法、源文件无法读取或解码是 CLI/源文件错误（码 4）。`read_text` 读取的文件出错仍是运行时错误（码 3）。

## 7. 错误、退出码与实现约束

| 类别 | 典型情况 | 退出码 |
|---|---|---:|
| 成功 | 程序完整执行 | 0 |
| `LexError` / `SyntaxError` | 非法字符/转义，缺分号，非法左值，函数外 `return`，循环外 `break`/`continue`（包括未进入本函数循环的函数体），`record` 声明字段重复（第二个字段名位置） | 2 |
| `RuntimeError` | 未定义变量、类型/边界/除零、重复绑定、`fail`、`read_text` 失败；若被动态 handler 捕获则按第 10 节恢复，否则 | 3 |
| `CliError` / `FileError` | CLI 用法、源文件读取/UTF-8 解码失败 | 4 |

源码相关诊断的一行格式为 `<source-path>:<line>:<column>: <类别>: <简短消息>`，写 stderr 并以 LF 结束；源文件路径使用 CLI 实参原文。无源码位置的 CLI/源文件错误为 `lwt: <类别>: <简短消息>`。消息中的换行、CR 转义成可见的 `\n`、`\r`，不得附带 Python traceback。词法错误指向非法字符/转义反斜杠/未闭合字符串开引号；语法错误指向第一个不符合预期的 token，文件结束时使用 EOF 位置（末字符之后，按规范化换行计数）。运行时错误指向触发运算符、访问符、赋值号或调用名；未定义变量读取指向该名字，构造错误指向类型名，条件/遍历类型错误指向 `when`、`while`、`each`，重复绑定指向后一个声明名。源文件必须先完整词法分析，再完整语法分析成功，才允许登记声明或执行任何普通语句；词法阶段的首错先报告，词法成功后才报告语法阶段的首错，不要求错误恢复或多错误聚合。运行时首个错误终止程序，先前完成的 stdout 输出保留。

解释器预定采用 Python 3.10+ 标准库、手写 lexer/parser、AST 树遍历运行时；不得用 Python `eval` 或 `exec` 执行 LWT 源码。这是**实现约束**，不是 LWT 用户程序可观察的语义。实现不得泄露 Python traceback；若宿主调用栈限制被触及，应转为 LWT 运行时错误，但本版本不承诺“512 层”等固定可移植上限。内存耗尽或进程被外部终止不属于本语言正常错误契约。

## 8. 规范性示例与设计决策

各代码块是独立源文件；输出块中的换行表示 `emit` 产生的 LF。除特别说明外，代码块描述规范预期；S24 的循环控制示例另有真实 CLI 实测记录。

### 8.1 变量、分支、循环与函数

```lwt
fn twice(x) { return x * 2; }
let n = 2;
when (n < 3) { emit twice(n); }
otherwise { emit 0; }
while (n < 4) { n = n + 1; }
emit n;
```

预期 stdout 为 `4\n4\n`，退出码 0。函数声明已在普通语句前登记。

### 8.2 结构、数组和浅快照

```lwt
record Student { name, score };
let students = [Student{name: "Li", score: 87}, Student{name: "Wu", score: 56}];
each (s in students) {
    when (s.score >= 60) { emit s.name + ":pass"; }
    otherwise { emit s.name + ":retry"; }
    push(students, s);
}
emit len(students);
```

预期 stdout 为 `Li:pass\nWu:retry\n4\n`；循环只遍历进入时的两个元素。`push` 的返回值未使用。

### 8.3 输入输出、参数和文件

```lwt
let line = input();
when (line == null) { emit "EOF"; }
otherwise { emit trim(line); }
emit len(args());
emit len(split(read_text(args()[0]), "\n"));
```

若以 `python -m lwt demo.lwt -- data.txt` 运行，stdin 为 ` hi \n`，`data.txt` 为 UTF-8 文本 `a\nb`，预期 stdout 为 `hi\n1\n2\n`、退出码 0。路径以进程当前工作目录为基准。

### 8.4 错误类别

| 独立源程序 | 预期 |
|---|---|
| `emit "bad\q";` | `LexError`，退出码 2，未知转义 |
| `emit (1 + 2) = 3;` | `SyntaxError`，退出码 2，左侧不可赋值 |
| `emit -7 / 3; emit -7 % 3;` | stdout `-3\n2\n`，退出码 0 |
| `emit true + 1;` | `RuntimeError`，退出码 3，类型不合 |
| `fail("stop");` | `RuntimeError`，退出码 3，消息 `stop` |
| `return 1;` | `SyntaxError`，退出码 2，函数外返回 |
| `emit "before"; break;` | `SyntaxError`，退出码 2，循环外 `break`；即使前面有 `emit`，stdout 仍为空 |

### 8.5 循环控制

以下内容与 [`examples/loop_control.lwt`](../examples/loop_control.lwt) 相同，在 S24 使用公开 CLI 实际运行。

```lwt
let i = 0;
while (i < 6) {
  i = i + 1;
  when (i == 2) { continue; }
  when (i == 4) { break; }
  emit i;
}

let values = [1, 2, 3];
each (value in values) {
  when (value == 1) {
    push(values, 4);
    continue;
  }
  when (value == 3) { break; }
  emit value;
}
emit values;
```

实测 stdout：

```text
1
3
2
[1, 2, 3, 4]
```

stderr 为空，退出码为 0。`while` 的 continue 跳过 `i == 2` 的输出，break 在 4 时退出；`each` 的 continue 跳过 1，新增的 4 不进入原快照，break 在 3 时结束遍历。

### 8.6 与既有草案的差异和取舍

| 来源/歧义 | 本规范决定 | 理由与影响 |
|---|---|---|
| [详细规划第 3.3 节](../详细实施规划.md)拟让解析器恢复并报告多个错误 | 仅报首个词法/语法错误；有错不执行 | 课程和 S1 验收未要求多错误聚合，首错定位足以测试，减少手写解析器复杂度；详细规划与路线图的 S3 描述已同步收窄 |
| [详细规划第 4 节](../详细实施规划.md)举约 512 层调用为可能上限 | 不设固定语言级数字；宿主调用栈错误须转为 LWT 错误 | Python 实际栈深受实现方式影响，固定 512 未获课程依据；不承诺无法跨平台验证的数字 |
| 草案要求复合值自引用安全显示但未给精确格式 | 当前路径遇环显示 `<cycle>`，共享非环对象重复展开 | `push` 与记录字段赋值使环真实可构造；必须保证 `str`/`emit` 终止，规则按身份易实现 |
| S1 初版规范为控制范围优先将 `break`、`continue` 排除在语法之外；课程要求循环控制，但未强制这两个关键字 | S24 以本节和第 3、5 节新增无标签的 `break;` 和 `continue;`，仅针对最近的 `while`/`each`；函数不继承调用方循环上下文 | 这是有意修订 S1 初版语法，补足可演示的循环控制能力；不增加其他语法，静态上下文在解析期检查，运行时只由最近循环捕获。S24 实施完成、等待主窗口审查 |
| 草案未定 CLI 参数分隔、`read_text` 路径、`input` EOF、输出转义等边界 | 分别按第 4、6、7 节冻结 | 防止黑盒测试和后续应用依赖实现者猜测 |

本规范主体已通过 S1 审查；S2 已将两项审查澄清写入正文：重复 `record` 声明字段是 `SyntaxError`、退出码 2、位置指向第二个重复字段名；注释中的 U+FEFF 与其他注释内容一样被忽略。S24 循环控制补充仍等待主窗口审查；第 8.5 节已用公开 CLI 实际运行，其余示例按各节标明为规范预期或已有实测。黑盒测试、指南、Agent 应用、性能数据、PPT 属于项目交付要求，并不由语言规范本身证明完成。

## 9. 静态函数库模块（S25）

### 9.1 声明与语法限制

模块系统是供多文件 LWT 程序复用函数的静态子集，不是完整包管理器。入口文件语法为 `program = { import_decl } { top_item } EOF`：零个或多个导入声明必须连续位于所有其他顶层项之前；随后仍可按现有语法声明 `record`、`fn` 并执行普通语句。库文件语法为 `module_file = { import_decl } { fn_decl } EOF`，因此库文件只可在开头导入其他库，随后声明零个或多个顶层函数。库文件不执行初始化语句，也不能声明顶层变量或 `record` 类型。块、函数体、分支和循环内部均不允许 `import`。导入声明必须使用字符串字面量和显式别名；不支持 `from`、通配符、动态路径、运行时导入或可作为普通值读取的模块对象。

```lwt
import "lib/text_utils.lwt" as text;

let cleaned = text.trim("  hello  ");
emit cleaned;
```

导入语句中的 `as` 是上下文词；`import` 是 S25 新增保留字，因此过去以它作为变量、函数、形参或字段名的源码需要改名。模块别名不创建普通变量绑定，但同名普通变量可独立声明；`alias.member(...)` 总按模块限定调用解释，别名不能作为一等值传递或读取成员值。相同源文件内别名不得重复，第二个别名处报 `SyntaxError`/2。

### 9.2 路径与模块图

`import "path" as alias;` 中的路径必须是相对文件路径。它相对于**书写该导入声明的文件目录**解析；主入口文件路径仍按 CLI 原有规则相对于进程工作目录解析。允许 `..`、Unicode 和空格，不要求 `.lwt` 后缀；绝对路径、目录、缺失文件、权限失败和非法 UTF-8 均是 `ImportError` 或文件层诊断、退出码 4，位置指向导入声明。导入路径先规范化并解析符号链接；同一规范化文件在一次解释进程中只载入、扫描、解析一次。不同导入方可给它起不同别名。

静态导入图必须在入口执行前完整读取、严格 UTF-8 解码、扫描、解析并链接。依赖图中的循环（包括库反向导入入口）在任何 `emit` 前以退出码 4 拒绝，诊断包含导入位置和一条简洁的循环路径。有效但未被调用的函数不执行；模块没有顶层可执行语句，所以导入也没有初始化副作用。`read_text(path)` 仍以进程当前工作目录为基准；模块中的 `args()` 与 `input()` 仍读取该进程唯一的 CLI 参数和 stdin，不创建模块级 I/O。

### 9.3 独立命名空间与调用

每个文件拥有独立的函数名空间和变量根作用域。入口调用库函数以及模块调用其依赖函数都必须限定：`text.trim(value)`。模块函数中的未限定用户函数调用只搜索**所属文件**的函数；它不会自动看到入口或调用者模块的函数、变量或局部作用域。模块函数不闭包。两个不同文件可声明同名函数，必须通过各自别名区分。函数可前向调用、相互调用和递归；内置函数在每个模块中仍可直接使用，用户函数仍不得遮蔽内置名称。

入口可以声明 `record` 类型，模块不可声明记录类型。入口构造的数组、记录、字符串和其他值可以作为参数传给模块函数；可变数组和记录仍按引用传递，模块函数可以读取或修改传入对象。模块不能借用入口的记录类型名来构造新实例；传入的现有记录仍可按已有字段访问和修改规则操作。

导入别名只用于限定函数调用。`alias.name(...)` 的别名必须存在且目标模块必须声明该函数；未知别名或成员按 `RuntimeError`/3 诊断，并在执行入口普通语句前完成链接检查。限定调用实参按现有函数规则在调用方上下文从左至右求值；被调用函数切换到其所属模块上下文运行，后续依赖调用使用该模块自己的别名表。数组/记录参数和进程级 I/O 按原规则共享。

### 9.4 来源路径与错误

入口文件的诊断仍显示 CLI 传入的原始源路径。导入文件的词法、语法和运行时诊断使用相对于入口文件目录的规范化路径，分隔符统一显示为 `/`；若模块位于入口目录上级，路径可包含 `../`。因此模块错误使用 `<模块相对路径>:<行>:<列>: <类别>: <消息>`，行列仍从 1 开始。缺失依赖、绝对路径和循环等加载错误定位到声明该 import 的源文件与位置。导入文件的 `LexError`/`SyntaxError` 退出码为 2，模块函数运行时错误为 `RuntimeError`/3，依赖加载错误为 4；不输出 Python traceback。模块图的任何读取、词法、语法或链接失败均不会留下入口程序 stdout。

### 9.5 规范性示例与实现约束

可从项目根目录通过公开 CLI 运行多文件演示：

```text
python -m lwt examples/modules/main.lwt
```

该程序导入 `stats_utils.lwt`，后者再导入 `text_utils.lwt`；入口把含字符串数组的 `Batch` record 传入库函数，预期 stdout 为 `demo:2\n`，stderr 为空，退出码为 0。该示例依赖真实模块调用、数组遍历和 record 字段访问，不在 Python 前端另行计算结果。

解释器实现必须使用 LWT 自身的 lexer、parser、AST 和运行时解释上述文件；禁止用 Python `eval()` 或 `exec()` 执行 LWT 源码。这是宿主实现约束，不是 LWT 用户程序可以观察的语言语义。

## 10. 运行时错误恢复（S26）

### 10.1 语法与捕获边界

attempt_stmt 的完整 EBNF 已列于第 3 节：attempt 后是 body 块，紧接 recover、恰好一个括号内标识符和 handler 块。两个关键字均为保留字；语句不加分号。允许嵌套，不支持可选 handler、多个 handler、类型过滤、finally、throw 或重试语义。

attempt 只捕获从 body 动态逸出的 LWT RuntimeError 且退出码为 3。除零、类型不匹配、未定义变量、数组越界、fail、read_text 失败，以及经普通函数或导入模块函数传播的运行时错误均属于此范围。捕获以最近的动态 attempt 为准。若无 handler，错误保持原有 RuntimeError 诊断、退出码 3 和已完成 stdout。

LexError、SyntaxError、CLI/源文件读取错误、模块路径读取/解码/循环错误、预执行模块 alias/member 链接错误、未处理的宿主异常、KeyboardInterrupt 和 SystemExit 不被捕获。所有入口和模块源文件均先完整读取、扫描、解析，模块图和调用链接及 AST 支持检查也先于普通语句执行；因此这些错误不会被 attempt 捕获，前置 emit 也不会部分输出。alias/member 链接错误虽使用 RuntimeError/3 类别，但在运行前检查阶段发生，仍不可捕获。

### 10.2 控制流、作用域与副作用

body 正常完成时跳过 handler，随后执行下一条语句。运行时错误被捕获后，handler 正常完成则继续执行 attempt 之后的语句。body 和 handler 都是普通块作用域；handler 标识符在 handler 执行期间绑定为 Error，handler 退出后不可见。handler 内局部声明、遮蔽和重复绑定沿用当前块规则。

return、break、continue 不是 RuntimeError，不运行当前 handler；return 仍退出所属函数，break/continue 仍作用于最近所属循环。内层 attempt 先处理自身错误；handler 内新发生的错误不被同一 attempt 再捕获，但会继续向外传播并可被外层 attempt 捕获。

attempt 不是事务，不撤销错误前已经完成的 emit、赋值、数组/record 修改、输入消费或其它副作用。Error 字段赋值本身是一个新的 RuntimeError。

### 10.3 Error 值

Error 值只由 recover 绑定创建，源程序不能构造或伪造内部 Error 值。它是不可变身份值，不是 record。以下五个字段只读：

| 字段 | 类型和值 |
|---|---|
| category | 捕获时固定为字符串 RuntimeError |
| message | 原始运行时诊断消息，不含类别、路径或行列前缀 |
| source | 最终诊断使用的源路径；入口为 CLI 原始路径，模块为相对入口目录的规范化路径；不可用时为 null |
| line | 最终诊断的一基行号；不可用时为 null |
| column | 最终诊断的一基列号；不可用时为 null |

source、line、column 与同一错误未捕获时诊断采用的位置一致。Error 的显示字段顺序固定为 category、message、source、line、column；字符串字段使用第 4.3 节复合字符串转义，整数与 null 不加引号。str(error) 与 emit error; 完全相同。格式示例：

    Error{category: "RuntimeError", message: "division by zero", source: "lib/math.lwt", line: 2, column: 12}

Error 按对象身份比较：同一值与自身相等，不同捕获生成的 Error 不相等。对已知字段赋值报告 RuntimeError，消息为 error fields are read-only，位置指向字段访问符；未知字段报告 error value has no field 'name'。Error 不满足 len 的字符串/数组参数要求，不是数组整数索引，也不是记录类型值；这些行为使用现有严格类型检查。Error{} 没有内建构造语义；若用户声明普通 record Error，则该语法仍按普通记录构造处理，所得值不是 Error。

### 10.4 规范性示例

将下例保存为 recover.lwt 后从当前目录执行。fail 的调用位置是第 1 行第 11 列：

    attempt { fail("bad"); } recover (problem) {
      emit problem.category;
      emit problem.message;
      emit problem.line;
      emit str(problem);
    }
    emit "continued";

预期 stdout 为 RuntimeError、bad、1、Error{category: "RuntimeError", message: "bad", source: "recover.lwt", line: 1, column: 11}、continued，各占一行；stderr 为空，退出码 0。

若 handler 本身再执行 fail，则同一 attempt 不会重新进入该 handler。没有外层 attempt 时，该错误按原规则写入 stderr、退出码 3，handler 之前的 stdout 保留。含词法/语法错误或无法加载模块的程序在任何普通语句前失败，即使错误文本处于 attempt 块中也不产生 stdout。

### 10.5 设计边界

S26 增加的是受控 RuntimeError 恢复机制，不是通用异常类型系统。错误类别和退出码既有含义不变；未处理的 RuntimeError 保留原诊断契约。实现可以使用内部 Error 值表示，但不得将 Python LwtError 对象本身暴露给 LWT 程序。
