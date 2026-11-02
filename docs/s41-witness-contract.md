# S41 差异见证搜索与证据契约 v1

编码前冻结。只接收用户显式指定可信 catalog 的 S39 v3 结果，并先由 `arena.verify` 对**整个结果**重新执行游戏/策略双层验真。参考与 1–2 个挑战者必须是该结果绑定的不同策略 ID。可信目录限制不是陌生程序沙箱。

## 顺序和预算

参考策略对局按 seed 数值升序；只扫描正常完成且两层验证标志为 true 的局。每局咨询按一基序号升序；挑战者按 ID 字典序比较。`--max-observations` 为跨全部参考对局的**总咨询数**，范围 1..32。一次参考观察即使有两个挑战者也只计一次；不删掉先前观察，策略进程在同一对局内长驻。最多 3 个策略进程加 1 个重放游戏进程；每请求沿用 S36 限时，整个 CLI 120 秒硬期限。第一个 MOVE 方向不同或 MOVE 与 NONE/TRAPPED 不同的对照为见证；同方向不同 FOOD/SPACE 原因不是方向分歧。未命中返回 `found=false`、已扫描次数与预算，不宣称策略等价或全局最小。

## CLI 与格式

`python -m app.lwt_snake.witness --result RESULT --catalog FILE --reference ID --challengers ID[,ID] --max-observations N --output NEW_DIR`。`--verify NEW_DIR --catalog FILE` 对搜索重算，并在命中时重新验证嵌套 S40 一步证据。输出目录必须不存在；正常含无见证退出 0，配置/写入错误退出 2，证据/执行错误退出 3，取消退出 130。

`witness.json`（schema_version=1）固定字段：`schema_version, result_path, result_sha256, catalog_path, catalog_sha256, reference, challengers, max_observations, scanned, found, case, step, challenger, reference_response, challenger_response, analysis_path, analysis_sha256`。未发现时后 6 个可空字段为 null；发现时 `analysis_path` 固定为 `analysis/analysis.json`。根结果及 catalog 仅存仓库相对路径、摘要；验真仍要求用户显式给 catalog，不能从结果路径自动授权执行策略。分析文件及分支遵守 S40 严格格式。另写确定性的 `agent-feedback.json` 与 `report.md`；反馈只给观察和可检查的中性问题，不自动修改策略。所有文件原子写、大小有界；JSON 不接受重复键、未知字段、bool 伪装整数、非有限数、越界路径和软链接。摘要是字节完整性标识，不是签名。

`--verify` 不信任 `found` 等自述字段：先重算同样搜索，逐字段比对 witness 与反馈及报告，命中时调用 S40 `verify` 检查原 v3、候选响应及一步分支。对局/策略故障是错误，不是 `found=false`。找到首个分歧后停止；“最早”仅相对本次输入、顺序和预算，不能解释成候选自然对局中的同序号局面或整局优势。
