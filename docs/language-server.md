# LWT Language Server（S29）

LWT Language Server 是 Python 实现的静态开发工具，通过标准输入/输出承载 LSP/JSON-RPC。它只读取源码、构建 AST、复用 S27 静态分析并建立编辑器查询索引；**不会执行被分析的 LWT 程序**。它不是 LWT 源语言语义的一部分，不改变普通 CLI、`--check` 或 `--profile` 的契约。本仓库没有制作或发布 VS Code 扩展，也没有验证真实编辑器连接。

## 启动和协议范围

从仓库根目录启动：

```powershell
python -m lwt.lsp_server
```

进程仅使用 stdio：stdin 接收 LSP frame，stdout 只输出 LSP frame；可读服务日志写 stderr。消息使用 ASCII header，以两个 CRLF 序列组成的空行分隔 header 和正文，并按 UTF-8 **字节数**计算 `Content-Length`。单条正文上限为 8 MiB，header 上限为 16 KiB；重复 JSON key、无效 UTF-8、非法 JSON、重复/缺失/非法 Content-Length、截断消息和非 UTF-8 Content-Type 均被拒绝。JSON-RPC batch 不受支持。

initialize capabilities 固定为：

```json
{
  "positionEncoding": "utf-16",
  "textDocumentSync": {"openClose": true, "change": 1},
  "hoverProvider": true,
  "definitionProvider": true,
  "documentSymbolProvider": true
}
```

`change: 1` 表示完整文本同步。服务支持 `initialize`、`initialized`、`shutdown`、`exit`、`textDocument/didOpen`、`didChange`、`didClose`、`publishDiagnostics`、`documentSymbol`、`hover` 和 `definition`。`exit` 必须是通知；shutdown 后的其它请求返回 Invalid Request。已 shutdown 后 `exit` 返回码 0；未 shutdown 直接 exit 或在未 shutdown 状态 EOF 返回码 1。干净 EOF 不会挂起。

JSON-RPC 错误码遵循：Parse error `-32700`、Invalid Request `-32600`、Method not found `-32601`、Invalid params `-32602`、Internal error `-32603`、Server not initialized `-32002`。内部异常以通用消息返回，不将 traceback、内部对象或本机路径放进响应。

## 文档、路径和位置

服务只接收本机 `file:` URI、`.lwt` 扩展名和 `languageId: "lwt"`。拒绝的 URI/文档通过可读诊断反馈，不会访问网络。URI 解码按规范处理百分号编码；路径 canonicalize 后用于比较、导入去重和 overlay 查找，对客户端返回规范化 file URI。中文、空格和 Unicode 路径受支持。

文档同步保存 URI、版本和完整文本。`didChange` 恰好接受一个没有 `range` 的完整文本变更；版本必须严格递增。增量范围、重复/旧版本或未知文档的通知被忽略，不覆盖当前文本。已打开文档的内存文本优先于磁盘副本；模块图中未打开的依赖以严格 UTF-8 从磁盘读取。关闭文档会清空该 URI 的诊断并移除 overlay，再用磁盘版本重新分析剩余打开文档。

LWT lexer 的位置为一基行号和 Unicode 码点列号；LSP 使用零基行号和 UTF-16 code unit 列。服务在输入输出边界显式换算，非 BMP 字符按两个 UTF-16 units 计数；拆分 surrogate pair 的光标位置不命中符号。Range end 排他，标识符范围使用实际 token 长度，EOF 语法错误使用零宽范围。CRLF、LF 和 CR 按 lexer 的换行归一化规则处理；字符串中的 U+2028 不会被当成逻辑换行。

## 诊断和语言功能

打开或更新后，服务按模块图顺序发布 push diagnostics。来源为 `lwt`、severity 为 error。静态诊断保留 S27 的 `STC001` 等码；lexer/parser/module/读取错误使用既有稳定码 `LEX001`、`PAR001`、`MOD001`、`SRC001`。导入模块的静态问题发布到实际模块 URI，不伪装为入口文件错误；重复来源产生的相同诊断会去重。修复后新集合替换旧集合，成功分析发布空数组。lexer/parser 仍使用首错模型；语法无效时清除该 AST 的旧索引，符号列表为空、hover/definition 返回 null，不做容错解析或完整语义恢复。

`textDocument/documentSymbol` 返回当前文件的 import alias、record、function 和顶层 let，按源码顺序排列；record 字段和函数参数作为 children。`hover` 展示语言关键字、十个内置函数、当前词法作用域变量、函数、record、模块 alias 和模块限定函数的源码可确定信息，不推断动态类型或显示运行时值。`definition` 支持普通变量绑定、用户函数、record 构造、模块 alias 和 `alias.function(...)`；遵守 S27 的模块命名空间、遮蔽、函数不捕获调用者、each 与 recover 作用域规则。字段访问不尝试猜测 record 类型。找不到唯一可靠定义时返回 null。

该服务没有自动补全、格式化、重命名、引用查找、语义 token、增量 parser、容错 AST、调试适配器、socket/HTTP 服务或 Marketplace 扩展。它按消息顺序单线程处理，不声明异步并发能力。

## 和 `--check` 的关系

```powershell
python -m lwt --check --format=json examples/modules/main.lwt
```

`--check` 是一次性 CLI 静态检查；Language Server 在文档打开/变化时自动推送诊断，并提供符号、悬停和跳转。二者复用 lexer/parser/module loader/S27 analyzer，不调用 runtime `execute()`，不运行 `emit`、`input()`、`read_text()` 或 `fail()`，不消费被分析程序的 stdin，也不生成 S28 profile。LSP 不会替代实际执行和测试。

## 通用 stdio client 配置示例

以下仅表示通用 client 启动信息，具体 client 的配置键名由其自身约定；它不是已验证的某一编辑器安装说明：

```json
{
  "command": "python",
  "args": ["-m", "lwt.lsp_server"],
  "transport": "stdio",
  "documentSelector": [{"language": "lwt", "pattern": "**/*.lwt"}]
}
```

协议级 smoke 可在仓库根目录运行：

```powershell
python tools/run_lsp_smoke.py
```

工具启动真实 `python -m lwt.lsp_server` 子进程，验证 framing、打开、诊断、符号、悬停、定义、错误后恢复、关闭、shutdown/exit 和退出码。脱敏、确定性摘要保存在 [`reports/lsp-smoke.json`](../reports/lsp-smoke.json)。这证明协议子集按固定 transcript 工作，不证明 VS Code、Neovim 或其它编辑器集成已通过。
