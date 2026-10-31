# LWT Snake replay v1

编码前冻结（S35）。JSON 是 UTF-8，schema_version=1、protocol_version=LWS1。唯一事务事实是无 LF 的规范 ASCII request/response 字符串，不另存可能矛盾的坐标副本。结构如下；最小完整记录必须有一个成功 INIT：

```json
{
  "schema_version": 1,
  "protocol_version": "LWS1",
  "source": {"algorithm": "lwt-utf8-lf-sha256-v1", "sha256": "64个小写十六进制字符"},
  "settings": {"width": 4, "height": 1, "seed": 1},
  "transactions": [
    {"request": "LWS1|000001|INIT|4|1|0000000001", "response": "LWS1|000001|STATE|READY|0|R|3|0|3|2,0;1,0;0,0"}
  ],
  "interruption": null,
  "origin": null
}
```

上例摘要位置是说明占位符；可运行有效样例会以真实源码摘要写入 examples。无效样例：把 schema_version 写成 true、重复 settings 键、删除第 2 笔却保留第 3 笔序号、增加 source_path 字段、写 NaN，均拒绝；合法范围内篡改 score/food 可能通过结构检查，但必须在真实 LWT 验证中报告首个分歧。

source 摘要严格 UTF-8 解码、仅去掉开头一个 BOM、将 CRLF/CR 变 LF，其余内容不变，再对 UTF-8 编码计算 SHA-256。算法名和摘要必须匹配仓库固定 game.lwt；记录文件不能提供源码路径、解释器命令或内嵌源码。摘要是兼容标识，不是防作弊签名。

请求序号从 1 连续；只允许 bridge 的 INIT/START/TURN/TICK/PAUSE/RESUME/RESET，INIT 只在第一笔，设置与 settings 相等。STATE 和消耗序号的 ERR 都完整录制。QUIT 是传输清理，不在记录/接管前缀中；真实验证完成后仍发送 QUIT 并检查正常退出。超时、损坏输出不生成假事务；interruption 可为最多 512 字符的原因，允许验证此前完整前缀。

集中上限：5000 笔事务、16 MiB 文件、JSON 整数字面量最多 10 位（bool 不算整数）、源协议帧沿用 128/4096 字节；拒绝未知字段、重复键、非有限数、坏 UTF-8、乱序和空记录。达到录制上限后不再追加，interruption 明确“仅保存到第 N 条”；可导出此前完整前缀。保存通过 worker 的串行边界取不可变副本，同目录唯一临时文件写完后 os.replace；失败保留原文件并只删除本次临时文件。不保证所有断电场景。

origin 为 null 或 {"parent_sha256": "父记录规范 JSON 的 SHA-256", "prefix_count": N}。子局包含完整父前缀及新增事务，可以独立验证，不依赖父文件位置。前缀含 N 笔事务（INIT 算第 1 笔），至少为 1。接管启动新引擎从 INIT 逐笔重建；不从坐标恢复随机/待转向状态，不为视觉暂停发送 PAUSE。RUNNING 只在明确接管后启用实时钟；终态不直接接管运行。

公共入口：`python -m app.lwt_snake.replay --verify FILE`。成功 stdout 为 `Verified N transactions.`、exit 0；文件/契约/源码兼容错误 stderr、exit 2；执行失败/取消/首个响应分歧 stderr、exit 3。这是应用工具退出码，不改变 LWT CLI。每请求有界超时，整次默认 30 秒；取消可打断当前进程等待并回收。验证与重建均只调用真实公开 LWT CLI，逐笔比较完整响应。首个分歧给事务索引、序号、命令、字段和有界预期/实际值。
